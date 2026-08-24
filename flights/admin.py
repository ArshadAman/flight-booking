from django.contrib import admin
from .models import FlightInventory, InventoryHold


@admin.register(FlightInventory)
class FlightInventoryAdmin(admin.ModelAdmin):
    list_display = (
        "origin",
        "destination",
        "airline_code",
        "flight_number",
        "departure_datetime",
        "seats_available",
        "seats_held",
        "waitlist_count",
        "price",
        "is_published",
        "is_enabled",
        "created_by",
    )
    list_editable = ("is_published", "is_enabled")
    search_fields = ("origin", "destination", "airline_code", "flight_number", "airline_name")
    list_filter = ("is_refundable", "cabin_class", "is_published", "is_enabled")


@admin.register(InventoryHold)
class InventoryHoldAdmin(admin.ModelAdmin):
    list_display = ("status", "inventory", "seats", "contact_email", "expires_at", "created_at")
    list_filter = ("status",)
    search_fields = ("contact_email", "contact_mobile", "contact_name")
