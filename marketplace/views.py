import logging
from collections import defaultdict
from urllib.parse import urlencode

import uuid as _uuid

from django.conf import settings as django_settings
from django.contrib import messages as django_messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Count, F, Q, Window
from django.db.models.functions import RowNumber
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.utils.timezone import now as timezone_now
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

from django_ratelimit.decorators import ratelimit

from .forms import DemandPostForm, DiscoverForm, MessageForm, ProfileForm, SignupForm, SupplyLotForm
from .context_processors import SKIN_COOKIE_NAME
from .matching import (
    bulk_suggestion_counts,
    get_suggestions_for_listing,
    get_suggestions_for_lot,
    get_suggestions_for_post,
    watchlisted_demand_post_ids,
    watchlisted_supply_lot_ids,
)
from .migration_control.conversations import ThreadWatchlistCoordinator
from .migration_control.identity import IdentityCompatibilityAdapter
from .migration_control.permissions import permission_service
from .models import (
    EmailVerificationToken,
    Listing,
    ListingStatus,
    ListingType,
    DismissedSuggestion,
    Message,
    MessageThread,
    ThreadReadState,
    User,
    WatchlistItem,
    WatchlistSource,
    WatchlistStatus,
)
from .notifications import send_new_message_notification
from .sse_client import publish_listing_updated

PAGE_SIZE = 25
SKIN_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
identity_adapter = IdentityCompatibilityAdapter()
conversation_coordinator = ThreadWatchlistCoordinator()


def _set_skin_cookie(response, skin_name):
    response.set_cookie(
        SKIN_COOKIE_NAME,
        skin_name,
        max_age=SKIN_COOKIE_MAX_AGE,
        samesite="Lax",
        httponly=True,
    )
    return response


def _send_verification_email(request, user):
    """Create a verification token and send the activation email.

    Revokes any prior unused tokens for this user (preserves rows for audit).
    Swallows email send errors — logs and warns the user instead of failing.
    """
    EmailVerificationToken.objects.filter(
        user=user, used_at=None, revoked_at=None
    ).update(revoked_at=timezone_now())

    token = EmailVerificationToken.objects.create(user=user)
    verification_url = request.build_absolute_uri(
        reverse("marketplace:verify_email_confirm", args=[token.token])
    )
    context = {
        "display_name": user.display_name or user.email,
        "verification_url": verification_url,
        "expiry_hours": EmailVerificationToken.TOKEN_EXPIRY_HOURS,
    }
    subject = render_to_string(
        "registration/verification_email_subject.txt", context
    ).strip()
    body = render_to_string("registration/verification_email_body.txt", context)
    try:
        send_mail(subject, body, None, [user.email])
    except Exception:
        logger.error(
            "Failed to send verification email to %s", user.email, exc_info=True
        )
        django_messages.warning(
            request,
            _(
                "Account created but we could not send the verification email. "
                "Use the resend option to try again."
            ),
        )


def _resolve_listing_by_pk_or_legacy(pk, listing_type):
    return Listing.objects.filter(pk=pk, type=listing_type).first()


def _get_listing_or_404(pk, listing_type):
    listing = _resolve_listing_by_pk_or_legacy(pk, listing_type)
    if listing is None:
        raise Http404
    return listing


def _resolve_listing_for_action(listing_pk, listing_type_raw):
    if not listing_pk:
        raise Http404
    try:
        parsed_pk = int(listing_pk)
    except (TypeError, ValueError) as exc:
        raise Http404 from exc

    if listing_type_raw in {"supply_lot", "supply"}:
        listing_type = ListingType.SUPPLY
    elif listing_type_raw in {"demand_post", "demand"}:
        listing_type = ListingType.DEMAND
    else:
        listing = Listing.objects.filter(pk=parsed_pk).first()
        if listing is None:
            raise Http404
        return listing

    listing = _resolve_listing_by_pk_or_legacy(parsed_pk, listing_type)
    if listing is None:
        raise Http404
    return listing


# ---------------------------------------------------------------------------
# Watchlist helpers
# ---------------------------------------------------------------------------

def _get_or_create_watchlist_item(user, listing=None, source=WatchlistSource.DIRECT):
    """Get or create a WatchlistItem. Returns (item, created)."""
    item, created = WatchlistItem.objects.get_or_create(
        user=user,
        listing=listing,
        defaults={"source": source},
    )
    return item, created


def _get_or_create_thread(watchlist_item):
    """Get or create listing-centric thread for a watchlist item."""
    listing = watchlist_item.resolve_listing()
    if listing is None:
        raise PermissionDenied
    result = conversation_coordinator.start_thread_with_autosave(
        user=watchlist_item.user,
        listing=listing,
        source=watchlist_item.source,
    )
    return result.thread, result.created


def _archive_watchlist_items_for_listing(listing):
    """Archive all watchlist items pointing at this listing."""
    WatchlistItem.objects.filter(
        listing=listing,
        status__in=[WatchlistStatus.STARRED, WatchlistStatus.WATCHING],
    ).update(status=WatchlistStatus.ARCHIVED)


def _restore_watchlist_items_for_listing(listing):
    """Restore archived watchlist items when a listing is reactivated."""
    WatchlistItem.objects.filter(
        listing=listing,
        status=WatchlistStatus.ARCHIVED,
    ).update(status=WatchlistStatus.WATCHING)


# ---------------------------------------------------------------------------
# Lot / post numbering helpers
# ---------------------------------------------------------------------------

def _build_lot_number_map(user):
    """Return {lot_pk: sequential_number} partitioned by item_text."""
    lots = (
        Listing.objects.filter(created_by_user=user, type=ListingType.SUPPLY)
        .annotate(
            row_num=Window(
                expression=RowNumber(),
                partition_by=[F("title")],
                order_by=F("created_at").asc(),
            )
        )
        .values_list("pk", "row_num")
    )
    return dict(lots)


def _build_post_number_map(user):
    """Return {post_pk: sequential_number} partitioned by item_text."""
    posts = (
        Listing.objects.filter(created_by_user=user, type=ListingType.DEMAND)
        .annotate(
            row_num=Window(
                expression=RowNumber(),
                partition_by=[F("title")],
                order_by=F("created_at").asc(),
            )
        )
        .values_list("pk", "row_num")
    )
    return dict(posts)


def _get_lot_number(lot):
    """Get the sequential number for a single supply lot."""
    earlier = Listing.objects.filter(
        created_by_user=lot.created_by_user,
        type=ListingType.SUPPLY,
        title=lot.title,
        created_at__lte=lot.created_at,
    ).count()
    return earlier


def _get_post_number(post):
    """Get the sequential number for a single demand post."""
    earlier = Listing.objects.filter(
        created_by_user=post.created_by_user,
        type=ListingType.DEMAND,
        title=post.title,
        created_at__lte=post.created_at,
    ).count()
    return earlier


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@ratelimit(key="ip", rate="5/h", method="POST", block=True)
def signup_view(request):
    if request.user.is_authenticated:
        return redirect("marketplace:dashboard")
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            identity_adapter.update_identity(
                user,
                organization_name=form.cleaned_data.get("organization_name"),
            )
            _send_verification_email(request, user)
            return redirect("marketplace:verify_email")
    else:
        form = SignupForm()
    return render(request, "registration/signup.html", {"form": form})


class MarketplaceLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    @staticmethod
    def _auth_request_metadata(request):
        username = (request.POST.get("username") or "").strip()
        user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:512]
        referer = (request.META.get("HTTP_REFERER") or "")[:512]
        origin = (request.META.get("HTTP_ORIGIN") or "")[:256]
        forwarded_for = (request.META.get("HTTP_X_FORWARDED_FOR") or "")[:256]
        return {
            "username": username,
            "ip": (
                forwarded_for.split(",")[0].strip()
                or request.META.get("REMOTE_ADDR", "")
                or "unknown"
            ),
            "x_forwarded_for": forwarded_for,
            "x_real_ip": (request.META.get("HTTP_X_REAL_IP") or "")[:128],
            "referer": referer,
            "origin": origin,
            "user_agent": user_agent,
            "path": request.path,
            "method": request.method,
            "accept_language": (request.META.get("HTTP_ACCEPT_LANGUAGE") or "")[:256],
            "session_key": request.session.session_key or "",
        }

    @staticmethod
    def _lockout_cache_key(request):
        meta = MarketplaceLoginView._auth_request_metadata(request)
        username = meta["username"].lower()
        ip = meta["ip"]
        return f"login_lockout:{ip}:{username}"

    def _is_login_locked_out(self, request):
        state = cache.get(self._lockout_cache_key(request))
        if not state:
            return False
        return int(timezone_now().timestamp()) < int(state.get("locked_until", 0))

    def _record_failed_login(self, request):
        now_ts = int(timezone_now().timestamp())
        key = self._lockout_cache_key(request)
        limit = int(getattr(django_settings, "LOGIN_FAILED_ATTEMPTS_LIMIT", 5))
        window = int(getattr(django_settings, "LOGIN_FAILED_WINDOW_SECONDS", 900))
        lockout_seconds = int(getattr(django_settings, "LOGIN_LOCKOUT_SECONDS", 900))

        state = cache.get(key) or {"count": 0, "first_failed_at": now_ts, "locked_until": 0}
        first_failed_at = int(state.get("first_failed_at", now_ts))
        if now_ts - first_failed_at > window:
            state = {"count": 0, "first_failed_at": now_ts, "locked_until": 0}

        state["count"] = int(state.get("count", 0)) + 1
        if state["count"] >= limit:
            state["locked_until"] = now_ts + lockout_seconds

        cache_ttl = max(window, lockout_seconds) + 60
        cache.set(key, state, timeout=cache_ttl)
        return state

    def _clear_failed_login(self, request):
        cache.delete(self._lockout_cache_key(request))

    def post(self, request, *args, **kwargs):
        if self._is_login_locked_out(request):
            meta = self._auth_request_metadata(request)
            form = self.get_form()
            form.add_error(
                None,
                _(
                    "Too many failed login attempts. Please wait and try again."
                ),
            )
            logger.warning(
                "auth.login_blocked_locked_out username=%s ip=%s xff=%s x_real_ip=%s "
                "referer=%s origin=%s ua=%s path=%s method=%s accept_language=%s",
                meta["username"],
                meta["ip"],
                meta["x_forwarded_for"],
                meta["x_real_ip"],
                meta["referer"],
                meta["origin"],
                meta["user_agent"],
                meta["path"],
                meta["method"],
                meta["accept_language"],
            )
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.get_user()
        self._clear_failed_login(self.request)
        if not user.email_verified:
            resend_url = "{}?{}".format(
                reverse("marketplace:resend_verification"),
                urlencode({"email": user.email}),
            )
            form.add_error(
                None,
                mark_safe(
                    _("Email not verified. ")
                    + f'<a href="{resend_url}">'
                    + _("Resend verification email")
                    + "</a>."
                ),
            )
            return self.form_invalid(form)
        response = super().form_valid(form)
        return _set_skin_cookie(response, user.skin)

    def form_invalid(self, form):
        if self.request.method == "POST":
            state = self._record_failed_login(self.request)
            meta = self._auth_request_metadata(self.request)
            logger.warning(
                "auth.login_failed username=%s ip=%s xff=%s x_real_ip=%s "
                "referer=%s origin=%s ua=%s path=%s method=%s "
                "attempt_count=%s first_failed_at=%s locked_until=%s",
                meta["username"],
                meta["ip"],
                meta["x_forwarded_for"],
                meta["x_real_ip"],
                meta["referer"],
                meta["origin"],
                meta["user_agent"],
                meta["path"],
                meta["method"],
                int(state.get("count", 0)),
                int(state.get("first_failed_at", 0)),
                int(state.get("locked_until", 0)),
            )
            if int(state.get("locked_until", 0)) > int(timezone_now().timestamp()):
                form.add_error(
                    None,
                    _(
                        "Too many failed login attempts. Please wait and try again."
                    ),
                )
        return super().form_invalid(form)


class MarketplaceLogoutView(LogoutView):
    next_page = "marketplace:login"
    http_method_names = ["get", "post", "options"]

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------

def verify_email(request):
    """'Check your email' confirmation page shown after signup or resend."""
    return render(request, "registration/email_verify.html")


def verify_email_confirm(request, token):
    """Activate account using the UUID token from the verification email."""
    try:
        obj = (
            EmailVerificationToken.objects
            .select_related("user")
            .get(token=token)
        )
    except EmailVerificationToken.DoesNotExist:
        raise Http404

    # Check terminal states outside the transaction — no write needed
    if obj.used_at is not None:
        return render(request, "registration/email_verify_used.html")

    if not obj.is_valid:
        # Expired: used_at is None, revoked_at is None, but past expiry
        return render(request, "registration/email_verify_expired.html")

    # Valid — activate atomically to prevent double-activation on concurrent clicks
    with transaction.atomic():
        try:
            obj = (
                EmailVerificationToken.objects
                .select_related("user")
                .select_for_update()
                .get(pk=obj.pk, used_at=None, revoked_at=None)
            )
        except EmailVerificationToken.DoesNotExist:
            # Another request already activated this token
            return render(request, "registration/email_verify_used.html")

        if not obj.is_valid:
            return render(request, "registration/email_verify_expired.html")

        obj.user.email_verified = True
        obj.user.save(update_fields=["email_verified"])
        obj.used_at = timezone_now()
        obj.save(update_fields=["used_at"])

    django_messages.success(request, _("Email verified. You can now log in."))
    return redirect("marketplace:login")


def resend_verification(request):
    """Resend a verification email to a given address."""
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        try:
            user = User.objects.get(email__iexact=email, email_verified=False)
            _send_verification_email(request, user)
        except Exception:
            pass  # neutral — do not leak account existence or already-verified status
        django_messages.info(
            request,
            _(
                "If an unverified account exists for that email, a new verification "
                "link has been sent."
            ),
        )
        return redirect("marketplace:verify_email")

    initial_email = request.GET.get("email", "")
    return render(
        request,
        "registration/resend_verification.html",
        {"initial_email": initial_email},
    )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard_view(request):
    user = request.user
    context = {}
    posts = Listing.objects.filter(
        created_by_user=user,
        type=ListingType.DEMAND,
    ).exclude(status=ListingStatus.DELETED).order_by("-created_at")[:5]
    post_numbers = _build_post_number_map(user)
    for p in posts:
        p.post_number = post_numbers.get(p.pk, 1)
    context["demand_posts"] = posts

    lots = Listing.objects.filter(
        created_by_user=user,
        type=ListingType.SUPPLY,
    ).exclude(status=ListingStatus.DELETED).order_by("-created_at")[:5]
    lot_numbers = _build_lot_number_map(user)
    for lot in lots:
        lot.lot_number = lot_numbers.get(lot.pk, 1)
    context["supply_lots"] = lots

    watchlist_count = WatchlistItem.objects.filter(
        user=user,
        status__in=[WatchlistStatus.STARRED, WatchlistStatus.WATCHING],
    ).count()
    context["watchlist_count"] = watchlist_count

    suggestions = []
    active_own = Listing.objects.filter(
        created_by_user=user,
        status=ListingStatus.ACTIVE,
    )
    for own_listing in active_own:
        for suggestion in get_suggestions_for_listing(own_listing, user, limit=3):
            suggestion.suggestion_type = "supply_lot" if suggestion.type == ListingType.SUPPLY else "demand_post"
            suggestions.append(suggestion)

    seen = set()
    unique_suggestions = []
    for suggestion in suggestions:
        if suggestion.pk in seen:
            continue
        seen.add(suggestion.pk)
        unique_suggestions.append(suggestion)

    context["suggestions"] = unique_suggestions[:5]
    context["watchlisted_pks"] = set(
        WatchlistItem.objects.filter(user=user, listing__isnull=False).values_list("listing_id", flat=True)
    )
    return render(request, "marketplace/dashboard.html", context)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@login_required
