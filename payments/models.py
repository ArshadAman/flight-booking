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
