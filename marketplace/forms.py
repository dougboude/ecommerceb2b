from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _

from .models import (
    Cadence,
    Category,
    DemandPost,
    Organization,
    Role,
    SupplyLot,
    User,
)


class SignupForm(UserCreationForm):
    role = forms.ChoiceField(choices=Role.choices, label=_("I am a"))
    country = forms.CharField(max_length=2, label=_("Country code"))
    # Buyer-only fields (shown/hidden via JS or validated server-side)
    org_name = forms.CharField(
        max_length=255, required=False, label=_("Organization name"),
    )
    org_type = forms.CharField(
        max_length=100, required=False, label=_("Organization type"),
    )

    class Meta:
        model = User
        fields = ("email", "password1", "password2", "role", "country")

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
    class Meta:
        model = DemandPost
        fields = [
            "item_text",
            "category",
            "quantity_value",
            "quantity_unit",
            "cadence",
            "location_country",
            "location_locality",
            "location_region",
            "location_postal_code",
            "radius_km",
            "shipping_allowed",
            "notes",
        ]


class SupplyLotForm(forms.ModelForm):
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
            "shipping_options",
            "asking_price",
            "price_unit",
            "notes",
        ]
        widgets = {
            "available_until": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class MessageForm(forms.Form):
    body = forms.CharField(widget=forms.Textarea, label=_("Message"))
