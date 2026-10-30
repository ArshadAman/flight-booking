from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAgentUser, is_platform_admin
from .models import AgentWallet, DepositRequest
from .serializers import AgentWalletSerializer, DepositRequestSerializer

User = get_user_model()
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

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        if not is_platform_admin(request.user):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        deposit = self.get_object()
        if deposit.status != DepositRequest.STATUS_PENDING:
            return Response({"detail": "Only pending deposits can be approved."}, status=400)
        remarks = request.data.get("remarks")
        with transaction.atomic():
            if remarks is not None:
                deposit.remarks = str(remarks)
            deposit.status = DepositRequest.STATUS_APPROVED
            deposit.save(update_fields=["status", "remarks", "updated_at"])
            wallet = get_or_create_wallet(deposit.agent)
            wallet.balance += deposit.amount
            wallet.save(update_fields=["balance", "updated_at"])
        return Response(DepositRequestSerializer(deposit).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        if not is_platform_admin(request.user):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        deposit = self.get_object()
        if deposit.status != DepositRequest.STATUS_PENDING:
            return Response({"detail": "Only pending deposits can be rejected."}, status=400)
        remarks = request.data.get("remarks") or "Rejected by admin"
        deposit.status = DepositRequest.STATUS_REJECTED
        deposit.remarks = str(remarks)
        deposit.save(update_fields=["status", "remarks", "updated_at"])
        return Response(DepositRequestSerializer(deposit).data)


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


class AdminWalletListAPIView(APIView):
    """GET /api/v1/payments/admin/wallets/ — platform admin view of agent balances."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not is_platform_admin(request.user):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        wallets = AgentWallet.objects.select_related("agent").order_by("-updated_at")
        rows = []
        for wallet in wallets:
            agent = wallet.agent
            profile = getattr(agent, "company_profile", None)
            agency = profile.company_name if profile and profile.company_name else ""
            full = agent.get_full_name().strip()
            rows.append(
                {
                    "id": str(wallet.id),
                    "agent_id": str(agent.id),
                    "agent_name": agency or full or agent.username,
                    "agent_email": agent.email,
                    "balance": wallet.balance,
                    "currency": wallet.currency,
                    "updated_at": wallet.updated_at,
                    "is_active": agent.is_active,
                }
            )
        return Response(rows)


class PlatformAgentListAPIView(APIView):
    """GET/POST /api/v1/payments/admin/agents/ — list or create travel agents (platform admin)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not is_platform_admin(request.user):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        agents = User.objects.filter(role=User.AGENT).order_by("-date_joined")
        rows = []
        for agent in agents:
            wallet = AgentWallet.objects.filter(agent=agent).first()
            profile = getattr(agent, "company_profile", None)
            agency = profile.company_name if profile and profile.company_name else ""
            full = agent.get_full_name().strip()
            last_deposit = (
                DepositRequest.objects.filter(agent=agent, status=DepositRequest.STATUS_APPROVED)
                .order_by("-updated_at")
                .first()
            )
            rows.append(
                {
                    "id": str(agent.id),
                    "username": agent.username,
                    "email": agent.email,
                    "agency_name": agency or full or agent.username,
                    "contact_name": full or agent.username,
                    "balance": str(wallet.balance) if wallet else "0",
                    "currency": wallet.currency if wallet else "INR",
                    "is_active": agent.is_active,
                    "date_joined": agent.date_joined,
                    "last_deposit_amount": str(last_deposit.amount) if last_deposit else None,
                    "last_deposit_at": last_deposit.updated_at if last_deposit else None,
                }
            )
        return Response(rows)

    def post(self, request):
        if not is_platform_admin(request.user):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        from accounts.serializers import AdminCreateAgentSerializer, UserSerializer

        serializer = AdminCreateAgentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        agent = serializer.save()
        wallet = AgentWallet.objects.filter(agent=agent).first()
        profile = getattr(agent, "company_profile", None)
        agency = profile.company_name if profile and profile.company_name else ""
        full = agent.get_full_name().strip()
        return Response(
            {
                "id": str(agent.id),
                "username": agent.username,
                "email": agent.email,
                "agency_name": agency or full or agent.username,
                "contact_name": full or agent.username,
                "balance": str(wallet.balance) if wallet else "0",
                "currency": wallet.currency if wallet else "INR",
                "is_active": agent.is_active,
                "date_joined": agent.date_joined,
                "user": UserSerializer(agent).data,
            },
            status=status.HTTP_201_CREATED,
        )


class PlatformAgentDetailAPIView(APIView):
    """GET /api/v1/payments/admin/agents/<uuid>/ — single agent profile for admin UI."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, agent_id):
        if not is_platform_admin(request.user):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        agent = get_object_or_404(User, id=agent_id, role=User.AGENT)
        wallet = AgentWallet.objects.filter(agent=agent).first()
        profile = getattr(agent, "company_profile", None)
        agency = profile.company_name if profile and profile.company_name else ""
        full = agent.get_full_name().strip()
        return Response(
            {
                "id": str(agent.id),
                "username": agent.username,
                "email": agent.email,
                "phone": getattr(agent, "phone_number", "") or "",
                "agency_name": agency or full or agent.username,
                "contact_name": full or agent.username,
                "balance": str(wallet.balance) if wallet else "0",
                "currency": wallet.currency if wallet else "INR",
                "is_active": agent.is_active,
                "date_joined": agent.date_joined,
                "company_profile": {
                    "company_name": profile.company_name if profile else "",
                    "trade_name": profile.trade_name if profile else "",
                    "gstin": profile.gstin if profile else "",
                    "pan": profile.pan if profile else "",
                    "phone": profile.phone if profile else "",
                    "email": profile.email if profile else agent.email,
                    "address": profile.address if profile else "",
                    "city": profile.city if profile else "",
                    "state": profile.state if profile else "",
                }
                if profile
                else None,
            }
        )
