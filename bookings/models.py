import datetime
import random
from django.db import models
from django.conf import settings
from core.models import BaseModel

class GroupBooking(BaseModel):
    TRIP_TYPE_CHOICES = [
        ('ONE_WAY', 'One-Way'),
        ('ROUND_TRIP', 'Round-Trip'),
        ('MULTI_CITY', 'Multi-City'),
    ]
    
    CABIN_CLASS_CHOICES = [
        ('ECONOMY', 'Economy'),
        ('PREMIUM', 'Premium Economy'),
        ('BUSINESS', 'Business'),
    ]
    
    TIMING_PREFERENCE_CHOICES = [
        ('MORNING', 'Morning'),
        ('AFTERNOON', 'Afternoon'),
        ('EVENING', 'Evening'),
    ]
    
    STATUS_CHOICES = [
        ('NEW_REQUEST', 'New Request'),
        ('FARE_QUOTED', 'Fare Quoted'),
        ('NEGOTIATION', 'Negotiation'),
        ('ACCEPTED', 'Accepted'),
        ('PAYMENT_PENDING', 'Payment Pending'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('PNR_CREATED', 'PNR Created'),
        ('NAME_SUBMITTED', 'Name Submitted'),
        ('TICKETED', 'Ticketed'),
        ('COMPLETED', 'Completed'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='group_bookings')
    request_id = models.CharField(max_length=50, unique=True, blank=True)
    group_name = models.CharField(max_length=255)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='NEW_REQUEST')
    origin = models.CharField(max_length=3)
    destination = models.CharField(max_length=3)
    departure_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)
    trip_type = models.CharField(max_length=20, choices=TRIP_TYPE_CHOICES, default='ROUND_TRIP')
    cabin_class = models.CharField(max_length=20, choices=CABIN_CLASS_CHOICES, default='ECONOMY')
    pax_adults = models.IntegerField(default=10)
    pax_children = models.IntegerField(default=0)
    pax_infants = models.IntegerField(default=0)
    expected_fare_per_pax = models.DecimalField(max_digits=12, decimal_places=2)
    airline_preference = models.CharField(max_length=100, blank=True, null=True)
    timing_preference = models.CharField(max_length=20, choices=TIMING_PREFERENCE_CHOICES, blank=True, null=True)
    group_category = models.CharField(max_length=100, blank=True, null=True)
    pnr_number = models.CharField(max_length=20, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    total_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    payment_deadline = models.DateTimeField(null=True, blank=True)
    balance_deadline = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.request_id:
            while True:
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                rand_part = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=4))
                req_id = f"GRP{timestamp}{rand_part}"
                if not GroupBooking.objects.filter(request_id=req_id).exists():
                    self.request_id = req_id
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.group_name} ({self.request_id}) - {self.status}"


class GroupQuote(BaseModel):
    booking = models.ForeignKey(GroupBooking, on_delete=models.CASCADE, related_name='quotes')
    quote_option_id = models.CharField(max_length=50)
    airline = models.CharField(max_length=100)
    flight_number = models.CharField(max_length=20)
    departure_time = models.DateTimeField()
    arrival_time = models.DateTimeField()
    fare_per_pax = models.DecimalField(max_digits=12, decimal_places=2)
    tax_per_pax = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    deposit_per_pax = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    payment_deadline = models.DateTimeField()
    balance_deadline = models.DateTimeField()
    terms_and_conditions = models.TextField(blank=True, null=True)
    is_selected = models.BooleanField(default=False)

    def __str__(self):
        return f"Quote {self.quote_option_id} for {self.booking.request_id} ({self.airline} {self.flight_number})"


class GroupPassenger(BaseModel):
    booking = models.ForeignKey(GroupBooking, on_delete=models.CASCADE, related_name='passengers')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=10)
    date_of_birth = models.DateField()
    passport_number = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.booking.request_id})"


class GroupChangeRequest(BaseModel):
    CHANGE_TYPE_CHOICES = [
        ('UPSIZE', 'Upsize'),
        ('DOWNSIZE', 'Downsize'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING_REVIEW', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    booking = models.ForeignKey(GroupBooking, on_delete=models.CASCADE, related_name='change_requests')
    change_request_id = models.CharField(max_length=50, unique=True, blank=True)
    change_type = models.CharField(max_length=10, choices=CHANGE_TYPE_CHOICES)
    pax_delta = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING_REVIEW')
    agent_notes = models.TextField(blank=True, null=True)
    admin_remarks = models.TextField(blank=True, null=True)
    adjusted_fare_per_pax = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.change_request_id:
            while True:
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                rand_part = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=4))
                cr_id = f"CR{timestamp}{rand_part}"
                if not GroupChangeRequest.objects.filter(change_request_id=cr_id).exists():
                    self.change_request_id = cr_id
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.change_type} Request {self.change_request_id} ({self.status}) for {self.booking.request_id}"
