from datetime import datetime, time

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .constants import COUNTRY_CHOICES, KM_PER_MILE, TIMEZONE_CHOICES
from .models import (
    Category,
    Frequency,
    Listing,
    ListingShippingScope,
    ListingStatus,
    ListingType,
    User,
)
from .migration_control.config import get_runtime_mode
from .skin_config import DEFAULT_SKIN_SLUG


class SignupForm(UserCreationForm):
    country = forms.ChoiceField(choices=COUNTRY_CHOICES, label=_("Country"))
    organization_name = forms.CharField(
        max_length=255, required=False, label=_("Organization name"),
    )
    class Meta:
        model = User
        fields = (
            "email",
            "display_name",
            "password1",
            "password2",
            "country",
            "organization_name",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.runtime_mode = get_runtime_mode()

    def clean(self):
        cleaned = super().clean()
        org_name = (cleaned.get("organization_name") or "").strip()
        cleaned["organization_name"] = org_name or None

        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.country = self.cleaned_data["country"]
        user.organization_name = self.cleaned_data.get("organization_name")
        if not user.skin:
            user.skin = DEFAULT_SKIN_SLUG
        if commit:
            user.save()
        return user


class DemandPostForm(forms.ModelForm):
    location_country = forms.ChoiceField(
        choices=COUNTRY_CHOICES, label=_("Country"),
    )

    class Meta:
        model = Listing
        fields = [
            "title",
            "category",
            "quantity",
            "unit",
            "frequency",
            "location_country",
            "location_locality",
            "location_region",
            "location_postal_code",
            "radius_km",
            "description",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.use_miles = user is not None and getattr(user, "distance_unit", "mi") == "mi"
        self.fields["title"].label = _("Item description")
        self.fields["description"].label = _("Notes")
        self.fields["description"].required = False

        # Quantity label for buyers
        self.fields["quantity"].label = _("Minimum quantity")
        self.fields["quantity"].help_text = _(
            "The minimum amount you want to purchase."
        )

        # Radius unit based on user preference
        if self.use_miles:
            self.fields["radius_km"].label = _("Search radius (miles)")
            if self.instance and self.instance.pk and self.instance.radius_km:
                self.initial["radius_km"] = round(
                    self.instance.radius_km / KM_PER_MILE
                )
        else:
            self.fields["radius_km"].label = _("Search radius (km)")
        self.fields["radius_km"].help_text = _("Leave blank for worldwide")
        self.fields["unit"].label = _("Unit")

    def clean_radius_km(self):
        value = self.cleaned_data.get("radius_km")
        if value is not None and self.use_miles:
            value = round(value * KM_PER_MILE)
        return value

    def save(self, commit=True):
        listing = super().save(commit=False)
        listing.type = ListingType.DEMAND
        listing.status = listing.status or ListingStatus.ACTIVE
        listing.shipping_scope = ""
        listing.price_unit = ""
        if commit:
            listing.save()
        return listing


class SupplyLotForm(forms.ModelForm):
    location_country = forms.ChoiceField(
        choices=COUNTRY_CHOICES, label=_("Country"),
    )
    available_until = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label=_("Available until"),
    )

    class Meta:
        model = Listing
        fields = [
            "title",
            "category",
            "quantity",
            "unit",
            "expires_at",
            "location_country",
            "location_locality",
            "location_region",
            "location_postal_code",
            "shipping_scope",
            "price_value",
            "price_unit",
            "description",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].label = _("Item description")
        self.fields["expires_at"].label = _("Available until")
        self.fields["expires_at"].widget = forms.DateInput(attrs={"type": "date"})
        self.fields["price_value"].label = _("Asking price")
        self.fields["description"].label = _("Notes")
        self.fields["description"].required = False
        # Keep supply scopes aligned to unified listing enum values.
        self.fields["shipping_scope"].choices = ListingShippingScope.choices
        if self.instance and self.instance.pk and self.instance.expires_at:
            self.initial["expires_at"] = self.instance.expires_at.date()

    def clean_expires_at(self):
        date_val = self.cleaned_data["expires_at"]
        return timezone.make_aware(datetime.combine(date_val, time(23, 59, 59)))

    def save(self, commit=True):
        listing = super().save(commit=False)
        listing.type = ListingType.SUPPLY
        listing.status = listing.status or ListingStatus.ACTIVE
        listing.radius_km = None
        listing.frequency = ""
        if commit:
            listing.save()
        return listing


class DiscoverForm(forms.Form):
    DIRECTION_FIND_SUPPLY = "find_supply"
    DIRECTION_FIND_DEMAND = "find_demand"
    SEARCH_MODE_SIMILAR = "similar"
    SEARCH_MODE_KEYWORD = "keyword"
    SORT_BEST_MATCH = "best_match"
    SORT_NEWEST = "newest"
    SORT_ENDING_SOON = "ending_soon"
    SEARCH_MODE_CHOICES = [
        (SEARCH_MODE_SIMILAR, _("Similar meaning")),
        (SEARCH_MODE_KEYWORD, _("Contains these words")),
    ]
    SORT_CHOICES = [
        (SORT_BEST_MATCH, _("Best match")),
        (SORT_NEWEST, _("Newest posted")),
        (SORT_ENDING_SOON, _("Ending soon")),
    ]
    DIRECTION_CHOICES = [
        (DIRECTION_FIND_SUPPLY, _("Find Supply")),
        (DIRECTION_FIND_DEMAND, _("Find Demand")),
    ]

    direction = forms.ChoiceField(
        choices=DIRECTION_CHOICES,
        initial=DIRECTION_FIND_SUPPLY,
        label=_("Direction"),
    )
    query = forms.CharField(
        max_length=200, label=_("Search"),
        widget=forms.TextInput(attrs={"placeholder": _("What are you looking for?")}),
    )
    search_mode = forms.ChoiceField(
        choices=SEARCH_MODE_CHOICES,
        initial=SEARCH_MODE_SIMILAR,
        widget=forms.RadioSelect,
        label=_("Search mode"),
    )
    sort_by = forms.ChoiceField(
        choices=SORT_CHOICES,
        initial=SORT_BEST_MATCH,
        label=_("Sort by"),
    )
    category = forms.ChoiceField(
        choices=[("", _("All categories"))] + list(Category.choices),
        required=False, label=_("Category"),
    )
    location_country = forms.ChoiceField(
        choices=[("", _("Any country"))] + list(COUNTRY_CHOICES),
        required=False, label=_("Country"),
    )
    radius = forms.ChoiceField(
        choices=[
            ("", _("Any distance")),
            ("25", "25"),
            ("50", "50"),
            ("100", "100"),
        ],
        required=False, label=_("Radius"),
    )
    exclude_watched = forms.BooleanField(
        required=False, initial=False,
        label=_("Hide listings I'm watching"),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and not self.is_bound:
            self.fields["location_country"].initial = user.country


class MessageForm(forms.Form):
    body = forms.CharField(widget=forms.Textarea, label=_("Message"))


class ProfileForm(forms.ModelForm):
    timezone = forms.ChoiceField(choices=TIMEZONE_CHOICES, label=_("Timezone"))

    class Meta:
        model = User
        fields = [
            "display_name",
            "organization_name",
            "first_name",
            "last_name",
            "timezone",
            "distance_unit",
            "skin",
            "email_on_message",
        ]

    def clean_organization_name(self):
        value = (self.cleaned_data.get("organization_name") or "").strip()
        return value or None
