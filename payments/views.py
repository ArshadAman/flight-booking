from decimal import Decimal
from rest_framework import permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAgentUser, is_platform_admin
from .models import AgentWallet, DepositRequest
from .serializers import AgentWalletSerializer, DepositRequestSerializer

DEFAULT_OPENING_BALANCE = Decimal("124500.00")

def get_or_create_wallet(user):
    wallet, _ = AgentWallet.objects.get_or_create(
        agent=user,
        defaults={"balance": DEFAULT_OPENING_BALANCE, "currency": "INR"},
    )
    return wallet

class AgentWalletView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAgentUser]

    def get(self, request):
        wallet = get_or_create_wallet(request.user)
        return Response(AgentWalletSerializer(wallet).data)

class DepositRequestViewSet(viewsets.ModelViewSet):
    serializer_class = DepositRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if is_platform_admin(user):
            return DepositRequest.objects.all()
        return DepositRequest.objects.filter(agent=user)

    def perform_create(self, serializer):
        serializer.save(agent=self.request.user)

class CustomerTransactionsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        from tickets.models import Ticket

        items = []
        tickets = Ticket.objects.filter(user=user).order_by("-created_at")[:50]
        for idx, t in enumerate(tickets):
            pax = t.passengers_data if isinstance(t.passengers_data, list) else []
            lead_name = "Passenger"
            if pax and isinstance(pax[0], dict):
                first = pax[0].get("first_name", "")
                last = pax[0].get("last_name", "")
                lead_name = f"{first} {last}".strip() or "Passenger"
            elif user.first_name:
                lead_name = f"{user.first_name} {user.last_name}".strip()
            dt = t.created_at
            items.append({
                "id": str(t.id),
                "date": dt.strftime("%d, %b %Y"),
                "time": dt.strftime("%I:%M %p"),
                "pnr": t.pnr_number or f"X{75+idx}OJKQ",
                "booking_id": t.pnr_number or f"DEP-10{250+idx}",
                "transaction_id": f"UPI{str(t.id)[:8].upper()}",
                "amount": float(t.total_amount or 0),
                "amount_received": float(t.total_amount or 0),
                "payment_mode": "NetBanking",
                "bank_name": "HDFC",
                "status": "PAID" if t.status == Ticket.STATUS_CONFIRMED else ("PARTIAL" if t.status == Ticket.STATUS_PENDING else "REJECTED"),
                "customer_name": lead_name,
            })

        deposits = DepositRequest.objects.filter(agent=user).order_by("-created_at")[:50]
        for idx, d in enumerate(deposits):
            dt = d.created_at
            items.append({
                "id": str(d.id),
                "date": dt.strftime("%d, %b %Y"),
                "time": dt.strftime("%I:%M %p"),
                "pnr": "-",
                "booking_id": (d.utr_number or d.request_id) or f"DEP-10{d.id}",
                "transaction_id": (d.utr_number or d.request_id) or f"TXN{d.id}",
                "amount": float(d.amount),
                "amount_received": float(d.amount) if d.status == DepositRequest.STATUS_APPROVED else 0.0,
                "payment_mode": d.payment_mode or "NetBanking",
                "bank_name": d.bank_name or "HDFC",
                "status": "PAID" if d.status == DepositRequest.STATUS_APPROVED else ("PARTIAL" if d.status == DepositRequest.STATUS_PENDING else "REJECTED"),
                "customer_name": user.first_name or user.username or "Agent Lead",
            })

        return Response(items)

class AgentLedgerAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        from tickets.models import Ticket

        wallet = get_or_create_wallet(user)
        current_balance = float(wallet.balance)

        entries = []
        deposits = DepositRequest.objects.filter(agent=user).order_by("-created_at")[:50]
        for d in deposits:
            dt = d.created_at
            entries.append({
                "id": str(d.id),
                "timestamp": dt,
                "date": dt.strftime("%d, %b %Y"),
                "time": dt.strftime("%I:%M %p"),
                "reference": (d.utr_number or d.request_id) or f"DEP-10{d.id}",
                "channel": "B2B",
                "transaction_type": "Deposit",
                "description": f"Wallet Deposit via {d.bank_name}",
                "bank_name": d.bank_name or "HDFC",
                "amount": float(d.amount),
                "balance": current_balance,
                "payment_mode": d.payment_mode or "NetBanking",
                "status": d.status,
            })

        tickets = Ticket.objects.filter(user=user).order_by("-created_at")[:50]
        for t in tickets:
            dt = t.created_at
            entries.append({
                "id": str(t.id),
                "timestamp": dt,
                "date": dt.strftime("%d, %b %Y"),
                "time": dt.strftime("%I:%M %p"),
                "reference": t.pnr_number or f"TKT-{str(t.id)[:6].upper()}",
                "channel": t.booking_channel or "B2B",
                "transaction_type": "Booking",
                "description": f"Flight Booking {t.origin} → {t.destination} ({t.airline_name})",
                "bank_name": "Wallet",
                "amount": -float(t.total_amount or 0),
                "balance": current_balance,
                "payment_mode": "Wallet",
                "status": "APPROVED" if t.status == Ticket.STATUS_CONFIRMED else "PENDING",
            })

        entries.sort(key=lambda x: x["timestamp"], reverse=True)
        for e in entries:
            del e["timestamp"]

        return Response(entries)
