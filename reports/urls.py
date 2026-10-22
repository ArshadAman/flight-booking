from django.urls import path
from .views import BookingReportsAPIView, FinancialReportsAPIView

urlpatterns = [
    path("bookings/", BookingReportsAPIView.as_view(), name="booking-reports"),
    path("financial/", FinancialReportsAPIView.as_view(), name="financial-reports"),
]
