from django.contrib import admin
from bookings.models import GroupBooking, GroupQuote, GroupPassenger, GroupChangeRequest

@admin.register(GroupBooking)
class GroupBookingAdmin(admin.ModelAdmin):
    list_display = ('request_id', 'group_name', 'status', 'origin', 'destination', 'departure_date', 'total_paid')
    list_filter = ('status', 'trip_type', 'cabin_class')
    search_fields = ('request_id', 'group_name', 'pnr_number')

@admin.register(GroupQuote)
class GroupQuoteAdmin(admin.ModelAdmin):
    list_display = ('booking', 'quote_option_id', 'airline', 'flight_number', 'fare_per_pax', 'is_selected')
    list_filter = ('is_selected', 'airline')
    search_fields = ('booking__request_id', 'quote_option_id')

@admin.register(GroupPassenger)
class GroupPassengerAdmin(admin.ModelAdmin):
    list_display = ('booking', 'first_name', 'last_name', 'gender', 'passport_number')
    search_fields = ('booking__request_id', 'first_name', 'last_name', 'passport_number')

@admin.register(GroupChangeRequest)
class GroupChangeRequestAdmin(admin.ModelAdmin):
    list_display = ('booking', 'change_request_id', 'change_type', 'pax_delta', 'status')
    list_filter = ('change_type', 'status')
    search_fields = ('booking__request_id', 'change_request_id')
