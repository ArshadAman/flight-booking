from django.urls import path
from .views import FlightSearchView, FlightRevalidateView

urlpatterns = [
    path('search/', FlightSearchView.as_view(), name='flight_search'),
    path('revalidate/', FlightRevalidateView.as_view(), name='flight_revalidate'),
]
