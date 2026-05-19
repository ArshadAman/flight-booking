from rest_framework import views, status, permissions
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from .serializers import FlightSearchRequestSerializer
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
