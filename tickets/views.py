from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Ticket
from .serializers import TicketSerializer, TicketPurchaseRequestSerializer, TicketCancelRequestSerializer
from flights.services import ProviderService, ProviderAPIException

class TicketViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ReadOnlyModelViewSet allowing users to perform list, retrieve, purchase, and cancel operations on their tickets.
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

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, *args, **kwargs):
        """
        POST /api/v1/tickets/{id}/cancel/
        Sends a cancellation request to the GDS provider and updates the ticket
        status to CANCELLED in the local database.
        """
        ticket = self.get_object()

        # Validate request body
        serializer = TicketCancelRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        remarks = serializer.validated_data.get('remarks', 'Customer requested cancellation')
        cancellation_type = serializer.validated_data.get('cancellation_type', 0)
        cancel_code = serializer.validated_data.get('cancel_code', '005')

        # Check ticket isn't already cancelled
        if ticket.status == Ticket.STATUS_CANCELLED:
            return Response(
                {'detail': 'Ticket is already cancelled.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Attempt GDS cancellation — gracefully fall back to local cancel if GDS fails
        gds_cancelled = False
        gds_error = None

        # Build dynamic cancellation details list
        cancel_details = []
        flight_id = ticket.flight_id or "0"

        # Pax_Id in temp_booking is 1-indexed based on passenger index
        pax_count = len(ticket.passengers_data) if ticket.passengers_data else 1
        pax_ids = [str(i) for i in range(1, pax_count + 1)]

        # Segment_Id is usually 0, 1, etc.
        segment_ids = []
        if ticket.segments_data:
            for seg in ticket.segments_data:
                segment_ids.append(str(seg.get('segment_id', '0')))
        if not segment_ids:
            segment_ids = ["0"]

        for pax_id in pax_ids:
            for seg_id in segment_ids:
                cancel_details.append({
                    "FlightId": str(flight_id),
                    "PassengerId": str(pax_id),
                    "SegmentId": str(seg_id)
                })

        try:
            ProviderService.cancel_ticket(
                pnr=ticket.pnr_number or '',
                booking_ref=ticket.booking_ref or '',
                cancel_details=cancel_details,
                remarks=remarks,
                cancellation_type=cancellation_type
            )
            gds_cancelled = True
        except ProviderAPIException as e:
            gds_error = str(e)

        # MMT-style Cancellation Fee & Refund Calculations
        paid_amount = float(ticket.total_amount)
        if cancellation_type == 0:  # Cancelled by User
            airline_penalty = min(3000.0 * pax_count, float(ticket.basic_amount or 0.0))
            service_fee = 300.0 * pax_count
            refund_amount = max(0.0, paid_amount - (airline_penalty + service_fee))
        else:  # Cancelled by Airline (Flight Rescheduled / Cancelled)
            airline_penalty = 0.0
            service_fee = 0.0
            refund_amount = paid_amount

        ticket.cancellation_data = {
            "cancelled_by": "User" if cancellation_type == 0 else "Airline",
            "cancellation_type": cancellation_type,
            "cancel_code": cancel_code,
            "paid_amount": paid_amount,
            "airline_penalty": airline_penalty,
            "service_fee": service_fee,
            "refund_amount": refund_amount,
            "remarks": remarks
        }

        # Always mark as cancelled locally even if GDS is unreachable (offline tickets)
        ticket.status = Ticket.STATUS_CANCELLED
        ticket.save(update_fields=['status', 'cancellation_data', 'updated_at'])

        response_serializer = self.get_serializer(ticket)
        response_data = response_serializer.data
        response_data['gds_cancelled'] = gds_cancelled
        if gds_error:
            response_data['gds_error'] = gds_error

        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='ssr', url_name='ssr')
    def get_ssr(self, request, *args, **kwargs):
        """
        GET /api/v1/tickets/{id}/ssr/
        Retrieves post-booking SSR options & seat maps.
        """
        ticket = self.get_object()

        # Check that the ticket is confirmed
        if ticket.status != Ticket.STATUS_CONFIRMED:
            return Response(
                {"detail": "SSR options are only available for confirmed bookings."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            ssr_options = ProviderService.get_post_ssr(
                booking_ref_no=ticket.booking_ref or '',
                airline_pnr=ticket.pnr_number or ''
            )
        except ProviderAPIException as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_502_BAD_GATEWAY
            )

        return Response(ssr_options, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='ssr/add', url_name='ssr-add')
    def add_ssr(self, request, *args, **kwargs):
        """
        POST /api/v1/tickets/{id}/ssr/add/
        Accepts body e.g., {'BookingSSRDetails': [{'Pax_Id': 1, 'SSR_Key': '...'}]}.
        Calls Initiate and Confirm GDS endpoints sequentially, and saves confirmed choices to Ticket.ssr_data.
        """
        ticket = self.get_object()

        # Check that the ticket is confirmed
        if ticket.status != Ticket.STATUS_CONFIRMED:
            return Response(
                {"detail": "SSRs can only be added to confirmed bookings."},
                status=status.HTTP_400_BAD_REQUEST
            )

        booking_ssr_details = request.data.get('BookingSSRDetails')
        if not booking_ssr_details or not isinstance(booking_ssr_details, list):
            return Response(
                {"detail": "BookingSSRDetails must be a non-empty list of selected SSRs."},
                status=status.HTTP_400_BAD_REQUEST
            )

        for detail in booking_ssr_details:
            if not isinstance(detail, dict) or 'Pax_Id' not in detail or 'SSR_Key' not in detail:
                return Response(
                    {"detail": "Each SSR detail must contain 'Pax_Id' and 'SSR_Key'."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        try:
            # Step 1: Initiate Post SSR
            ProviderService.initiate_post_ssr(
                booking_ref_no=ticket.booking_ref or '',
                booking_ssr_details=booking_ssr_details,
                airline_pnr=ticket.pnr_number or ''
            )

            # Step 2: Confirm Post SSR
            ProviderService.confirm_post_ssr(
                booking_ref_no=ticket.booking_ref or '',
                booking_ssr_details=booking_ssr_details,
                airline_pnr=ticket.pnr_number or ''
            )
        except ProviderAPIException as e:
            return Response(
                {"detail": f"Failed to add SSR: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY
            )

        # Update local Ticket record's ssr_data
        ticket.ssr_data = {"BookingSSRDetails": booking_ssr_details}
        ticket.save(update_fields=['ssr_data', 'updated_at'])

        response_serializer = self.get_serializer(ticket)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
