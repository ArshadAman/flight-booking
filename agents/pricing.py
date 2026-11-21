"""Apply agent markup rules to published offline inventory (Route Fee / B2B API)."""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Q


def _parse_price(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    text = str(value).replace(",", "").replace("INR", "").strip() or "0"
    return Decimal(text)


def resolve_markup_rule(
    *,
    agent_id,
    channel: str = "B2B_API",
    airline: str = "ALL",
    origin: str = "",
    destination: str = "",
):
    """Best matching active MarkupRule for an agent listing (most specific sector wins)."""
    from agents.models import MarkupRule

    airline = (airline or "ALL").upper()
    origin = (origin or "").upper()
    destination = (destination or "").upper()
    sector_exact = f"{origin}-{destination}" if origin and destination else ""
    channel_candidates = {channel, "B2B_API", "B2B", "ALL"}

    qs = MarkupRule.objects.filter(is_active=True).filter(channel__in=channel_candidates)
    if agent_id:
        qs = qs.filter(Q(agent_id=agent_id) | Q(agent__isnull=True))
    else:
        qs = qs.filter(agent__isnull=True)

    def score(rule) -> int:
        s = 0
        if rule.agent_id and agent_id and str(rule.agent_id) == str(agent_id):
            s += 8
        if (rule.channel or "").upper() in {channel, "B2B_API"}:
            s += 4
        rule_airline = (rule.airline or "ALL").upper()
        if rule_airline == airline:
            s += 2
        elif rule_airline == "ALL":
            s += 1
        rule_sector = (rule.sector or "ALL").upper()
        if sector_exact and rule_sector == sector_exact:
            s += 16
        elif rule_sector == "ALL":
            s += 4
        return s

    candidates = list(qs[:50])
    if not candidates:
        return None
    return max(candidates, key=score)


def apply_agent_markup(
    base_price,
    *,
    agent_id,
    channel: str = "B2B_API",
    airline: str = "ALL",
    origin: str = "",
    destination: str = "",
):
    base = _parse_price(base_price)
    rule = resolve_markup_rule(
        agent_id=agent_id,
        channel=channel,
        airline=airline,
        origin=origin,
        destination=destination,
    )
    if not rule:
        return base
    value = _parse_price(rule.value)
    if rule.markup_type == rule.TYPE_PERCENTAGE:
        return (base * (Decimal("1") + value / Decimal("100"))).quantize(Decimal("0.01"))
    return (base + value).quantize(Decimal("0.01"))