from django.conf import settings
from django.db import models

from core.models import BaseModel


class FlightInventory(BaseModel):
    """
    Locally managed flight inventory created by agents for sale flows.
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="flight_inventories",
        db_column="agent_id",
    )
    airline_code = models.CharField(max_length=10)
    airline_name = models.CharField(max_length=100, blank=True, default="")
    flight_number = models.CharField(max_length=20)
    origin = models.CharField(max_length=3)
    destination = models.CharField(max_length=3)
    departure_datetime = models.DateTimeField()
    arrival_datetime = models.DateTimeField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    seats_available = models.PositiveIntegerField()
    cabin_class = models.CharField(max_length=20, default="Economy")
    duration = models.CharField(max_length=50, blank=True, default="")
    is_refundable = models.BooleanField(default=True)
    baggage_check_in = models.CharField(max_length=50, blank=True, default="")
    baggage_hand = models.CharField(max_length=50, blank=True, default="")
    segments = models.JSONField(default=list, blank=True, null=True, db_column="segments")

    class Meta:
        ordering = ["-departure_datetime", "-created_at"]
        verbose_name = "Flight Inventory"
        verbose_name_plural = "Flight Inventory"
        db_table = "flights_agentflightinventory"

    def __str__(self):
        return f"{self.origin}->{self.destination} {self.airline_code}{self.flight_number}"
