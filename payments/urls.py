from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AgentWalletView, DepositRequestViewSet, CustomerTransactionsAPIView, AgentLedgerAPIView

router = DefaultRouter()
router.register(r"deposit-requests", DepositRequestViewSet, basename="deposit-requests")

urlpatterns = [
    path("wallet/", AgentWalletView.as_view(), name="agent-wallet"),
    path("transactions/", CustomerTransactionsAPIView.as_view(), name="customer-transactions"),
    path("ledger/", AgentLedgerAPIView.as_view(), name="agent-ledger"),
    path("", include(router.urls)),
]
