from datetime import datetime, time

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .constants import COUNTRY_CHOICES, KM_PER_MILE, TIMEZONE_CHOICES
from .models import (
    Category,
    DemandPost,
    Frequency,
    Organization,
    Role,
    SupplyLot,
    User,
)


class SignupForm(UserCreationForm):
    role = forms.ChoiceField(choices=Role.choices, label=_("I am a"))
    country = forms.ChoiceField(choices=COUNTRY_CHOICES, label=_("Country"))
    # Buyer-only fields (shown/hidden via JS or validated server-side)
    org_name = forms.CharField(
        max_length=255, required=False, label=_("Organization name"),
    )
    org_type = forms.CharField(
        max_length=100, required=False, label=_("Organization type"),
    )

    class Meta:
        model = User
        fields = ("email", "display_name", "password1", "password2", "role", "country")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("role") == Role.BUYER:
            if not cleaned.get("org_name"):
                self.add_error("org_name", _("Organization name is required for buyers."))
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data["role"]
        user.country = self.cleaned_data["country"]
        if commit:
            user.save()
            if user.role == Role.BUYER:
                Organization.objects.create(
                    name=self.cleaned_data["org_name"],
                    type=self.cleaned_data.get("org_type", ""),
                    country=user.country,
                    owner=user,
                )
        return user


class DemandPostForm(forms.ModelForm):
    location_country = forms.ChoiceField(
        choices=COUNTRY_CHOICES, label=_("Country"),
    )

    class Meta:
        model = DemandPost
        fields = [
            "item_text",
            "category",
            "quantity_value",
            "quantity_unit",
            "frequency",
            "location_country",
            "location_locality",
            "location_region",
            "location_postal_code",
            "radius_km",
            "shipping_allowed",
            "notes",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.use_miles = user is not None and getattr(user, "distance_unit", "mi") == "mi"

        # Quantity label for buyers
        self.fields["quantity_value"].label = _("Minimum quantity")
        self.fields["quantity_value"].help_text = _(
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

        # Shipping allowed clarity
        self.fields["shipping_allowed"].label = _("Include shipped items")
        self.fields["shipping_allowed"].help_text = _(
            "Allow matches from suppliers who can ship to your area, "
            "even if they're outside your search radius."
        )

    def clean_radius_km(self):
        value = self.cleaned_data.get("radius_km")
        if value is not None and self.use_miles:
            value = round(value * KM_PER_MILE)
        return value


class SupplyLotForm(forms.ModelForm):
    location_country = forms.ChoiceField(
        choices=COUNTRY_CHOICES, label=_("Country"),
    )
    available_until = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label=_("Available until"),
    )

    class Meta:
        model = SupplyLot
        fields = [
            "item_text",
            "category",
            "quantity_value",
            "quantity_unit",
            "available_until",
            "location_country",
            "location_locality",
            "location_region",
            "location_postal_code",
            "shipping_scope",
            "asking_price",
            "price_unit",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.available_until:
            self.initial["available_until"] = self.instance.available_until.date()

    def clean_available_until(self):
        date_val = self.cleaned_data["available_until"]
        return timezone.make_aware(datetime.combine(date_val, time(23, 59, 59)))


class DiscoverForm(forms.Form):
    SEARCH_MODE_SIMILAR = "similar"
    SEARCH_MODE_KEYWORD = "keyword"
    SEARCH_MODE_CHOICES = [
        (SEARCH_MODE_SIMILAR, _("Similar meaning")),
        (SEARCH_MODE_KEYWORD, _("Contains these words")),
    ]

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
        fields = ["display_name", "first_name", "last_name", "timezone", "distance_unit", "skin"]
