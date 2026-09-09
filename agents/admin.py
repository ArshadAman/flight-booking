from django.contrib import admin
from .models import InventoryRestriction, AgentAuditLog


@admin.register(InventoryRestriction)
class InventoryRestrictionAdmin(admin.ModelAdmin):
    list_display = ("scope", "airline_code", "origin", "destination", "is_blocked", "agent", "reason", "created_at")
    list_filter = ("scope", "is_blocked")
    search_fields = ("airline_code", "airline_name", "origin", "destination", "reason")


@admin.register(AgentAuditLog)
class AgentAuditLogAdmin(admin.ModelAdmin):
    list_display = ("entry", "action_type", "agent", "performed_by", "created_at")
    list_filter = ("action_type",)
    search_fields = ("entry", "reference", "agent__username")