def profile_view(request):
    profile = identity_adapter.get_profile(request.user)
    supply_listings = (
        Listing.objects.filter(
            created_by_user=request.user,
            type=ListingType.SUPPLY,
            status=ListingStatus.ACTIVE,
        )
        .order_by("-created_at")[:5]
    )
    demand_listings = (
        Listing.objects.filter(
            created_by_user=request.user,
            type=ListingType.DEMAND,
            status=ListingStatus.ACTIVE,
        )
        .order_by("-created_at")[:5]
    )
    display_seed = (profile.display_name or request.user.email or "?").strip()
    profile_initial = display_seed[0].upper() if display_seed else "?"
    return render(
        request,
        "marketplace/profile.html",
        {
            "identity_profile": profile,
            "member_since": request.user.date_joined,
            "profile_initial": profile_initial,
            "supply_listings": supply_listings,
            "demand_listings": demand_listings,
        },
    )


@login_required
def profile_edit(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            user = form.save()
            identity_adapter.update_identity(
                user,
                organization_name=form.cleaned_data.get("organization_name"),
            )
            django_messages.success(request, _("Profile updated."))
            response = redirect("marketplace:profile")
            return _set_skin_cookie(response, user.skin)
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "marketplace/profile_edit.html", {"form": form})


# ---------------------------------------------------------------------------
# Profile image upload
# ---------------------------------------------------------------------------

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@login_required
@require_POST
def upload_profile_image(request):
    from .image_pipeline import ImageValidationError, process_profile_image

    file = request.FILES.get("avatar")
    if not file:
        return JsonResponse({"error": "No file provided."}, status=400)

    # Size check
    if file.size > django_settings.MAX_UPLOAD_SIZE_BYTES:
        mb = django_settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        return JsonResponse({"error": f"File exceeds the {mb} MB size limit."}, status=400)

    # Content-type pre-screen
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        return JsonResponse(
            {"error": "Unsupported file type. Please upload a JPEG, PNG, or WebP image."},
            status=400,
        )

    # Process through pipeline
    try:
        image_bytes, ext = process_profile_image(file, request.user)
    except ImageValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    # Build storage path: profile_images/{user_id}/{uuid}.{ext}
    filename = f"profile_images/{request.user.pk}/{_uuid.uuid4().hex}.{ext}"

    # Remember old filename before overwriting (capture as string to avoid side effects)
    old_name = request.user.profile_image.name if request.user.profile_image else None

    # Save new image
    content = ContentFile(image_bytes, name=filename)
    request.user.profile_image.save(filename, content, save=False)
    request.user.profile_image_updated_at = timezone_now()
    request.user.save(update_fields=["profile_image", "profile_image_updated_at"])

    # Capture URL while profile_image is set
    avatar_url = request.user.profile_image_url

    # Delete old file after successful save (use storage directly to avoid FieldFile side effects)
    if old_name:
        try:
            from django.core.files.storage import default_storage
            default_storage.delete(old_name)
        except Exception:
            logger.warning(
                "Could not delete old profile image for user_id=%s: %s",
                request.user.pk,
                old_name,
            )

    return JsonResponse({"avatar_url": avatar_url})


@login_required
@require_POST
def remove_profile_image(request):
    old_name = request.user.profile_image.name if request.user.profile_image else None

    request.user.profile_image = None
    request.user.profile_image_updated_at = timezone_now()
    request.user.save(update_fields=["profile_image", "profile_image_updated_at"])

    if old_name:
        try:
            from django.core.files.storage import default_storage
            default_storage.delete(old_name)
        except Exception:
            logger.warning(
                "Could not delete profile image during removal for user_id=%s: %s",
                request.user.pk,
                old_name,
            )

    return JsonResponse({"avatar_initials": request.user.avatar_initials})


# ---------------------------------------------------------------------------
# Demand/Supply listing views (route names retained for compatibility)
# ---------------------------------------------------------------------------


@login_required
def demand_post_list(request):
    qs = Listing.objects.filter(
        created_by_user=request.user,
        type=ListingType.DEMAND,
    ).exclude(status=ListingStatus.DELETED).order_by("-created_at")
    total_count = qs.count()
    active_count = qs.filter(status=ListingStatus.ACTIVE).count()
    post_numbers = _build_post_number_map(request.user)
    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    counts = bulk_suggestion_counts(page_obj, request.user, listing_side="demand")
    for post in page_obj:
        post.post_number = post_numbers.get(post.pk, 1)
        post.unsaved_count, post.saved_count = counts.get(post.pk, (0, 0))
    return render(request, "marketplace/demand_post_list.html", {
        "page_obj": page_obj,
        "total_count": total_count,
        "active_count": active_count,
    })


@login_required
def demand_post_create(request):
    if request.method == "POST":
        form = DemandPostForm(request.POST, user=request.user)
        if form.is_valid():
            post = form.save(commit=False)
            post.created_by_user = request.user
            post.created_at = timezone_now()
            post.save()
            _sync_listing_to_vector_index(post)
            publish_listing_updated(post, changed_fields=["create"])
            django_messages.success(request, _("Demand listing created."))
            return redirect("marketplace:demand_post_detail", pk=post.pk)
    else:
        form = DemandPostForm(user=request.user)
    return render(request, "marketplace/demand_post_form.html", {"form": form})


@login_required
def demand_post_edit(request, pk):
    post = _get_listing_or_404(pk, ListingType.DEMAND)
    permission_service.authorize_listing_mutation(request.user.pk, post, "edit").deny_if_not_allowed()
    if request.method == "POST":
        form = DemandPostForm(request.POST, instance=post, user=request.user)
        if form.is_valid():
            post = form.save()
            _sync_listing_to_vector_index(post)
            publish_listing_updated(post, changed_fields=["edit"])
            django_messages.success(request, _("Demand listing updated."))
            return redirect("marketplace:demand_post_detail", pk=post.pk)
    else:
        form = DemandPostForm(instance=post, user=request.user)
    return render(request, "marketplace/demand_post_form.html", {"form": form, "editing": True})


@login_required
def demand_post_detail(request, pk):
    post = _get_listing_or_404(pk, ListingType.DEMAND)
    if post.is_expired and post.status == ListingStatus.ACTIVE:
        post.status = ListingStatus.EXPIRED
        post.save(update_fields=["status"])
        _remove_listing_from_vector_index(post)
        publish_listing_updated(post, changed_fields=["status"])
    is_owner = post.created_by_user == request.user
    is_watchlisted = False
    can_convert = False
    message_unavailable_reason = ""
    if not is_owner:
        is_watchlisted = WatchlistItem.objects.filter(
            user=request.user,
            listing=post,
        ).exists()
        can_convert = post.status == ListingStatus.ACTIVE and not post.is_expired
        if not can_convert:
            message_unavailable_reason = _(
                "Messaging is unavailable because this listing is not active."
            )
    post.post_number = _get_post_number(post)
    suggestions = []
    if is_owner and post.status == ListingStatus.ACTIVE:
        suggestions = get_suggestions_for_post(post, request.user, limit=5)
        for listing in suggestions:
            listing.suggestion_type = "supply_lot"
    watchlisted_pks = watchlisted_supply_lot_ids(request.user) if suggestions else set()

    listing_threads = []
    if is_owner:
        listing_threads = list(
            MessageThread.objects.filter(listing=post).select_related(
                "created_by_user", "listing", "listing__created_by_user",
            ).annotate(
                message_count=Count("messages"),
                last_message_at=models.Max("messages__created_at"),
            ).filter(message_count__gt=0).order_by("-last_message_at")
        )
        for thread in listing_threads:
            thread.counterparty = thread.counterparty_for(request.user)

    return render(request, "marketplace/demand_post_detail.html", {
        "post": post,
        "suggestions": suggestions,
        "is_owner": is_owner,
        "is_watchlisted": is_watchlisted,
        "can_convert": can_convert,
        "message_unavailable_reason": message_unavailable_reason,
        "watchlisted_pks": watchlisted_pks,
        "listing_threads": listing_threads,
    })


