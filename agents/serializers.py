from rest_framework import serializers
from .models import InventoryRestriction, AgentAuditLog, Supplier, Notice, AgentCommission


class InventoryRestrictionSerializer(serializers.ModelSerializer):
    agent_username = serializers.CharField(source="agent.username", read_only=True, allow_null=True)

    class Meta:
        model = InventoryRestriction
        fields = [
            "id",
            "agent",
            "agent_username",
            "scope",
            "airline_code",
            "airline_name",
            "origin",
            "destination",
            "is_blocked",
            "reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "agent_username"]

    def validate(self, attrs):
        scope = attrs.get("scope") or getattr(self.instance, "scope", None)
        airline = (attrs.get("airline_code") or getattr(self.instance, "airline_code", "") or "").strip().upper()
        origin = (attrs.get("origin") or getattr(self.instance, "origin", "") or "").strip().upper()
        dest = (attrs.get("destination") or getattr(self.instance, "destination", "") or "").strip().upper()

        if "airline_code" in attrs:
            attrs["airline_code"] = airline
        if "origin" in attrs:
            attrs["origin"] = origin
        if "destination" in attrs:
            attrs["destination"] = dest

        if scope == InventoryRestriction.SCOPE_AIRLINE and not airline:
            raise serializers.ValidationError({"airline_code": "Airline code is required for airline blocks."})
        if scope == InventoryRestriction.SCOPE_ROUTE and (not origin or not dest):
            raise serializers.ValidationError({"origin": "Origin and destination are required for route blocks."})
        return attrs


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = (
            "id",
            "code",
            "name",
            "contact_name",
            "email",
            "phone",
            "status",
            "inventory_count",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "code", "created_at", "updated_at")


class AgentAuditLogSerializer(serializers.ModelSerializer):
    by_agent = serializers.SerializerMethodField()

    class Meta:
        model = AgentAuditLog
        fields = (
            "id",
            "action_type",
            "entry",
            "reference",
            "metadata",
            "by_agent",
            "created_at",
        )
        read_only_fields = fields

    def get_by_agent(self, obj):
        user = obj.performed_by or obj.agent
        if not user:
            return "AGT"
        base = "".join(ch for ch in f"{user.first_name}{user.last_name}{user.username}" if ch.isalpha())
        return (base.upper()[:3] or "AGT")


class NoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notice
        fields = ("id", "category", "label", "title", "body", "is_active", "created_at")
        read_only_fields = ("id", "created_at")


class AgentCommissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentCommission
        fields = ("id", "category", "method", "markup", "updated_at")
        read_only_fields = ("id", "updated_at")
