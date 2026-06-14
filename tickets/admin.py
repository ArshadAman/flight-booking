from django.contrib import admin
from .models import Ticket


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        'ticket_number', 'pnr_number', 'booking_ref',
        'user', 'origin', 'destination',
        'departure_datetime', 'airline_name', 'status',
        'total_amount', 'currency', 'created_at',
    ]
    list_filter = ['status', 'travel_type', 'airline_code', 'currency']
    search_fields = [
        'ticket_number', 'pnr_number', 'booking_ref',
        'user__username', 'user__email',
        'origin', 'destination',
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