@login_required
@require_POST
def demand_post_toggle(request, pk):
    post = _get_listing_or_404(pk, ListingType.DEMAND)
    permission_service.authorize_listing_mutation(request.user.pk, post, "toggle").deny_if_not_allowed()
    if post.status == ListingStatus.ACTIVE:
        post.status = ListingStatus.PAUSED
    elif post.status in (ListingStatus.PAUSED, ListingStatus.FULFILLED):
        post.status = ListingStatus.ACTIVE
    post.save(update_fields=["status"])
    _sync_listing_to_vector_index(post)
    publish_listing_updated(post, changed_fields=["status"])
    if post.status == ListingStatus.ACTIVE:
        django_messages.success(request, _("Demand listing resumed."))
    else:
        django_messages.success(request, _("Demand listing paused."))
    return redirect("marketplace:demand_post_detail", pk=post.pk)


@login_required
def demand_post_delete(request, pk):
    post = _get_listing_or_404(pk, ListingType.DEMAND)
    permission_service.authorize_listing_mutation(request.user.pk, post, "delete").deny_if_not_allowed()
    if request.method == "POST":
        post.status = ListingStatus.DELETED
        post.save(update_fields=["status"])
        _archive_watchlist_items_for_listing(post)
        _remove_listing_from_vector_index(post)
        publish_listing_updated(post, changed_fields=["status", "delete"])
        django_messages.success(request, _("Demand listing deleted."))
        return redirect("marketplace:demand_post_list")
    return render(request, "marketplace/listing_delete_confirm.html", {
        "listing_title": post.item_text,
        "delete_url": request.path,
        "cancel_url": redirect("marketplace:demand_post_detail", pk=post.pk).url,
    })


@login_required
def supply_lot_list(request):
    qs = Listing.objects.filter(
        created_by_user=request.user,
        type=ListingType.SUPPLY,
    ).exclude(status=ListingStatus.DELETED).order_by("-created_at")
    total_count = qs.count()
    active_count = qs.filter(status=ListingStatus.ACTIVE).count()
    lot_numbers = _build_lot_number_map(request.user)
    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    counts = bulk_suggestion_counts(page_obj, request.user, listing_side="supply")
    for lot in page_obj:
        lot.lot_number = lot_numbers.get(lot.pk, 1)
        lot.unsaved_count, lot.saved_count = counts.get(lot.pk, (0, 0))
    return render(request, "marketplace/supply_lot_list.html", {
        "page_obj": page_obj,
        "total_count": total_count,
        "active_count": active_count,
    })


@login_required
def supply_lot_create(request):
    if request.method == "POST":
        form = SupplyLotForm(request.POST)
        if form.is_valid():
            lot = form.save(commit=False)
            lot.created_by_user = request.user
            lot.created_at = timezone_now()
            lot.save()
            _sync_listing_to_vector_index(lot)
            publish_listing_updated(lot, changed_fields=["create"])
            django_messages.success(request, _("Supply listing created."))
            return redirect("marketplace:supply_lot_detail", pk=lot.pk)
    else:
        form = SupplyLotForm()
    return render(request, "marketplace/supply_lot_form.html", {"form": form})


@login_required
def supply_lot_edit(request, pk):
    lot = _get_listing_or_404(pk, ListingType.SUPPLY)
    permission_service.authorize_listing_mutation(request.user.pk, lot, "edit").deny_if_not_allowed()
    if request.method == "POST":
        form = SupplyLotForm(request.POST, instance=lot)
        if form.is_valid():
            was_expired = lot.status == ListingStatus.EXPIRED
            lot = form.save()
            # Allow owners to reactivate expired supply listings by setting a new future date.
            if was_expired and lot.expires_at and lot.expires_at > timezone_now():
                lot.status = ListingStatus.ACTIVE
                lot.save(update_fields=["status"])
                django_messages.success(request, _("Supply listing reactivated with a new availability date."))
            else:
                django_messages.success(request, _("Supply listing updated."))
            _sync_listing_to_vector_index(lot)
            publish_listing_updated(lot, changed_fields=["edit", "status"])
            return redirect("marketplace:supply_lot_detail", pk=lot.pk)
    else:
        form = SupplyLotForm(instance=lot)
    return render(request, "marketplace/supply_lot_form.html", {"form": form, "editing": True})


@login_required
def supply_lot_detail(request, pk):
    lot = _get_listing_or_404(pk, ListingType.SUPPLY)
    if lot.is_expired and lot.status == ListingStatus.ACTIVE:
        lot.status = ListingStatus.EXPIRED
        lot.save(update_fields=["status"])
        _remove_listing_from_vector_index(lot)
        publish_listing_updated(lot, changed_fields=["status"])
    is_owner = lot.created_by_user == request.user
    is_watchlisted = False
    can_convert = False
    message_unavailable_reason = ""
    if not is_owner:
        is_watchlisted = WatchlistItem.objects.filter(
            user=request.user,
            listing=lot,
        ).exists()
        can_convert = lot.status == ListingStatus.ACTIVE and not lot.is_expired
        if not can_convert:
            message_unavailable_reason = _(
                "Messaging is unavailable because this listing is not active."
            )
    lot.lot_number = _get_lot_number(lot)
    suggestions = []
    if is_owner and lot.status == ListingStatus.ACTIVE:
        suggestions = get_suggestions_for_lot(lot, request.user, limit=5)
        for listing in suggestions:
            listing.suggestion_type = "demand_post"
    watchlisted_pks = watchlisted_demand_post_ids(request.user) if suggestions else set()

    listing_threads = []
    if is_owner:
        listing_threads = list(
            MessageThread.objects.filter(listing=lot).select_related(
                "created_by_user", "listing", "listing__created_by_user",
            ).annotate(
                message_count=Count("messages"),
                last_message_at=models.Max("messages__created_at"),
            ).filter(message_count__gt=0).order_by("-last_message_at")
        )
        for thread in listing_threads:
            thread.counterparty = thread.counterparty_for(request.user)

    return render(request, "marketplace/supply_lot_detail.html", {
        "lot": lot,
        "suggestions": suggestions,
        "is_owner": is_owner,
        "is_watchlisted": is_watchlisted,
        "can_convert": can_convert,
        "message_unavailable_reason": message_unavailable_reason,
        "watchlisted_pks": watchlisted_pks,
        "listing_threads": listing_threads,
    })


@login_required
@require_POST
def supply_lot_toggle(request, pk):
    lot = _get_listing_or_404(pk, ListingType.SUPPLY)
    permission_service.authorize_listing_mutation(request.user.pk, lot, "toggle").deny_if_not_allowed()
    previous_status = lot.status
    now = timezone_now()
    if lot.status == ListingStatus.ACTIVE:
        lot.status = ListingStatus.WITHDRAWN
    elif lot.status in (ListingStatus.WITHDRAWN, ListingStatus.PAUSED):
        if lot.expires_at is None or lot.expires_at <= now:
            lot.status = ListingStatus.EXPIRED
            lot.save(update_fields=["status"])
            _remove_listing_from_vector_index(lot)
            publish_listing_updated(lot, changed_fields=["status"])
            django_messages.warning(
                request,
                _("Supply listing is expired. Update Available until to a future date to reactivate."),
            )
            return redirect("marketplace:supply_lot_detail", pk=lot.pk)
        lot.status = ListingStatus.ACTIVE
    if lot.status == previous_status:
        return redirect("marketplace:supply_lot_detail", pk=lot.pk)
    lot.save(update_fields=["status"])
    _sync_listing_to_vector_index(lot)
    publish_listing_updated(lot, changed_fields=["status"])
    if lot.status == ListingStatus.ACTIVE:
        django_messages.success(request, _("Supply listing unpaused."))
    else:
        django_messages.success(request, _("Supply listing paused."))
    return redirect("marketplace:supply_lot_detail", pk=lot.pk)


