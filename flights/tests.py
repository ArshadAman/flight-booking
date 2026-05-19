import json
from unittest.mock import patch, MagicMock
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from datetime import date, timedelta
from flights.serializers import FlightSearchRequestSerializer

class FlightSearchTests(APITestCase):
    def setUp(self):
        self.search_url = reverse('flight_search')
        self.valid_payload = {
            "origin": "DEL",
            "destination": "BOM",
            "travel_date": (date.today() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "adult_count": 1,
            "child_count": 0,
            "infant_count": 0,
            "class_of_travel": "0"
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
