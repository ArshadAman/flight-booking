from django.urls import path
from .views import AgentWalletView

urlpatterns = [
    path("wallet/", AgentWalletView.as_view(), name="agent-wallet"),
]
