from django.db import models
from django.conf import settings
from core.models import BaseModel

class Ticket(BaseModel):
    STATUS_PENDING = 'PENDING'
    STATUS_CONFIRMED = 'CONFIRMED'
    STATUS_FAILED = 'FAILED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tickets',
        help_text="The user who bought/owns this ticket."
    )

    # Offline/Agent Inventory details
    agent_flight_inventory = models.ForeignKey(
        'flights.AgentFlightInventory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets',
        help_text="Linked agent inventory, if offline booking."
    )
    agent_cancellation_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason given by agent for cancelling this booking request."
    )

    # Booking & PNR Details
    pnr_number = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        help_text="Passenger Name Record (PNR)"
    )
    ticket_number = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        help_text="Airline Ticket Number"
    )
    booking_ref = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="GDS provider Booking_RefNo used for cancellation (e.g. 'FBB64ZDT')."
    )
    flight_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="GDS flight ID used for cancellation."
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default=STATUS_PENDING,
        help_text="Current issuance status of the ticket."
    )

    # Flight Summary Details
    origin = models.CharField(
        max_length=3, 
        help_text="3-letter IATA departure airport code, e.g. 'DEL'."
    )
    destination = models.CharField(
        max_length=3, 
        help_text="3-letter IATA arrival airport code, e.g. 'BOM'."
    )
    departure_datetime = models.DateTimeField(
        help_text="Flight departure date and time."
    )
    arrival_datetime = models.DateTimeField(
        help_text="Flight arrival date and time."
    )
    travel_type = models.IntegerField(
        choices=[(0, 'One-Way'), (1, 'Round-Trip')], 
        default=0,
        help_text="Trip direction type mapping (0 = One-Way, 1 = Round-Trip)."
    )

    # Carrier Details
    airline_code = models.CharField(
        max_length=10, 
        help_text="Airline carrier key, e.g. 'AI'."
    )
    airline_name = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="Carrier description name, e.g. 'Air India'."
    )
    flight_number = models.CharField(
        max_length=20, 
        help_text="Specific carrier flight tag, e.g. '9757'."
    )
    cabin_class = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        help_text="Cabin travel tier (Economy, Premium, Business, First)."
    )

    # Pricing & Currency Details
    basic_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0.00,
        help_text="Base tariff amount paid."
    )
    tax_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0.00,
        help_text="Tax / auxiliary surcharge fees paid."
    )
    total_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0.00,
        help_text="Aggregate booking total cost."
    )
    currency = models.CharField(
        max_length=3, 
        default='INR',
        help_text="Tariff transaction currency code."
    )

    # Baggage Details
    baggage_check_in = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        help_text="Maximum allowed check-in baggage allowance weight/count."
    )
    baggage_hand = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        help_text="Maximum allowed hand baggage allowance weight."
    )
    
    # Custom attributes
    is_refundable = models.BooleanField(
        default=True,
        help_text="Identifies if the ticket is eligible for refund on cancellation."
    )
    food_onboard = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        help_text="Onboard food catering rules/description."
    )

    # Structured metadata stores for multi-segment flight details and passengers
    segments_data = models.JSONField(
        default=list, 
        blank=True, 
        help_text="Chronological segment arrays containing stopover and terminal details."
    )
    passengers_data = models.JSONField(
        default=list,
        blank=True,
        help_text="Manifest details containing name, document, and gender details of all passengers."
    )
    ssr_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Confirmed passenger-wise Special Service Requests (meals, baggage, seats, etc.)"
    )
    cancellation_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Metadata regarding ticket cancellation charges, initiator, and refund amounts."
    )

    CHANNEL_B2C = "B2C"
    CHANNEL_B2B = "B2B"
    CHANNEL_CHOICES = [
        (CHANNEL_B2C, "B2C"),
        (CHANNEL_B2B, "B2B"),
    ]
    booking_channel = models.CharField(
        max_length=8,
        choices=CHANNEL_CHOICES,
        default=CHANNEL_B2C,
        blank=True,
        help_text="Commercial channel categorization for admin reporting (B2B vs B2C).",
    )

    class Meta:
        verbose_name = 'Ticket'
        verbose_name_plural = 'Tickets'
        ordering = ['-created_at']

    def __str__(self):
        return f"Ticket {self.ticket_number or 'PENDING'} ({self.origin} -> {self.destination}) for {self.user.username}"
