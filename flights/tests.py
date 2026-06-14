import json
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from datetime import date, timedelta
from flights.serializers import FlightSearchRequestSerializer, FlightRevalidateRequestSerializer
from flights.models import FlightInventory

class FlightSearchTests(APITestCase):
    def setUp(self):
        self.search_url = reverse('flight_search')
        self.revalidate_url = reverse('flight_revalidate')
        self.valid_payload = {
            "origin": "DEL",
            "destination": "BOM",
            "travel_date": (date.today() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "adult_count": 1,
            "child_count": 0,
            "infant_count": 0,
            "class_of_travel": "0"
        }
        self.revalidate_payload = {
            "search_key": "mock_search_token_12345",
            "flight_key": "mock_flight_key_12345",
            "fare_id": "4908357683079097850",
            "customer_mobile": "9173456988",
            "gst_input": False,
            "single_pricing": True,
            "source_type": 0,
        }

    def test_serializer_validation_past_date(self):
        payload = self.valid_payload.copy()
        payload["travel_date"] = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        serializer = FlightSearchRequestSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("travel_date", serializer.errors)

    def test_serializer_validation_same_airports(self):
        payload = self.valid_payload.copy()
        payload["destination"] = "DEL"
        
        serializer = FlightSearchRequestSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("destination", serializer.errors)

    def test_serializer_validation_infants_exceed_adults(self):
        payload = self.valid_payload.copy()
        payload["adult_count"] = 1
        payload["infant_count"] = 2
        
        serializer = FlightSearchRequestSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("infant_count", serializer.errors)

    def test_revalidate_serializer_requires_core_fields(self):
        payload = self.revalidate_payload.copy()
        payload.pop("fare_id")

        serializer = FlightRevalidateRequestSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("fare_id", serializer.errors)

    @patch('flights.services.requests.post')
    def test_flight_search_api_success(self, mock_post):
        # Create standard FlyShop mock response payload
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Response_Header": {
                "Error_Code": "0000",
                "Error_Desc": "SUCCESS",
                "Error_InnerException": "",
                "Request_Id": "12345",
                "Status_Id": "11"
            },
            "Search_Key": "mock_search_token_12345",
            "TripDetails": [
                {
                    "Flights": [
                        {
                            "Airline_Code": "SG",
                            "Block_Ticket_Allowed": True,
                            "Cached": False,
                            "Destination": "BOM",
                            "Segments": [
                                {
                                    "Segment_Id": 0,
                                    "Airline_Code": "SG",
                                    "Airline_Name": "SpiceJet",
                                    "Flight_Number": "6287",
                                    "Aircraft_Type": "737",
                                    "Origin": "DEL",
                                    "Origin_City": "DELHI",
                                    "Origin_Terminal": "3",
                                    "Destination": "BOM",
                                    "Destination_City": "MUMBAI",
                                    "Destination_Terminal": "2",
                                    "Departure_DateTime": "06/12/2026 00:50",
                                    "Arrival_DateTime": "06/12/2026 02:40",
                                    "Duration": "01:50",
                                    "Stop_Over": None,
                                    "Return_Flight": False
                                }
                            ],
                            "Fares": [
                                {
                                    "FareDetails": [
                                        {
                                            "AirportTax_Amount": 679,
                                            "Basic_Amount": 4226,
                                            "Currency_Code": "INR",
                                            "Total_Amount": 4905,
                                            "Free_Baggage": {
                                                "Check_In_Baggage": "15 KG",
                                                "Hand_Baggage": "7 KG"
                                            }
                                        }
                                    ],
                                    "FareType": 0,
                                    "Fare_Id": "4908357683079097850",
                                    "Food_onboard": "F",
                                    "GSTMandatory": False,
                                    "Refundable": True,
                                    "Seats_Available": "9"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        mock_post.return_value = mock_response

        # Execute API POST call
        response = self.client.post(self.search_url, self.valid_payload, format='json')

        # Verify expectations
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertEqual(data['search_key'], "mock_search_token_12345")
        self.assertEqual(len(data['flights']), 1)
        
        flight = data['flights'][0]
        self.assertEqual(flight['airline_code'], "SG")
        self.assertEqual(flight['origin'], "DEL")
        self.assertEqual(flight['destination'], "BOM")
        self.assertEqual(len(flight['segments']), 1)
        self.assertEqual(len(flight['fares']), 1)
        
        fare = flight['fares'][0]
        self.assertEqual(fare['fare_id'], "4908357683079097850")
        self.assertEqual(fare['price_details']['total_amount'], 4905.0)
        self.assertEqual(fare['baggage']['check_in'], "15 KG")

    @patch('flights.services.requests.post')
    def test_flight_search_student_defence_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Response_Header": {
                "Error_Code": "0000",
                "Error_Desc": "SUCCESS",
            },
            "Search_Key": "mock_search_token_student_defence",
            "TripDetails": []
        }
        mock_post.return_value = mock_response

        payload = self.valid_payload.copy()
        payload["student_fare_search"] = True
        payload["defence_fare_search"] = True

        response = self.client.post(self.search_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        mock_post.assert_called_once()
        called_args, called_kwargs = mock_post.call_args
        called_payload = called_kwargs.get('json', {})
        self.assertTrue(called_payload.get("StudentFare_Search"))
        self.assertTrue(called_payload.get("DefenceFare_Search"))

    @patch('flights.services.requests.post')
    def test_flight_search_api_provider_failure(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Response_Header": {
                "Error_Code": "E001",
                "Error_Desc": "Sector Not Available",
                "Error_InnerException": "",
                "Request_Id": "12345",
                "Status_Id": "11"
            }
        }
        mock_post.return_value = mock_response

        response = self.client.post(self.search_url, self.valid_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertFalse(response.data['success'])
        self.assertIn("Provider Error: Sector Not Available", response.data['message'])

    @patch('flights.services.requests.post')
    def test_flight_revalidate_api_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Response_Header": {
                "Error_Code": "0000",
                "Error_Desc": "SUCCESS",
                "Error_InnerException": "",
                "Request_Id": "12345",
                "Status_Id": "11"
            },
            "AirRepriceResponses": [
                {
                    "IsFareChange": False,
                    "Flight": {
                        "Airline_Code": "SG",
                        "Block_Ticket_Allowed": True,
                        "Cached": False,
                        "Destination": "BOM",
                        "Flight_Id": "5416863216316396891",
                        "Flight_Key": "mock_flight_key_12345",
                        "IsFareChange": False,
                        "IsLCC": True,
                        "InventoryType": 1,
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
                                "Origin_Terminal": "3",
                                "Destination": "BOM",
                                "Destination_City": "MUMBAI",
                                "Destination_Terminal": "2",
                                "Departure_DateTime": "06/12/2026 00:50",
                                "Arrival_DateTime": "06/12/2026 02:40",
                                "Duration": "01:50",
                                "Stop_Over": None,
                                "Return_Flight": False
                            }
                        ],
                        "Fares": [
                            {
                                "FareDetails": [
                                    {
                                        "AirportTax_Amount": 563,
                                        "Basic_Amount": 1924,
                                        "Currency_Code": "INR",
                                        "Total_Amount": 2487,
                                        "Free_Baggage": {
                                            "Check_In_Baggage": "15 KG",
                                            "Hand_Baggage": "7 KG"
                                        }
                                    }
                                ],
                                "FareType": 0,
                                "Fare_Id": "4908357683079097850",
                                "Food_onboard": "F",
                                "GSTMandatory": False,
                                "Refundable": True,
                                "Seats_Available": "1"
                            }
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        response = self.client.post(self.revalidate_url, self.revalidate_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['search_key'], self.revalidate_payload['search_key'])
        self.assertEqual(response.data['fare_id'], self.revalidate_payload['fare_id'])
        self.assertTrue(response.data['repriced'])
        self.assertEqual(response.data['flight']['airline_code'], 'SG')
        self.assertEqual(response.data['flight']['fares'][0]['price_details']['total_amount'], 2487.0)

    @patch('flights.services.requests.post')
    def test_flight_revalidate_api_provider_failure(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Response_Header": {
                "Error_Code": "E001",
                "Error_Desc": "Fare Not Available",
                "Error_InnerException": "",
                "Request_Id": "12345",
                "Status_Id": "11"
            }
        }
        mock_post.return_value = mock_response

        response = self.client.post(self.revalidate_url, self.revalidate_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertFalse(response.data['success'])
        self.assertIn("Provider Error: Fare Not Available", response.data['message'])

    @patch('flights.services.requests.post')
    def test_fare_type_normalization(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Response_Header": {
                "Error_Code": "0000",
                "Error_Desc": "SUCCESS",
            },
            "Search_Key": "mock_search_token_12345",
            "TripDetails": [
                {
                    "Flights": [
                        {
                            "Airline_Code": "6E",
                            "Block_Ticket_Allowed": True,
                            "Cached": False,
                            "Destination": "BOM",
                            "Segments": [
                                {
                                    "Segment_Id": 0,
                                    "Airline_Code": "6E",
                                    "Airline_Name": "IndiGo",
                                    "Flight_Number": "101",
                                    "Aircraft_Type": "A320",
                                    "Origin": "DEL",
                                    "Origin_City": "DELHI",
                                    "Destination": "BOM",
                                    "Destination_City": "MUMBAI",
                                    "Departure_DateTime": "06/12/2026 00:50",
                                    "Arrival_DateTime": "06/12/2026 02:40",
                                    "Duration": "01:50",
                                }
                            ],
                            "Fares": [
                                {
                                    "FareDetails": [
                                        {
                                            "AirportTax_Amount": 500,
                                            "Basic_Amount": 3000,
                                            "Currency_Code": "INR",
                                            "Total_Amount": 3500,
                                            "Free_Baggage": {"Check_In_Baggage": "15 KG"},
                                            "FareClasses": [
                                                {
                                                    "Class_Code": "U",
                                                    "Class_Desc": "SF",
                                                    "FareBasis": "USPF"
                                                }
                                            ]
                                        }
                                    ],
                                    "FareType": 0,
                                    "Fare_Id": "fare_student",
                                    "ProductClass": "SF",
                                    "Food_onboard": "F",
                                    "GSTMandatory": False,
                                    "Refundable": True,
                                    "Seats_Available": "9"
                                },
                                {
                                    "FareDetails": [
                                        {
                                            "AirportTax_Amount": 500,
                                            "Basic_Amount": 3000,
                                            "Currency_Code": "INR",
                                            "Total_Amount": 3500,
                                            "Free_Baggage": {"Check_In_Baggage": "15 KG"},
                                            "FareClasses": [
                                                {
                                                    "Class_Code": "V",
                                                    "Class_Desc": "MILITARY",
                                                    "FareBasis": "VDEF"
                                                }
                                            ]
                                        }
                                    ],
                                    "FareType": 0,
                                    "Fare_Id": "fare_defence",
                                    "ProductClass": "DD",
                                    "Food_onboard": "F",
                                    "GSTMandatory": False,
                                    "Refundable": True,
                                    "Seats_Available": "9"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        mock_post.return_value = mock_response

        response = self.client.post(self.search_url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        fares = response.data['flights'][0]['fares']
        self.assertEqual(len(fares), 2)
        
        # Verify student fare mapping
        self.assertEqual(fares[0]['fare_id'], "fare_student")
        self.assertEqual(fares[0]['fare_type'], "STU")
        self.assertEqual(fares[0]['product_class'], "SF")
        self.assertEqual(fares[0]['class_desc'], "SF")
        self.assertEqual(fares[0]['fare_basis'], "USPF")
        
        # Verify defence fare mapping
        self.assertEqual(fares[1]['fare_id'], "fare_defence")
        self.assertEqual(fares[1]['fare_type'], "DEF")
        self.assertEqual(fares[1]['product_class'], "DD")


class FlightSSRTests(APITestCase):
    def setUp(self):
        self.ssr_url = reverse('flight_ssr')
        self.payload = {
            "search_key": "mock_search_token_12345",
            "flight_key": "mock_flight_key_12345"
        }

    @patch('flights.services.requests.post')
    def test_get_ssr_options_success(self, mock_post):
        # We mock two responses because get_pre_ssr calls requests.post twice:
        # first to Air_GetSSR, second to Air_GetSeatMap.
        mock_response_ssr = MagicMock()
        mock_response_ssr.status_code = 200
        mock_response_ssr.json.return_value = {
            "Response_Header": {
                "Error_Code": "0000",
                "Error_Desc": "SUCCESS"
            },
            "SSRFlightDetails": [
                {
                    "SSRDetails": [
                        {
                            "SSR_Code": "VGML",
                            "SSR_TypeName": "MEALS",
                            "SSR_TypeDesc": "Veg Meal",
                            "Total_Amount": 250
                        }
                    ]
                }
            ]
        }

        mock_response_seat = MagicMock()
        mock_response_seat.status_code = 200
        mock_response_seat.json.return_value = {
            "Response_Header": {
                "Error_Code": "0000",
                "Error_Desc": "SUCCESS"
            },
            "AirSeatMaps": [
                {
                    "Flight_Id": "mock_flight_key_12345",
                    "Seat_Segments": []
                }
            ]
        }

        # side_effect returns mock_response_ssr on the first call, mock_response_seat on the second call.
        mock_post.side_effect = [mock_response_ssr, mock_response_seat]

        response = self.client.post(self.ssr_url, self.payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify the structure contains both merged lists
        self.assertIn("SSRFlightDetails", response.data)
        self.assertIn("AirSeatMaps", response.data)
        self.assertEqual(len(response.data["SSRFlightDetails"]), 1)
        self.assertEqual(len(response.data["AirSeatMaps"]), 1)
        self.assertEqual(response.data["SSRFlightDetails"][0]["SSRDetails"][0]["SSR_Code"], "VGML")
        self.assertEqual(response.data["AirSeatMaps"][0]["Flight_Id"], "mock_flight_key_12345")

    @patch('flights.services.requests.post')
    def test_get_ssr_options_seat_map_graceful_degradation(self, mock_post):
        # If the seat map service fails or returns an error, we should degrade gracefully and return empty AirSeatMaps.
        mock_response_ssr = MagicMock()
        mock_response_ssr.status_code = 200
        mock_response_ssr.json.return_value = {
            "Response_Header": {
                "Error_Code": "0000",
                "Error_Desc": "SUCCESS"
            },
            "SSRFlightDetails": [
                {
                    "SSRDetails": [
                        {
                            "SSR_Code": "VGML",
                            "SSR_TypeName": "MEALS"
                        }
                    ]
                }
            ]
        }

        mock_response_seat = MagicMock()
        mock_response_seat.status_code = 200
        mock_response_seat.json.return_value = {
            "Response_Header": {
                "Error_Code": "E100",
                "Error_Desc": "Seat map not available"
            }
        }

        mock_post.side_effect = [mock_response_ssr, mock_response_seat]

        response = self.client.post(self.ssr_url, self.payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # AirSeatMaps must be empty list rather than breaking the request
        self.assertEqual(response.data["AirSeatMaps"], [])
        self.assertEqual(len(response.data["SSRFlightDetails"]), 1)

    @patch('flights.services.requests.post')
    def test_get_ssr_options_validation_error(self, mock_post):
        # Test validation error when missing flight_key or search_key
        payload = {"search_key": "mock_search_token_12345"}
        response = self.client.post(self.ssr_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class FlightInventoryTests(APITestCase):
    def setUp(self):
        self.url = reverse("flight_inventory")
        self.user = get_user_model().objects.create_user(
            username="agent1",
            password="testpass123",
            role="AGENT",
        )
        self.client.force_authenticate(user=self.user)
        self.payload = {
            "airline_code": "AI",
            "airline_name": "Air India",
            "flight_number": "AI121",
            "origin": "DEL",
            "destination": "BOM",
            "departure_datetime": "2026-07-01T23:00:00Z",
            "arrival_datetime": "2026-07-02T01:30:00Z",
            "price": "1000.00",
            "seats_available": 10,
            "cabin_class": "Economy",
            "duration": "2h 30m",
            "is_refundable": True,
            "baggage_check_in": "15 kg",
            "baggage_hand": "7 kg",
            "apis_required": True,
            "policies": {
                "cancellation": "Non-refundable within 24 hours.",
                "change": "Changes allowed with fee.",
            },
            "segments": [
                {
                    "segment_id": 0,
                    "airline_code": "AI",
                    "airline_name": "Air India",
                    "flight_number": "AI121",
                    "aircraft_type": "Airbus A320",
                    "origin": "DEL",
                    "origin_city": "New Delhi",
                    "origin_terminal": "Terminal 3",
                    "destination": "BOM",
                    "destination_city": "Mumbai",
                    "destination_terminal": "Terminal 2",
                    "departure_datetime": "2026-07-01T23:00:00Z",
                    "arrival_datetime": "2026-07-02T01:30:00Z",
                    "duration": "2h 30m",
                    "stop_over": None,
                    "return_flight": False,
                }
            ],
        }

    def test_create_inventory_success(self):
        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FlightInventory.objects.count(), 1)

        inventory = FlightInventory.objects.get()
        self.assertEqual(inventory.created_by, self.user)
        self.assertEqual(inventory.origin, "DEL")
        self.assertEqual(inventory.segments[0]["destination"], "BOM")

    def test_create_inventory_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
