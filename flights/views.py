from rest_framework import views, status, permissions
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from .serializers import (
    FlightSearchRequestSerializer,
    FlightRevalidateRequestSerializer,
    FlightInventoryCreateSerializer,
    FlightInventoryResponseSerializer,
    SearchResponseSerializer,
    RevalidateResponseSerializer,
)
from .models import FlightInventory
from .services import ProviderService, ProviderAPIException

class FlightSearchView(views.APIView):
    """
    Exposes a public API endpoint to search for flight options.
    Integrates seamlessly with the external FlyShop UAT API provider.
    """
    permission_classes = (permissions.AllowAny,)

    @extend_schema(
        request=FlightSearchRequestSerializer,
        summary="Search Flights",
        description="Searches for flights matching origin, destination, travel dates, passenger counts, and travel class. Supports both one-way and round-trip searches."
        ,
        responses={200: OpenApiResponse(response=SearchResponseSerializer)}
    )
    def post(self, request, *args, **kwargs):
        serializer = FlightSearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Invoke third-party provider integration through service layer
        search_results = ProviderService.search_flights(serializer.validated_data)
        
        return Response(
            data=search_results,
            status=status.HTTP_200_OK
        )


class FlightRevalidateView(views.APIView):
    """
    Revalidates a selected flight and fare before booking.
    """
    permission_classes = (permissions.AllowAny,)

    @extend_schema(
        request=FlightRevalidateRequestSerializer,
        summary="Revalidate Flight Fare",
        description="Checks whether a selected flight and fare are still valid before booking."
        ,
        responses={200: OpenApiResponse(response=RevalidateResponseSerializer)}
    )
    def post(self, request, *args, **kwargs):
        serializer = FlightRevalidateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        revalidate_result = ProviderService.reprice_flight(serializer.validated_data)

        return Response(
            data=revalidate_result,
            status=status.HTTP_200_OK
        )


class FlightSSRView(views.APIView):
    """
    Retrieves pre-booking SSR options (seat maps, meals, baggage, wheelchair) for a selected flight.
    """
    permission_classes = (permissions.AllowAny,)

    def post(self, request, *args, **kwargs):
        search_key = request.data.get('search_key')
        flight_key = request.data.get('flight_key')
        if not search_key or not flight_key:
            return Response(
                {"detail": "search_key and flight_key are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            ssr_options = ProviderService.get_pre_ssr(search_key, flight_key)
        except ProviderAPIException as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_502_BAD_GATEWAY
            )

        return Response(ssr_options, status=status.HTTP_200_OK)


class FlightInventoryView(views.APIView):
    """
    Creates locally managed agent inventory flights used by the sale flow.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        if not (
            request.user.is_staff
            or getattr(request.user, "role", None) in {"ADMIN", "AGENT"}
        ):
            return Response(
                {"detail": "Only agents or admins can view flight inventory."},
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = FlightInventory.objects.all()
        if not (request.user.is_staff or getattr(request.user, "role", None) == "ADMIN"):
            queryset = queryset.filter(created_by=request.user)

        serializer = FlightInventoryResponseSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=FlightInventoryCreateSerializer,
        responses={201: OpenApiResponse(response=FlightInventoryResponseSerializer)},
        summary="Create Flight Inventory",
        description="Creates a locally managed flight inventory record for agent sale flows.",
    )
    def post(self, request, *args, **kwargs):
        if not (
            request.user.is_staff
            or getattr(request.user, "role", None) in {"ADMIN", "AGENT"}
        ):
            return Response(
                {"detail": "Only agents or admins can create flight inventory."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = FlightInventoryCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        inventory = serializer.save()

        response_serializer = FlightInventoryResponseSerializer(inventory)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
