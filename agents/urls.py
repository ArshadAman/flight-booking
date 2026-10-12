from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InventoryRestrictionViewSet, AgentHistoryListView, AgentDashboardAPIView

router = DefaultRouter()
router.register(r"restrictions", InventoryRestrictionViewSet, basename="inventory-restrictions")

urlpatterns = [
    path("dashboard/", AgentDashboardAPIView.as_view(), name="agent-dashboard"),
    path("history/", AgentHistoryListView.as_view(), name="agent-history"),
    path("", include(router.urls)),
]
