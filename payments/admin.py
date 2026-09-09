from django.contrib import admin
from .models import AgentWallet


@admin.register(AgentWallet)
class AgentWalletAdmin(admin.ModelAdmin):
    list_display = ("agent", "balance", "currency", "updated_at")
    search_fields = ("agent__username", "agent__email")
    readonly_fields = ("created_at", "updated_at")
