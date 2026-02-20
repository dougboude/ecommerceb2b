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
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from django_ratelimit.decorators import ratelimit

from .forms import DemandPostForm, DiscoverForm, MessageForm, ProfileForm, SignupForm, SupplyLotForm
from .matching import (
    get_suggestions_for_lot,
    get_suggestions_for_post,
    watchlisted_demand_post_ids,
    watchlisted_supply_lot_ids,
)
from .models import (
    DemandPost,
    DemandStatus,
    DismissedSuggestion,
    Message,
    MessageThread,
    Role,
    SupplyLot,
    SupplyStatus,
    WatchlistItem,
    WatchlistSource,
    WatchlistStatus,
)

PAGE_SIZE = 25


# ---------------------------------------------------------------------------
# Watchlist helpers
# ---------------------------------------------------------------------------

def _get_or_create_watchlist_item(user, supply_lot=None, demand_post=None, source=WatchlistSource.DIRECT):
    """Get or create a WatchlistItem. Returns (item, created)."""
    lookup = {"user": user}
    if supply_lot:
        lookup["supply_lot"] = supply_lot
    else:
        lookup["demand_post"] = demand_post
    item, created = WatchlistItem.objects.get_or_create(
        defaults={"source": source},
        **lookup,
    )
    return item, created


def _get_or_create_thread(watchlist_item):
    """Get or create a MessageThread for a watchlist item. Returns (thread, created)."""
    if hasattr(watchlist_item, "thread"):
        return watchlist_item.thread, False
    if watchlist_item.supply_lot:
        buyer = watchlist_item.user
        supplier = watchlist_item.supply_lot.created_by
    else:
        supplier = watchlist_item.user
        buyer = watchlist_item.demand_post.created_by
    thread, created = MessageThread.objects.get_or_create(
        watchlist_item=watchlist_item,
        defaults={"buyer": buyer, "supplier": supplier},
    )
    return thread, created


def _archive_watchlist_items_for_lot(lot):
    """Archive all watchlist items pointing at this supply lot."""
    WatchlistItem.objects.filter(
        supply_lot=lot,
        status__in=[WatchlistStatus.STARRED, WatchlistStatus.WATCHING],
    ).update(status=WatchlistStatus.ARCHIVED)


def _archive_watchlist_items_for_post(post):
    """Archive all watchlist items pointing at this demand post."""
    WatchlistItem.objects.filter(
        demand_post=post,
        status__in=[WatchlistStatus.STARRED, WatchlistStatus.WATCHING],
    ).update(status=WatchlistStatus.ARCHIVED)


def _restore_watchlist_items_for_lot(lot):
    """Restore archived watchlist items when a lot is reactivated."""
    WatchlistItem.objects.filter(
        supply_lot=lot, status=WatchlistStatus.ARCHIVED,
    ).update(status=WatchlistStatus.WATCHING)


def _restore_watchlist_items_for_post(post):
    """Restore archived watchlist items when a post is reactivated."""
    WatchlistItem.objects.filter(
        demand_post=post, status=WatchlistStatus.ARCHIVED,
    ).update(status=WatchlistStatus.WATCHING)


# ---------------------------------------------------------------------------
# Lot / post numbering helpers
# ---------------------------------------------------------------------------

def _build_lot_number_map(user):
    """Return {lot_pk: sequential_number} partitioned by item_text."""
    lots = (
        SupplyLot.objects.filter(created_by=user)
        .annotate(
            row_num=Window(
                expression=RowNumber(),
                partition_by=[F("item_text")],
                order_by=F("created_at").asc(),
            )
        )
        .values_list("pk", "row_num")
    )
    return dict(lots)


def _build_post_number_map(user):
    """Return {post_pk: sequential_number} partitioned by item_text."""
    posts = (
        DemandPost.objects.filter(created_by=user)
        .annotate(
            row_num=Window(
                expression=RowNumber(),
                partition_by=[F("item_text")],
                order_by=F("created_at").asc(),
            )
        )
        .values_list("pk", "row_num")
    )
    return dict(posts)


def _get_lot_number(lot):
    """Get the sequential number for a single supply lot."""
    earlier = SupplyLot.objects.filter(
        created_by=lot.created_by,
        item_text=lot.item_text,
        created_at__lte=lot.created_at,
    ).count()
    return earlier


