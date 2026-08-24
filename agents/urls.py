from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InventoryRestrictionViewSet

router = DefaultRouter()
router.register(r"restrictions", InventoryRestrictionViewSet, basename="inventory-restrictions")

urlpatterns = [
    path("", include(router.urls)),
]
