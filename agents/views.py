from rest_framework import viewsets, permissions
from accounts.permissions import IsAdminUser
from .models import InventoryRestriction
from .serializers import InventoryRestrictionSerializer


class InventoryRestrictionViewSet(viewsets.ModelViewSet):
    """Admin CRUD for airline/route inventory blocks."""

    serializer_class = InventoryRestrictionSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    queryset = InventoryRestriction.objects.select_related("agent").all()

    def get_queryset(self):
        qs = super().get_queryset()
        scope = (self.request.query_params.get("scope") or "").upper()
        if scope in {InventoryRestriction.SCOPE_AIRLINE, InventoryRestriction.SCOPE_ROUTE}:
            qs = qs.filter(scope=scope)
        agent = self.request.query_params.get("agent")
        if agent:
            qs = qs.filter(agent_id=agent)
        return qs
