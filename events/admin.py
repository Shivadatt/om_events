from django.contrib import admin

from .models import ActivityLog, Booking, Category, Customer, DecorationItem, ItemImage, Lead, Quotation, QuotationItem, Review


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "sort_order", "updated_at")
    list_editable = ("is_active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "description")


class ItemImageInline(admin.TabularInline):
    model = ItemImage
    extra = 0


@admin.register(DecorationItem)
class DecorationItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "offer_price", "rating", "is_featured", "is_active")
    list_filter = ("category", "is_featured", "is_active", "availability")
    list_editable = ("is_featured", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "description", "tags", "themes")
    inlines = (ItemImageInline,)


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "request_type", "event_date", "budget", "status", "created_at")
    list_filter = ("status", "request_type", "event_date")
    list_editable = ("status",)
    search_fields = ("name", "phone", "email", "requirements")
    date_hierarchy = "created_at"


class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 0
    readonly_fields = ("decoration_item", "name", "quantity", "unit_price", "color", "theme", "notes")


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ("public_id", "customer", "event_date", "grand_total", "status", "created_at")
    list_filter = ("status", "event_date")
    search_fields = ("public_id", "customer__name", "customer__phone", "location")
    readonly_fields = ("public_id", "subtotal", "discount", "delivery_charge", "travel_charge", "gst_amount", "grand_total")
    inlines = (QuotationItemInline,)
    date_hierarchy = "created_at"


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "city", "created_at")
    search_fields = ("name", "phone", "email")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("customer_name", "event_name", "rating", "is_verified", "is_published", "created_at")
    list_filter = ("rating", "is_verified", "is_published")
    list_editable = ("is_verified", "is_published")


admin.site.register(Booking)
admin.site.register(ActivityLog)
admin.site.site_header = "Om Events Management"
admin.site.site_title = "Om Events"
admin.site.index_title = "Celebration operations"

