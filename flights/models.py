from django.conf import settings
from django.db import models
from core.models import BaseModel


class AgentFlightInventory(BaseModel):
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='flight_inventories',
        help_text="The agent who owns this pre-purchased flight inventory."
    )
    airline_code = models.CharField(max_length=10, help_text="e.g. '6E'")
    airline_name = models.CharField(max_length=100, blank=True, default="", help_text="e.g. 'IndiGo'")
    flight_number = models.CharField(max_length=20, help_text="e.g. '6E-2012'")
    origin = models.CharField(max_length=3, help_text="3-letter IATA code, e.g. 'DEL'")
    destination = models.CharField(max_length=3, help_text="3-letter IATA code, e.g. 'BOM'")

    departure_datetime = models.DateTimeField(help_text="Departure date and time.")
    arrival_datetime = models.DateTimeField(help_text="Arrival date and time.")

    price = models.DecimalField(max_digits=12, decimal_places=2, help_text="Ticket price.")
    seats_available = models.IntegerField(default=10, help_text="Number of available seats.")
    seats_held = models.IntegerField(
        default=0,
        help_text="Seats temporarily held (not yet confirmed).",
    )
    waitlist_count = models.IntegerField(
        default=0,
        help_text="Number of passengers currently waitlisted for this flight.",
    )
    cabin_class = models.CharField(max_length=20, default="Economy", help_text="Economy, Business, etc.")
    duration = models.CharField(max_length=50, default="2h 0m", help_text="Flight duration, e.g. '2h 15m'")

    is_refundable = models.BooleanField(default=True, help_text="Is the ticket refundable?")
    baggage_check_in = models.CharField(max_length=50, default="15 Kg", help_text="e.g. '15 Kg'")
    baggage_hand = models.CharField(max_length=50, default="7 Kg", help_text="e.g. '7' Kg")

    segments = models.JSONField(
        null=True,
        blank=True,
        help_text="JSON list containing segments details for multi-segment flights."
    )
    is_published = models.BooleanField(
        default=True,
        help_text="When True, inventory appears on For Sale and in flight search.",
    )
    is_enabled = models.BooleanField(
        default=True,
        help_text="Admin kill-switch. When False, inventory is hidden from all channels.",
    )
    sales_closing_datetime = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional cutoff datetime — sales stop at this time even if seats are available.",
    )
    apis_required = models.BooleanField(
        default=False,
        help_text="Whether passport/API passenger details are required for booking.",
    )
    policies = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text="Cancellation / change / refund policy text for this inventory.",
    )

    class Meta:
        verbose_name = 'Agent Flight Inventory'
        verbose_name_plural = 'Agent Flight Inventories'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.airline_code} {self.flight_number} ({self.origin} -> {self.destination}) - ₹{self.price} ({self.seats_available} seats)"

    @property
    def sellable_seats(self) -> int:
        from django.utils import timezone
        if self.sales_closing_datetime and timezone.now() >= self.sales_closing_datetime:
            return 0
        return max(0, int(self.seats_available or 0) - int(self.seats_held or 0))

    @property
    def created_by(self):
        return self.agent

    @created_by.setter
    def created_by(self, value):
        self.agent = value


class InventoryHold(BaseModel):
    """Seat hold or waitlist entry against agent offline inventory."""

    STATUS_HOLD = "HOLD"
    STATUS_WAITLIST = "WAITLIST"
    STATUS_CONFIRMED = "CONFIRMED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_EXPIRED = "EXPIRED"
    STATUS_CHOICES = [
        (STATUS_HOLD, "Seat Hold"),
        (STATUS_WAITLIST, "Waitlist"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_EXPIRED, "Expired"),
    ]

    inventory = models.ForeignKey(
        AgentFlightInventory,
        on_delete=models.CASCADE,
        related_name="holds",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inventory_holds",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_HOLD)
    seats = models.PositiveIntegerField(default=1)
    contact_name = models.CharField(max_length=120, blank=True, default="")
    contact_email = models.EmailField(blank=True, default="")
    contact_mobile = models.CharField(max_length=20, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.status} {self.seats} seat(s) on {self.inventory_id}"


# Alias for backward compatibility
FlightInventory = AgentFlightInventory
