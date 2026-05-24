from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from django.utils import timezone
from decimal import Decimal
from .models import Ticket

User = get_user_model()

class TicketAPITests(APITestCase):
    def setUp(self):
        # Create standard customers
        self.customer_a = User.objects.create_user(
            username='customera',
            password='Password123!',
            role='CUSTOMER',
            phone_number='1234567890'
        )
        self.customer_b = User.objects.create_user(
            username='customerb',
            password='Password123!',
            role='CUSTOMER',
            phone_number='0987654321'
        )
        # Create administrative staff user
        self.admin_user = User.objects.create_superuser(
            username='adminuser',
            password='AdminPassword123!',
            role='ADMIN'
        )

        # Create ticket for Customer A
        self.ticket_a = Ticket.objects.create(
            user=self.customer_a,
            pnr_number='PNRA12',
            ticket_number='TKT-12345',
            status='CONFIRMED',
            origin='DEL',
            destination='BOM',
            departure_datetime=timezone.now() + timezone.timedelta(days=10),
            arrival_datetime=timezone.now() + timezone.timedelta(days=10, hours=2),
            travel_type=0,
            airline_code='AI',
            airline_name='Air India',
            flight_number='AI-9757',
            cabin_class='Economy',
            basic_amount=Decimal('10000.00'),
            tax_amount=Decimal('2000.00'),
            total_amount=Decimal('12000.00'),
            currency='INR',
            baggage_check_in='15 Kg',
            baggage_hand='7 Kg',
            is_refundable=True,
            segments_data=[{"segment_id": 0, "flight_number": "AI-9757"}],
            passengers_data=[{"first_name": "Customer", "last_name": "A", "gender": "M"}]
        )

        # Create ticket for Customer B
        self.ticket_b = Ticket.objects.create(
            user=self.customer_b,
            pnr_number='PNRB56',
            ticket_number='TKT-67890',
            status='PENDING',
            origin='BOM',
            destination='DEL',
            departure_datetime=timezone.now() + timezone.timedelta(days=12),
            arrival_datetime=timezone.now() + timezone.timedelta(days=12, hours=2),
            travel_type=0,
            airline_code='6E',
            airline_name='IndiGo',
            flight_number='6E-5321',
            cabin_class='Economy',
            basic_amount=Decimal('8000.00'),
            tax_amount=Decimal('1500.00'),
            total_amount=Decimal('9500.00'),
            currency='INR',
            baggage_check_in='15 Kg',
            baggage_hand='7 Kg',
            is_refundable=False,
            segments_data=[{"segment_id": 0, "flight_number": "6E-5321"}],
            passengers_data=[{"first_name": "Customer", "last_name": "B", "gender": "F"}]
        )

        self.list_url = reverse('ticket-list')

    def test_unauthenticated_user_access_denied(self):
        """
        Verify that requests from anonymous/unauthenticated users return 401 Unauthorized.
        """
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_only_retrieves_own_tickets_list(self):
        """
        Verify that a customer can only list their own tickets.
        """
        self.client.force_authenticate(user=self.customer_a)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only contain Customer A's ticket
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['ticket_number'], 'TKT-12345')

    def test_customer_can_retrieve_own_ticket_detail(self):
        """
        Verify that a customer can successfully retrieve their own ticket detail.
        """
        self.client.force_authenticate(user=self.customer_a)
        detail_url = reverse('ticket-detail', kwargs={'pk': self.ticket_a.id})
        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['ticket_number'], 'TKT-12345')
        self.assertEqual(response.data['origin'], 'DEL')
        self.assertEqual(response.data['total_amount'], '12000.00')

    def test_customer_cannot_retrieve_others_ticket_detail(self):
        """
        Verify that a customer attempting to retrieve a ticket owned by another user gets a 404.
        """
        # Authenticated as Customer A, trying to view Customer B's ticket
        self.client.force_authenticate(user=self.customer_a)
        detail_url = reverse('ticket-detail', kwargs={'pk': self.ticket_b.id})
        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_can_view_all_tickets(self):
        """
        Verify that staff / administrative users can view tickets from all customers.
        """
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should contain both tickets
        self.assertEqual(len(response.data), 2)
        ticket_numbers = [item['ticket_number'] for item in response.data]
        self.assertIn('TKT-12345', ticket_numbers)
        self.assertIn('TKT-67890', ticket_numbers)

    def test_admin_can_retrieve_any_ticket_detail(self):
        """
        Verify that staff / administrative users can retrieve detail of any ticket.
        """
        self.client.force_authenticate(user=self.admin_user)
        
        # Admin retrieves Customer B's ticket
        detail_url = reverse('ticket-detail', kwargs={'pk': self.ticket_b.id})
        response = self.client.get(detail_url)

        self.assertEqual(response.data['ticket_number'], 'TKT-67890')
        self.assertEqual(response.data['status'], 'PENDING')

    def test_anonymous_cannot_buy_ticket(self):
        """
        Verify that an unauthenticated user cannot call the buy endpoint.
        """
        buy_url = reverse('ticket-buy')
        payload = {
            "search_key": "some_search_key",
            "flight_key": "some_flight_key",
            "fare_id": "some_fare_id",
            "customer_mobile": "1234567890",
            "passenger_mobile": "1234567890",
            "passenger_email": "passenger@example.com",
            "passengers": []
        }
        response = self.client.post(buy_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('flights.services.requests.post')
    def test_successful_ticket_buy_flow(self, mock_post):
        """
        Verify that a fully authorized purchase flows atomically:
        - Reprice, TempBooking, and Ticketing API calls are made and mock-succeed.
        - A confirmed Ticket instance is written to the database.
        """
        self.client.force_authenticate(user=self.customer_a)
        buy_url = reverse('ticket-buy')

        # Prepare payload
        payload = {
            "search_key": "mock_search_token",
            "flight_key": "mock_flight_key",
            "fare_id": "4908357683079097850",
            "customer_mobile": "1234567890",
            "passenger_mobile": "1234567890",
            "passenger_email": "passenger@example.com",
            "passengers": [
                {
                    "pax_type": 0,
                    "title": "Mr",
                    "first_name": "John",
                    "last_name": "Doe",
                    "gender": 0,
                    "dob": "1996-05-15",
                    "passport_number": None,
                    "pancard_number": None
                }
            ]
        }

        # Mock three responses sequentially: Reprice, TempBooking, Ticketing
        mock_reprice_resp = MagicMock()
        mock_reprice_resp.status_code = 200
        mock_reprice_resp.json.return_value = {
            "Response_Header": {"Error_Code": "0000", "Error_Desc": "SUCCESS"},
            "AirRepriceResponses": [
                {
                    "IsFareChange": False,
                    "Flight": {
                        "Airline_Code": "SG",
                        "Block_Ticket_Allowed": True,
                        "Cached": False,
                        "Destination": "BOM",
                        "Flight_Key": "mock_flight_key_repriced",
                        "Origin": "DEL",
                        "Repriced": True,
                        "Segments": [
                            {
                                "Segment_Id": 0,
                                "Airline_Code": "SG",
                                "Airline_Name": "SpiceJet",
                                "Flight_Number": "6287",
                                "Aircraft_Type": "737",
                                "Origin": "DEL",
                                "Origin_City": "DELHI",
                                "Destination": "BOM",
                                "Destination_City": "MUMBAI",
                                "Departure_DateTime": "06/15/2026 00:50",
                                "Arrival_DateTime": "06/15/2026 02:40",
                                "Duration": "01:50",
                                "Return_Flight": False
                            }
                        ],
                        "Fares": [
                            {
                                "Fare_Id": "4908357683079097850",
                                "Refundable": True,
                                "Seats_Available": "9",
                                "Food_onboard": "F",
                                "GSTMandatory": False,
                                "FareDetails": [
                                    {
                                        "AirportTax_Amount": 679.0,
                                        "Basic_Amount": 4226.0,
                                        "Currency_Code": "INR",
                                        "Total_Amount": 4905.0,
                                        "Free_Baggage": {
                                            "Check_In_Baggage": "15 KG",
                                            "Hand_Baggage": "7 KG"
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
        }

        mock_temp_resp = MagicMock()
        mock_temp_resp.status_code = 200
        mock_temp_resp.json.return_value = {
            "Response_Header": {"Error_Code": "0000", "Error_Desc": "SUCCESS"},
            "Booking_RefNo": "FBB64ZDT"
        }

        mock_ticket_resp = MagicMock()
        mock_ticket_resp.status_code = 200
        mock_ticket_resp.json.return_value = {
            "Response_Header": {"Error_Code": "0000", "Error_Desc": "SUCCESS"},
            "Booking_RefNo": "FBB64ZDT",
            "AirlinePNRDetails": [
                {
                    "AirlinePNRs": [
                        {
                            "Airline_Code": "SG",
                            "Airline_PNR": "KEVG6H",
                            "Record_Locator": "210908133015"
                        }
                    ],
                    "Flight_Id": "5416863216316396891",
                    "Status_Id": "11"
                }
            ]
        }

        mock_post.side_effect = [mock_reprice_resp, mock_temp_resp, mock_ticket_resp]

        # Call the endpoint
        response = self.client.post(buy_url, payload, format='json')

        # Check response assertions
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['pnr_number'], 'KEVG6H')
        self.assertEqual(response.data['ticket_number'], '210908133015')
        self.assertEqual(response.data['status'], 'CONFIRMED')
        self.assertEqual(response.data['origin'], 'DEL')
        self.assertEqual(response.data['destination'], 'BOM')
        self.assertEqual(response.data['total_amount'], '4905.00')

        # Assert database record exists
        ticket_in_db = Ticket.objects.get(pnr_number='KEVG6H')
        self.assertEqual(ticket_in_db.user, self.customer_a)
        self.assertEqual(ticket_in_db.flight_id, '5416863216316396891')
        self.assertEqual(len(ticket_in_db.passengers_data), 1)
        self.assertEqual(ticket_in_db.passengers_data[0]['first_name'], 'John')

    @patch('flights.services.requests.post')
    def test_ticket_buy_flow_reprice_failure(self, mock_post):
        """
        Verify that if reprice fails, the flow terminates and no ticket is committed to DB.
        """
        self.client.force_authenticate(user=self.customer_a)
        buy_url = reverse('ticket-buy')

        payload = {
            "search_key": "mock_search_token",
            "flight_key": "mock_flight_key",
            "fare_id": "4908357683079097850",
            "customer_mobile": "1234567890",
            "passenger_mobile": "1234567890",
            "passenger_email": "passenger@example.com",
            "passengers": [
                {
                    "pax_type": 0,
                    "title": "Mr",
                    "first_name": "John",
                    "last_name": "Doe",
                    "gender": 0,
                    "dob": "1996-05-15",
                    "passport_number": None,
                    "pancard_number": None
                }
            ]
        }

        # Mock reprice returning "Fare Not Available" error
        mock_reprice_resp = MagicMock()
        mock_reprice_resp.status_code = 200
        mock_reprice_resp.json.return_value = {
            "Response_Header": {
                "Error_Code": "E001",
                "Error_Desc": "Fare Not Available"
            }
        }
        mock_post.return_value = mock_reprice_resp

        response = self.client.post(buy_url, payload, format='json')

        # Assert failure
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertFalse(response.data['success'])
        self.assertIn("Provider Error: Fare Not Available", response.data['message'])

        # Assert no extra Ticket is written to DB
        # Count should remain at 2 (the setup tickets)
        self.assertEqual(Ticket.objects.count(), 2)

    @patch('flights.services.requests.post')
    def test_dynamic_cancellation_flow(self, mock_post):
        """
        Verify that ticket cancellation triggers a dynamic GDS cancel request
        containing all passenger and segment combinations with correct FlightId.
        """
        self.client.force_authenticate(user=self.customer_a)
        
        # Populate dynamic ticket properties
        self.ticket_a.flight_id = "5416863216316396891"
        self.ticket_a.booking_ref = "FBB64ZDT"
        self.ticket_a.passengers_data = [
            {"first_name": "PaxOne", "last_name": "Doe", "gender": "M"},
            {"first_name": "PaxTwo", "last_name": "Doe", "gender": "F"}
        ]
        self.ticket_a.segments_data = [
            {"segment_id": 0, "flight_number": "AI-9757"},
            {"segment_id": 1, "flight_number": "AI-9758"}
        ]
        self.ticket_a.save()

        cancel_url = reverse('ticket-cancel', kwargs={'pk': self.ticket_a.id})

        # Mock successful GDS cancellation response
        mock_cancel_resp = MagicMock()
        mock_cancel_resp.status_code = 200
        mock_cancel_resp.json.return_value = {
            "Response_Header": {
                "Error_Code": "0000",
                "Error_Desc": "SUCCESS"
            }
        }
        mock_post.return_value = mock_cancel_resp

        response = self.client.post(cancel_url, {"remarks": "Changed travel plans"}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['gds_cancelled'])
        self.assertEqual(response.data['status'], 'CANCELLED')

        # Verify that requests.post was called with the correct dynamic cancel details
        mock_post.assert_called_once()
        called_args, called_kwargs = mock_post.call_args
        called_payload = called_kwargs.get('json', {})
        
        self.assertEqual(called_payload.get('Airline_PNR'), self.ticket_a.pnr_number)
        self.assertEqual(called_payload.get('RefNo'), self.ticket_a.booking_ref)
        self.assertEqual(called_payload.get('ReqRemarks'), "Changed travel plans")
        
        cancel_details = called_payload.get('AirTicketCancelDetails', [])
        # We have 2 passengers x 2 segments = 4 combinations
        self.assertEqual(len(cancel_details), 4)
        
        expected_details = [
            {"FlightId": "5416863216316396891", "PassengerId": "1", "SegmentId": "0"},
            {"FlightId": "5416863216316396891", "PassengerId": "1", "SegmentId": "1"},
            {"FlightId": "5416863216316396891", "PassengerId": "2", "SegmentId": "0"},
            {"FlightId": "5416863216316396891", "PassengerId": "2", "SegmentId": "1"}
        ]
        self.assertEqual(cancel_details, expected_details)

