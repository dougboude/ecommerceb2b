"""
manage.py seed_test_data

Wipes all application data and populates a rich, deterministic test dataset
covering every user state, listing state, messaging state, and UI surface.

Usage:
    .venv/bin/python manage.py seed_test_data            # flush + seed
    .venv/bin/python manage.py seed_test_data --no-flush # seed without wiping

Maintenance note:
    Update this command whenever a new model, status, or feature is added.
    The goal is that every new spec leaves a representative data row here.
"""

import io
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils.timezone import now as timezone_now

from marketplace.models import (
    Category,
    DismissedSuggestion,
    EmailVerificationToken,
    Frequency,
    Listing,
    ListingShippingScope,
    ListingStatus,
    ListingType,
    Message,
    MessageThread,
    ThreadReadState,
    WatchlistItem,
    WatchlistSource,
    WatchlistStatus,
)

User = get_user_model()

SEED_PASSWORD = "Seedpass1!"

# ---------------------------------------------------------------------------
# Persona definitions
# ---------------------------------------------------------------------------

PERSONAS = [
    {
        "handle": "alice",
        "email": "alice@seed.test",
        "display_name": "Alice Thornton",
        "organization_name": "Thornton Farms",
        "country": "US",
        "email_verified": True,
        "avatar_color": (72, 149, 239),    # blue
    },
    {
        "handle": "bob",
        "email": "bob@seed.test",
        "display_name": "Bob Mercado",
        "organization_name": "Mercado Provisions",
        "country": "US",
        "email_verified": True,
        "avatar_color": (56, 176, 0),      # green
    },
    {
        "handle": "carol",
        "email": "carol@seed.test",
        "display_name": "Carol Vance",
        "organization_name": None,
        "country": "CA",
        "email_verified": True,
        "avatar_color": None,              # no profile image
    },
    {
        "handle": "dave",
        "email": "dave@seed.test",
        "display_name": "Dave Okonkwo",
        "organization_name": "Okonkwo & Sons",
        "country": "GB",
        "email_verified": True,
        "avatar_color": (230, 126, 34),    # orange
    },
    {
        "handle": "eve",
        "email": "eve@seed.test",
        "display_name": "Eve Nakamura",
        "organization_name": None,
        "country": "JP",
        "email_verified": False,           # unverified — tests login blocking
        "avatar_color": None,
    },
]


