from rest_framework import serializers
from .models import AgentWallet, DepositRequest


class AgentWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentWallet
        fields = ("id", "balance", "currency", "updated_at")
        read_only_fields = fields


class DepositRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = DepositRequest
        fields = (
            "id",
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