@login_required
def supply_lot_delete(request, pk):
    lot = _get_listing_or_404(pk, ListingType.SUPPLY)
    permission_service.authorize_listing_mutation(request.user.pk, lot, "delete").deny_if_not_allowed()
    if request.method == "POST":
        lot.status = ListingStatus.DELETED
        lot.save(update_fields=["status"])
        _archive_watchlist_items_for_listing(lot)
        _remove_listing_from_vector_index(lot)
        publish_listing_updated(lot, changed_fields=["status", "delete"])
        django_messages.success(request, _("Supply listing deleted."))
        return redirect("marketplace:supply_lot_list")
    return render(request, "marketplace/listing_delete_confirm.html", {
        "listing_title": lot.item_text,
        "delete_url": request.path,
        "cancel_url": redirect("marketplace:supply_lot_detail", pk=lot.pk).url,
    })


# ---------------------------------------------------------------------------
# Discover (search)
# ---------------------------------------------------------------------------

def _normalize_discover_direction(direction):
    if direction in {
        DiscoverForm.DIRECTION_FIND_SUPPLY,
        DiscoverForm.DIRECTION_FIND_DEMAND,
    }:
        return direction
    return DiscoverForm.DIRECTION_FIND_SUPPLY


def _discover_listing_types_for_direction(direction):
    normalized = _normalize_discover_direction(direction)
    if normalized == DiscoverForm.DIRECTION_FIND_DEMAND:
        return ListingType.DEMAND, ListingType.DEMAND
    return ListingType.SUPPLY, ListingType.SUPPLY


def _discover_direction_label(direction):
    normalized = _normalize_discover_direction(direction)
    if normalized == DiscoverForm.DIRECTION_FIND_DEMAND:
        return _("Find Demand")
    return _("Find Supply")


def _discover_listing_payload(listing, default_listing_type):
    listing_type = default_listing_type
    listing_pk = listing.pk
    detail_url_name = (
        "marketplace:supply_lot_detail"
        if listing_type == ListingType.SUPPLY
        else "marketplace:demand_post_detail"
    )
    encoded_type = "supply_lot" if listing_type == ListingType.SUPPLY else "demand_post"
    return encoded_type, listing_pk, detail_url_name


def _decorate_discover_results(results, direction):
    default_listing_type, _ = _discover_listing_types_for_direction(direction)
    for listing in results:
        listing.discover_listing_type, listing.discover_listing_pk, listing.discover_detail_url_name = (
            _discover_listing_payload(listing, default_listing_type)
        )
        listing.discover_ending_at = getattr(listing, "expires_at", None)


def _run_discover_search(user, query, category, country, direction, search_mode="similar"):
    """Run discover search and return results list."""
    listing_type, target_listing_type = _discover_listing_types_for_direction(direction)

    if search_mode == "keyword":
        return _keyword_search(
            query=query,
            listing_type=listing_type,
            user=user,
            category=category or None,
            country=country or None,
            limit=20,
        )

    from .vector_search import search_listings
    return search_listings(
        query=query,
        listing_type=listing_type,
        user=user,
        category=category or None,
        country=country or None,
        limit=20,
    )


def _sort_discover_results(results, sort_by, direction):
    """Sort discover results based on user-selected mode."""
    if sort_by == DiscoverForm.SORT_NEWEST:
        return sorted(results, key=lambda listing: listing.created_at, reverse=True)

    if sort_by == DiscoverForm.SORT_ENDING_SOON:
        normalized_direction = _normalize_discover_direction(direction)
        if normalized_direction == DiscoverForm.DIRECTION_FIND_SUPPLY:
            return sorted(
                results,
                key=lambda listing: (
                    listing.expires_at is None,
                    listing.expires_at or listing.created_at,
                ),
            )
        return sorted(
            results,
            key=lambda listing: (
                listing.expires_at is None,
                listing.expires_at or listing.created_at,
            ),
        )

    return results


def _is_short_query(query):
    words = [w for w in query.strip().split() if w]
    return len(words) <= 2


def _discover_watchlisted_pks(user, direction):
    """Return set of PKs already on the user's watchlist."""
    normalized_direction = _normalize_discover_direction(direction)
    if normalized_direction == DiscoverForm.DIRECTION_FIND_SUPPLY:
        return set(WatchlistItem.objects.filter(
            user=user,
            listing__type=ListingType.SUPPLY,
            listing__isnull=False,
        ).values_list("listing_id", flat=True))
    return set(WatchlistItem.objects.filter(
        user=user,
        listing__type=ListingType.DEMAND,
        listing__isnull=False,
    ).values_list("listing_id", flat=True))


@login_required
def discover_view(request):
    user = request.user
    results = []
    searched = False
    watchlisted_pks = set()
    short_query_hint = False
    active_direction = _normalize_discover_direction(
        request.session.get("discover_last_direction")
    )

    if request.method == "POST":
        form = DiscoverForm(request.POST, user=user)
        if form.is_valid() and form.cleaned_data.get("query"):
            query = form.cleaned_data["query"]
            direction = _normalize_discover_direction(form.cleaned_data.get("direction"))
            active_direction = direction
            category = form.cleaned_data.get("category") or ""
            country = form.cleaned_data.get("location_country") or ""
            radius = form.cleaned_data.get("radius") or ""
            search_mode = form.cleaned_data.get("search_mode", "similar")
            sort_by = form.cleaned_data.get("sort_by", DiscoverForm.SORT_BEST_MATCH)
            exclude_watched = form.cleaned_data.get("exclude_watched", False)

            # Store params in session
            request.session["discover_last_query"] = query
            request.session["discover_last_direction"] = direction
            request.session["discover_last_category"] = category
            request.session["discover_last_country"] = country
            request.session["discover_last_radius"] = radius
            request.session["discover_last_search_mode"] = search_mode
            request.session["discover_last_sort_by"] = sort_by
            request.session["discover_last_exclude_watched"] = exclude_watched

            results = _run_discover_search(user, query, category, country, direction, search_mode)
            results = _sort_discover_results(results, sort_by, direction)
            _decorate_discover_results(results, direction)
            searched = True
            watchlisted_pks = _discover_watchlisted_pks(user, direction)
            if exclude_watched and watchlisted_pks:
                results = [r for r in results if r.discover_listing_pk not in watchlisted_pks]
            if not results and search_mode == "similar" and _is_short_query(query):
                short_query_hint = True
    else:
        # Repopulate from session only when redirected back from save/unsave
        keep_results = request.session.pop("discover_keep_results", False)
        session_query = request.session.get("discover_last_query", "")
        if keep_results and session_query:
            initial = {
                "query": session_query,
                "direction": _normalize_discover_direction(
                    request.session.get("discover_last_direction")
                ),
                "category": request.session.get("discover_last_category", ""),
                "location_country": request.session.get("discover_last_country", ""),
                "radius": request.session.get("discover_last_radius", ""),
                "search_mode": request.session.get("discover_last_search_mode", "similar"),
                "sort_by": request.session.get("discover_last_sort_by", DiscoverForm.SORT_BEST_MATCH),
                "exclude_watched": request.session.get("discover_last_exclude_watched", False),
            }
            active_direction = initial["direction"]
            form = DiscoverForm(initial=initial, user=user)
            results = _run_discover_search(
                user, session_query,
                initial["category"], initial["location_country"],
                initial["direction"],
                initial["search_mode"],
            )
            results = _sort_discover_results(results, initial["sort_by"], initial["direction"])
            _decorate_discover_results(results, initial["direction"])
            searched = True
            watchlisted_pks = _discover_watchlisted_pks(user, initial["direction"])
            if initial["exclude_watched"] and watchlisted_pks:
                results = [r for r in results if r.discover_listing_pk not in watchlisted_pks]
            if not results and initial["search_mode"] == "similar" and _is_short_query(session_query):
                short_query_hint = True
        else:
            form = DiscoverForm(user=user)

    return render(request, "marketplace/discover.html", {
        "form": form,
        "results": results,
        "searched": searched,
        "watchlisted_pks": watchlisted_pks,
        "short_query_hint": short_query_hint,
        "active_direction_label": _discover_direction_label(active_direction),
    })


