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


class AgentAuditLog(BaseModel):
    """
    Offline portal History entries (Figma: Date / Time / Action icon / Entry / By Agent).
    """

    ACTION_BOOKING = "BOOKING"
    ACTION_PNR = "PNR"
    ACTION_CANCEL = "CANCEL"
    ACTION_HOLD = "HOLD"
    ACTION_PROFILE = "PROFILE"
    ACTION_INVENTORY = "INVENTORY"
    ACTION_OTHER = "OTHER"
    ACTION_CHOICES = [
        (ACTION_BOOKING, "Booking"),
        (ACTION_PNR, "PNR"),
        (ACTION_CANCEL, "Cancel"),
        (ACTION_HOLD, "Hold"),
        (ACTION_PROFILE, "Profile"),
        (ACTION_INVENTORY, "Inventory"),
        (ACTION_OTHER, "Other"),
    ]

    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="performed_audit_logs",
    )
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES, default=ACTION_OTHER)
    entry = models.CharField(max_length=255)
    reference = models.CharField(max_length=64, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Agent Audit Log"
        verbose_name_plural = "Agent Audit Logs"

    def __str__(self):
        return f"{self.entry} ({self.agent_id})"


def log_agent_action(
    *,
    agent,
    entry,
    action_type=AgentAuditLog.ACTION_OTHER,
    performed_by=None,
    reference="",
    metadata=None,
):
    if agent is None:
        return None
    return AgentAuditLog.objects.create(
        agent=agent,
        performed_by=performed_by or agent,
        action_type=action_type,
        entry=entry[:255],
        reference=(reference or "")[:64],
        metadata=metadata or {},
    )
