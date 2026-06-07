import datetime
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from bookings.models import GroupBooking, GroupQuote, GroupPassenger, GroupChangeRequest
from decimal import Decimal

User = get_user_model()

class GroupTravelAPITests(APITestCase):
    def setUp(self):
        # Create users
        self.agent_user = User.objects.create_user(
            username='agent_test',
            email='agent@test.com',
            password='password123',
            role=User.AGENT
        )
        self.admin_user = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='password123',
            role=User.ADMIN
        )
        
        # Base booking data
        self.booking_data = {
            'group_name': 'Test Group Tour',
            'origin': 'DEL',
            'destination': 'BOM',
            'departure_date': '2026-07-01',
            'return_date': '2026-07-10',
            'trip_type': 'ROUND_TRIP',
            'cabin_class': 'ECONOMY',
            'pax_adults': 15,
            'pax_children': 2,
            'pax_infants': 1,
            'expected_fare_per_pax': '5000.00',
            'airline_preference': 'IndiGo',
            'timing_preference': 'MORNING',
            'group_category': 'Leisure',
            'remarks': 'Need vegetarian meals'
        }

    def test_group_booking_lifecycle(self):
        # 1. Create a booking (Agent)
        self.client.force_authenticate(user=self.agent_user)
        create_url = reverse('group-booking-create-booking')
        response = self.client.post(create_url, self.booking_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking_id = response.data['id']
        self.assertEqual(response.data['status'], 'NEW_REQUEST')
        self.assertEqual(response.data['pax_adults'], 15)
        
        # 2. Upload quotes (Admin)
        self.client.force_authenticate(user=self.admin_user)
        quote_url = reverse('group-booking-upload-quote', kwargs={'pk': booking_id})
        quote_data = [
            {
                'quote_option_id': 'opt_1',
                'airline': 'IndiGo',
                'flight_number': '6E-123',
                'departure_time': '2026-07-01T08:00:00Z',
                'arrival_time': '2026-07-01T10:00:00Z',
                'fare_per_pax': '4800.00',
                'tax_per_pax': '500.00',
                'deposit_per_pax': '1000.00',
                'payment_deadline': '2026-06-15T18:00:00Z',
                'balance_deadline': '2026-06-25T18:00:00Z',
                'terms_and_conditions': 'Non-refundable'
            },
            {
                'quote_option_id': 'opt_2',
                'airline': 'Air India',
                'flight_number': 'AI-456',
                'departure_time': '2026-07-01T09:00:00Z',
                'arrival_time': '2026-07-01T11:15:00Z',
                'fare_per_pax': '5200.00',
                'tax_per_pax': '600.00',
                'deposit_per_pax': '1200.00',
                'payment_deadline': '2026-06-16T18:00:00Z',
                'balance_deadline': '2026-06-26T18:00:00Z',
                'terms_and_conditions': '1 piece baggage'
            }
        ]
        
        response = self.client.post(quote_url, quote_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify status transitioned to FARE_QUOTED
        booking = GroupBooking.objects.get(id=booking_id)
        self.assertEqual(booking.status, 'FARE_QUOTED')
        self.assertEqual(booking.quotes.count(), 2)

        # 3. Negotiate (Agent)
        self.client.force_authenticate(user=self.agent_user)
        negotiate_url = reverse('group-booking-negotiate', kwargs={'pk': booking_id})
        response = self.client.post(negotiate_url, {'remarks': 'Can we get fare at 4500 per pax?'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'NEGOTIATION')
        self.assertEqual(booking.remarks, 'Can we get fare at 4500 per pax?')

        # 4. Accept Quote (Agent)
        accept_url = reverse('group-booking-accept-quote', kwargs={'pk': booking_id})
        response = self.client.post(accept_url, {'quote_option_id': 'opt_1'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        # ACCEPTED -> PAYMENT_PENDING transition
        self.assertEqual(booking.status, 'PAYMENT_PENDING')
        selected_quote = booking.quotes.get(quote_option_id='opt_1')
        self.assertTrue(selected_quote.is_selected)

        # 5. Record Payment - Partially Paid (Agent)
        payment_url = reverse('group-booking-record-payment', kwargs={'pk': booking_id})
        response = self.client.post(payment_url, {'amount': '30000.00'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'PARTIALLY_PAID')
        self.assertEqual(booking.total_paid, Decimal('30000.00'))

        # 6. Record Payment - Fully Paid (Agent)
        response = self.client.post(payment_url, {'amount': '65400.00'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'PAID')
        self.assertEqual(booking.total_paid, Decimal('95400.00'))

        # 7. Upload passengers (Agent)
        passengers_url = reverse('group-booking-upload-passengers', kwargs={'pk': booking_id})
        passenger_list = [
            {
                'first_name': 'John',
                'last_name': 'Doe',
                'gender': 'Male',
                'date_of_birth': '1990-05-15',
                'passport_number': 'A12345678'
            },
            {
                'first_name': 'Jane',
                'last_name': 'Doe',
                'gender': 'Female',
                'date_of_birth': '1992-08-20',
                'passport_number': 'B87654321'
            }
        ]
        response = self.client.post(passengers_url, passenger_list, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'NAME_SUBMITTED')
        self.assertEqual(booking.passengers.count(), 2)

        # 8. Issue ticket (Admin)
        self.client.force_authenticate(user=self.admin_user)
        ticket_url = reverse('group-booking-issue-ticket', kwargs={'pk': booking_id})
        response = self.client.post(ticket_url, {'pnr_number': 'PNR12345'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'TICKETED')
        self.assertEqual(booking.pnr_number, 'PNR12345')

        # 9. Complete Booking (Admin)
        complete_url = reverse('group-booking-complete-booking', kwargs={'pk': booking_id})
        response = self.client.post(complete_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'COMPLETED')

    def test_change_request_lifecycle(self):
        # Create a booking
        self.client.force_authenticate(user=self.agent_user)
        create_url = reverse('group-booking-create-booking')
        response = self.client.post(create_url, self.booking_data)
        booking_id = response.data['id']
        
        # Accept quote to establish selection
        self.client.force_authenticate(user=self.admin_user)
        quote_url = reverse('group-booking-upload-quote', kwargs={'pk': booking_id})
        self.client.post(quote_url, [
            {
                'quote_option_id': 'opt_1',
                'airline': 'IndiGo',
                'flight_number': '6E-123',
                'departure_time': '2026-07-01T08:00:00Z',
                'arrival_time': '2026-07-01T10:00:00Z',
                'fare_per_pax': '4800.00',
                'payment_deadline': '2026-06-15T18:00:00Z',
                'balance_deadline': '2026-06-25T18:00:00Z',
            }
        ], format='json')
        
        self.client.force_authenticate(user=self.agent_user)
        accept_url = reverse('group-booking-accept-quote', kwargs={'pk': booking_id})
        self.client.post(accept_url, {'quote_option_id': 'opt_1'})

        # Agent submits an UPSIZE change request
        change_req_url = reverse('group-booking-create-change-request', kwargs={'pk': booking_id})
        cr_data = {
            'change_type': 'UPSIZE',
            'pax_delta': 5,
            'agent_notes': 'Add 5 more adults'
        }
        response = self.client.post(change_req_url, cr_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cr_id = response.data['change_request_id']

        # Admin resolves the change request - approves it
        self.client.force_authenticate(user=self.admin_user)
        resolve_url = reverse('group-booking-resolve-change-request', kwargs={'pk': booking_id, 'cr_id': cr_id})
        resolve_data = {
            'status': 'APPROVED',
            'admin_remarks': 'Approved additional seats',
            'adjusted_fare_per_pax': '4900.00'
        }
        response = self.client.patch(resolve_url, resolve_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify changes propagated to Booking
        booking = GroupBooking.objects.get(id=booking_id)
        self.assertEqual(booking.pax_adults, 20) # 15 + 5
        self.assertEqual(booking.expected_fare_per_pax, Decimal('4900.00'))