@login_required
def discover_clear(request):
    """Clear discover search session state and redirect to a fresh form."""
    for key in ["discover_last_query", "discover_last_category",
                "discover_last_country", "discover_last_radius",
                "discover_last_search_mode", "discover_last_sort_by",
                "discover_last_direction",
                "discover_last_exclude_watched", "discover_keep_results"]:
        request.session.pop(key, None)
    django_messages.success(request, _("Search cleared. Try a new query."))
    return redirect("marketplace:discover")


def _keyword_search(query, listing_type, user, category=None, country=None, limit=20):
    """Keyword search using Django ORM. Splits query into words and requires all (AND)."""
    from django.utils import timezone
    now = timezone.now()

    words = query.split()
    if not words:
        return []

    # Build AND filter: every word must appear in title
    word_filter = Q()
    for word in words:
        word_filter &= Q(title__icontains=word)

    qs = Listing.objects.filter(
        word_filter,
        type=listing_type,
        status=ListingStatus.ACTIVE,
    ).exclude(created_by_user=user)
    if listing_type == ListingType.SUPPLY:
        qs = qs.filter(expires_at__gt=now)
    else:
        qs = qs.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    if category:
        qs = qs.filter(category=category)
    if country:
        qs = qs.filter(location_country=country)
    return list(qs.order_by("-created_at")[:limit])


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

def _attach_unread_counts(user, items):
    """Attach .unread_count to each WatchlistItem. Two DB queries total."""
    item_threads = {}
    for item in items:
        thread = item.thread
        if thread:
            item_threads[item.pk] = thread.pk
    thread_ids = list(item_threads.values())
    for item in items:
        item.unread_count = 0
    if not thread_ids:
        return
    # Query 1: read states
    read_states = {
        rs.thread_id: rs.last_read_at
        for rs in ThreadReadState.objects.filter(user=user, thread_id__in=thread_ids)
    }
    # Query 2: all non-own messages for those threads, filtered in Python
    unread_map = {tid: 0 for tid in thread_ids}
    for thread_id, created_at in (
        Message.objects
        .filter(thread_id__in=thread_ids)
        .exclude(sender=user)
        .values_list("thread_id", "created_at")
    ):
        last_read = read_states.get(thread_id)
        if last_read is None or created_at > last_read:
            unread_map[thread_id] += 1
    for item in items:
        thread_id = item_threads.get(item.pk)
        if thread_id:
            item.unread_count = unread_map.get(thread_id, 0)


@login_required
def watchlist_view(request):
    return render(
        request,
        "marketplace/watchlist.html",
        _build_watchlist_context(request.user, request.GET),
    )


def _build_watchlist_context(user, params=None):
    params = params or {}
    has_explicit_status_filters = any(
        key in params for key in ("show_starred", "show_watching", "show_archived")
    )
    show_starred = (
        params.get("show_starred") == "1" if has_explicit_status_filters else True
    )
    show_watching = (
        params.get("show_watching") == "1" if has_explicit_status_filters else True
    )
    show_archived = (
        params.get("show_archived") == "1" if has_explicit_status_filters else True
    )
    conversations_only = params.get("conversation_only") == "1"

    qs = WatchlistItem.objects.filter(user=user).select_related(
        "listing",
        "listing__created_by_user",
    )

    starred = list(qs.filter(status=WatchlistStatus.STARRED).order_by("-updated_at"))
    watching = list(qs.filter(status=WatchlistStatus.WATCHING).order_by("-updated_at"))
    archived = list(qs.filter(status=WatchlistStatus.ARCHIVED).order_by("-updated_at"))

    for item in starred + watching + archived:
        item.resolved_listing = item.resolve_listing()

    _attach_unread_counts(user, starred)
    _attach_unread_counts(user, watching)
    _attach_unread_counts(user, archived)

    if conversations_only:
        starred = [item for item in starred if item.thread]
        watching = [item for item in watching if item.thread]
        archived = [item for item in archived if item.thread]

    if not show_starred:
        starred = []
    if not show_watching:
        watching = []
    if not show_archived:
        archived = []

    active_items = starred + watching
    active_count = len(active_items)
    conversation_count = sum(1 for item in active_items if item.thread)
    unread_conversation_count = sum(1 for item in active_items if getattr(item, "unread_count", 0) > 0)

    filters = {
        "show_starred": show_starred,
        "show_watching": show_watching,
        "show_archived": show_archived,
        "conversation_only": conversations_only,
    }
    filters_query_parts = []
    if show_starred:
        filters_query_parts.append("show_starred=1")
    if show_watching:
        filters_query_parts.append("show_watching=1")
    if show_archived:
        filters_query_parts.append("show_archived=1")
    if conversations_only:
        filters_query_parts.append("conversation_only=1")

    return {
        "starred": starred,
        "watching": watching,
        "archived": archived,
        "active_count": active_count,
        "conversation_count": conversation_count,
        "unread_conversation_count": unread_conversation_count,
        "watchlist_filters": filters,
        "filters_querystring": "&".join(filters_query_parts),
    }


@login_required
@require_POST
def watchlist_star(request, pk):
    item = get_object_or_404(WatchlistItem, pk=pk, user=request.user)
    if item.status == WatchlistStatus.STARRED:
        item.status = WatchlistStatus.WATCHING
    else:
        item.status = WatchlistStatus.STARRED
    item.save(update_fields=["status"])

    if request.headers.get("HX-Request"):
        return render(
            request,
            "marketplace/_watchlist_content.html",
            _build_watchlist_context(request.user, request.GET),
        )
    if item.status == WatchlistStatus.STARRED:
        django_messages.success(request, _("Added to starred items."))
    else:
        django_messages.success(request, _("Moved to watching."))
    return redirect("marketplace:watchlist")


@login_required
@require_POST
def watchlist_archive(request, pk):
    item = get_object_or_404(WatchlistItem, pk=pk)
    permission_service.authorize_watchlist_action(request.user.pk, item, "archive").deny_if_not_allowed()
    item.status = WatchlistStatus.ARCHIVED
    item.save(update_fields=["status"])
    django_messages.success(request, _("Watchlist item archived."))
    return redirect("marketplace:watchlist")


@login_required
@require_POST
def watchlist_unarchive(request, pk):
    item = get_object_or_404(WatchlistItem, pk=pk)
    permission_service.authorize_watchlist_action(request.user.pk, item, "unarchive").deny_if_not_allowed()
    item.status = WatchlistStatus.WATCHING
    item.save(update_fields=["status"])
    django_messages.success(request, _("Watchlist item restored to watching."))
    return redirect("marketplace:watchlist")