class Command(BaseCommand):
    help = "Wipe data and seed a rich deterministic test dataset."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-flush",
            action="store_true",
            help="Skip flushing existing data before seeding.",
        )

    def handle(self, *args, **options):
        if not options["no_flush"]:
            self.stdout.write("Flushing database...")
            call_command("flush", "--no-input", verbosity=0)
            self.stdout.write(self.style.SUCCESS("  Database cleared.\n"))

        now = timezone_now()

        # ── 1. Users ─────────────────────────────────────────────────────────

        self.stdout.write("Creating users...")
        users = {}
        for p in PERSONAS:
            user = User.objects.create_user(
                email=p["email"],
                password=SEED_PASSWORD,
                display_name=p["display_name"],
                organization_name=p["organization_name"],
                country=p["country"],
                email_verified=p["email_verified"],
            )
            if p["avatar_color"]:
                _attach_avatar(user, p["avatar_color"])
            if not p["email_verified"]:
                # Create a pending (unused) verification token so the resend
                # flow has something to revoke.
                EmailVerificationToken.objects.create(user=user)
            users[p["handle"]] = user
            status = "verified" if p["email_verified"] else "UNVERIFIED"
            self.stdout.write(f"  {p['display_name']:20s}  {p['email']:28s}  [{status}]")

        alice = users["alice"]
        bob   = users["bob"]
        carol = users["carol"]
        dave  = users["dave"]

        # ── 2. Supply listings (Alice) ────────────────────────────────────────

        self.stdout.write("\nCreating supply listings...")

        # Active — multiple categories, used for discover + messaging tests
        supply_active_1 = _listing(
            ListingType.SUPPLY, alice,
            title="Heritage Tomatoes — Mixed Varieties",
            category=Category.FOOD_FRESH,
            status=ListingStatus.ACTIVE,
            quantity=500, unit="kg",
            price_value="2.40", price_unit="kg",
            shipping_scope=ListingShippingScope.DOMESTIC,
            location_country="US", location_locality="Sacramento", location_region="CA",
            description=(
                "Heirloom and hybrid tomato mix. Includes Brandywine, Cherokee Purple, "
                "and Sungold. Harvested weekly May–October."
            ),
            created_at=now - timedelta(days=30),
            expires_at=now + timedelta(days=60),
        )

        supply_active_2 = _listing(
            ListingType.SUPPLY, alice,
            title="Cold-Pressed Sunflower Oil",
            category=Category.FOOD_SHELF,
            status=ListingStatus.ACTIVE,
            quantity=200, unit="L",
            price_value="3.80", price_unit="L",
            shipping_scope=ListingShippingScope.NORTH_AMERICA,
            location_country="US", location_locality="Sacramento", location_region="CA",
            description="Single-origin, unrefined. 5L and 20L containers available.",
            created_at=now - timedelta(days=14),
        )

        supply_active_3 = _listing(
            ListingType.SUPPLY, alice,
            title="Dried Lavender Bundles",
            category=Category.BOTANICAL,
            status=ListingStatus.ACTIVE,
            quantity=1000, unit="units",
            price_value="1.20", price_unit="units",
            shipping_scope=ListingShippingScope.WORLDWIDE,
            location_country="US", location_locality="Sacramento", location_region="CA",
            description="Culinary and fragrance grade. Bundled in 50-stem lots.",
            created_at=now - timedelta(days=7),
        )

        # Paused — should not appear in discover results
        supply_paused = _listing(
            ListingType.SUPPLY, alice,
            title="Organic Wheat Flour (Paused)",
            category=Category.FOOD_SHELF,
            status=ListingStatus.PAUSED,
            quantity=2000, unit="kg",
            shipping_scope=ListingShippingScope.DOMESTIC,
            location_country="US", location_locality="Sacramento", location_region="CA",
            created_at=now - timedelta(days=45),
        )

        # Expired — expires_at in the past; lazy expiry display test
        supply_expired = _listing(
            ListingType.SUPPLY, alice,
            title="Seasonal Stone Fruit (Expired)",
            category=Category.FOOD_FRESH,
            status=ListingStatus.ACTIVE,    # status is "active" but expires_at is past
            quantity=300, unit="kg",
            shipping_scope=ListingShippingScope.LOCAL_ONLY,
            location_country="US", location_locality="Sacramento", location_region="CA",
            created_at=now - timedelta(days=90),
            expires_at=now - timedelta(days=10),
        )

        self.stdout.write(f"  Alice: 3 active, 1 paused, 1 expired")

        # ── 3. Supply listings (Dave) ─────────────────────────────────────────

        supply_fulfilled = _listing(
            ListingType.SUPPLY, dave,
            title="Artisan Cheese Wheels (Fulfilled)",
            category=Category.FOOD_SHELF,
            status=ListingStatus.FULFILLED,
            quantity=50, unit="units",
            shipping_scope=ListingShippingScope.DOMESTIC,
            location_country="GB", location_locality="Bristol",
            created_at=now - timedelta(days=60),
        )

        supply_withdrawn = _listing(
            ListingType.SUPPLY, dave,
            title="Raw Beeswax Blocks (Withdrawn)",
            category=Category.ANIMAL_PRODUCT,
            status=ListingStatus.WITHDRAWN,
            quantity=100, unit="kg",
            shipping_scope=ListingShippingScope.DOMESTIC,
            location_country="GB", location_locality="Bristol",
            created_at=now - timedelta(days=50),
        )

        supply_dave_active = _listing(
            ListingType.SUPPLY, dave,
            title="Cold Smoked Scottish Salmon",
            category=Category.FOOD_SHELF,
            status=ListingStatus.ACTIVE,
            quantity=80, unit="kg",
            price_value="22.00", price_unit="kg",
            shipping_scope=ListingShippingScope.WORLDWIDE,
            location_country="GB", location_locality="Bristol",
            description="Traditional oak-smoked Atlantic salmon. Vacuum-packed, 2-week shelf life.",
            created_at=now - timedelta(days=5),
        )

        self.stdout.write(f"  Dave:  1 active, 1 fulfilled, 1 withdrawn")

        # ── 4. Supply listing (Carol) ─────────────────────────────────────────

        supply_carol = _listing(
            ListingType.SUPPLY, carol,
            title="Wild Blueberries — Frozen IQF",
            category=Category.FOOD_FRESH,
            status=ListingStatus.ACTIVE,
            quantity=400, unit="kg",
            price_value="4.50", price_unit="kg",
            shipping_scope=ListingShippingScope.NORTH_AMERICA,
            location_country="CA", location_locality="Vancouver",
            created_at=now - timedelta(days=10),
        )

        self.stdout.write(f"  Carol: 1 active supply")

        # ── 5. Demand listings (Bob) ──────────────────────────────────────────

        self.stdout.write("\nCreating demand listings...")

        demand_active_1 = _listing(
            ListingType.DEMAND, bob,
            title="Looking for: Fresh Tomatoes (any variety)",
            category=Category.FOOD_FRESH,
            status=ListingStatus.ACTIVE,
            quantity=200, unit="kg",
            frequency=Frequency.RECURRING,
            location_country="US", location_locality="Portland", location_region="OR",
            description="Need reliable weekly supply for restaurant group. Prefer certified organic.",
            created_at=now - timedelta(days=20),
            expires_at=now + timedelta(days=90),
        )

        demand_active_2 = _listing(
            ListingType.DEMAND, bob,
            title="Bulk Cooking Oil — any cold-pressed",
            category=Category.FOOD_SHELF,
            status=ListingStatus.ACTIVE,
            quantity=100, unit="L",
            frequency=Frequency.RECURRING,
            location_country="US", location_locality="Portland", location_region="OR",
            created_at=now - timedelta(days=8),
        )

        demand_paused = _listing(
            ListingType.DEMAND, bob,
            title="Seasonal Berries (Paused)",
            category=Category.FOOD_FRESH,
            status=ListingStatus.PAUSED,
            quantity=50, unit="kg",
            frequency=Frequency.SEASONAL,
            location_country="US", location_locality="Portland", location_region="OR",
            created_at=now - timedelta(days=35),
        )

        demand_expired = _listing(
            ListingType.DEMAND, bob,
            title="Holiday Gift Baskets — Specialty Foods (Expired)",
            category=Category.FOOD_SHELF,
            status=ListingStatus.ACTIVE,
            quantity=30, unit="units",
            frequency=Frequency.ONE_TIME,
            location_country="US", location_locality="Portland", location_region="OR",
            created_at=now - timedelta(days=50),
            expires_at=now - timedelta(days=5),
        )

        self.stdout.write(f"  Bob:   2 active, 1 paused, 1 expired")

        # ── 6. Demand listing (Carol) ─────────────────────────────────────────

        demand_carol = _listing(
            ListingType.DEMAND, carol,
            title="Dried Herbs and Botanicals — wholesale",
            category=Category.BOTANICAL,
            status=ListingStatus.ACTIVE,
            quantity=20, unit="kg",
            frequency=Frequency.RECURRING,
            location_country="CA", location_locality="Vancouver",
            created_at=now - timedelta(days=3),
        )

        self.stdout.write(f"  Carol: 1 active demand")

        # ── 7. Watchlist items ────────────────────────────────────────────────

        self.stdout.write("\nCreating watchlist items...")

        # Bob watches Alice's tomato listing (active)
        WatchlistItem.objects.create(
            user=bob, listing=supply_active_1,
            status=WatchlistStatus.WATCHING, source=WatchlistSource.SEARCH,
        )

        # Bob watches Alice's lavender listing (active)
        WatchlistItem.objects.create(
            user=bob, listing=supply_active_3,
            status=WatchlistStatus.WATCHING, source=WatchlistSource.SUGGESTION,
        )

        # Carol watches Bob's tomato demand (archived — tests archive state)
        WatchlistItem.objects.create(
            user=carol, listing=demand_active_1,
            status=WatchlistStatus.ARCHIVED, source=WatchlistSource.SEARCH,
        )

        # Dave watches Carol's supply listing (active)
        WatchlistItem.objects.create(
            user=dave, listing=supply_carol,
            status=WatchlistStatus.WATCHING, source=WatchlistSource.DIRECT,
        )

        self.stdout.write("  Bob:   2 watching (Alice tomatoes, Alice lavender)")
        self.stdout.write("  Carol: 1 archived (Bob tomato demand)")
        self.stdout.write("  Dave:  1 watching (Carol blueberries)")

        # ── 8. Message threads ────────────────────────────────────────────────

        self.stdout.write("\nCreating message threads...")

        # Thread 1: Bob → Alice's tomato listing (multiple messages, unread by Alice)
        thread_bob_alice = MessageThread.objects.create(
            listing=supply_active_1, created_by_user=bob,
        )
        _message(thread_bob_alice, bob,
                 "Hi Alice — I saw your heritage tomato listing. "
                 "I run a restaurant group in Portland and I'm interested in a "
                 "recurring weekly order. Do you ship to Oregon?",
                 now - timedelta(hours=48))
        _message(thread_bob_alice, alice,
                 "Hi Bob! Yes, we do ship to Oregon — usually Tuesday and Friday runs. "
                 "What quantities are you looking for on a weekly basis?",
                 now - timedelta(hours=36))
        _message(thread_bob_alice, bob,
                 "We'd probably start with 80–100kg per week and scale from there. "
                 "Can you accommodate that? Also, are the Brandywines available year-round?",
                 now - timedelta(hours=2))
        # Alice has NOT read the last message — unread indicator should show
        ThreadReadState.objects.create(
            thread=thread_bob_alice, user=alice,
            last_read_at=now - timedelta(hours=37),
        )
        # Bob has read all messages
        ThreadReadState.objects.create(
            thread=thread_bob_alice, user=bob,
            last_read_at=now - timedelta(hours=1),
        )
        self.stdout.write("  Thread 1: Bob → Alice 'Heritage Tomatoes' (3 msgs, unread by Alice)")

        # Thread 2: Carol → Alice's lavender listing (single message, read by both)
        thread_carol_alice = MessageThread.objects.create(
            listing=supply_active_3, created_by_user=carol,
        )
        _message(thread_carol_alice, carol,
                 "Hello! I'm interested in your dried lavender. "
                 "Do you have culinary-grade available in 500-stem bulk lots? "
                 "I'm based in Vancouver — what would shipping look like?",
                 now - timedelta(days=3))
        _message(thread_carol_alice, alice,
                 "Hi Carol, yes! Culinary-grade is available. "
                 "For Vancouver I usually ship via FedEx International — "
                 "runs about $40 CAD flat for up to 2000 stems. Want me to put together a quote?",
                 now - timedelta(days=2, hours=18))
        ThreadReadState.objects.create(
            thread=thread_carol_alice, user=alice,
            last_read_at=now - timedelta(days=2, hours=17),
        )
        ThreadReadState.objects.create(
            thread=thread_carol_alice, user=carol,
            last_read_at=now - timedelta(days=2),
        )
        self.stdout.write("  Thread 2: Carol → Alice 'Lavender' (2 msgs, read by both)")

        # Thread 3: Bob → Dave's salmon listing (single unanswered message)
        thread_bob_dave = MessageThread.objects.create(
            listing=supply_dave_active, created_by_user=bob,
        )
        _message(thread_bob_dave, bob,
                 "Dave — your cold-smoked salmon looks incredible. "
                 "Any chance you'd ship to the US? I'm in Portland, OR.",
                 now - timedelta(hours=6))
        # Dave has not read or replied — unread for Dave
        self.stdout.write("  Thread 3: Bob → Dave 'Salmon' (1 msg, unread by Dave)")

        # ── 9. Dismissed suggestion ───────────────────────────────────────────

        self.stdout.write("\nCreating dismissed suggestion...")
        DismissedSuggestion.objects.create(user=bob, listing=supply_active_2)
        self.stdout.write("  Bob dismissed Alice's sunflower oil listing")

        # ── Summary ───────────────────────────────────────────────────────────

        self.stdout.write("\n" + "─" * 60)
        self.stdout.write(self.style.SUCCESS("Seed data installed successfully.\n"))
        self.stdout.write("Login credentials (password for all accounts):")
        self.stdout.write(f"  Password: {SEED_PASSWORD}\n")
        self.stdout.write("Accounts:")
        self.stdout.write("  alice@seed.test    — supplier, verified, has avatar")
        self.stdout.write("  bob@seed.test      — demand poster, verified, has avatar")
        self.stdout.write("  carol@seed.test    — both supply+demand, verified, NO avatar")
        self.stdout.write("  dave@seed.test     — supplier, verified, has avatar")
        self.stdout.write("  eve@seed.test      — verified=FALSE (tests login blocking)\n")
        self.stdout.write("Interesting states to explore:")
        self.stdout.write("  Expired listings   — Alice 'Stone Fruit', Bob 'Holiday Gift Baskets'")
        self.stdout.write("  Paused listings    — Alice 'Wheat Flour', Bob 'Seasonal Berries'")
        self.stdout.write("  Fulfilled/Withdrawn — Dave 'Cheese Wheels', Dave 'Beeswax'")
        self.stdout.write("  Unread message     — Alice inbox has 1 unread from Bob")
        self.stdout.write("  Unread message     — Dave inbox has 1 unread from Bob")
        self.stdout.write("  Archived watchlist — Carol's watchlist shows 1 archived item")
        self.stdout.write("  Dismissed suggestion — Bob dismissed Alice's sunflower oil\n")
        self.stdout.write(f"  Django admin       — create a superuser separately with:")
        self.stdout.write(f"    .venv/bin/python manage.py createsuperuser")
        self.stdout.write("─" * 60)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _listing(listing_type, user, *, created_at=None, **kwargs):
    """Create and save a Listing, bypassing auto_now_add on created_at."""
    now = timezone_now()
    listing = Listing(
        type=listing_type,
        created_by_user=user,
        created_at=created_at or now,
        **kwargs,
    )
    listing.save()
    return listing


def _message(thread, sender, body, created_at=None):
    """Create a Message with a controlled timestamp."""
    msg = Message(thread=thread, sender=sender, body=body)
    msg.save()
    if created_at:
        # Override auto_now_add after the fact
        Message.objects.filter(pk=msg.pk).update(created_at=created_at)
    return msg


def _attach_avatar(user, rgb_color):
    """
    Generate a simple solid-color circle PNG and attach it as the user's
    profile image. This gives every seeded user a distinct, visually
    identifiable avatar without requiring real photos.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return  # Pillow not available — skip silently

    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Filled circle
    draw.ellipse([0, 0, size - 1, size - 1], fill=(*rgb_color, 255))
    # Subtle inner highlight ring
    draw.ellipse([20, 20, size - 21, size - 21], outline=(255, 255, 255, 60), width=6)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    filename = f"profile_images/{user.pk}/seed_avatar.png"
    user.profile_image.save(filename, ContentFile(buf.read(), name=filename), save=False)
    user.profile_image_updated_at = timezone_now()
    user.save(update_fields=["profile_image", "profile_image_updated_at"])
