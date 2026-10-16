from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    InventoryRestrictionViewSet,
    AgentHistoryListView,
    AgentDashboardAPIView,
    SupplierViewSet,
    NoticeViewSet,
    AgentCommissionAPIView,
    DiscountViewSet,
    MarkupRuleViewSet,
    ServiceChargeViewSet,
    StaffMemberViewSet,
    CompanyProfileView,
    InvoiceSettingView,
)

router = DefaultRouter()
router.register(r"suppliers", SupplierViewSet, basename="suppliers")
router.register(r"notices", NoticeViewSet, basename="notices")
router.register(r"restrictions", InventoryRestrictionViewSet, basename="inventory-restrictions")
router.register(r"discounts", DiscountViewSet, basename="discounts")
router.register(r"markups", MarkupRuleViewSet, basename="markups")
router.register(r"service-charges", ServiceChargeViewSet, basename="service-charges")
router.register(r"staff", StaffMemberViewSet, basename="staff")

urlpatterns = [
    path("dashboard/", AgentDashboardAPIView.as_view(), name="agent-dashboard"),
    path("history/", AgentHistoryListView.as_view(), name="agent-history"),
    path("commission/", AgentCommissionAPIView.as_view(), name="agent-commission"),
    path("company-profile/", CompanyProfileView.as_view(), name="agent-company-profile"),
    path("invoice-settings/", InvoiceSettingView.as_view(), name="agent-invoice-settings"),
    path("", include(router.urls)),
]
