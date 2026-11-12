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
    agent_id = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            'id',
            'user',
            'user_email',
            'user_name',
            'passenger_count',
            'is_agent_booking',
            'agent_id',
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
            'booking_channel',
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
            'agent_id',
            'created_at',
            'updated_at'
        ]

    def get_agent_id(self, obj):
        inv = getattr(obj, "agent_flight_inventory", None)
        if inv is not None and getattr(inv, "agent_id", None):
            return str(inv.agent_id)
        return None

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
    gender = serializers.CharField(
        required=False,
        allow_blank=True,
        default="0",
        help_text="Gender: 0/M/Male or 1/F/Female.",
    )

    def validate_gender(self, value):
        raw = str(value).strip().upper() if value is not None else "0"
        if raw in {"0", "M", "MALE"}:
            return 0
        if raw in {"1", "F", "FEMALE"}:
            return 1
        raise serializers.ValidationError("Gender must be 0/M or 1/F.")
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
    ticket_number = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Optional per-passenger airline ticket number.",
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
        max_length=512,
        required=True,
        allow_blank=False,
        help_text="Required reason / remarks for cancellation."
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


class TicketCancellationSerializer(serializers.ModelSerializer):
    agent_username = serializers.SerializerMethodField()
    agent_display_name = serializers.SerializerMethodField()

    class Meta:
        from .models import TicketCancellation
        model = TicketCancellation
        fields = (
            "id",
            "claim_id",
            "ticket",
            "requested_by",
            "agent_username",
            "agent_display_name",
            "pnr",
            "passenger_name",
            "sector",
            "travel_date",
            "fare_paid",
            "airline_penalty",
            "agent_service_fee",
            "refund_amount",
            "status",
            "reason",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "claim_id",
            "requested_by",
            "agent_username",
            "agent_display_name",
            "pnr",
            "passenger_name",
            "sector",
            "travel_date",
            "fare_paid",
            "refund_amount",
            "status",
            "created_at",
            "updated_at",
        )

    def get_agent_username(self, obj):
        if obj.requested_by_id:
            return getattr(obj.requested_by, "username", "") or ""
        inv = getattr(obj.ticket, "agent_flight_inventory", None) if obj.ticket_id else None
        if inv and inv.agent_id:
            return getattr(inv.agent, "username", "") or ""
        return ""

    def get_agent_display_name(self, obj):
        user = obj.requested_by
        if user:
            full = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
            if full:
                return full
            company = getattr(user, "company_name", None)
            if company:
                return str(company)
            return getattr(user, "username", "") or ""
        return self.get_agent_username(obj) or "—"

    def validate(self, attrs):
        from .models import TicketCancellation, Ticket

        request = self.context.get("request")
        ticket = attrs.get("ticket") or getattr(self.instance, "ticket", None)
        if self.instance is None:
            if not ticket:
                raise serializers.ValidationError({"ticket": "Ticket is required for a refund claim."})
            if ticket.status not in (Ticket.STATUS_CONFIRMED, Ticket.STATUS_PENDING):
                raise serializers.ValidationError(
                    {"ticket": "Refund claims are only allowed for confirmed or pending bookings."}
                )
            if TicketCancellation.objects.filter(
                ticket=ticket, status=TicketCancellation.STATUS_PENDING
            ).exists():
                raise serializers.ValidationError(
                    {"ticket": "A pending refund claim already exists for this booking."}
                )
            user = getattr(request, "user", None)
            if user and not getattr(user, "is_staff", False):
                from accounts.permissions import is_platform_admin

                if not is_platform_admin(user):
                    can = ticket.user_id == user.id or (
                        ticket.agent_flight_inventory_id
                        and ticket.agent_flight_inventory.agent_id == user.id
                    )
                    if not can:
                        raise serializers.ValidationError(
                            {"ticket": "You do not have permission to request a refund on this booking."}
                        )
        return attrs

    def create(self, validated_data):
        from decimal import Decimal
        from .models import TicketCancellation

        request = self.context["request"]
        ticket = validated_data["ticket"]
        reason = validated_data.get("reason") or ""
        airline_penalty = validated_data.get("airline_penalty", Decimal("5000"))
        agent_service_fee = validated_data.get("agent_service_fee", Decimal("500"))
        fare_paid = Decimal(str(ticket.total_amount or 0))
        refund_amount = max(Decimal("0"), fare_paid - airline_penalty - agent_service_fee)

        pax = ticket.passengers_data or []
        primary = pax[0] if isinstance(pax, list) and pax else {}
        passenger_name = " ".join(
            str(primary.get(k) or "").strip()
            for k in ("first_name", "last_name")
            if primary.get(k)
        ).strip() or getattr(ticket.user, "username", "Passenger")

        travel_date = None
        if ticket.departure_datetime:
            travel_date = ticket.departure_datetime.date()

        return TicketCancellation.objects.create(
            ticket=ticket,
            requested_by=request.user,
            pnr=ticket.pnr_number or "",
            passenger_name=passenger_name,
            sector=f"{ticket.origin or ''}-{ticket.destination or ''}".strip("-") or "—",
            travel_date=travel_date,
            fare_paid=fare_paid,
            airline_penalty=airline_penalty,
            agent_service_fee=agent_service_fee,
            refund_amount=refund_amount,
            reason=reason,
            status=TicketCancellation.STATUS_PENDING,
        )


class TicketAmendmentSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import TicketAmendment
        model = TicketAmendment
        fields = (
            "id",
            "amendment_id",
            "ticket",
            "pnr",
            "passenger_name",
            "amendment_type",
            "old_value",
            "new_value",
            "fare_difference",
            "service_fee",
            "total_payable",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "amendment_id", "created_at", "updated_at")
