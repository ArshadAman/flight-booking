from rest_framework import serializers
from .models import Ticket

class TicketSerializer(serializers.ModelSerializer):
    """
    ModelSerializer mapping all details of a passenger ticket.
    """
    user_email = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    passenger_count = serializers.SerializerMethodField()
    is_agent_booking = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            'id',
            'user',
            'user_email',
            'user_name',
            'passenger_count',
            'is_agent_booking',
            'agent_flight_inventory',
            'agent_cancellation_reason',
            'pnr_number',
            'ticket_number',
            'booking_ref',
            'flight_id',
            'status',
            'origin',
            'destination',
            'departure_datetime',
            'arrival_datetime',
            'travel_type',
            'airline_code',
            'airline_name',
            'flight_number',
            'cabin_class',
            'basic_amount',
            'tax_amount',
            'total_amount',
            'currency',
            'baggage_check_in',
            'baggage_hand',
            'is_refundable',
            'food_onboard',
            'segments_data',
            'passengers_data',
            'ssr_data',
            'cancellation_data',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'user',
            'user_email',
            'user_name',
            'passenger_count',
            'is_agent_booking',
            'created_at',
            'updated_at'
        ]

    def get_user_email(self, obj):
        user = getattr(obj, 'user', None)
        return getattr(user, 'email', None) or ''

    def get_user_name(self, obj):
        user = getattr(obj, 'user', None)
        if not user:
            return ''
        name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
        return name or getattr(user, 'username', '') or getattr(user, 'email', '') or ''

    def get_passenger_count(self, obj):
        data = obj.passengers_data or []
        return len(data) if isinstance(data, list) else 0

    def get_is_agent_booking(self, obj):
        return bool(obj.agent_flight_inventory_id)


class PassengerDetailsSerializer(serializers.Serializer):
    """
    Serializer to validate individual passenger manifests.
    """
    pax_type = serializers.IntegerField(
        default=0,
        help_text="Passenger type mapping (0 = Adult, 1 = Child, 2 = Infant)."
    )
    title = serializers.CharField(
        max_length=10,
        default="Mr",
        help_text="Title, e.g. Mr, Mrs, Ms."
    )
    first_name = serializers.CharField(
        max_length=100,
        help_text="Passenger first name."
    )
    last_name = serializers.CharField(
        max_length=100,
        help_text="Passenger last name."
    )
    gender = serializers.IntegerField(
        default=0,
        help_text="Gender mapping (0 = Male, 1 = Female)."
    )
    dob = serializers.DateField(
        required=False,
        allow_null=True,
        help_text="Date of birth in YYYY-MM-DD format."
    )
    passport_number = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Passport number (required for international sectors)."
    )
    outbound_meal = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Selected outbound meal code."
    )
    return_meal = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Selected return meal code."
    )
    meal_code = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Primary meal code."
    )
    pancard_number = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Pan card identifier (optional, for tax validations)."
    )
    student_id = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Student ID card number (required for student fares)."
    )
    defence_service_id = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Defence Service ID card number (required for defence/military/airforce fares)."
    )
    defence_issue_date = serializers.DateField(
        required=False,
        allow_null=True,
        help_text="Defence card issue date in YYYY-MM-DD format."
    )
    defence_expiry_date = serializers.DateField(
        required=False,
        allow_null=True,
        help_text="Defence card expiry date in YYYY-MM-DD format."
    )


class TicketPurchaseRequestSerializer(serializers.Serializer):
    """
    Serializer mapping the flight booking purchase/issuance payload.
    """
    search_key = serializers.CharField(
        max_length=4096,
        help_text="Search session token returned by search flights."
    )
    flight_key = serializers.CharField(
        max_length=8192,
        help_text="Itinerary selection key returned by search flights."
    )
    fare_id = serializers.CharField(
        max_length=128,
        help_text="Fare pricing selection key returned by search flights."
    )
    customer_mobile = serializers.CharField(
        max_length=20,
        help_text="Customer agency mobile number contact."
    )
    passenger_mobile = serializers.CharField(
        max_length=20,
        help_text="Primary passenger contact mobile number."
    )
    passenger_email = serializers.EmailField(
        help_text="Primary passenger booking notification email address."
    )
    passengers = PassengerDetailsSerializer(
        many=True,
        help_text="List of passenger detail dicts included in ticket booking."
    )
    travel_type = serializers.IntegerField(
        required=False,
        default=0,
        help_text="0=One-Way, 1=Round-Trip, 2=Multi-City."
    )
    gst_input = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Whether GST details should be included during revalidation."
    )
    single_pricing = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Whether the provider should return a single pricing quote."
    )
    source_type = serializers.IntegerField(
        required=False,
        default=0,
        help_text="Provider source type flag for Air_Reprice."
    )
    booking_ssr_details = serializers.JSONField(
        required=False,
        default=list,
        help_text="Optional list of pre-booking SSR choices, e.g. [{'Pax_Id': 1, 'SSR_Key': '...'}]"
    )


class TicketCancelRequestSerializer(serializers.Serializer):
    """
    Serializer for ticket cancellation requests.
    """
    remarks = serializers.CharField(
        max_length=256,
        required=False,
        default="Customer requested cancellation",
        help_text="Optional reason for cancellation."
    )
    cancellation_type = serializers.IntegerField(
        required=False,
        default=0,
        help_text="0 for User Initiated, 1 for Airline Initiated / Schedule Change."
    )
    cancel_code = serializers.CharField(
        max_length=10,
        required=False,
        default="005",
        help_text="FlyShop GDS cancel code classification."
    )
