import secrets

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def generate_public_id():
    return secrets.token_urlsafe(10)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, db_index=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=20, default="✦")
    color = models.CharField(max_length=20, default="#c79b61")
    image_url = models.URLField(max_length=500, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sort_order", "name")
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    def to_dict(self):
        return {
            "id": self.pk, "name": self.name, "slug": self.slug, "description": self.description,
            "icon": self.icon, "color": self.color, "image_url": self.image_url,
            "item_count": self.items.filter(is_active=True).count(),
        }


class DecorationItem(TimeStampedModel):
    category = models.ForeignKey(Category, related_name="items", on_delete=models.PROTECT)
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True, db_index=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    offer_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    duration_hours = models.DecimalField(max_digits=5, decimal_places=1, default=3)
    popularity = models.PositiveIntegerField(default=0, db_index=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5)
    review_count = models.PositiveIntegerField(default=0)
    availability = models.CharField(max_length=30, default="available")
    tags = models.CharField(max_length=500, blank=True)
    colors = models.CharField(max_length=500, blank=True)
    themes = models.CharField(max_length=500, blank=True)
    image_url = models.CharField(max_length=500, blank=True)
    video_url = models.CharField(max_length=500, blank=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-popularity",)
        indexes = [models.Index(fields=("category", "is_active")), models.Index(fields=("is_featured", "-popularity"))]

    def __str__(self):
        return self.name

    @property
    def effective_price(self):
        return self.offer_price if self.offer_price is not None else self.price

    def to_dict(self):
        return {
            "id": self.pk, "name": self.name, "slug": self.slug, "description": self.description,
            "category": self.category.name, "category_slug": self.category.slug,
            "price": float(self.price), "offer_price": float(self.offer_price) if self.offer_price is not None else None,
            "effective_price": float(self.effective_price), "duration_hours": float(self.duration_hours),
            "popularity": self.popularity, "rating": float(self.rating), "review_count": self.review_count,
            "availability": self.availability, "tags": [x.strip() for x in self.tags.split(",") if x.strip()],
            "colors": [x.strip() for x in self.colors.split(",") if x.strip()],
            "themes": [x.strip() for x in self.themes.split(",") if x.strip()],
            "image_url": self.image_url, "video_url": self.video_url, "is_featured": self.is_featured,
        }


class ItemImage(models.Model):
    item = models.ForeignKey(DecorationItem, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="items/%Y/%m/")
    alt_text = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "pk")


class Customer(TimeStampedModel):
    name = models.CharField(max_length=160)
    phone = models.CharField(max_length=20, db_index=True)
    email = models.EmailField(blank=True)
    city = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.name} · {self.phone}"


class Lead(TimeStampedModel):
    REQUEST_TYPES = [("callback", "Callback"), ("discount", "Discount"), ("package", "Custom package"),
                     ("meeting", "Meeting"), ("site_visit", "Site visit")]
    STATUSES = [("new", "New"), ("contacted", "Contacted"), ("qualified", "Qualified"), ("won", "Won"), ("closed", "Closed")]
    name = models.CharField(max_length=160)
    phone = models.CharField(max_length=20, db_index=True)
    email = models.EmailField(blank=True)
    request_type = models.CharField(max_length=50, choices=REQUEST_TYPES, default="callback")
    event_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    requirements = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=STATUSES, default="new", db_index=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.name} · {self.get_request_type_display()}"

    def to_dict(self):
        return {
            "id": self.pk, "name": self.name, "phone": self.phone, "email": self.email,
            "request_type": self.get_request_type_display(), "event_date": self.event_date.isoformat() if self.event_date else None,
            "budget": float(self.budget or 0), "requirements": self.requirements, "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


class Quotation(TimeStampedModel):
    public_id = models.CharField(max_length=32, unique=True, db_index=True, default=generate_public_id)
    customer = models.ForeignKey(Customer, related_name="quotations", on_delete=models.PROTECT)
    event_date = models.DateField()
    event_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=500)
    notes = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    delivery_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    travel_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gst_percent = models.DecimalField(max_digits=5, decimal_places=2, default=18)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=30, default="draft", db_index=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.public_id.upper()} · {self.customer.name}"

    def to_dict(self):
        return {
            "id": self.pk, "public_id": self.public_id, "customer": self.customer.name, "phone": self.customer.phone,
            "event_date": self.event_date.isoformat(), "location": self.location, "subtotal": float(self.subtotal),
            "discount": float(self.discount), "gst_amount": float(self.gst_amount), "grand_total": float(self.grand_total),
            "status": self.status, "created_at": self.created_at.isoformat(),
        }


class QuotationItem(models.Model):
    quotation = models.ForeignKey(Quotation, related_name="items", on_delete=models.CASCADE)
    decoration_item = models.ForeignKey(DecorationItem, on_delete=models.PROTECT)
    name = models.CharField(max_length=180)
    quantity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(50)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    color = models.CharField(max_length=80, blank=True)
    theme = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)


class Booking(TimeStampedModel):
    quotation = models.OneToOneField(Quotation, related_name="booking", on_delete=models.PROTECT)
    booking_number = models.CharField(max_length=30, unique=True, db_index=True)
    advance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=30, default="pending")
    status = models.CharField(max_length=30, default="pending")


class Review(TimeStampedModel):
    customer_name = models.CharField(max_length=160)
    event_name = models.CharField(max_length=160)
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField()
    image_url = models.CharField(max_length=500, blank=True)
    is_verified = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ("-created_at",)

    def to_dict(self):
        return {
            "customer_name": self.customer_name, "event_name": self.event_name, "rating": self.rating,
            "comment": self.comment, "image_url": self.image_url, "is_verified": self.is_verified,
        }


class ActivityLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=120)
    entity_type = models.CharField(max_length=80, blank=True)
    entity_id = models.CharField(max_length=80, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
