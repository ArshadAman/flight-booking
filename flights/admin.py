from django.contrib import admin

from .models import FlightInventory


@admin.register(FlightInventory)
class FlightInventoryAdmin(admin.ModelAdmin):
    list_display = (
        "origin",
        "destination",
        "airline_code",
        "flight_number",
        "departure_datetime",
        "seats_available",
        "price",
        "created_by",
    )
    search_fields = ("origin", "destination", "airline_code", "flight_number", "airline_name")
    list_filter = ("is_refundable", "cabin_class")
