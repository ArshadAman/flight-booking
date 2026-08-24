"""Shared helpers for offline / For Sale inventory channel rules."""
from __future__ import annotations

from django.db.models import Q, QuerySet


def apply_inventory_channel_filters(qs: QuerySet, agent_id=None) -> QuerySet:
    """Keep only inventory that is published, enabled, and not blocked by restrictions."""
    qs = qs.filter(is_published=True, is_enabled=True)

    try:
        from agents.models import InventoryRestriction
    except Exception:
        return qs

    airline_blocks = InventoryRestriction.objects.filter(
        scope=InventoryRestriction.SCOPE_AIRLINE,
        is_blocked=True,
    ).filter(Q(agent__isnull=True) | Q(agent_id=agent_id) if agent_id else Q(agent__isnull=True))

    # Global airline blocks always apply; agent-specific only when filtering that agent.
    global_airlines = set(
        InventoryRestriction.objects.filter(
            scope=InventoryRestriction.SCOPE_AIRLINE,
            is_blocked=True,
            agent__isnull=True,
        ).values_list("airline_code", flat=True)
    )
    if global_airlines:
        qs = qs.exclude(airline_code__in=[c.upper() for c in global_airlines if c])

    if agent_id:
        agent_airlines = set(
            InventoryRestriction.objects.filter(
                scope=InventoryRestriction.SCOPE_AIRLINE,
                is_blocked=True,
                agent_id=agent_id,
            ).values_list("airline_code", flat=True)
        )
        if agent_airlines:
            qs = qs.exclude(airline_code__in=[c.upper() for c in agent_airlines if c])

    route_blocks = InventoryRestriction.objects.filter(
        scope=InventoryRestriction.SCOPE_ROUTE,
        is_blocked=True,
        agent__isnull=True,
    )
    for block in route_blocks:
        qs = qs.exclude(origin=block.origin.upper(), destination=block.destination.upper())

    if agent_id:
        for block in InventoryRestriction.objects.filter(
            scope=InventoryRestriction.SCOPE_ROUTE,
            is_blocked=True,
            agent_id=agent_id,
        ):
            qs = qs.exclude(origin=block.origin.upper(), destination=block.destination.upper())

    return qs


def inventory_is_restricted(inventory) -> bool:
    """True if a single inventory row is blocked by airline/route rules."""
    try:
        from agents.models import InventoryRestriction
    except Exception:
        return False

    airline = (inventory.airline_code or "").upper()
    origin = (inventory.origin or "").upper()
    dest = (inventory.destination or "").upper()
    agent_id = getattr(inventory, "agent_id", None)

    if InventoryRestriction.objects.filter(
        scope=InventoryRestriction.SCOPE_AIRLINE,
        is_blocked=True,
        airline_code__iexact=airline,
    ).filter(Q(agent__isnull=True) | Q(agent_id=agent_id)).exists():
        return True

    if InventoryRestriction.objects.filter(
        scope=InventoryRestriction.SCOPE_ROUTE,
        is_blocked=True,
        origin__iexact=origin,
        destination__iexact=dest,
    ).filter(Q(agent__isnull=True) | Q(agent_id=agent_id)).exists():
        return True

    return False