@login_required
@require_POST
def watchlist_delete(request, pk):
    item = get_object_or_404(WatchlistItem, pk=pk)
    permission_service.authorize_watchlist_action(request.user.pk, item, "delete").deny_if_not_allowed()
    item.delete()
    django_messages.success(request, _("Removed from watchlist."))
    return redirect("marketplace:watchlist")


@login_required
@require_POST
def watchlist_message(request, pk):
    """Create thread for a watchlist item and redirect to it."""
    item = get_object_or_404(WatchlistItem, pk=pk, user=request.user)
    thread, _ = _get_or_create_thread(item)
    return redirect("marketplace:thread_detail", pk=thread.pk)


# ---------------------------------------------------------------------------
# Discover actions (save, message)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def discover_save(request):
    """Save a listing from search results to watchlist."""
    listing_pk = request.POST.get("listing_pk")
    listing_type = request.POST.get("listing_type")
    next_url = request.POST.get("next")
    listing = _resolve_listing_for_action(listing_pk, listing_type)
    _get_or_create_watchlist_item(request.user, listing=listing, source=WatchlistSource.SEARCH)
    django_messages.success(request, _("Saved to watchlist."))
    if next_url:
        return redirect(next_url)
    request.session["discover_keep_results"] = True
    return redirect("marketplace:discover")


@login_required
@require_POST
def discover_unsave(request):
    """Remove a listing from watchlist via discover results."""
    listing_pk = request.POST.get("listing_pk")
    listing_type = request.POST.get("listing_type")
    next_url = request.POST.get("next")
    listing = _resolve_listing_for_action(listing_pk, listing_type)
    WatchlistItem.objects.filter(
        user=request.user,
        listing=listing,
    ).delete()
    django_messages.success(request, _("Removed from watchlist."))
    if next_url:
        return redirect(next_url)
    request.session["discover_keep_results"] = True
    return redirect("marketplace:discover")


@login_required
@require_POST
def discover_message(request):
    """Save + create thread + redirect to thread."""
    listing_pk = request.POST.get("listing_pk")
    listing_type = request.POST.get("listing_type")
    listing = _resolve_listing_for_action(listing_pk, listing_type)
    permission_service.authorize_message_initiation(request.user.pk, listing).deny_if_not_allowed()
    result = conversation_coordinator.start_thread_with_autosave(
        user=request.user,
        listing=listing,
        source=WatchlistSource.DIRECT,
    )
    django_messages.success(request, _("Conversation ready. Send your message below."))
    return redirect("marketplace:thread_detail", pk=result.thread.pk)


# ---------------------------------------------------------------------------
# Suggestion actions
# ---------------------------------------------------------------------------

@login_required
@require_POST
def suggestion_save(request):
    """Save a suggestion to watchlist."""
    listing_pk = request.POST.get("listing_pk")
    listing_type = request.POST.get("listing_type")
    listing = _resolve_listing_for_action(listing_pk, listing_type)
    _get_or_create_watchlist_item(request.user, listing=listing, source=WatchlistSource.SUGGESTION)
    django_messages.success(request, _("Saved to watchlist."))
    next_url = request.POST.get("next", "marketplace:dashboard")
    return redirect(next_url)


@login_required
@require_POST
def suggestion_dismiss(request):
    """Dismiss a suggestion so it won't show again."""
    listing_pk = request.POST.get("listing_pk")
    listing_type = request.POST.get("listing_type")
    listing = _resolve_listing_for_action(listing_pk, listing_type)
    DismissedSuggestion.objects.get_or_create(user=request.user, listing=listing)
    django_messages.success(request, _("Suggestion dismissed. You can find more matches in Discover."))
    next_url = request.POST.get("next", "marketplace:dashboard")
    return redirect(next_url)


# ---------------------------------------------------------------------------
# Messaging
# ---------------------------------------------------------------------------

@login_required
@ratelimit(key="user", rate="30/10m", method="POST", block=True)
def thread_detail(request, pk):
    thread = get_object_or_404(
        MessageThread.objects.select_related(
            "listing",
            "listing__created_by_user",
            "created_by_user",
        ),
        pk=pk,
    )
    permission_service.authorize_thread_access(request.user.pk, thread, "access").deny_if_not_allowed()

    # Mark thread as read for current user
    from django.utils import timezone
    ThreadReadState.objects.update_or_create(
        thread=thread, user=request.user,
        defaults={"last_read_at": timezone.now()},
    )

    listing = thread.get_listing()
    listing_deleted = listing is None or listing.status == "deleted"
    if request.method == "POST":
        if listing_deleted:
            raise PermissionDenied
        enter_pref = bool(request.POST.get("enter_to_send"))
        if request.user.enter_to_send != enter_pref:
            request.user.enter_to_send = enter_pref
            request.user.save(update_fields=["enter_to_send"])
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = Message.objects.create(
                thread=thread,
                sender=request.user,
                body=form.cleaned_data["body"],
            )
            send_new_message_notification(msg)
            from .sse_client import publish_new_message
            publish_new_message(msg)
            # Update read state after sending (sender has read their own message)
            ThreadReadState.objects.update_or_create(
                thread=thread, user=request.user,
                defaults={"last_read_at": timezone.now()},
            )
            return redirect("marketplace:thread_detail", pk=thread.pk)
    else:
        form = MessageForm(initial={"enter_to_send": request.user.enter_to_send})
    return render(request, "marketplace/thread_detail.html", _build_thread_context(
        thread=thread,
        user=request.user,
        form=form,
        back_to_messages_url=reverse("marketplace:inbox"),
        workspace_mode=False,
    ))


def _build_thread_context(thread, user, form, back_to_messages_url, workspace_mode):
    listing = thread.get_listing()
    listing_deleted = listing is None or listing.status == "deleted"
    msgs = thread.messages.select_related("sender").all()
    counterparty = thread.counterparty_for(user)
    listing_detail_url = ""
    listing_kind_label = ""
    if listing is not None:
        if listing.type == ListingType.SUPPLY:
            listing_detail_url = reverse("marketplace:supply_lot_detail", kwargs={"pk": listing.pk})
            listing_kind_label = _("Supply listing")
        else:
            listing_detail_url = reverse("marketplace:demand_post_detail", kwargs={"pk": listing.pk})
            listing_kind_label = _("Demand listing")
    return {
        "thread": thread,
        "messages_list": msgs,
        "form": form,
        "counterparty": counterparty,
        "listing": listing,
        "listing_detail_url": listing_detail_url,
        "listing_kind_label": listing_kind_label,
        "is_supply": thread.is_supply_thread(),
        "listing_deleted": listing_deleted,
        "thread_post_url": reverse("marketplace:thread_detail", kwargs={"pk": thread.pk}),
        "back_to_messages_url": back_to_messages_url,
        "workspace_mode": workspace_mode,
    }


@login_required
def thread_fragment(request, pk):
    if request.headers.get("HX-Request") != "true":
        return redirect("marketplace:thread_detail", pk=pk)
    thread = get_object_or_404(
        MessageThread.objects.select_related(
            "listing",
            "listing__created_by_user",
            "created_by_user",
        ),
        pk=pk,
    )
    permission_service.authorize_thread_access(request.user.pk, thread, "access").deny_if_not_allowed()
    from django.utils import timezone
    ThreadReadState.objects.update_or_create(
        thread=thread, user=request.user,
        defaults={"last_read_at": timezone.now()},
    )
    form = MessageForm(initial={"enter_to_send": request.user.enter_to_send})
    return render(request, "marketplace/thread_detail_fragment.html", _build_thread_context(
        thread=thread,
        user=request.user,
        form=form,
        back_to_messages_url=f"{reverse('marketplace:inbox')}?thread={thread.pk}",
        workspace_mode=True,
    ))


# ---------------------------------------------------------------------------
# Inbox
# ---------------------------------------------------------------------------

