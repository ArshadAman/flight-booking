from django.conf import settings
from django.db import models
from core.models import BaseModel


class InventoryRestriction(BaseModel):
    """
    Platform controls to block airline codes or routes from offline inventory channels.
    When agent is null, the restriction applies globally.
    """

    SCOPE_AIRLINE = "AIRLINE"
    SCOPE_ROUTE = "ROUTE"
    SCOPE_CHOICES = [
        (SCOPE_AIRLINE, "Airline"),
        (SCOPE_ROUTE, "Route"),
    ]

    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inventory_restrictions",
        null=True,
        blank=True,
        help_text="Optional agent scope. Null = global restriction.",
    )
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES)
    airline_code = models.CharField(max_length=10, blank=True, default="")
    airline_name = models.CharField(max_length=100, blank=True, default="")
    origin = models.CharField(max_length=3, blank=True, default="")
    destination = models.CharField(max_length=3, blank=True, default="")
    is_blocked = models.BooleanField(default=True)
    reason = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Inventory Restriction"
        verbose_name_plural = "Inventory Restrictions"

    def __str__(self):
        if self.scope == self.SCOPE_AIRLINE:
            return f"Block airline {self.airline_code} ({'global' if not self.agent_id else self.agent_id})"
        return f"Block route {self.origin}-{self.destination}"
