from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver


@receiver(pre_save, sender="tickets.Ticket")
def cache_ticket_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._prev_status = None
        return
    try:
        prev = sender.objects.get(pk=instance.pk)
        instance._prev_status = prev.status
    except sender.DoesNotExist:
        instance._prev_status = None


@receiver(post_save, sender="tickets.Ticket")
def audit_ticket_changes(sender, instance, created, **kwargs):
    try:
        from agents.models import AgentAuditLog, log_agent_action
        from payments.views import get_or_create_wallet
        from decimal import Decimal
    except Exception:
        return

    agent = None
    if getattr(instance, "agent_flight_inventory_id", None):
        try:
            agent = instance.agent_flight_inventory.agent
        except Exception:
            agent = None
    if agent is None and getattr(instance, "user_id", None):
        # fallback: ticket owner if agent role
        user = instance.user
        if getattr(user, "role", "") == "AGENT":
            agent = user
    if agent is None:
        return

    ref = instance.pnr_number or instance.booking_ref or str(instance.id)[:8].upper()
    route = ""
    if getattr(instance, "origin", None) and getattr(instance, "destination", None):
        route = f" — {instance.origin}→{instance.destination}"

    if created:
        log_agent_action(
            agent=agent,
            action_type=AgentAuditLog.ACTION_BOOKING,
            entry=f"Booking Created{route}",
            reference=ref,
            metadata={"ticket_id": str(instance.id), "status": instance.status},
        )
        return

    prev = getattr(instance, "_prev_status", None)
    if prev == instance.status:
        if instance.pnr_number and prev != "CANCELLED":
            # PNR may have been attached without status change
            pass
        return

    if instance.status == "CANCELLED" and prev != "CANCELLED":
        log_agent_action(
            agent=agent,
            action_type=AgentAuditLog.ACTION_CANCEL,
            entry=f"Booking Cancelled{route}",
            reference=ref,
            metadata={"ticket_id": str(instance.id)},
        )
        try:
            amount = Decimal(str(instance.total_amount or 0))
            if amount > 0:
                wallet = get_or_create_wallet(agent)
                wallet.balance = Decimal(wallet.balance) + amount
                wallet.save(update_fields=["balance", "updated_at"])
        except Exception:
            pass
        return

    if instance.status == "CONFIRMED" and prev != "CONFIRMED":
        entry = f"PNR Issued{route}" if instance.pnr_number else f"Booking Confirmed{route}"
        log_agent_action(
            agent=agent,
            action_type=AgentAuditLog.ACTION_PNR if instance.pnr_number else AgentAuditLog.ACTION_BOOKING,
            entry=entry,
            reference=ref,
            metadata={"ticket_id": str(instance.id), "pnr": instance.pnr_number},
        )
        try:
            amount = Decimal(str(instance.total_amount or 0))
            if amount > 0:
                wallet = get_or_create_wallet(agent)
                wallet.balance = max(Decimal("0.00"), Decimal(wallet.balance) - amount)
                wallet.save(update_fields=["balance", "updated_at"])
        except Exception:
            pass
