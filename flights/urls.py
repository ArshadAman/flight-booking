from django.urls import path
from .views import FlightSearchView, FlightRevalidateView, FlightSSRView

urlpatterns = [
    path('search/', FlightSearchView.as_view(), name='flight_search'),
    path('revalidate/', FlightRevalidateView.as_view(), name='flight_revalidate'),
    path('ssr/', FlightSSRView.as_view(), name='flight_ssr'),
]
