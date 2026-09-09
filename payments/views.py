from decimal import Decimal

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAgentUser
from .models import AgentWallet
from .serializers import AgentWalletSerializer


DEFAULT_OPENING_BALANCE = Decimal("124500.00")


def get_or_create_wallet(user):
    wallet, _ = AgentWallet.objects.get_or_create(
        agent=user,
        defaults={"balance": DEFAULT_OPENING_BALANCE, "currency": "INR"},
    )
    return wallet


class AgentWalletView(APIView):
    """
    GET /api/v1/payments/wallet/
    Returns the authenticated agent's wallet balance for the offline portal navbar.
    """

    permission_classes = [permissions.IsAuthenticated, IsAgentUser]

    def get(self, request):
        wallet = get_or_create_wallet(request.user)
        return Response(AgentWalletSerializer(wallet).data)
