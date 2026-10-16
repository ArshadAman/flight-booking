from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TicketViewSet, TicketCancellationViewSet, TicketAmendmentViewSet

router = DefaultRouter()
router.register(r"cancellations", TicketCancellationViewSet, basename="ticket-cancellations")
router.register(r"amendments", TicketAmendmentViewSet, basename="ticket-amendments")
router.register(r"", TicketViewSet, basename="ticket")

urlpatterns = [
    path("", include(router.urls)),
]
