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

from .forms import DemandPostForm, MessageForm, ProfileForm, SignupForm, SupplyLotForm
from .matching import evaluate_demand_post, evaluate_supply_lot
from .models import (
    DemandPost,
    DemandStatus,
    Match,
    Message,
    MessageThread,
    Role,
    SupplyLot,
    SupplyStatus,
)

PAGE_SIZE = 25


def _active_matches():
    """Return Match queryset excluding withdrawn/expired lots and paused/fulfilled/expired posts."""
    return Match.objects.filter(
        supply_lot__status=SupplyStatus.ACTIVE,
        demand_post__status=DemandStatus.ACTIVE,
    )


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
    active_match_filter = Count(
        "matches",
        filter=models.Q(
            matches__supply_lot__status=SupplyStatus.ACTIVE,
            matches__demand_post__status=DemandStatus.ACTIVE,
        ),
    )
    if user.role == Role.BUYER:
        posts = DemandPost.objects.filter(
            created_by=user,
        ).annotate(match_count=active_match_filter).order_by("-created_at")[:5]
        post_numbers = _build_post_number_map(user)
        for p in posts:
            p.post_number = post_numbers.get(p.pk, 1)
        context["demand_posts"] = posts
        matches = _active_matches().filter(
            demand_post__created_by=user,
        ).select_related(
            "demand_post", "supply_lot", "supply_lot__created_by", "thread",
        ).order_by("-created_at")
        grouped = defaultdict(list)
        for m in matches:
            grouped[m.demand_post].append(m)
        context["grouped_matches"] = dict(grouped)
        context["match_count"] = matches.count()
    else:
        lots = SupplyLot.objects.filter(
            created_by=user,
        ).annotate(match_count=active_match_filter).order_by("-created_at")[:5]
        lot_numbers = _build_lot_number_map(user)
        for lot in lots:
            lot.lot_number = lot_numbers.get(lot.pk, 1)
        context["supply_lots"] = lots
        matches = _active_matches().filter(
            supply_lot__created_by=user,
        ).select_related(
            "demand_post", "demand_post__created_by", "supply_lot", "thread",
        ).order_by("-created_at")
        grouped = defaultdict(list)
        for m in matches:
            grouped[m.supply_lot].append(m)
        context["grouped_matches"] = dict(grouped)
        context["match_count"] = matches.count()
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
    active_match_count = Count(
        "matches",
        filter=Q(
            matches__supply_lot__status=SupplyStatus.ACTIVE,
            matches__demand_post__status=DemandStatus.ACTIVE,
        ),
    )
    qs = DemandPost.objects.filter(created_by=request.user).annotate(
        match_count=active_match_count,
    ).order_by("-created_at")
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
            evaluate_demand_post(post)
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
            evaluate_demand_post(post)
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
    post = get_object_or_404(DemandPost, pk=pk, created_by=request.user)
    post.post_number = _get_post_number(post)
    matches = _active_matches().filter(
        demand_post=post,
    ).select_related(
        "supply_lot", "supply_lot__created_by", "thread",
    ).order_by("-created_at")
    post.match_count = matches.count()
    return render(request, "marketplace/demand_post_detail.html", {
        "post": post,
        "matches": matches,
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
    if post.status == "active":
        evaluate_demand_post(post)
    return redirect("marketplace:demand_post_detail", pk=post.pk)


# ---------------------------------------------------------------------------
# SupplyLot (supplier)
# ---------------------------------------------------------------------------

@login_required
def supply_lot_list(request):
    if request.user.role != Role.SUPPLIER:
        raise PermissionDenied
    active_match_count = Count(
        "matches",
        filter=Q(
            matches__supply_lot__status=SupplyStatus.ACTIVE,
            matches__demand_post__status=DemandStatus.ACTIVE,
        ),
    )
    qs = SupplyLot.objects.filter(created_by=request.user).annotate(
        match_count=active_match_count,
    ).order_by("-created_at")
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
            evaluate_supply_lot(lot)
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
            evaluate_supply_lot(lot)
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
    lot = get_object_or_404(SupplyLot, pk=pk, created_by=request.user)
    lot.lot_number = _get_lot_number(lot)
    matches = _active_matches().filter(
        supply_lot=lot,
    ).select_related(
        "demand_post", "demand_post__created_by", "thread",
    ).order_by("-created_at")
    lot.match_count = matches.count()
    return render(request, "marketplace/supply_lot_detail.html", {
        "lot": lot,
        "matches": matches,
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
    if lot.status == "active":
        evaluate_supply_lot(lot)
    return redirect("marketplace:supply_lot_detail", pk=lot.pk)


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------

@login_required
def match_list(request):
    user = request.user
    if user.role == Role.BUYER:
        qs = _active_matches().filter(
            demand_post__created_by=user,
        ).select_related(
            "demand_post", "supply_lot", "supply_lot__created_by", "thread",
        )
    else:
        qs = _active_matches().filter(
            supply_lot__created_by=user,
        ).select_related(
            "demand_post", "demand_post__created_by", "supply_lot", "thread",
        )
    matches = qs.order_by("-created_at")
    grouped = defaultdict(list)
    if user.role == Role.BUYER:
        for m in matches:
            grouped[m.demand_post].append(m)
    else:
        for m in matches:
            grouped[m.supply_lot].append(m)
    return render(request, "marketplace/match_list.html", {
        "grouped_matches": dict(grouped),
    })


# ---------------------------------------------------------------------------
# Messaging
# ---------------------------------------------------------------------------

@login_required
@ratelimit(key="user", rate="30/10m", method="POST", block=True)
def thread_detail(request, pk):
    thread = get_object_or_404(
        MessageThread.objects.select_related(
            "match",
            "match__supply_lot",
            "match__supply_lot__created_by",
            "match__demand_post",
            "match__demand_post__created_by",
            "buyer",
            "supplier",
        ),
        pk=pk,
    )
    if request.user not in (thread.buyer, thread.supplier):
        raise PermissionDenied
    if request.method == "POST":
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
    })
