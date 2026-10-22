from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

api_urlpatterns = [
    path("auth/", include("accounts.urls")),
    path("flights/", include("flights.urls")),
    path("bookings/", include("bookings.urls")),
    path("payments/", include("payments.urls")),
    path("agents/", include("agents.urls")),
    path("tickets/", include("tickets.urls")),
    path("reports/", include("reports.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_urlpatterns)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("doc/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
