from rest_framework import viewsets, permissions, generics
from accounts.permissions import IsAdminUser, IsAgentUser, is_platform_admin
from .models import InventoryRestriction, AgentAuditLog
from .serializers import InventoryRestrictionSerializer, AgentAuditLogSerializer


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


class AgentHistoryListView(generics.ListAPIView):
    """
    GET /api/v1/agents/history/
    Offline portal History feed for the authenticated agent.
    """

    serializer_class = AgentAuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsAgentUser]

    def get_queryset(self):
        user = self.request.user
        qs = AgentAuditLog.objects.select_related("agent", "performed_by").all()
        if is_platform_admin(user) and self.request.query_params.get("agent"):
            return qs.filter(agent_id=self.request.query_params.get("agent"))
        return qs.filter(agent=user)
