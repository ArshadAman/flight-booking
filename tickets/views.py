from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Ticket
from .serializers import TicketSerializer, TicketPurchaseRequestSerializer
from flights.services import ProviderService

class TicketViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ReadOnlyModelViewSet allowing users to perform list, retrieve, and purchase operations on their tickets.
    """
    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Dynamically filters the queryset based on user authentication:
        - Admin/Staff users can view all tickets in the system.
        - ordinary Customers and B2B Agents can only view their own tickets.
        """
        user = self.request.user
        if user.is_staff or user.role == 'ADMIN':
            return Ticket.objects.all()
        return Ticket.objects.filter(user=user)

    @action(detail=False, methods=['post'], url_path='buy')
    def buy(self, request, *args, **kwargs):
        """
        POST /api/v1/tickets/buy/
        Synchronously coordinates fare revalidation, temporary reservation, 
        and PNR generation against the FlyShop provider, storing confirmed 
        records in the local Ticket database model.
        """
        serializer = TicketPurchaseRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Call ProviderService to coordinate external booking & ticketing
        ticket_data = ProviderService.buy_ticket(
            validated_data=serializer.validated_data,
            user=request.user
        )

        # Create and save local Ticket record in DB
        ticket = Ticket.objects.create(
            user=request.user,
            status=Ticket.STATUS_CONFIRMED,
            **ticket_data
        )

        # Serialize and return finalized database Ticket record
        response_serializer = self.get_serializer(ticket)
        return Response(
            data=response_serializer.data,
            status=status.HTTP_201_CREATED
        )
