from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FlightSearchView,
    FlightRevalidateView,
    FlightSSRView,
    AgentFlightInventoryViewSet,
    PublicForSaleInventoryView,
    InventoryHoldViewSet,
)

router = DefaultRouter()
router.register(r"inventory", AgentFlightInventoryViewSet, basename="agent-inventory")
router.register(r"holds", InventoryHoldViewSet, basename="inventory-holds")

urlpatterns = [
    path("search/", FlightSearchView.as_view(), name="flight_search"),
    path("revalidate/", FlightRevalidateView.as_view(), name="flight_revalidate"),
    path("ssr/", FlightSSRView.as_view(), name="flight_ssr"),
    path("for-sale/", PublicForSaleInventoryView.as_view(), name="for_sale_inventory"),
    path("inventory/", AgentFlightInventoryViewSet.as_view({"get": "list", "post": "create"}), name="flight_inventory"),
    path("", include(router.urls)),
]
