from rest_framework import serializers
from datetime import date

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
        help_text="Date of travel in YYYY-MM-DD format."
    )
    return_date = serializers.DateField(
        required=False,
        allow_null=True,
        help_text="Date of return in YYYY-MM-DD format. Triggers round-trip search if provided."
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

    def validate_origin(self, value):
        return value.strip().upper()

    def validate_destination(self, value):
        return value.strip().upper()

    def validate_airline_code(self, value):
        if value:
            return value.strip().upper()
        return value

    def validate(self, attrs):
        origin = attrs.get('origin')
        destination = attrs.get('destination')
        travel_date = attrs.get('travel_date')
        return_date = attrs.get('return_date')
        infants = attrs.get('infant_count', 0)
        adults = attrs.get('adult_count', 1)

        # Origin and Destination must differ
        if origin == destination:
            raise serializers.ValidationError(
                {"destination": "Origin and Destination airports cannot be the same."}
            )

        # Travel date must be in the future or today
        if travel_date < date.today():
            raise serializers.ValidationError(
                {"travel_date": "Travel date cannot be in the past."}
            )

        # Return date validation
        if return_date:
            if return_date < travel_date:
                raise serializers.ValidationError(
                    {"return_date": "Return date must be on or after the travel date."}
                )

        # Infant count constraint (cannot exceed adult count)
        if infants > adults:
            raise serializers.ValidationError(
                {"infant_count": "Number of infants cannot exceed the number of adult passengers."}
            )

        return attrs
