from django.db import models
from django.conf import settings
from core.models import BaseModel

class AgentFlightInventory(BaseModel):
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='flight_inventories',
        help_text="The agent who owns this pre-purchased flight inventory."
    )
    airline_code = models.CharField(max_length=10, help_text="e.g. '6E'")
    airline_name = models.CharField(max_length=100, help_text="e.g. 'IndiGo'")
    flight_number = models.CharField(max_length=20, help_text="e.g. '6E-2012'")
    origin = models.CharField(max_length=3, help_text="3-letter IATA code, e.g. 'DEL'")
    destination = models.CharField(max_length=3, help_text="3-letter IATA code, e.g. 'BOM'")
    
    departure_datetime = models.DateTimeField(help_text="Departure date and time.")
    arrival_datetime = models.DateTimeField(help_text="Arrival date and time.")
    
    price = models.DecimalField(max_digits=12, decimal_places=2, help_text="Ticket price.")
    seats_available = models.IntegerField(default=10, help_text="Number of available seats.")
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

    class Meta:
        verbose_name = 'Agent Flight Inventory'
        verbose_name_plural = 'Agent Flight Inventories'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.airline_code} {self.flight_number} ({self.origin} -> {self.destination}) - ₹{self.price} ({self.seats_available} seats)"
