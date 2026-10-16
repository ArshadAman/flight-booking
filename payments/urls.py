from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AgentWalletView, DepositRequestViewSet

router = DefaultRouter()
router.register(r"deposit-requests", DepositRequestViewSet, basename="deposit-requests")

urlpatterns = [
    path("wallet/", AgentWalletView.as_view(), name="agent-wallet"),
    path("", include(router.urls)),
]
