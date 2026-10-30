from rest_framework import serializers
from .models import AgentWallet, DepositRequest


class AgentWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentWallet
        fields = ("id", "balance", "currency", "updated_at")
        read_only_fields = fields


class DepositRequestSerializer(serializers.ModelSerializer):
    agent_id = serializers.UUIDField(source="agent.id", read_only=True)
    agent_name = serializers.SerializerMethodField()
    agent_email = serializers.EmailField(source="agent.email", read_only=True)

    class Meta:
        model = DepositRequest
        fields = (
            "id",
            "agent_id",
            "agent_name",
            "agent_email",
            "request_id",
            "amount",
            "payment_mode",
            "bank_name",
            "utr_number",
            "deposit_date",
            "deposit_slip",
            "status",
            "remarks",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "request_id", "created_at", "updated_at")

    def get_agent_name(self, obj):
        profile = getattr(obj.agent, "company_profile", None)
        if profile and profile.company_name:
            return profile.company_name
        full = obj.agent.get_full_name().strip()
        return full or obj.agent.username
