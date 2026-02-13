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
    # SupplyLot (supplier)
    path("supply/", views.supply_lot_list, name="supply_lot_list"),
    path("supply/new/", views.supply_lot_create, name="supply_lot_create"),
    path("supply/<int:pk>/", views.supply_lot_detail, name="supply_lot_detail"),
    path("supply/<int:pk>/edit/", views.supply_lot_edit, name="supply_lot_edit"),
    path("supply/<int:pk>/toggle/", views.supply_lot_toggle, name="supply_lot_toggle"),
    # Matches
    path("matches/", views.match_list, name="match_list"),
    # Messaging
    path("threads/<int:pk>/", views.thread_detail, name="thread_detail"),
]
