from rest_framework import serializers
from .models import AgentWallet


class AgentWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentWallet
        fields = ("id", "balance", "currency", "updated_at")
        read_only_fields = fields
