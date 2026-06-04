from rest_framework import serializers
from datetime import date


class TripSegmentSerializer(serializers.Serializer):
    """One leg of a multi-city itinerary."""
    origin = serializers.CharField(max_length=3, min_length=3)
    destination = serializers.CharField(max_length=3, min_length=3)
    travel_date = serializers.DateField()

    def validate_origin(self, value):
        return value.strip().upper()

    def validate_destination(self, value):
        return value.strip().upper()


class FlightSearchRequestSerializer(serializers.Serializer):
    CLASS_ECONOMY = '0'
    CLASS_PREMIUM_ECONOMY = '1'
    CLASS_BUSINESS = '2'
    CLASS_FIRST = '3'

    CLASS_CHOICES = [
        (CLASS_ECONOMY, 'Economy'),
        (CLASS_PREMIUM_ECONOMY, 'Premium Economy'),
        (CLASS_BUSINESS, 'Business'),
        (CLASS_FIRST, 'First Class'),
    ]

    origin = serializers.CharField(
        max_length=3,
        min_length=3,
        help_text="3-letter IATA code for the departure airport, e.g., 'DEL'."
    )
    destination = serializers.CharField(
        max_length=3,
        min_length=3,
        help_text="3-letter IATA code for the arrival airport, e.g., 'BOM'."
    )
    travel_date = serializers.DateField(
        required=False,
        allow_null=True,
        help_text="Date of travel in YYYY-MM-DD format. Not required for multi-city."
    )
    return_date = serializers.DateField(
        required=False,
        allow_null=True,
        help_text="Date of return in YYYY-MM-DD format. Triggers round-trip search if provided."
    )
    travel_type = serializers.IntegerField(
        required=False,
        default=0,
        help_text="0=One-Way, 1=Round-Trip, 2=Multi-City."
    )
    trip_segments = TripSegmentSerializer(
        many=True,
        required=False,
        default=list,
        help_text="List of legs for multi-city searches. Requires travel_type=2."
    )
    adult_count = serializers.IntegerField(
        min_value=1,
        max_value=9,
        default=1,
        help_text="Number of adult passengers (12+ years)."
    )
    child_count = serializers.IntegerField(
        min_value=0,
        max_value=9,
        default=0,
        help_text="Number of child passengers (2-11 years)."
    )
    infant_count = serializers.IntegerField(
        min_value=0,
        max_value=9,
        default=0,
        help_text="Number of infant passengers (under 2 years)."
    )
    class_of_travel = serializers.ChoiceField(
        choices=CLASS_CHOICES,
        default=CLASS_ECONOMY,
        help_text="Cabin class: '0'=Economy, '1'=Premium Economy, '2'=Business, '3'=First Class."
    )
    airline_code = serializers.CharField(
        max_length=5,
        required=False,
        allow_blank=True,
        help_text="Filter results by specific airline carrier code, e.g., '6E'."
    )
    student_fare_search = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Whether to search specifically for student fare discounts."
    )
    defence_fare_search = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Whether to search specifically for defence/military/airforce discounts."
    )

    def validate_origin(self, value):
        return value.strip().upper()

    def validate_destination(self, value):
        return value.strip().upper()

    def validate_airline_code(self, value):
        if value:
            return value.strip().upper()
        return value

    def validate(self, attrs):
        travel_type = attrs.get('travel_type', 0)
        origin = attrs.get('origin')
        destination = attrs.get('destination')
        travel_date = attrs.get('travel_date')
        return_date = attrs.get('return_date')
        trip_segments = attrs.get('trip_segments', [])
        infants = attrs.get('infant_count', 0)
        adults = attrs.get('adult_count', 1)

        if travel_type == 2:
            # Multi-city: require at least 2 segments
            if len(trip_segments) < 2:
                raise serializers.ValidationError(
                    {"trip_segments": "Multi-city search requires at least 2 trip segments."}
                )
            for idx, seg in enumerate(trip_segments):
                if seg['origin'] == seg['destination']:
                    raise serializers.ValidationError(
                        {"trip_segments": f"Segment {idx + 1}: origin and destination cannot be the same."}
                    )
                seg_date = seg.get('travel_date')
                if seg_date and seg_date < date.today():
                    raise serializers.ValidationError(
                        {"trip_segments": f"Segment {idx + 1}: travel date cannot be in the past."}
                    )
        else:
            # One-way / Round-trip: require standard fields
            if not origin or not destination:
                raise serializers.ValidationError(
                    {"origin": "Origin and Destination are required for one-way or round-trip searches."}
                )
            if origin == destination:
                raise serializers.ValidationError(
                    {"destination": "Origin and Destination airports cannot be the same."}
                )
            if travel_date and travel_date < date.today():
                raise serializers.ValidationError(
                    {"travel_date": "Travel date cannot be in the past."}
                )
            if return_date and travel_date and return_date < travel_date:
                raise serializers.ValidationError(
                    {"return_date": "Return date must be on or after the travel date."}
                )

        # Infant count constraint (cannot exceed adult count)
        if infants > adults:
            raise serializers.ValidationError(
                {"infant_count": "Number of infants cannot exceed the number of adult passengers."}
            )

        return attrs


