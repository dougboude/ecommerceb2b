from collections import defaultdict

from django.contrib import messages as django_messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Count, F, Q, Window
from django.db.models.functions import RowNumber
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

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
    Listing,
    ListingStatus,
    ListingType,
    DismissedSuggestion,
    Message,
    MessageThread,
    ThreadReadState,
    WatchlistItem,
    WatchlistSource,
    WatchlistStatus,
)
from .notifications import send_new_message_notification

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
            login(request, user)
            django_messages.success(request, _("Account created successfully."))
            response = redirect("marketplace:dashboard")
            return _set_skin_cookie(response, user.skin)
    else:
        form = SignupForm()
    return render(request, "registration/signup.html", {"form": form})


class MarketplaceLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        return _set_skin_cookie(response, form.get_user().skin)


class MarketplaceLogoutView(LogoutView):
    next_page = "marketplace:login"


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
# Demand/Supply listing views (route names retained for compatibility)
# ---------------------------------------------------------------------------


@login_required
def demand_post_list(request):
    qs = Listing.objects.filter(
        created_by_user=request.user,
        type=ListingType.DEMAND,
    ).exclude(status=ListingStatus.DELETED).order_by("-created_at")
    post_numbers = _build_post_number_map(request.user)
    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    counts = bulk_suggestion_counts(page_obj, request.user, listing_side="demand")
    for post in page_obj:
        post.post_number = post_numbers.get(post.pk, 1)
        post.unsaved_count, post.saved_count = counts.get(post.pk, (0, 0))
    return render(request, "marketplace/demand_post_list.html", {"page_obj": page_obj})


@login_required
def demand_post_create(request):
    if request.method == "POST":
        form = DemandPostForm(request.POST, user=request.user)
        if form.is_valid():
            post = form.save(commit=False)
            post.created_by_user = request.user
            post.save()
            _sync_listing_to_vector_index(post)
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
            django_messages.success(request, _("Demand listing updated."))
            return redirect("marketplace:demand_post_detail", pk=post.pk)
    else:
        form = DemandPostForm(instance=post, user=request.user)
    return render(request, "marketplace/demand_post_form.html", {"form": form, "editing": True})


@login_required
def demand_post_detail(request, pk):
    post = _get_listing_or_404(pk, ListingType.DEMAND)
    is_owner = post.created_by_user == request.user
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
    if post.status == ListingStatus.ACTIVE:
        _restore_watchlist_items_for_listing(post)
    else:
        _archive_watchlist_items_for_listing(post)
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
    lot_numbers = _build_lot_number_map(request.user)
    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    counts = bulk_suggestion_counts(page_obj, request.user, listing_side="supply")
    for lot in page_obj:
        lot.lot_number = lot_numbers.get(lot.pk, 1)
        lot.unsaved_count, lot.saved_count = counts.get(lot.pk, (0, 0))
    return render(request, "marketplace/supply_lot_list.html", {"page_obj": page_obj})


@login_required
def supply_lot_create(request):
    if request.method == "POST":
        form = SupplyLotForm(request.POST)
        if form.is_valid():
            lot = form.save(commit=False)
            lot.created_by_user = request.user
            lot.save()
            _sync_listing_to_vector_index(lot)
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
            lot = form.save()
            _sync_listing_to_vector_index(lot)
            django_messages.success(request, _("Supply listing updated."))
            return redirect("marketplace:supply_lot_detail", pk=lot.pk)
    else:
        form = SupplyLotForm(instance=lot)
    return render(request, "marketplace/supply_lot_form.html", {"form": form, "editing": True})


@login_required
def supply_lot_detail(request, pk):
    lot = _get_listing_or_404(pk, ListingType.SUPPLY)
    is_owner = lot.created_by_user == request.user
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
        "watchlisted_pks": watchlisted_pks,
        "listing_threads": listing_threads,
    })


