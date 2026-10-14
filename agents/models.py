from django.conf import settings
from django.db import models
from core.models import BaseModel


class Supplier(BaseModel):
    """Airline or inventory supplier onboarded by admin. Requests start pending."""

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_DENIED = "denied"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_DENIED, "Denied"),
    ]

    code = models.CharField(max_length=20, unique=True, blank=True, default="")
    name = models.CharField(max_length=160)
    contact_name = models.CharField(max_length=120, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    inventory_count = models.PositiveIntegerField(default=0)
    notes = models.CharField(max_length=255, blank=True, default="")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_requests",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Supplier"
        verbose_name_plural = "Suppliers"

    def save(self, *args, **kwargs):
        if not self.code:
            prefix = "SUP-"
            existing = Supplier.objects.filter(code__startswith=prefix).count() + 1
            self.code = f"{prefix}{existing:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} {self.name}"


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


class Notice(BaseModel):
    """Board item shown to agents under My Account → Notice Board."""

    CATEGORY_AIRLINE = "airline"
    CATEGORY_FINANCE = "finance"
    CATEGORY_CONTACT = "contact"
    CATEGORY_OTHER = "other"
    CATEGORY_CHOICES = [
        (CATEGORY_AIRLINE, "Airline"),
        (CATEGORY_FINANCE, "Finance"),
        (CATEGORY_CONTACT, "Contact"),
        (CATEGORY_OTHER, "Other"),
    ]

    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    label = models.CharField(max_length=40, blank=True, default="")
    title = models.CharField(max_length=160)
    body = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category", "-created_at"]

    def __str__(self):
        return self.title


class AgentCommission(BaseModel):
    """Markup rule an agent saves from Manage Commission."""

    CATEGORY_FLIGHT = "flight"
    CATEGORY_REBOOK = "rebook"
    CATEGORY_CHOICES = [
        (CATEGORY_FLIGHT, "Flight"),
        (CATEGORY_REBOOK, "Rebooking"),
    ]
    METHOD_NONE = "none"
    METHOD_FLAT = "flat"
    METHOD_STANDARD = "standard"
    METHOD_SIMPLE = "simple"
    METHOD_CUSTOM = "custom"
    METHOD_CHOICES = [
        (METHOD_NONE, "No Calculation"),
        (METHOD_FLAT, "Flat Calculation"),
        (METHOD_STANDARD, "Standard Calculation"),
        (METHOD_SIMPLE, "Simple Calculation"),
        (METHOD_CUSTOM, "Custom Calculation"),
    ]

    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="commissions",
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_FLIGHT)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default=METHOD_NONE)
    markup = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = [("agent", "category")]

    def __str__(self):
        return f"{self.agent_id} {self.category} {self.method}"
