from decimal import Decimal

from django.conf import settings
from django.db import models
from core.models import BaseModel


class AgentWallet(BaseModel):
    """
    Agent prepaid / credit wallet shown as Balance in the offline portal navbar.
    """

    agent = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("124500.00"))
    currency = models.CharField(max_length=3, default="INR")

    class Meta:
        verbose_name = "Agent Wallet"
        verbose_name_plural = "Agent Wallets"

    def __str__(self):
        return f"{self.agent_id} · {self.currency} {self.balance}"


class DepositRequest(BaseModel):
    """
    Agent balance top-up / deposit request with bank transfer / UTR proof.
    """

    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="deposit_requests",
    )
    request_id = models.CharField(max_length=40, unique=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_mode = models.CharField(max_length=40, default="NEFT/RTGS")
    bank_name = models.CharField(max_length=120, blank=True, default="")
    utr_number = models.CharField(max_length=120)
    deposit_date = models.DateField(null=True, blank=True)
    deposit_slip = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    remarks = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.request_id:
            import random
            self.request_id = f"DEP-{random.randint(100000, 999999)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.request_id} · ₹{self.amount} ({self.status})"
