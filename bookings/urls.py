from django.urls import path, include
from rest_framework.routers import DefaultRouter
from bookings.views import GroupBookingViewSet

router = DefaultRouter()
router.register(r'group-bookings', GroupBookingViewSet, basename='group-booking')

urlpatterns = [
    path('', include(router.urls)),
]
