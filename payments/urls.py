from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AdminWalletListAPIView,
    AgentLedgerAPIView,
    AgentWalletView,
    CustomerTransactionsAPIView,
    DepositRequestViewSet,
    PlatformAgentDetailAPIView,
    PlatformAgentListAPIView,
)

router = DefaultRouter()
router.register(r"deposit-requests", DepositRequestViewSet, basename="deposit-requests")

urlpatterns = [
    path("wallet/", AgentWalletView.as_view(), name="agent-wallet"),
    path("transactions/", CustomerTransactionsAPIView.as_view(), name="customer-transactions"),
    path("ledger/", AgentLedgerAPIView.as_view(), name="agent-ledger"),
    path("admin/wallets/", AdminWalletListAPIView.as_view(), name="admin-wallets"),
    path("admin/agents/", PlatformAgentListAPIView.as_view(), name="platform-agents"),
    path("admin/agents/<uuid:agent_id>/", PlatformAgentDetailAPIView.as_view(), name="platform-agent-detail"),
    path("", include(router.urls)),
]
