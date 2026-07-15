import logging
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Ticket
from .serializers import TicketSerializer, TicketPurchaseRequestSerializer, TicketCancelRequestSerializer
from flights.services import ProviderService, ProviderAPIException
from accounts.permissions import is_platform_admin

logger = logging.getLogger('tickets.views')

class TicketViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ReadOnlyModelViewSet allowing users to perform list, retrieve, purchase, and cancel operations on their tickets.
    """
    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Dynamically filters the queryset based on user authentication:
        - Admin/Staff/Superuser can view all tickets (including bookings created from the user panel).
        - AGENT users can view their own bookings or booking requests against their inventory.
        - Ordinary Customers and B2B Agents can only view their own tickets.
        Supports query filters: ?status=CONFIRMED&origin=DEL&pnr=XYZ&search=term
        """
        user = self.request.user
        if is_platform_admin(user):
            qs = Ticket.objects.select_related('user', 'agent_flight_inventory').all()
        elif getattr(user, 'role', '') == 'AGENT':
            from django.db.models import Q
            qs = Ticket.objects.select_related('user', 'agent_flight_inventory').filter(
                Q(user=user) | Q(agent_flight_inventory__agent=user)
            )
        else:
            qs = Ticket.objects.select_related('user', 'agent_flight_inventory').filter(user=user)

        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param.upper())

        origin = self.request.query_params.get('origin')
        if origin:
            qs = qs.filter(origin__iexact=origin)

        destination = self.request.query_params.get('destination')
        if destination:
            qs = qs.filter(destination__iexact=destination)

        pnr = self.request.query_params.get('pnr')
        if pnr:
            qs = qs.filter(pnr_number__icontains=pnr)

        search = self.request.query_params.get('search')
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(pnr_number__icontains=search)
                | Q(ticket_number__icontains=search)
                | Q(booking_ref__icontains=search)
                | Q(flight_number__icontains=search)
                | Q(origin__icontains=search)
                | Q(destination__icontains=search)
                | Q(airline_name__icontains=search)
                | Q(user__email__icontains=search)
                | Q(user__username__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
            )

        return qs.order_by('-created_at')

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

        flight_key = serializer.validated_data.get('flight_key')
        if flight_key and flight_key.startswith("agent-"):
            from flights.models import AgentFlightInventory
            from decimal import Decimal
            import random
            
            agent_id = flight_key.replace("agent-", "")
            try:
                af = AgentFlightInventory.objects.get(id=agent_id)
            except AgentFlightInventory.DoesNotExist:
                return Response(
                    {'detail': 'Selected agent flight inventory no longer exists.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            passengers = serializer.validated_data.get('passengers', [])
            pax_count = len(passengers)
            if af.seats_available < pax_count:
                return Response(
                    {'detail': f'Not enough seats available. Only {af.seats_available} seats remaining.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Decrement seats
            af.seats_available -= pax_count
            af.save()

            # Construct passenger data
            passengers_data = []
            for pax in passengers:
                dob_val = pax.get('dob')
                dob_str = dob_val.strftime("%Y-%m-%d") if dob_val else None
                pax_entry = {
                    "title": pax.get('title', 'Mr'),
                    "first_name": pax.get('first_name'),
                    "last_name": pax.get('last_name'),
                    "gender": "M" if pax.get('gender') == 0 else "F",
                    "dob": dob_str,
                    "passport_number": pax.get('passport_number'),
                    "pancard_number": pax.get('pancard_number')
                }
                passengers_data.append(pax_entry)

            # Construct segment data
            from flights.services import get_airport_timezone
            
            segments_data = []
            if af.segments and isinstance(af.segments, list):
                from datetime import datetime
                for idx, seg in enumerate(af.segments):
                    seg_origin = seg.get("origin", "")
                    seg_dest = seg.get("destination", "")
                    seg_dep_tz = get_airport_timezone(seg_origin)
                    seg_arr_tz = get_airport_timezone(seg_dest)
                    
                    dep_dt_str = seg.get("departure_datetime", "")
                    arr_dt_str = seg.get("arrival_datetime", "")
                    
                    if dep_dt_str.endswith('Z'):
                        dep_dt_str = dep_dt_str.replace('Z', '+00:00')
                    if arr_dt_str.endswith('Z'):
                        arr_dt_str = arr_dt_str.replace('Z', '+00:00')
                        
                    try:
                        seg_utc_dep = datetime.fromisoformat(dep_dt_str)
                        seg_utc_arr = datetime.fromisoformat(arr_dt_str)
                        seg_local_dep = seg_utc_dep.astimezone(seg_dep_tz)
                        seg_local_arr = seg_utc_arr.astimezone(seg_arr_tz)
                        dep_formatted = seg_local_dep.strftime("%m/%d/%Y %H:%M")
                        arr_formatted = seg_local_arr.strftime("%m/%d/%Y %H:%M")
                    except Exception:
                        dep_formatted = dep_dt_str
                        arr_formatted = arr_dt_str
                        
                    segments_data.append({
                        "segment_id": seg.get("segment_id", idx),
                        "airline_code": seg.get("airline_code", af.airline_code),
                        "airline_name": seg.get("airline_name", af.airline_name),
                        "flight_number": seg.get("flight_number", af.flight_number),
                        "origin": seg_origin,
                        "destination": seg_dest,
                        "departure_datetime": dep_formatted,
                        "arrival_datetime": arr_formatted,
                        "duration": seg.get("duration", af.duration),
                        "return_flight": False
                    })
            else:
                segments_data = [{
                    "segment_id": 0,
                    "airline_code": af.airline_code,
                    "airline_name": af.airline_name,
                    "flight_number": af.flight_number,
                    "origin": af.origin,
                    "destination": af.destination,
                    "departure_datetime": af.departure_datetime.strftime("%m/%d/%Y %H:%M"),
                    "arrival_datetime": af.arrival_datetime.strftime("%m/%d/%Y %H:%M"),
                    "duration": af.duration,
                    "return_flight": False
                }]

            booking_ref = f"FBA{random.randint(10000, 99999)}"
            
            ticket = Ticket.objects.create(
                user=request.user,
                agent_flight_inventory=af,
                status=Ticket.STATUS_PENDING,
                booking_ref=booking_ref,
                origin=af.origin,
                destination=af.destination,
                departure_datetime=af.departure_datetime,
                arrival_datetime=af.arrival_datetime,
                travel_type=serializer.validated_data.get('travel_type', 0),
                airline_code=af.airline_code,
                airline_name=af.airline_name,
                flight_number=af.flight_number,
                cabin_class=af.cabin_class,
                basic_amount=af.price,
                tax_amount=Decimal('0.00'),
                total_amount=af.price * pax_count,
                currency='INR',
                baggage_check_in=af.baggage_check_in,
                baggage_hand=af.baggage_hand,
                is_refundable=af.is_refundable,
                food_onboard='F',
                segments_data=segments_data,
                passengers_data=passengers_data,
                ssr_data={"BookingSSRDetails": serializer.validated_data.get('booking_ssr_details', [])}
            )

            response_serializer = self.get_serializer(ticket)
            return Response(
                data=response_serializer.data,
                status=status.HTTP_201_CREATED
            )

        # Call ProviderService to coordinate external booking & ticketing
        ticket_data = ProviderService.buy_ticket(
            validated_data=serializer.validated_data,
            user=request.user
        )

        flight_key = serializer.validated_data.get('flight_key', '')
        is_local = flight_key and flight_key.startswith('local-')
        ticket_status = Ticket.STATUS_PENDING if is_local else Ticket.STATUS_CONFIRMED

        # Create and save local Ticket record in DB
        ticket = Ticket.objects.create(
            user=request.user,
            status=ticket_status,
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

        if not ticket.agent_flight_inventory:
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
        else:
            # Local agent flight booking
            # Increment seats back
            inventory = ticket.agent_flight_inventory
            inventory.seats_available += pax_count
            inventory.save(update_fields=['seats_available', 'updated_at'])
            gds_cancelled = True

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
            "cancelled_by": "Admin" if is_platform_admin(request.user) else ("User" if cancellation_type == 0 else "Airline"),
            "cancellation_type": cancellation_type,
            "cancel_code": cancel_code,
            "paid_amount": paid_amount,
            "airline_penalty": airline_penalty,
            "service_fee": service_fee,
            "refund_amount": refund_amount,
            "remarks": remarks,
            "actor_user_id": str(getattr(request.user, "id", "")),
            "actor_username": getattr(request.user, "username", ""),
            "actor_email": getattr(request.user, "email", ""),
            "actor_role": getattr(request.user, "role", ""),
            "ticket_owner_id": str(getattr(ticket.user, "id", "")),
            "ticket_owner_email": getattr(ticket.user, "email", ""),
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

        if ticket.agent_flight_inventory:
            return Response(
                {"detail": "SSR options are not available for agent bookings."},
                status=status.HTTP_400_BAD_REQUEST
            )

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
        If the GDS call fails, the selections are still saved locally so the user experience is not broken.
        """
        ticket = self.get_object()

        if ticket.agent_flight_inventory:
            return Response(
                {"detail": "SSRs are not supported for agent flights."},
                status=status.HTTP_400_BAD_REQUEST
            )

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

        # Always update local Ticket record's ssr_data
        ticket.ssr_data = {"BookingSSRDetails": booking_ssr_details}
        ticket.save(update_fields=['ssr_data', 'updated_at'])

        response_serializer = self.get_serializer(ticket)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='agent-fulfill', url_name='agent-fulfill')
    def agent_fulfill(self, request, *args, **kwargs):
        """
        POST /api/v1/tickets/{id}/agent-fulfill/
        Agents use this endpoint to upload the final Airline PNR and Ticket number,
        which transitions the ticket to CONFIRMED.
        """
        user = request.user
        if not (is_platform_admin(user) or getattr(user, 'role', '') == 'AGENT'):
            return Response(
                {'detail': 'Only agents or admins can fulfill agent bookings.'},
                status=status.HTTP_403_FORBIDDEN
            )

        ticket = self.get_object()
        if not ticket.agent_flight_inventory:
            return Response(
                {'detail': 'This is not an agent booking request.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not (is_platform_admin(user) or ticket.agent_flight_inventory.agent == user):
            return Response(
                {'detail': 'You do not have permission to fulfill this booking.'},
                status=status.HTTP_403_FORBIDDEN
            )

        if ticket.status != Ticket.STATUS_PENDING:
            return Response(
                {'detail': f'Ticket cannot be fulfilled. Current status is {ticket.status}.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        pnr_number = request.data.get('pnr_number')
        ticket_number = request.data.get('ticket_number')

        if not pnr_number or not ticket_number:
            return Response(
                {'detail': 'Both pnr_number and ticket_number are required to fulfill booking.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        ticket.pnr_number = pnr_number
        ticket.ticket_number = ticket_number
        ticket.status = Ticket.STATUS_CONFIRMED
        ticket.save(update_fields=['pnr_number', 'ticket_number', 'status', 'updated_at'])

        response_serializer = self.get_serializer(ticket)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='agent-cancel', url_name='agent-cancel')
    def agent_cancel(self, request, *args, **kwargs):
        """
        POST /api/v1/tickets/{id}/agent-cancel/
        Agents use this to reject/cancel a pending booking, specifying a reason.
        This transitions the ticket to CANCELLED and restores seats in the inventory.
        """
        user = request.user
        if not (is_platform_admin(user) or getattr(user, 'role', '') == 'AGENT'):
            return Response(
                {'detail': 'Only agents or admins can cancel agent bookings.'},
                status=status.HTTP_403_FORBIDDEN
            )

        ticket = self.get_object()
        if not ticket.agent_flight_inventory:
            return Response(
                {'detail': 'This is not an agent booking.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not (is_platform_admin(user) or ticket.agent_flight_inventory.agent == user):
            return Response(
                {'detail': 'You do not have permission to cancel this booking.'},
                status=status.HTTP_403_FORBIDDEN
            )

        if ticket.status == Ticket.STATUS_CANCELLED:
            return Response(
                {'detail': 'Ticket is already cancelled.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        remarks = request.data.get('remarks') or request.data.get('reason') or "Agent cancelled booking request"

        # Increment seats back
        inventory = ticket.agent_flight_inventory
        pax_count = len(ticket.passengers_data) if ticket.passengers_data else 1
        inventory.seats_available += pax_count
        inventory.save(update_fields=['seats_available', 'updated_at'])

        # Update ticket status & cancellation details
        ticket.status = Ticket.STATUS_CANCELLED
        ticket.agent_cancellation_reason = remarks
        
        paid_amount = float(ticket.total_amount)
        ticket.cancellation_data = {
            "cancelled_by": "Agent" if not is_platform_admin(user) else "Admin",
            "cancellation_type": 1,
            "paid_amount": paid_amount,
            "airline_penalty": 0.0,
            "service_fee": 0.0,
            "refund_amount": paid_amount,
            "remarks": remarks,
            "actor_user_id": str(getattr(user, "id", "")),
            "actor_username": getattr(user, "username", ""),
        }
        ticket.save(update_fields=['status', 'agent_cancellation_reason', 'cancellation_data', 'updated_at'])

        response_serializer = self.get_serializer(ticket)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='admin-status', url_name='admin-status')
    def admin_status(self, request, *args, **kwargs):
        """
        POST /api/v1/tickets/{id}/admin-status/
        Body: { "status": "CONFIRMED"|"PENDING"|"FAILED"|"CANCELLED", "remarks": "..." }
        Platform admins only — used from Admin API Booking to force-update status.
        """
        if not is_platform_admin(request.user):
            return Response(
                {'detail': 'Only admins can update ticket status.'},
                status=status.HTTP_403_FORBIDDEN
            )

        ticket = self.get_object()
        new_status = str(request.data.get('status', '')).upper().strip()
        allowed = {
            Ticket.STATUS_PENDING,
            Ticket.STATUS_CONFIRMED,
            Ticket.STATUS_FAILED,
            Ticket.STATUS_CANCELLED,
        }
        if new_status not in allowed:
            return Response(
                {'detail': f'Invalid status. Allowed: {", ".join(sorted(allowed))}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        remarks = request.data.get('remarks') or f'Status set to {new_status} by admin'
        previous = ticket.status
        ticket.status = new_status

        meta = dict(ticket.cancellation_data or {}) if isinstance(ticket.cancellation_data, dict) else {}
        meta['admin_status_updates'] = meta.get('admin_status_updates') or []
        if not isinstance(meta['admin_status_updates'], list):
            meta['admin_status_updates'] = []
        meta['admin_status_updates'].append({
            'from': previous,
            'to': new_status,
            'remarks': remarks,
            'actor_user_id': str(getattr(request.user, 'id', '')),
            'actor_username': getattr(request.user, 'username', ''),
            'actor_email': getattr(request.user, 'email', ''),
        })
        ticket.cancellation_data = meta
        ticket.save(update_fields=['status', 'cancellation_data', 'updated_at'])

        return Response(self.get_serializer(ticket).data, status=status.HTTP_200_OK)