def _get_post_number(post):
    """Get the sequential number for a single demand post."""
    earlier = DemandPost.objects.filter(
        created_by=post.created_by,
        item_text=post.item_text,
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
            login(request, user)
            django_messages.success(request, _("Account created successfully."))
            return redirect("marketplace:dashboard")
    else:
        form = SignupForm()
    return render(request, "registration/signup.html", {"form": form})


class MarketplaceLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True


class MarketplaceLogoutView(LogoutView):
    next_page = "marketplace:login"


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard_view(request):
    user = request.user
    context = {}
    if user.role == Role.BUYER:
        posts = DemandPost.objects.filter(
            created_by=user,
        ).exclude(status=DemandStatus.DELETED).order_by("-created_at")[:5]
        post_numbers = _build_post_number_map(user)
        for p in posts:
            p.post_number = post_numbers.get(p.pk, 1)
        context["demand_posts"] = posts

        # Watchlist summary
        watchlist_count = WatchlistItem.objects.filter(
            user=user, status__in=[WatchlistStatus.STARRED, WatchlistStatus.WATCHING],
        ).count()
        context["watchlist_count"] = watchlist_count

        # Suggestions
        suggestions = []
        for post in DemandPost.objects.filter(created_by=user, status=DemandStatus.ACTIVE):
            suggestions.extend(get_suggestions_for_post(post, user, limit=3))
        # Deduplicate by supply lot pk
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            if s.pk not in seen:
                seen.add(s.pk)
                unique_suggestions.append(s)
        context["suggestions"] = unique_suggestions[:5]
        context["suggestion_type"] = "supply_lot"
        context["watchlisted_pks"] = watchlisted_supply_lot_ids(user)
    else:
        lots = SupplyLot.objects.filter(
            created_by=user,
        ).exclude(status=SupplyStatus.DELETED).order_by("-created_at")[:5]
        lot_numbers = _build_lot_number_map(user)
        for lot in lots:
            lot.lot_number = lot_numbers.get(lot.pk, 1)
        context["supply_lots"] = lots

        # Watchlist summary
        watchlist_count = WatchlistItem.objects.filter(
            user=user, status__in=[WatchlistStatus.STARRED, WatchlistStatus.WATCHING],
        ).count()
        context["watchlist_count"] = watchlist_count

        # Suggestions
        suggestions = []
        for lot in SupplyLot.objects.filter(created_by=user, status=SupplyStatus.ACTIVE):
            suggestions.extend(get_suggestions_for_lot(lot, user, limit=3))
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            if s.pk not in seen:
                seen.add(s.pk)
                unique_suggestions.append(s)
        context["suggestions"] = unique_suggestions[:5]
        context["suggestion_type"] = "demand_post"
        context["watchlisted_pks"] = watchlisted_demand_post_ids(user)
    return render(request, "marketplace/dashboard.html", context)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@login_required
def profile_view(request):
    return render(request, "marketplace/profile.html")


@login_required
def profile_edit(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            django_messages.success(request, _("Profile updated."))
            return redirect("marketplace:profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "marketplace/profile_edit.html", {"form": form})


# ---------------------------------------------------------------------------
# DemandPost (buyer)
# ---------------------------------------------------------------------------

@login_required
def demand_post_list(request):
    if request.user.role != Role.BUYER:
        raise PermissionDenied
    qs = DemandPost.objects.filter(created_by=request.user).exclude(status=DemandStatus.DELETED).order_by("-created_at")
    post_numbers = _build_post_number_map(request.user)
    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    for post in page_obj:
        post.post_number = post_numbers.get(post.pk, 1)
    return render(request, "marketplace/demand_post_list.html", {"page_obj": page_obj})


@login_required
def demand_post_create(request):
    if request.user.role != Role.BUYER:
        raise PermissionDenied
    if request.method == "POST":
        form = DemandPostForm(request.POST, user=request.user)
        if form.is_valid():
            post = form.save(commit=False)
            post.created_by = request.user
            post.organization = request.user.organization
            post.save()
            _sync_listing_to_vector_index(post)
            django_messages.success(request, _("Demand post created."))
            return redirect("marketplace:demand_post_detail", pk=post.pk)
    else:
        form = DemandPostForm(user=request.user)
    return render(request, "marketplace/demand_post_form.html", {"form": form})


@login_required
def demand_post_edit(request, pk):
    post = get_object_or_404(DemandPost, pk=pk, created_by=request.user)
    if request.method == "POST":
        form = DemandPostForm(request.POST, instance=post, user=request.user)
        if form.is_valid():
            form.save()
            _sync_listing_to_vector_index(post)
            django_messages.success(request, _("Demand post updated."))
            return redirect("marketplace:demand_post_detail", pk=post.pk)
    else:
        form = DemandPostForm(instance=post, user=request.user)
    return render(request, "marketplace/demand_post_form.html", {
        "form": form,
        "editing": True,
    })


@login_required
def demand_post_detail(request, pk):
    post = get_object_or_404(DemandPost, pk=pk)
    is_owner = post.created_by == request.user
    post.post_number = _get_post_number(post)
    suggestions = []
    if is_owner and post.status == DemandStatus.ACTIVE:
        suggestions = get_suggestions_for_post(post, request.user, limit=5)
    watchlisted_pks = watchlisted_supply_lot_ids(request.user) if suggestions else set()
    return render(request, "marketplace/demand_post_detail.html", {
        "post": post,
        "suggestions": suggestions,
        "is_owner": is_owner,
        "watchlisted_pks": watchlisted_pks,
    })


@login_required
@require_POST
def demand_post_toggle(request, pk):
    post = get_object_or_404(DemandPost, pk=pk, created_by=request.user)
    if post.status == "active":
        post.status = "paused"
    elif post.status in ("paused", "fulfilled"):
        post.status = "active"
    post.save(update_fields=["status"])
    _sync_listing_to_vector_index(post)
    if post.status == "active":
        _restore_watchlist_items_for_post(post)
    else:
        _archive_watchlist_items_for_post(post)
    return redirect("marketplace:demand_post_detail", pk=post.pk)


@login_required
def demand_post_delete(request, pk):
    post = get_object_or_404(DemandPost, pk=pk, created_by=request.user)
    if request.method == "POST":
        post.status = DemandStatus.DELETED
        post.save(update_fields=["status"])
        _archive_watchlist_items_for_post(post)
        _remove_listing_from_vector_index(post)
        django_messages.success(request, _("Demand post deleted."))
        return redirect("marketplace:demand_post_list")
    return render(request, "marketplace/listing_delete_confirm.html", {
        "listing_title": post.item_text,
        "delete_url": request.path,
        "cancel_url": redirect("marketplace:demand_post_detail", pk=post.pk).url,
    })


# ---------------------------------------------------------------------------
# SupplyLot (supplier)
# ---------------------------------------------------------------------------

@login_required
def supply_lot_list(request):
    if request.user.role != Role.SUPPLIER:
        raise PermissionDenied
    qs = SupplyLot.objects.filter(created_by=request.user).exclude(status=SupplyStatus.DELETED).order_by("-created_at")
    lot_numbers = _build_lot_number_map(request.user)
    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    for lot in page_obj:
        lot.lot_number = lot_numbers.get(lot.pk, 1)
    return render(request, "marketplace/supply_lot_list.html", {"page_obj": page_obj})


@login_required
def supply_lot_create(request):
    if request.user.role != Role.SUPPLIER:
        raise PermissionDenied
    if request.method == "POST":
        form = SupplyLotForm(request.POST)
        if form.is_valid():
            lot = form.save(commit=False)
            lot.created_by = request.user
            lot.save()
            _sync_listing_to_vector_index(lot)
            django_messages.success(request, _("Supply lot created."))
            return redirect("marketplace:supply_lot_detail", pk=lot.pk)
    else:
        form = SupplyLotForm()
    return render(request, "marketplace/supply_lot_form.html", {"form": form})


@login_required
def supply_lot_edit(request, pk):
    lot = get_object_or_404(SupplyLot, pk=pk, created_by=request.user)
    if request.method == "POST":
        form = SupplyLotForm(request.POST, instance=lot)
        if form.is_valid():
            form.save()
            _sync_listing_to_vector_index(lot)
            django_messages.success(request, _("Supply lot updated."))
            return redirect("marketplace:supply_lot_detail", pk=lot.pk)
    else:
        form = SupplyLotForm(instance=lot)
    return render(request, "marketplace/supply_lot_form.html", {
        "form": form,
        "editing": True,
    })


@login_required
def supply_lot_detail(request, pk):
    lot = get_object_or_404(SupplyLot, pk=pk)
    is_owner = lot.created_by == request.user
    lot.lot_number = _get_lot_number(lot)
    suggestions = []
    if is_owner and lot.status == SupplyStatus.ACTIVE:
        suggestions = get_suggestions_for_lot(lot, request.user, limit=5)
    watchlisted_pks = watchlisted_demand_post_ids(request.user) if suggestions else set()
    return render(request, "marketplace/supply_lot_detail.html", {
        "lot": lot,
        "suggestions": suggestions,
        "is_owner": is_owner,
        "watchlisted_pks": watchlisted_pks,
    })


@login_required
@require_POST
def supply_lot_toggle(request, pk):
    lot = get_object_or_404(SupplyLot, pk=pk, created_by=request.user)
    if lot.status == "active":
        lot.status = "withdrawn"
    elif lot.status == "withdrawn":
        lot.status = "active"
    lot.save(update_fields=["status"])
    _sync_listing_to_vector_index(lot)
    if lot.status == "active":
        _restore_watchlist_items_for_lot(lot)
    else:
        _archive_watchlist_items_for_lot(lot)
    return redirect("marketplace:supply_lot_detail", pk=lot.pk)


@login_required
def supply_lot_delete(request, pk):
    lot = get_object_or_404(SupplyLot, pk=pk, created_by=request.user)
    if request.method == "POST":
        lot.status = SupplyStatus.DELETED
        lot.save(update_fields=["status"])
        _archive_watchlist_items_for_lot(lot)
        _remove_listing_from_vector_index(lot)
        django_messages.success(request, _("Supply lot deleted."))
        return redirect("marketplace:supply_lot_list")
    return render(request, "marketplace/listing_delete_confirm.html", {
        "listing_title": lot.item_text,
        "delete_url": request.path,
        "cancel_url": redirect("marketplace:supply_lot_detail", pk=lot.pk).url,
    })


# ---------------------------------------------------------------------------
# Discover (search)
# ---------------------------------------------------------------------------

def _run_discover_search(user, query, category, country, search_mode="similar"):
    """Run discover search and return results list."""
    if user.role == Role.BUYER:
        listing_type = "supply_lot"
    else:
        listing_type = "demand_post"

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


def _discover_watchlisted_pks(user):
    """Return set of PKs already on the user's watchlist."""
    if user.role == Role.BUYER:
        return set(WatchlistItem.objects.filter(
            user=user, supply_lot__isnull=False,
        ).values_list("supply_lot_id", flat=True))
    return set(WatchlistItem.objects.filter(
        user=user, demand_post__isnull=False,
    ).values_list("demand_post_id", flat=True))


@login_required
def discover_view(request):
    user = request.user
    results = []
    searched = False
    watchlisted_pks = set()

    if request.method == "POST":
        form = DiscoverForm(request.POST, user=user)
        if form.is_valid() and form.cleaned_data.get("query"):
            query = form.cleaned_data["query"]
            category = form.cleaned_data.get("category") or ""
            country = form.cleaned_data.get("location_country") or ""
            radius = form.cleaned_data.get("radius") or ""
            search_mode = form.cleaned_data.get("search_mode", "similar")

            # Store params in session
            request.session["discover_last_query"] = query
            request.session["discover_last_category"] = category
            request.session["discover_last_country"] = country
            request.session["discover_last_radius"] = radius
            request.session["discover_last_search_mode"] = search_mode

            results = _run_discover_search(user, query, category, country, search_mode)
            searched = True
            watchlisted_pks = _discover_watchlisted_pks(user)
    else:
        # Repopulate from session only when redirected back from save/unsave
        keep_results = request.session.pop("discover_keep_results", False)
        session_query = request.session.get("discover_last_query", "")
        if keep_results and session_query:
            initial = {
                "query": session_query,
                "category": request.session.get("discover_last_category", ""),
                "location_country": request.session.get("discover_last_country", ""),
                "radius": request.session.get("discover_last_radius", ""),
                "search_mode": request.session.get("discover_last_search_mode", "similar"),
            }
            form = DiscoverForm(initial=initial, user=user)
            results = _run_discover_search(
                user, session_query,
                initial["category"], initial["location_country"],
                initial["search_mode"],
            )
            searched = True
            watchlisted_pks = _discover_watchlisted_pks(user)
        else:
            form = DiscoverForm(user=user)

    return render(request, "marketplace/discover.html", {
        "form": form,
        "results": results,
        "searched": searched,
        "watchlisted_pks": watchlisted_pks,
    })


@login_required
def discover_clear(request):
    """Clear discover search session state and redirect to a fresh form."""
    for key in ["discover_last_query", "discover_last_category",
                "discover_last_country", "discover_last_radius",
                "discover_last_search_mode", "discover_keep_results"]:
        request.session.pop(key, None)
    return redirect("marketplace:discover")


def _keyword_search(query, listing_type, user, category=None, country=None, limit=20):
    """Keyword search using Django ORM. Splits query into words and requires all (AND)."""
    from django.utils import timezone
    now = timezone.now()

    words = query.split()
    if not words:
        return []

    # Build AND filter: every word must appear in item_text
    word_filter = Q()
    for word in words:
        word_filter &= Q(item_text__icontains=word)

    if listing_type == "supply_lot":
        qs = SupplyLot.objects.filter(
            word_filter,
            status=SupplyStatus.ACTIVE,
            available_until__gt=now,
        ).exclude(created_by=user)
        if category:
            qs = qs.filter(category=category)
        if country:
            qs = qs.filter(location_country=country)
        return list(qs.order_by("-created_at")[:limit])
    else:
        qs = DemandPost.objects.filter(
            word_filter,
            status=DemandStatus.ACTIVE,
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now),
        ).exclude(created_by=user)
        if category:
            qs = qs.filter(category=category)
        if country:
            qs = qs.filter(location_country=country)
        return list(qs.order_by("-created_at")[:limit])


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

@login_required
def watchlist_view(request):
    user = request.user
    qs = WatchlistItem.objects.filter(user=user)
    if user.role == Role.BUYER:
        qs = qs.select_related("supply_lot", "supply_lot__created_by", "thread")
    else:
        qs = qs.select_related("demand_post", "demand_post__created_by", "thread")

    watching = list(qs.filter(
        status__in=[WatchlistStatus.STARRED, WatchlistStatus.WATCHING],
    ).order_by("-updated_at"))
    archived = list(qs.filter(status=WatchlistStatus.ARCHIVED).order_by("-updated_at"))

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
    item = get_object_or_404(WatchlistItem, pk=pk, user=request.user)
    item.status = WatchlistStatus.ARCHIVED
    item.save(update_fields=["status"])
    return redirect("marketplace:watchlist")


@login_required
@require_POST
def watchlist_unarchive(request, pk):
    item = get_object_or_404(WatchlistItem, pk=pk, user=request.user)
    item.status = WatchlistStatus.WATCHING
    item.save(update_fields=["status"])
    return redirect("marketplace:watchlist")


@login_required
@require_POST
def watchlist_delete(request, pk):
    item = get_object_or_404(WatchlistItem, pk=pk, user=request.user)
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
    listing_type = request.POST.get("listing_type")
    listing_pk = request.POST.get("listing_pk")
    if listing_type == "supply_lot":
        lot = get_object_or_404(SupplyLot, pk=listing_pk)
        _get_or_create_watchlist_item(request.user, supply_lot=lot, source=WatchlistSource.SEARCH)
    elif listing_type == "demand_post":
        post = get_object_or_404(DemandPost, pk=listing_pk)
        _get_or_create_watchlist_item(request.user, demand_post=post, source=WatchlistSource.SEARCH)
    django_messages.success(request, _("Saved to watchlist."))
    request.session["discover_keep_results"] = True
    return redirect("marketplace:discover")


@login_required
@require_POST
def discover_unsave(request):
    """Remove a listing from watchlist via discover results."""
    listing_type = request.POST.get("listing_type")
    listing_pk = request.POST.get("listing_pk")
    if listing_type == "supply_lot":
        WatchlistItem.objects.filter(
            user=request.user, supply_lot_id=listing_pk,
        ).delete()
    elif listing_type == "demand_post":
        WatchlistItem.objects.filter(
            user=request.user, demand_post_id=listing_pk,
        ).delete()
    django_messages.success(request, _("Removed from watchlist."))
    request.session["discover_keep_results"] = True
    return redirect("marketplace:discover")


@login_required
@require_POST
def discover_message(request):
    """Save + create thread + redirect to thread."""
    listing_type = request.POST.get("listing_type")
    listing_pk = request.POST.get("listing_pk")
    if listing_type == "supply_lot":
        lot = get_object_or_404(SupplyLot, pk=listing_pk)
        item, _ = _get_or_create_watchlist_item(request.user, supply_lot=lot, source=WatchlistSource.DIRECT)
    elif listing_type == "demand_post":
        post = get_object_or_404(DemandPost, pk=listing_pk)
        item, _ = _get_or_create_watchlist_item(request.user, demand_post=post, source=WatchlistSource.DIRECT)
    else:
        raise PermissionDenied
    thread, _ = _get_or_create_thread(item)
    return redirect("marketplace:thread_detail", pk=thread.pk)


# ---------------------------------------------------------------------------
# Suggestion actions
# ---------------------------------------------------------------------------

@login_required
@require_POST
def suggestion_save(request):
    """Save a suggestion to watchlist."""
    listing_type = request.POST.get("listing_type")
    listing_pk = request.POST.get("listing_pk")
    if listing_type == "supply_lot":
        lot = get_object_or_404(SupplyLot, pk=listing_pk)
        _get_or_create_watchlist_item(request.user, supply_lot=lot, source=WatchlistSource.SUGGESTION)
    elif listing_type == "demand_post":
        post = get_object_or_404(DemandPost, pk=listing_pk)
        _get_or_create_watchlist_item(request.user, demand_post=post, source=WatchlistSource.SUGGESTION)
    django_messages.success(request, _("Saved to watchlist."))
    next_url = request.POST.get("next", "marketplace:dashboard")
    return redirect(next_url)


@login_required
@require_POST
def suggestion_dismiss(request):
    """Dismiss a suggestion so it won't show again."""
    listing_type = request.POST.get("listing_type")
    listing_pk = request.POST.get("listing_pk")
    if listing_type == "supply_lot":
        lot = get_object_or_404(SupplyLot, pk=listing_pk)
        DismissedSuggestion.objects.get_or_create(user=request.user, supply_lot=lot)
    elif listing_type == "demand_post":
        post = get_object_or_404(DemandPost, pk=listing_pk)
        DismissedSuggestion.objects.get_or_create(user=request.user, demand_post=post)
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
            "watchlist_item",
            "watchlist_item__supply_lot",
            "watchlist_item__supply_lot__created_by",
            "watchlist_item__demand_post",
            "watchlist_item__demand_post__created_by",
            "buyer",
            "supplier",
        ),
        pk=pk,
    )
    if request.user not in (thread.buyer, thread.supplier):
        raise PermissionDenied
    listing = thread.watchlist_item.supply_lot or thread.watchlist_item.demand_post
    listing_deleted = listing.status == "deleted"
    if request.method == "POST":
        if listing_deleted:
            raise PermissionDenied
        form = MessageForm(request.POST)
        if form.is_valid():
            Message.objects.create(
                thread=thread,
                sender=request.user,
                body=form.cleaned_data["body"],
            )
            return redirect("marketplace:thread_detail", pk=thread.pk)
    else:
        form = MessageForm()
    msgs = thread.messages.select_related("sender").all()
    counterparty = thread.supplier if request.user == thread.buyer else thread.buyer
    return render(request, "marketplace/thread_detail.html", {
        "thread": thread,
        "messages_list": msgs,
        "form": form,
        "counterparty": counterparty,
        "listing_deleted": listing_deleted,
    })


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
