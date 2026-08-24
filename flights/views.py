import csv
import io
from datetime import timedelta

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import views, status, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse
from accounts.permissions import IsAgentUser, IsAdminUser, is_platform_admin
from .models import AgentFlightInventory, InventoryHold
from .serializers import (
    FlightSearchRequestSerializer,
    FlightRevalidateRequestSerializer,
    FlightInventoryCreateSerializer,
    FlightInventoryResponseSerializer,
    SearchResponseSerializer,
    RevalidateResponseSerializer,
    AgentFlightInventorySerializer,
    PublicForSaleInventorySerializer,
    InventoryHoldSerializer,
)
from .services import ProviderService, ProviderAPIException
from .inventory_rules import apply_inventory_channel_filters, inventory_is_restricted


class FlightSearchView(views.APIView):
    permission_classes = (permissions.AllowAny,)

    @extend_schema(
        request=FlightSearchRequestSerializer,
        summary="Search Flights",
        responses={200: OpenApiResponse(response=SearchResponseSerializer)},
    )
    def post(self, request, *args, **kwargs):
        serializer = FlightSearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        search_results = ProviderService.search_flights(serializer.validated_data)
        return Response(data=search_results, status=status.HTTP_200_OK)


class FlightRevalidateView(views.APIView):
    permission_classes = (permissions.AllowAny,)

    @extend_schema(
        request=FlightRevalidateRequestSerializer,
        summary="Revalidate Flight Fare",
        responses={200: OpenApiResponse(response=RevalidateResponseSerializer)},
    )
    def post(self, request, *args, **kwargs):
        serializer = FlightRevalidateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        revalidate_result = ProviderService.reprice_flight(serializer.validated_data)
        return Response(data=revalidate_result, status=status.HTTP_200_OK)