class FlightRevalidateRequestSerializer(serializers.Serializer):
    search_key = serializers.CharField(
        max_length=4096,
        help_text="Search token returned by the flight search API."
    )
    flight_key = serializers.CharField(
        max_length=8192,
        help_text="Provider flight key for the selected itinerary."
    )
    fare_id = serializers.CharField(
        max_length=128,
        help_text="Selected fare identifier returned by the search API."
    )
    customer_mobile = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        help_text="Customer mobile number used by the provider for reprice validation."
    )
    gst_input = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Whether GST details should be considered during revalidation."
    )
    single_pricing = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Whether the provider should return a single pricing quote."
    )
    source_type = serializers.IntegerField(
        required=False,
        default=0,
        min_value=0,
        help_text="Provider source type flag for Air_Reprice."
    )


# --- Response / output serializers for OpenAPI validation ---
class FlightSegmentSerializer(serializers.Serializer):
    segment_id = serializers.IntegerField()
    airline_code = serializers.CharField(max_length=8, allow_blank=True)
    airline_name = serializers.CharField(max_length=128, allow_blank=True)
    flight_number = serializers.CharField(max_length=32, allow_blank=True)
    aircraft_type = serializers.CharField(max_length=64, allow_blank=True)
    origin = serializers.CharField(max_length=8, allow_blank=True)
    origin_city = serializers.CharField(max_length=128, allow_blank=True)
    origin_terminal = serializers.CharField(max_length=16, allow_blank=True)
    destination = serializers.CharField(max_length=8, allow_blank=True)
    destination_city = serializers.CharField(max_length=128, allow_blank=True)
    destination_terminal = serializers.CharField(max_length=16, allow_blank=True)
    departure_datetime = serializers.CharField(max_length=64, allow_blank=True)
    arrival_datetime = serializers.CharField(max_length=64, allow_blank=True)
    duration = serializers.CharField(max_length=32, allow_blank=True)
    stop_over = serializers.CharField(max_length=64, allow_null=True, required=False)
    return_flight = serializers.BooleanField(required=False)


class PriceDetailsSerializer(serializers.Serializer):
    currency = serializers.CharField(max_length=8)
    basic_amount = serializers.FloatField()
    tax_amount = serializers.FloatField()
    total_amount = serializers.FloatField()


class BaggageSerializer(serializers.Serializer):
    check_in = serializers.CharField(max_length=64, allow_null=True, required=False)
    hand = serializers.CharField(max_length=64, allow_null=True, required=False)


class FareSerializer(serializers.Serializer):
    fare_id = serializers.CharField(max_length=128)
    refundable = serializers.BooleanField()
    seats_available = serializers.CharField(max_length=16, allow_blank=True)
    food_onboard = serializers.CharField(max_length=8, allow_blank=True)
    gst_mandatory = serializers.BooleanField()
    price_details = PriceDetailsSerializer()
    baggage = BaggageSerializer()
    fare_type = serializers.CharField(max_length=32, required=False, allow_blank=True, default="PUB")
    product_class = serializers.CharField(max_length=32, required=False, allow_blank=True)
    fare_basis = serializers.CharField(max_length=128, required=False, allow_blank=True)
    class_desc = serializers.CharField(max_length=128, required=False, allow_blank=True)



class FlightSerializer(serializers.Serializer):
    flight_key = serializers.CharField()
    flight_id = serializers.IntegerField(allow_null=True, required=False)
    airline_code = serializers.CharField(max_length=8, allow_blank=True)
    origin = serializers.CharField(max_length=8, allow_blank=True)
    destination = serializers.CharField(max_length=8, allow_blank=True)
    block_ticket_allowed = serializers.BooleanField(required=False)
    cached = serializers.BooleanField(required=False)
    repriced = serializers.BooleanField(required=False)
    is_fare_change = serializers.BooleanField(required=False)
    gst_entry_allowed = serializers.BooleanField(required=False)
    has_more_class = serializers.BooleanField(required=False)
    inventory_type = serializers.IntegerField(allow_null=True, required=False)
    is_lcc = serializers.BooleanField(required=False)
    segments = FlightSegmentSerializer(many=True)
    fares = FareSerializer(many=True)


class SearchDataSerializer(serializers.Serializer):
    search_key = serializers.CharField()
    flights = FlightSerializer(many=True)


class SearchResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    data = SearchDataSerializer()


class RevalidateDataSerializer(serializers.Serializer):
    search_key = serializers.CharField()
    flight_key = serializers.CharField()
    fare_id = serializers.CharField()
    repriced = serializers.BooleanField()
    is_fare_change = serializers.BooleanField()
    flight = FlightSerializer()


class RevalidateResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    data = RevalidateDataSerializer()