@login_required
def inbox_view(request):
    user = request.user
    thread_list = _build_inbox_threads_for_user(user)
    unread_threads = sum(1 for t in thread_list if t.is_unread)
    view_mode = _parse_inbox_view_mode(request)
    grouped_threads = _build_grouped_inbox_threads(thread_list) if view_mode == "grouped" else []

    selected_thread = None
    selected_thread_context = None
    selected_thread_param = request.GET.get("thread")
    if selected_thread_param:
        try:
            selected_pk = int(selected_thread_param)
        except (TypeError, ValueError):
            selected_pk = None
        if selected_pk is not None:
            selected_thread = next((t for t in thread_list if t.pk == selected_pk), None)

    if selected_thread is not None:
        from django.utils import timezone
        ThreadReadState.objects.update_or_create(
            thread=selected_thread, user=user,
            defaults={"last_read_at": timezone.now()},
        )
        selected_thread_context = _build_thread_context(
            thread=selected_thread,
            user=user,
            form=MessageForm(initial={"enter_to_send": user.enter_to_send}),
            back_to_messages_url=reverse("marketplace:inbox"),
            workspace_mode=True,
        )

    toggle_params = {"thread": selected_thread.pk} if selected_thread is not None else {}
    if view_mode == "grouped":
        toggle_params["view"] = "flat"
        toggle_label = _("All conversations")
    else:
        toggle_params["view"] = "grouped"
        toggle_label = _("Group by listing")
    toggle_url = reverse("marketplace:inbox")
    if toggle_params:
        toggle_url = f"{toggle_url}?{urlencode(toggle_params)}"

    return render(request, "marketplace/inbox.html", {
        "threads": thread_list,
        "grouped_threads": grouped_threads,
        "view_mode": view_mode,
        "toggle_label": toggle_label,
        "toggle_url": toggle_url,
        "unread_threads": unread_threads,
        "selected_thread": selected_thread,
        "selected_thread_context": selected_thread_context,
    })


def _parse_inbox_view_mode(request):
    mode = (request.GET.get("view") or "").strip().lower()
    return "grouped" if mode == "grouped" else "flat"


def _build_grouped_inbox_threads(thread_list):
    groups = []
    by_listing = {}
    for thread in thread_list:
        if thread.listing is not None:
            listing_key = str(thread.listing.pk)
            listing_title = thread.listing.item_text
        else:
            listing_key = f"missing-{thread.pk}"
            listing_title = _("Listing unavailable")
        if listing_key not in by_listing:
            group = {
                "listing_key": listing_key,
                "listing_title": listing_title,
                "rows": [],
            }
            by_listing[listing_key] = group
            groups.append(group)
        by_listing[listing_key]["rows"].append(thread)
    return groups


def _build_inbox_threads_for_user(user):
    from django.db.models import Subquery, OuterRef
    read_at_sq = ThreadReadState.objects.filter(
        thread=OuterRef("pk"), user=user,
    ).values("last_read_at")[:1]
    last_msg_body_sq = Message.objects.filter(
        thread=OuterRef("pk"),
    ).order_by("-created_at", "-pk").values("body")[:1]
    last_msg_sender_id_sq = Message.objects.filter(
        thread=OuterRef("pk"),
    ).order_by("-created_at", "-pk").values("sender_id")[:1]
    last_msg_sender_display_sq = Message.objects.filter(
        thread=OuterRef("pk"),
    ).order_by("-created_at", "-pk").values("sender__display_name")[:1]
    last_msg_sender_email_sq = Message.objects.filter(
        thread=OuterRef("pk"),
    ).order_by("-created_at", "-pk").values("sender__email")[:1]
    last_other_msg_sq = Message.objects.filter(
        thread=OuterRef("pk"),
    ).exclude(sender=user).order_by("-created_at", "-pk").values("created_at")[:1]
    threads = (
        MessageThread.objects.filter(
            Q(created_by_user=user)
            | Q(listing__created_by_user=user),
        )
        .select_related(
            "listing",
            "listing__created_by_user",
            "created_by_user",
        )
        .annotate(
            last_message_at=models.Max("messages__created_at"),
            last_other_message_at=Subquery(last_other_msg_sq),
            user_read_at=Subquery(read_at_sq),
            last_message_body=Subquery(last_msg_body_sq),
            last_message_sender_id=Subquery(last_msg_sender_id_sq),
            last_message_sender_display=Subquery(last_msg_sender_display_sq),
            last_message_sender_email=Subquery(last_msg_sender_email_sq),
        )
        .filter(last_message_at__isnull=False)
        .order_by("-last_message_at", "-pk")
    )
    thread_list = list(threads)
    for t in thread_list:
        _decorate_inbox_thread_for_user(t, user)
    return thread_list


def _decorate_inbox_thread_for_user(thread, user):
    thread.counterparty = thread.counterparty_for(user)
    thread.listing = thread.get_listing()
    thread.listing_detail_url = ""
    thread.listing_kind_label = ""
    if thread.listing is not None:
        if thread.listing.type == ListingType.SUPPLY:
            thread.listing_detail_url = reverse("marketplace:supply_lot_detail", kwargs={"pk": thread.listing.pk})
            thread.listing_kind_label = _("Supply")
        else:
            thread.listing_detail_url = reverse("marketplace:demand_post_detail", kwargs={"pk": thread.listing.pk})
            thread.listing_kind_label = _("Demand")
    sender_label = (thread.last_message_sender_display or "").strip() or (thread.last_message_sender_email or "").strip() or (thread.counterparty.display_name or thread.counterparty.email)
    preview_prefix = _("You") if thread.last_message_sender_id == user.pk else sender_label
    raw_preview = f"{preview_prefix}: {(thread.last_message_body or '').strip()}"
    if len(raw_preview) > 120:
        raw_preview = f"{raw_preview[:117]}..."
    thread.preview = raw_preview
    thread.is_unread = (
        thread.last_other_message_at is not None
        and (thread.user_read_at is None or thread.last_other_message_at > thread.user_read_at)
    )


@login_required
def inbox_thread_row_fragment(request, pk):
    thread = get_object_or_404(
        MessageThread.objects.select_related(
            "listing",
            "listing__created_by_user",
            "created_by_user",
        ),
        pk=pk,
    )
    permission_service.authorize_thread_access(request.user.pk, thread, "access").deny_if_not_allowed()
    hydrated = None
    for candidate in _build_inbox_threads_for_user(request.user):
        if candidate.pk == thread.pk:
            hydrated = candidate
            break
    if hydrated is None:
        raise Http404
    return render(
        request,
        "marketplace/inbox_thread_row_fragment.html",
        {"thread": hydrated, "selected_thread_pk": None},
    )


@login_required
@require_POST
def suggestion_message(request):
    """Create watchlist item + thread from a suggestion card and redirect to thread."""
    listing_pk = request.POST.get("listing_pk")
    listing_type = request.POST.get("listing_type")
    listing = _resolve_listing_for_action(listing_pk, listing_type)
    permission_service.authorize_message_initiation(request.user.pk, listing).deny_if_not_allowed()
    result = conversation_coordinator.start_thread_with_autosave(
        user=request.user,
        listing=listing,
        source=WatchlistSource.SUGGESTION,
    )
    django_messages.success(request, _("Conversation ready. Send your message below."))
    return redirect("marketplace:thread_detail", pk=result.thread.pk)


# ---------------------------------------------------------------------------
# Vector index sync helper
# ---------------------------------------------------------------------------

def _sync_listing_to_vector_index(listing):
    """Sync a listing to the ChromaDB vector index. Silently handles errors."""
    try:
        from .vector_search import index_listing
        index_listing(listing)
    except Exception:
        pass


def _remove_listing_from_vector_index(listing):
    """Remove a listing from the ChromaDB vector index. Silently handles errors."""
    try:
        from .vector_search import remove_listing
        remove_listing(listing)
    except Exception:
        pass
