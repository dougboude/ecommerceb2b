from django.urls import path

from . import views

app_name = "marketplace"

urlpatterns = [
    # Auth
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.MarketplaceLoginView.as_view(), name="login"),
    path("logout/", views.MarketplaceLogoutView.as_view(), name="logout"),
    # Dashboard
    path("", views.dashboard_view, name="dashboard"),
    # Profile
    path("profile/", views.profile_view, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    # DemandPost (buyer)
    path("demands/", views.demand_post_list, name="demand_post_list"),
    path("demands/new/", views.demand_post_create, name="demand_post_create"),
    path("demands/<int:pk>/", views.demand_post_detail, name="demand_post_detail"),
    path("demands/<int:pk>/edit/", views.demand_post_edit, name="demand_post_edit"),
    path("demands/<int:pk>/toggle/", views.demand_post_toggle, name="demand_post_toggle"),
    path("demands/<int:pk>/delete/", views.demand_post_delete, name="demand_post_delete"),
    # SupplyLot (supplier)
    path("supply/", views.supply_lot_list, name="supply_lot_list"),
    path("supply/new/", views.supply_lot_create, name="supply_lot_create"),
    path("supply/<int:pk>/", views.supply_lot_detail, name="supply_lot_detail"),
    path("supply/<int:pk>/edit/", views.supply_lot_edit, name="supply_lot_edit"),
    path("supply/<int:pk>/toggle/", views.supply_lot_toggle, name="supply_lot_toggle"),
    path("supply/<int:pk>/delete/", views.supply_lot_delete, name="supply_lot_delete"),
    # Discover
    path("discover/", views.discover_view, name="discover"),
    path("discover/clear/", views.discover_clear, name="discover_clear"),
    path("discover/save/", views.discover_save, name="discover_save"),
    path("discover/unsave/", views.discover_unsave, name="discover_unsave"),
    path("discover/message/", views.discover_message, name="discover_message"),
    # Watchlist
    path("watchlist/", views.watchlist_view, name="watchlist"),
    path("watchlist/<int:pk>/star/", views.watchlist_star, name="watchlist_star"),
    path("watchlist/<int:pk>/archive/", views.watchlist_archive, name="watchlist_archive"),
    path("watchlist/<int:pk>/unarchive/", views.watchlist_unarchive, name="watchlist_unarchive"),
    path("watchlist/<int:pk>/delete/", views.watchlist_delete, name="watchlist_delete"),
    path("watchlist/<int:pk>/message/", views.watchlist_message, name="watchlist_message"),
    # Suggestions
    path("suggestions/save/", views.suggestion_save, name="suggestion_save"),
    path("suggestions/dismiss/", views.suggestion_dismiss, name="suggestion_dismiss"),
    # Messaging
    path("threads/<int:pk>/", views.thread_detail, name="thread_detail"),
]
