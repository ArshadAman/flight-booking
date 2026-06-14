from rest_framework import views, status, permissions, viewsets
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from accounts.permissions import IsAgentUser
from .models import AgentFlightInventory
from .serializers import (
    FlightSearchRequestSerializer,
    FlightRevalidateRequestSerializer,
    SearchResponseSerializer,
    RevalidateResponseSerializer,
    AgentFlightInventorySerializer,
)
from .services import ProviderService


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


class AgentFlightInventoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for agents to manage their pre-purchased flight inventory.
    """
    serializer_class = AgentFlightInventorySerializer
    permission_classes = [permissions.IsAuthenticated, IsAgentUser]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'ADMIN' or user.is_staff:
            return AgentFlightInventory.objects.all()
        return AgentFlightInventory.objects.filter(agent=user)

    def perform_create(self, serializer):
        serializer.save(agent=self.request.user)

