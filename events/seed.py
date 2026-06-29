from django.contrib.auth import get_user_model

from .models import Category, DecorationItem, Review

CATEGORIES = [
    ("Birthday Celebrations", "birthday", "Joyful themes designed around their favorite things.", "🎈", "#e58b9d"),
    ("Wedding & Engagement", "wedding", "Elegant stages and entrances for once-in-a-lifetime vows.", "💍", "#c79b61"),
    ("Baby Celebrations", "baby", "Soft, playful worlds for showers and welcome-home moments.", "☁", "#75a9a6"),
    ("Corporate Events", "corporate", "Polished launches, openings, and branded experiences.", "✦", "#7c86bd"),
    ("Surprise & Proposal", "proposal", "Thoughtful romantic settings with a cinematic reveal.", "♡", "#c96f64"),
    ("Grand Entries", "entries", "Fog, flowers, cold fire, and choreography for impact.", "⚡", "#a483c0"),
]

ITEMS = [
    ("birthday", "Pastel Dream Birthday", "pastel-dream-birthday", "A layered pastel balloon wall, personalized neon, plinths and floral accents.", 18500, 14900, "Pastel,Pink,Lilac,Blue", "Princess,Minimal,Rainbow", True, 98),
    ("birthday", "Wild One Safari", "wild-one-safari", "Organic balloon styling, illustrated jungle panels, props and cake presentation.", 24000, 20900, "Sage,Gold,Brown,Cream", "Safari,Kids,Nature", True, 91),
    ("wedding", "Ivory Vow Stage", "ivory-vow-stage", "An architectural ivory stage with warm lamps, layered florals and premium seating.", 78000, 69900, "Ivory,Gold,Blush", "Royal,Floral,Minimal", True, 96),
    ("wedding", "Saffron Ring Ceremony", "saffron-ring-ceremony", "Contemporary marigold geometry, brass accents and ambient candle styling.", 56000, 49900, "Saffron,Yellow,White", "Traditional,Floral,Modern", True, 88),
    ("baby", "Little Cloud Welcome", "little-cloud-welcome", "Cloud forms, soft blue balloons, warm lighting and a customized baby name sign.", 22000, 18500, "Blue,White,Silver", "Cloud,Teddy,Minimal", True, 93),
    ("baby", "Teddy Garden Shower", "teddy-garden-shower", "An intimate garden-inspired baby shower with teddy props and muted florals.", 29000, 24900, "Beige,Sage,White", "Teddy,Garden,Boho", False, 82),
    ("corporate", "Signature Brand Launch", "signature-brand-launch", "Modular branded stage, media wall, intelligent lighting and welcome zone.", 95000, 87500, "Custom,Black,White", "Launch,Premium,Branded", True, 90),
    ("corporate", "Opening Day Essentials", "opening-day-essentials", "Ribbon ceremony entrance, branded balloon columns and photo moment.", 32000, 28500, "Custom,Gold,White", "Opening,Branded,Classic", False, 75),
    ("proposal", "Birthday", "moonlit-marry-me", "Private candle aisle, illuminated letters, florals and a sparkling reveal moment.", 38000, 32900, "Red,White,Gold", "Romantic,Candlelight,Premium", True, 99),
    ("proposal", "Terrace Sunset Story", "terrace-sunset-story", "A terrace picnic, warm festoons, photo timeline and intimate floral styling.", 27000, 23900, "Peach,White,Amber", "Sunset,Boho,Intimate", False, 86),
    ("entries", "Royal Fog Entry", "royal-fog-entry", "Low fog aisle, four cold pyro moments and coordinated spotlight cues.", 18000, 15900, "White,Gold", "Royal,Cinematic,Wedding", True, 95),
    ("entries", "Flower Shower Walk", "flower-shower-walk", "A graceful floral shower entry with coordinated attendants and aisle styling.", 14500, 12500, "Pink,White,Red", "Floral,Traditional,Romantic", False, 84),
]

SAMPLE_MEDIA = {
    "birthday": "/static/media/photos/birthday-balloons.jpg",
    "wedding": "/static/media/photos/wedding-stage.jpg",
    "baby": "/static/media/photos/birthday-balloons.jpg",
    "corporate": "/static/media/photos/luxury-reception.jpg",
    "proposal": "/static/media/photos/birthday.jpg",
    "entries": "/static/media/photos/wedding-stage.jpg",
}

REVIEWS = [
    ("Riya & Aakash", "Engagement", 5, "They understood the mood instantly. Every corner felt intentional, and the quotation stayed completely transparent."),
    ("Meera Patel", "First Birthday", 5, "Beautiful execution, calm team, zero last-minute chaos. The pastel setup looked even better in person."),
    ("Arjun Mehta", "Brand Launch", 5, "Professional from site visit through teardown. Their timing and attention to brand details were excellent."),
]


def seed_database(**kwargs):
    if Category.objects.exists():
        return

    User = get_user_model()
    if not User.objects.filter(username="admin@omevents.in").exists():
        User.objects.create_superuser(
            username="admin@omevents.in", email="admin@omevents.in",
            password="ChangeMe123!", first_name="Platform", last_name="Admin",
        )

    category_map = {}
    for name, slug, description, icon, color in CATEGORIES:
        category_map[slug] = Category.objects.create(
            name=name, slug=slug, description=description, icon=icon, color=color,
        )
    for category_slug, name, slug, description, price, offer, colors, themes, featured, popularity in ITEMS:
        DecorationItem.objects.create(
            category=category_map[category_slug], name=name, slug=slug, description=description,
            price=price, offer_price=offer, colors=colors, themes=themes,
            tags=f"{category_slug},premium,customizable", is_featured=featured,
            popularity=popularity, rating=4.8, review_count=12 + popularity % 17,
            image_url=SAMPLE_MEDIA[category_slug],
            video_url="/static/media/videos/wedding-showcase.mp4",
        )
    Review.objects.bulk_create([
        Review(customer_name=name, event_name=event, rating=rating, comment=comment, is_verified=True, is_published=True)
        for name, event, rating, comment in REVIEWS
    ])
