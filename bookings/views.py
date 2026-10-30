from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from django.db.models import Q
from decimal import Decimal

from bookings.models import GroupBooking, GroupQuote, GroupPassenger, GroupChangeRequest, GroupServiceCase
from bookings.serializers import (
    GroupBookingSerializer,
    GroupQuoteSerializer,
    GroupPassengerSerializer,
    GroupChangeRequestSerializer,
    GroupServiceCaseSerializer,
)
from bookings.state_machine import transition, InvalidTransition
from accounts.permissions import is_platform_admin


def _group_operator(user) -> bool:
    if is_platform_admin(user):
        return True
    return getattr(user, "role", "") in ("AGENT", "ADMIN")


class GroupBookingViewSet(viewsets.ModelViewSet):
    serializer_class = GroupBookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if is_platform_admin(user):
            return GroupBooking.objects.all().order_by("-created_at")

        if getattr(user, "role", "") == "AGENT":
            return GroupBooking.objects.filter(
                Q(user=user) | Q(status__in=["NEW_REQUEST", "FARE_QUOTED", "NEGOTIATION"])
            ).order_by("-created_at")

        return GroupBooking.objects.filter(user=user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["post"], url_path="create")
    def create_booking(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="quote")
    def upload_quote(self, request, pk=None):
        user = request.user
        if not _group_operator(user):
            return Response(
                {"detail": "Only agents and administrators can upload quotes."},
                status=status.HTTP_403_FORBIDDEN,
            )

        booking = self.get_object()
        if booking.status not in ("NEW_REQUEST", "NEGOTIATION", "FARE_QUOTED"):
            return Response(
                {"detail": f"Cannot upload quotes in current status: {booking.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = request.data
        is_many = isinstance(data, list)
        serializer = GroupQuoteSerializer(data=data, many=is_many)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            serializer.save(booking=booking)
            if booking.status != "FARE_QUOTED":
                try:
                    transition(booking, "FARE_QUOTED")
                except InvalidTransition as exc:
                    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            booking.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="negotiate")
    def negotiate(self, request, pk=None):
        booking = self.get_object()
        if booking.status != "FARE_QUOTED":
            return Response(
                {"detail": "Booking must be in FARE_QUOTED status to negotiate."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        remarks = request.data.get("remarks")
        if not remarks:
            return Response(
                {"detail": "Negotiation remarks are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            booking.remarks = remarks
            try:
                transition(booking, "NEGOTIATION")
            except InvalidTransition as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            booking.save()

        return Response(
            {
                "message": "Negotiation remarks submitted successfully.",
                "status": booking.status,
                "remarks": booking.remarks,
            }
        )

    @action(detail=True, methods=["post"], url_path="accept")
    def accept_quote(self, request, pk=None):
        booking = self.get_object()
        if booking.status not in ("FARE_QUOTED", "NEGOTIATION"):
            return Response(
                {"detail": "Booking must be in FARE_QUOTED or NEGOTIATION status to accept a quote."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        quote_option_id = request.data.get("quote_option_id")
        if not quote_option_id:
            return Response(
                {"detail": "quote_option_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            quote = booking.quotes.get(quote_option_id=quote_option_id)
        except GroupQuote.DoesNotExist:
            return Response({"detail": "Quote option not found."}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            booking.quotes.update(is_selected=False)
            quote.is_selected = True
            quote.save()

            booking.payment_deadline = quote.payment_deadline
            booking.balance_deadline = quote.balance_deadline

            try:
                transition(booking, "PAYMENT_PENDING")
            except InvalidTransition as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            booking.save()

        return Response(
            {
                "message": "Quote accepted and payment demands generated.",
                "status": booking.status,
                "payment_deadline": booking.payment_deadline,
                "balance_deadline": booking.balance_deadline,
            }
        )

    @action(detail=True, methods=["post"], url_path="payment")
    def record_payment(self, request, pk=None):
        booking = self.get_object()
        if booking.status not in ("PAYMENT_PENDING", "PARTIALLY_PAID"):
            return Response(
                {"detail": "Booking is not in a payable state."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount_str = request.data.get("amount")
        if not amount_str:
            return Response({"detail": "Amount is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = Decimal(str(amount_str))
        except ValueError:
            return Response({"detail": "Invalid amount format."}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response(
                {"detail": "Amount must be greater than zero."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        selected_quote = booking.quotes.filter(is_selected=True).first()
        if not selected_quote:
            return Response(
                {"detail": "No quote option has been accepted/selected for this booking."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total_pax = booking.pax_adults + booking.pax_children + booking.pax_infants
        total_cost = (selected_quote.fare_per_pax + selected_quote.tax_per_pax) * total_pax

        proof_name = (request.data.get("proof_name") or "").strip()
        proof_data = request.data.get("proof_data") or ""
        if isinstance(proof_data, str) and len(proof_data) > 2_000_000:
            return Response(
                {"detail": "Payment screenshot is too large."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            booking.total_paid += amount
            target = "PAID" if booking.total_paid >= total_cost else "PARTIALLY_PAID"
            try:
                transition(booking, target)
            except InvalidTransition as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            if proof_name:
                booking.payment_proof_name = proof_name[:255]
            if proof_data:
                booking.payment_proof_data = proof_data
            booking.save()

        return Response(
            {
                "message": f"Payment of {amount} recorded successfully.",
                "total_paid": booking.total_paid,
                "total_cost": total_cost,
                "status": booking.status,
                "has_payment_proof": bool(booking.payment_proof_data),
            }
        )

    @action(detail=True, methods=["post"], url_path="pnr")
    def submit_pnr(self, request, pk=None):
        user = request.user
        if not _group_operator(user):
            return Response(
                {"detail": "Only agents and administrators can submit PNR."},
                status=status.HTTP_403_FORBIDDEN,
            )

        booking = self.get_object()
        pnr_number = (request.data.get("pnr_number") or "").strip()
        if not pnr_number:
            return Response(
                {"detail": "pnr_number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            try:
                transition(booking, "PNR_CREATED")
            except InvalidTransition as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            booking.pnr_number = pnr_number
            booking.save()

        return Response(
            {
                "message": "PNR submitted successfully.",
                "pnr_number": booking.pnr_number,
                "status": booking.status,
            }
        )

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel_booking(self, request, pk=None):
        user = request.user
        if getattr(user, "role", "") == "CUSTOMER":
            return Response(
                {"detail": "Customers cannot cancel group bookings."},
                status=status.HTTP_403_FORBIDDEN,
            )

        booking = self.get_object()
        with transaction.atomic():
            try:
                transition(booking, "CANCELLED")
            except InvalidTransition as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            booking.save()

        return Response(
            {
                "message": "Booking cancelled successfully.",
                "status": booking.status,
            }
        )

    @action(detail=True, methods=["post"], url_path="service-case")
    def create_service_case(self, request, pk=None):
        booking = self.get_object()
        kind = (request.data.get("kind") or "").upper()
        if kind not in {GroupServiceCase.KIND_REBOOK, GroupServiceCase.KIND_REFUND}:
            return Response(
                {"detail": "kind must be REBOOK or REFUND."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            step = int(request.data.get("step") or 1)
        except (TypeError, ValueError):
            step = 1
        step = max(1, min(step, 6))
        payload = request.data.get("payload") or {}
        if not isinstance(payload, dict):
            return Response(
                {"detail": "payload must be an object."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        case_status = GroupServiceCase.STATUS_SUBMITTED if step >= 6 else GroupServiceCase.STATUS_OPEN
        case = GroupServiceCase.objects.create(
            booking=booking,
            kind=kind,
            step=step,
            status=case_status,
            payload=payload,
        )
        return Response(GroupServiceCaseSerializer(case).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="passengers")
    def upload_passengers(self, request, pk=None):
        booking = self.get_object()
        if booking.status != "PNR_CREATED":
            return Response(
                {"detail": "Passengers can only be uploaded after PNR is created."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        passengers_data = request.data
        if not isinstance(passengers_data, list):
            return Response(
                {"detail": "Passenger list must be a list of objects."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = GroupPassengerSerializer(data=passengers_data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            booking.passengers.all().delete()
            serializer.save(booking=booking)
            try:
                transition(booking, "NAME_SUBMITTED")
            except InvalidTransition as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            booking.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="ticket")
    def issue_ticket(self, request, pk=None):
        user = request.user
        if not is_platform_admin(user):
            return Response(
                {"detail": "Only administrators can issue tickets."},
                status=status.HTTP_403_FORBIDDEN,
            )

        booking = self.get_object()
        if booking.status != "NAME_SUBMITTED":
            return Response(
                {"detail": "Booking must be in NAME_SUBMITTED status to issue a ticket."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pnr_number = request.data.get("pnr_number")
        if pnr_number:
            booking.pnr_number = pnr_number

        if not booking.pnr_number:
            return Response(
                {"detail": "PNR number is required to issue tickets."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            try:
                transition(booking, "TICKETED")
            except InvalidTransition as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            booking.save()

        return Response(
            {
                "message": "Ticket issued successfully.",
                "pnr_number": booking.pnr_number,
                "status": booking.status,
            }
        )

    @action(detail=True, methods=["post"], url_path="complete")
    def complete_booking(self, request, pk=None):
        user = request.user
        if not is_platform_admin(user):
            return Response(
                {"detail": "Only administrators can complete bookings."},
                status=status.HTTP_403_FORBIDDEN,
            )

        booking = self.get_object()
        if booking.status != "TICKETED":
            return Response(
                {"detail": "Booking must be in TICKETED status to complete."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            try:
                transition(booking, "COMPLETED")
            except InvalidTransition as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            booking.save()

        return Response(
            {
                "message": "Booking marked as COMPLETED successfully.",
                "status": booking.status,
            }
        )

    @action(detail=True, methods=["post"], url_path="change-request")
    def create_change_request(self, request, pk=None):
        booking = self.get_object()
        if booking.status in ("COMPLETED", "CANCELLED"):
            return Response(
                {"detail": "Cannot request size changes on a completed or cancelled booking."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = GroupChangeRequestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(booking=booking)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["patch"], url_path=r"change-request/(?P<cr_id>[^/.]+)/resolve")
    def resolve_change_request(self, request, pk=None, cr_id=None):
        user = request.user
        if not is_platform_admin(user):
            return Response(
                {"detail": "Only administrators can resolve change requests."},
                status=status.HTTP_403_FORBIDDEN,
            )

        booking = self.get_object()

        try:
            import uuid

            is_uuid = False
            try:
                uuid.UUID(cr_id)
                is_uuid = True
            except ValueError:
                pass

            if is_uuid:
                cr = booking.change_requests.get(id=cr_id)
            else:
                cr = booking.change_requests.get(change_request_id=cr_id)
        except GroupChangeRequest.DoesNotExist:
            return Response(
                {"detail": "Change request not found for this booking."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if cr.status != "PENDING_REVIEW":
            return Response(
                {"detail": "This change request has already been resolved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        resolution_status = request.data.get("status")
        if resolution_status not in ["APPROVED", "REJECTED"]:
            return Response(
                {"detail": "Status must be either APPROVED or REJECTED."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        admin_remarks = request.data.get("admin_remarks")
        adjusted_fare = request.data.get("adjusted_fare_per_pax")

        with transaction.atomic():
            cr.status = resolution_status
            if admin_remarks:
                cr.admin_remarks = admin_remarks
            if adjusted_fare is not None:
                try:
                    cr.adjusted_fare_per_pax = Decimal(str(adjusted_fare))
                except ValueError:
                    return Response(
                        {"detail": "Invalid adjusted_fare_per_pax format."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            cr.save()

            if resolution_status == "APPROVED":
                delta = cr.pax_delta
                if cr.change_type == "UPSIZE":
                    booking.pax_adults += delta
                elif cr.change_type == "DOWNSIZE":
                    if booking.pax_adults >= delta:
                        booking.pax_adults -= delta
                    else:
                        remaining = delta - booking.pax_adults
                        booking.pax_adults = 0
                        if booking.pax_children >= remaining:
                            booking.pax_children -= remaining
                        else:
                            booking.pax_children = 0

                if cr.adjusted_fare_per_pax is not None:
                    booking.expected_fare_per_pax = cr.adjusted_fare_per_pax
                booking.save()

        return Response(
            {
                "message": f"Change request {resolution_status.lower()} successfully.",
                "change_request": GroupChangeRequestSerializer(cr).data,
                "booking_pax_adults": booking.pax_adults,
                "booking_pax_children": booking.pax_children,
                "booking_expected_fare": booking.expected_fare_per_pax,
            }
        )