class FlightSSRView(views.APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request, *args, **kwargs):
        search_key = request.data.get("search_key")
        flight_key = request.data.get("flight_key")
        if not search_key or not flight_key:
            return Response(
                {"detail": "search_key and flight_key are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            ssr_options = ProviderService.get_pre_ssr(search_key, flight_key)
        except ProviderAPIException as e:
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(ssr_options, status=status.HTTP_200_OK)


class PublicForSaleInventoryView(views.APIView):
    """Public catalog of published agent offline inventory for For Sale storefronts."""

    permission_classes = (permissions.AllowAny,)

    def get(self, request, *args, **kwargs):
        qs = AgentFlightInventory.objects.filter(
            departure_datetime__gte=timezone.now(),
        ).select_related("agent").order_by("departure_datetime")

        partner = (request.query_params.get("partner") or request.query_params.get("agent") or "").strip()
        if partner:
            qs = qs.filter(agent_id=partner)

        qs = apply_inventory_channel_filters(qs, agent_id=partner or None)
        # Prefer sellable seats (available - held)
        qs = [row for row in qs if row.sellable_seats > 0 or row.waitlist_count >= 0]
        # Keep rows with sellable seats for bookable list; waitlist-only still listed if sold out
        bookable = [row for row in qs if row.sellable_seats > 0]
        sold_out_waitlist = [row for row in qs if row.sellable_seats <= 0]
        # Show bookable first, then sold-out (for waitlist CTA)
        ordered = bookable + sold_out_waitlist

        origin = (request.query_params.get("origin") or "").strip().upper()
        destination = (request.query_params.get("destination") or "").strip().upper()
        if origin:
            ordered = [r for r in ordered if r.origin == origin]
        if destination:
            ordered = [r for r in ordered if r.destination == destination]

        serializer = PublicForSaleInventorySerializer(ordered, many=True)
        return Response({"results": serializer.data, "count": len(serializer.data)})


class InventoryHoldViewSet(viewsets.ModelViewSet):
    """Create seat holds / waitlist entries for offline inventory."""

    serializer_class = InventoryHoldSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = InventoryHold.objects.select_related("inventory", "user").all()
        if is_platform_admin(user):
            return qs
        if getattr(user, "role", "") == "AGENT":
            return qs.filter(inventory__agent=user)
        return qs.filter(user=user)

    def create(self, request, *args, **kwargs):
        inventory_id = request.data.get("inventory")
        seats = int(request.data.get("seats") or 1)
        prefer_waitlist = str(request.data.get("prefer_waitlist") or "").lower() in {"1", "true", "yes"}

        try:
            inv = AgentFlightInventory.objects.get(id=inventory_id)
        except AgentFlightInventory.DoesNotExist:
            return Response({"detail": "Inventory not found."}, status=status.HTTP_404_NOT_FOUND)

        if not inv.is_published or not inv.is_enabled or inventory_is_restricted(inv):
            return Response({"detail": "Inventory is not available."}, status=status.HTTP_400_BAD_REQUEST)

        if seats < 1:
            return Response({"detail": "Seats must be at least 1."}, status=status.HTTP_400_BAD_REQUEST)

        if inv.sellable_seats >= seats and not prefer_waitlist:
            hold_status = InventoryHold.STATUS_HOLD
            inv.seats_held = int(inv.seats_held or 0) + seats
            inv.save(update_fields=["seats_held", "updated_at"])
            expires = timezone.now() + timedelta(hours=24)
        else:
            hold_status = InventoryHold.STATUS_WAITLIST
            inv.waitlist_count = int(inv.waitlist_count or 0) + seats
            inv.save(update_fields=["waitlist_count", "updated_at"])
            expires = None

        hold = InventoryHold.objects.create(
            inventory=inv,
            user=request.user,
            status=hold_status,
            seats=seats,
            contact_name=request.data.get("contact_name") or "",
            contact_email=request.data.get("contact_email") or getattr(request.user, "email", "") or "",
            contact_mobile=request.data.get("contact_mobile") or "",
            notes=request.data.get("notes") or "",
            expires_at=expires,
        )
        return Response(InventoryHoldSerializer(hold).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, *args, **kwargs):
        hold = self.get_object()
        if hold.status in {InventoryHold.STATUS_CANCELLED, InventoryHold.STATUS_EXPIRED, InventoryHold.STATUS_CONFIRMED}:
            return Response({"detail": f"Hold already {hold.status}."}, status=status.HTTP_400_BAD_REQUEST)

        inv = hold.inventory
        if hold.status == InventoryHold.STATUS_HOLD:
            inv.seats_held = max(0, int(inv.seats_held or 0) - hold.seats)
            inv.save(update_fields=["seats_held", "updated_at"])
        elif hold.status == InventoryHold.STATUS_WAITLIST:
            inv.waitlist_count = max(0, int(inv.waitlist_count or 0) - hold.seats)
            inv.save(update_fields=["waitlist_count", "updated_at"])

        hold.status = InventoryHold.STATUS_CANCELLED
        hold.save(update_fields=["status", "updated_at"])
        return Response(InventoryHoldSerializer(hold).data)


class AgentFlightInventoryViewSet(viewsets.ModelViewSet):
    """ViewSet for agents to manage their pre-purchased flight inventory."""

    permission_classes = [permissions.IsAuthenticated, IsAgentUser]

    def get_serializer_class(self):
        if self.action == "create":
            return FlightInventoryCreateSerializer
        if self.action in ["list", "retrieve"]:
            return FlightInventoryResponseSerializer
        return AgentFlightInventorySerializer

    def get_queryset(self):
        user = self.request.user
        qs = AgentFlightInventory.objects.select_related("agent").all()
        if getattr(user, "role", "") == "ADMIN" or user.is_staff:
            agent = self.request.query_params.get("agent")
            if agent:
                qs = qs.filter(agent_id=agent)
            return qs.order_by("-created_at")
        return qs.filter(agent=user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(agent=self.request.user)

    def partial_update(self, request, *args, **kwargs):
        # Only admins may flip is_enabled
        if "is_enabled" in request.data and not is_platform_admin(request.user):
            data = dict(request.data)
            data.pop("is_enabled", None)
            request._full_data = data
        return super().partial_update(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request, *args, **kwargs):
        """Citizenplane-style inventory export (CSV or JSON)."""
        fmt = (request.query_params.get("format") or "csv").lower()
        qs = self.get_queryset()
        rows = []
        for inv in qs:
            rows.append(
                {
                    "id": str(inv.id),
                    "partner": getattr(inv.agent, "username", ""),
                    "partner_id": str(inv.agent_id),
                    "airline_code": inv.airline_code,
                    "airline_name": inv.airline_name,
                    "flight_number": inv.flight_number,
                    "origin": inv.origin,
                    "destination": inv.destination,
                    "departure_datetime": inv.departure_datetime.isoformat(),
                    "arrival_datetime": inv.arrival_datetime.isoformat(),
                    "cabin_class": inv.cabin_class,
                    "seats_available": inv.seats_available,
                    "seats_held": inv.seats_held,
                    "sellable_seats": inv.sellable_seats,
                    "waitlist_count": inv.waitlist_count,
                    "price": str(inv.price),
                    "currency": "INR",
                    "is_published": inv.is_published,
                    "is_enabled": inv.is_enabled,
                    "is_refundable": inv.is_refundable,
                    "baggage_check_in": inv.baggage_check_in,
                    "baggage_hand": inv.baggage_hand,
                    "duration": inv.duration,
                }
            )

        if fmt == "json":
            return Response({"results": rows, "count": len(rows), "format": "citizenplane-compatible"})

        buffer = io.StringIO()
        fieldnames = list(rows[0].keys()) if rows else [
            "id", "partner", "airline_code", "flight_number", "origin", "destination",
            "departure_datetime", "seats_available", "price", "is_published",
        ]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        response = HttpResponse(buffer.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="inventory_export.csv"'
        return response

    @action(detail=False, methods=["get"], url_path="analytics")
    def analytics(self, request, *args, **kwargs):
        qs = self.get_queryset()
        total = qs.count()
        published = qs.filter(is_published=True, is_enabled=True).count()
        seats = sum(int(x.seats_available or 0) for x in qs)
        held = sum(int(x.seats_held or 0) for x in qs)
        waitlist = sum(int(x.waitlist_count or 0) for x in qs)
        value = sum(float(x.price or 0) * max(0, int(x.seats_available or 0)) for x in qs)
        return Response(
            {
                "listings": total,
                "published": published,
                "seats_available": seats,
                "seats_held": held,
                "waitlist_count": waitlist,
                "inventory_value_inr": round(value, 2),
            }
        )
