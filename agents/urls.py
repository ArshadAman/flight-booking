from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    InventoryRestrictionViewSet,
    AgentHistoryListView,
    AgentDashboardAPIView,
    SupplierViewSet,
    NoticeViewSet,
    AgentCommissionAPIView,
)

router = DefaultRouter()
router.register(r"suppliers", SupplierViewSet, basename="suppliers")
router.register(r"notices", NoticeViewSet, basename="notices")
router.register(r"restrictions", InventoryRestrictionViewSet, basename="inventory-restrictions")

urlpatterns = [
    path("dashboard/", AgentDashboardAPIView.as_view(), name="agent-dashboard"),
    path("history/", AgentHistoryListView.as_view(), name="agent-history"),
    path("commission/", AgentCommissionAPIView.as_view(), name="agent-commission"),
    path("", include(router.urls)),
]