@login_required
@require_POST
def supply_lot_toggle(request, pk):
    lot = _get_listing_or_404(pk, ListingType.SUPPLY)
    permission_service.authorize_listing_mutation(request.user.pk, lot, "toggle").deny_if_not_allowed()
    if lot.status == ListingStatus.ACTIVE:
        lot.status = ListingStatus.WITHDRAWN
    elif lot.status == ListingStatus.WITHDRAWN:
        lot.status = ListingStatus.ACTIVE
    lot.save(update_fields=["status"])
    _sync_listing_to_vector_index(lot)
    if lot.status == ListingStatus.ACTIVE:
        _restore_watchlist_items_for_listing(lot)
    else:
        _archive_watchlist_items_for_listing(lot)
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
        if listing.discover_listing_type == "supply_lot":
            listing.discover_ending_at = getattr(listing, "available_until", None)
        else:
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
                    listing.available_until is None,
                    listing.available_until or listing.created_at,
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

    if request.method == "POST":
        form = DiscoverForm(request.POST, user=user)
        if form.is_valid() and form.cleaned_data.get("query"):
            query = form.cleaned_data["query"]
            direction = _normalize_discover_direction(form.cleaned_data.get("direction"))
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
    user = request.user
    qs = WatchlistItem.objects.filter(user=user).select_related(
        "listing",
        "listing__created_by_user",
    )

    watching = list(qs.filter(
        status__in=[WatchlistStatus.STARRED, WatchlistStatus.WATCHING],
    ).order_by("-updated_at"))
    archived = list(qs.filter(status=WatchlistStatus.ARCHIVED).order_by("-updated_at"))

    for item in watching + archived:
        item.resolved_listing = item.resolve_listing()

    _attach_unread_counts(user, watching)
    _attach_unread_counts(user, archived)

    return render(request, "marketplace/watchlist.html", {
        "watching": watching,
        "archived": archived,
    })


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
        is_starred = item.status == WatchlistStatus.STARRED
        inactive = item.status == WatchlistStatus.ARCHIVED
        item.resolved_listing = item.resolve_listing()
        _attach_unread_counts(request.user, [item])
        return render(request, "marketplace/_watchlist_card.html", {
            "item": item,
            "show_star": not is_starred and not inactive,
            "show_unstar": is_starred,
            "show_archive": not inactive,
            "show_unarchive": inactive,
            "show_remove": not inactive,
            "inactive": inactive,
        })
    return redirect("marketplace:watchlist")


@login_required
@require_POST
def watchlist_archive(request, pk):
    item = get_object_or_404(WatchlistItem, pk=pk)
    permission_service.authorize_watchlist_action(request.user.pk, item, "archive").deny_if_not_allowed()
    item.status = WatchlistStatus.ARCHIVED
    item.save(update_fields=["status"])
    return redirect("marketplace:watchlist")


@login_required
@require_POST
def watchlist_unarchive(request, pk):
    item = get_object_or_404(WatchlistItem, pk=pk)
    permission_service.authorize_watchlist_action(request.user.pk, item, "unarchive").deny_if_not_allowed()
    item.status = WatchlistStatus.WATCHING
    item.save(update_fields=["status"])
    return redirect("marketplace:watchlist")


@login_required
@require_POST
def watchlist_delete(request, pk):
    item = get_object_or_404(WatchlistItem, pk=pk)
    permission_service.authorize_watchlist_action(request.user.pk, item, "delete").deny_if_not_allowed()
    item.delete()
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
    listing = _resolve_listing_for_action(listing_pk, listing_type)
    _get_or_create_watchlist_item(request.user, listing=listing, source=WatchlistSource.SEARCH)
    django_messages.success(request, _("Saved to watchlist."))
    request.session["discover_keep_results"] = True
    return redirect("marketplace:discover")


@login_required
@require_POST
def discover_unsave(request):
    """Remove a listing from watchlist via discover results."""
    listing_pk = request.POST.get("listing_pk")
    listing_type = request.POST.get("listing_type")
    listing = _resolve_listing_for_action(listing_pk, listing_type)
    WatchlistItem.objects.filter(
        user=request.user,
        listing=listing,
    ).delete()
    django_messages.success(request, _("Removed from watchlist."))
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
        form = MessageForm()
    msgs = thread.messages.select_related("sender").all()
    counterparty = thread.counterparty_for(request.user)
    return render(request, "marketplace/thread_detail.html", {
        "thread": thread,
        "messages_list": msgs,
        "form": form,
        "counterparty": counterparty,
        "listing": listing,
        "is_supply": thread.is_supply_thread(),
        "listing_deleted": listing_deleted,
    })


# ---------------------------------------------------------------------------
# Inbox
# ---------------------------------------------------------------------------

@login_required
def inbox_view(request):
    from django.db.models import F, Subquery, OuterRef
    from django.utils import timezone

    user = request.user

    read_at_sq = ThreadReadState.objects.filter(
        thread=OuterRef("pk"), user=user,
    ).values("last_read_at")[:1]

    last_msg_body_sq = Message.objects.filter(
        thread=OuterRef("pk"),
    ).order_by("-created_at").values("body")[:1]

    last_other_msg_sq = Message.objects.filter(
        thread=OuterRef("pk"),
    ).exclude(sender=user).order_by("-created_at").values("created_at")[:1]

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
        )
        .filter(last_message_at__isnull=False)
        .order_by("-last_message_at")
    )

    thread_list = []
    for t in threads:
        t.counterparty = t.counterparty_for(user)
        t.listing = t.get_listing()
        preview = (t.last_message_body or "")[:120]
        if len(t.last_message_body or "") > 120:
            preview += "..."
        t.preview = preview
        t.is_unread = (
            t.last_other_message_at is not None
            and (t.user_read_at is None or t.last_other_message_at > t.user_read_at)
        )
        thread_list.append(t)

    return render(request, "marketplace/inbox.html", {
        "threads": thread_list,
    })


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
