import random
import logging
import requests
from django.conf import settings
from rest_framework.exceptions import APIException

logger = logging.getLogger('flights.provider')

class ProviderAPIException(APIException):
    status_code = 502
    default_detail = 'Flight Provider API encountered an error.'
    default_code = 'provider_error'

class ProviderService:
    @staticmethod
    def generate_request_id():
        """
        Generates a random 25-digit numeric string for tracking FlyShop API calls.
        """
        return "".join([str(random.randint(0, 9)) for _ in range(25)])

    @classmethod
    def search_flights(cls, validated_data):
        """
        Communicates with the external FlyShop UAT API, normalizes the response,
        and logs the integration flow securely.
        """
        # Read parameters from settings
        base_url = settings.FLIGHT_API_BASE_URL.rstrip('/')
        endpoint = f"{base_url}/airlinehost/AirAPIService.svc/JSONService/Air_Search"
        
        # Extract query inputs
        origin = validated_data.get('origin')
        destination = validated_data.get('destination')
        travel_date = validated_data.get('travel_date')
        return_date = validated_data.get('return_date')
        adults = validated_data.get('adult_count', 1)
        children = validated_data.get('child_count', 0)
        infants = validated_data.get('infant_count', 0)
        class_of_travel = validated_data.get('class_of_travel', '0')
        airline_code = validated_data.get('airline_code', '')

        # Generate unique request trace id
        request_id = cls.generate_request_id()

        # Build auth header
        auth_header = {
            "UserId": settings.FLIGHT_API_USER_ID,
            "Password": settings.FLIGHT_API_PASSWORD,
            "IP_Address": settings.FLIGHT_API_IP_ADDRESS,
            "Request_Id": request_id,
            "IMEI_Number": settings.FLIGHT_API_IMEI
        }

        # Build TripInfo list
        trip_info = [
            {
                "Origin": origin,
                "Destination": destination,
                "TravelDate": travel_date.strftime("%m/%d/%Y"),
                "Trip_Id": 0
            }
        ]

        travel_type = 0  # 0 = One Way, 1 = Return
        if return_date:
            travel_type = 1
            trip_info.append({
                "Origin": destination,
                "Destination": origin,
                "TravelDate": return_date.strftime("%m/%d/%Y"),
                "Trip_Id": 1
            })

        # Base search request payload
        payload = {
            "Auth_Header": auth_header,
            "Travel_Type": travel_type,
            "Booking_Type": 0,
            "TripInfo": trip_info,
            "Adult_Count": str(adults),
            "Child_Count": str(children),
            "Infant_Count": str(infants),
            "Class_Of_Travel": class_of_travel,
            "InventoryType": 0,
            "Filtered_Airline": [
                {
                    "Airline_Code": airline_code
                }
            ]
        }

        # Secure Log: Mask password in log output
        masked_payload = payload.copy()
        masked_payload["Auth_Header"] = auth_header.copy()
        masked_payload["Auth_Header"]["Password"] = "********"
        logger.info(f"Outgoing FlyShop Search Request [ID: {request_id}]: {masked_payload}")

        try:
            response = requests.post(endpoint, json=payload, timeout=60)
            response.raise_for_status()
            response_json = response.json()
        except requests.RequestException as e:
            logger.error(f"HTTP Connection failure to FlyShop [ID: {request_id}]: {str(e)}")
            raise ProviderAPIException("Unable to connect to the external flight service provider.")
        except ValueError:
            logger.error(f"Invalid JSON response returned from FlyShop [ID: {request_id}]")
            raise ProviderAPIException("Received invalid response from the flight service provider.")

        # Log incoming response metadata
        logger.info(f"Incoming FlyShop Search Response [ID: {request_id}] status_code={response.status_code}")

        # Check response headers for provider-specific errors
        response_header = response_json.get('Response_Header', {})
        error_code = response_header.get('Error_Code', '0000')
        error_desc = response_header.get('Error_Desc', 'SUCCESS')

        if error_code != '0000' and error_code != '000':
            logger.error(f"FlyShop search failed [ID: {request_id}] Code: {error_code}, Desc: {error_desc}")
            raise ProviderAPIException(f"Provider Error: {error_desc} (Code: {error_code})")

        # Normalize the raw results
        search_key = response_json.get('Search_Key')
        raw_trip_details = response_json.get('TripDetails', [])
        
        normalized_flights = cls._normalize_trip_details(raw_trip_details)

        return {
            "search_key": search_key,
            "flights": normalized_flights
        }

    @classmethod
    def _normalize_trip_details(cls, raw_trip_details):
        """
        Parses FlyShop's deeply nested flights and fares into a clean frontend layout.
        """
        normalized_list = []

        for trip in raw_trip_details:
            raw_flights = trip.get('Flights', [])
            
            for flight in raw_flights:
                airline_code = flight.get('Airline_Code')
                destination = flight.get('Destination')
                block_ticket_allowed = flight.get('Block_Ticket_Allowed', False)
                cached = flight.get('Cached', False)

                # Segment normalization (stops, airports, terminals, schedules)
                raw_segments = flight.get('Segments', [])
                normalized_segments = []
                
                for seg in raw_segments:
                    normalized_segments.append({
                        "segment_id": seg.get('Segment_Id', 0),
                        "airline_code": seg.get('Airline_Code', airline_code),
                        "airline_name": seg.get('Airline_Name', ''),
                        "flight_number": seg.get('Flight_Number', '').strip(),
                        "aircraft_type": seg.get('Aircraft_Type', ''),
                        "origin": seg.get('Origin', ''),
                        "origin_city": seg.get('Origin_City', ''),
                        "origin_terminal": seg.get('Origin_Terminal', ''),
                        "destination": seg.get('Destination', ''),
                        "destination_city": seg.get('Destination_City', ''),
                        "destination_terminal": seg.get('Destination_Terminal', ''),
                        "departure_datetime": seg.get('Departure_DateTime', ''),
                        "arrival_datetime": seg.get('Arrival_DateTime', ''),
                        "duration": seg.get('Duration', ''),
                        "stop_over": seg.get('Stop_Over'),
                        "return_flight": seg.get('Return_Flight', False)
                    })

                # Determine dynamic origin and destination airports based on segment chain
                computed_origin = normalized_segments[0]["origin"] if normalized_segments else ""
                computed_destination = normalized_segments[-1]["destination"] if normalized_segments else destination

                # Fare option normalization (prices, classes, refundability)
                raw_fares = flight.get('Fares', [])
                normalized_fares = []

                for fare in raw_fares:
                    fare_id = fare.get('Fare_Id')
                    refundable = fare.get('Refundable', True)
                    seats_available = fare.get('Seats_Available', '')
                    food_onboard = fare.get('Food_onboard', 'F')
                    gst_mandatory = fare.get('GSTMandatory', False)
                    
                    # Extract exact pricing details from within FareDetails array
                    raw_details_list = fare.get('FareDetails', [])
                    price_details = {
                        "currency": "INR",
                        "basic_amount": 0.0,
                        "tax_amount": 0.0,
                        "total_amount": 0.0
                    }
                    baggage_details = {
                        "check_in": None,
                        "hand": None
                    }

                    if raw_details_list:
                        # Taking first fare detail object (covers normalized single customer quote)
                        detail = raw_details_list[0]
                        price_details = {
                            "currency": detail.get('Currency_Code', 'INR'),
                            "basic_amount": float(detail.get('Basic_Amount', 0.0)),
                            "tax_amount": float(detail.get('AirportTax_Amount', 0.0)),
                            "total_amount": float(detail.get('Total_Amount', 0.0))
                        }
                        raw_baggage = detail.get('Free_Baggage', {})
                        baggage_details = {
                            "check_in": raw_baggage.get('Check_In_Baggage'),
                            "hand": raw_baggage.get('Hand_Baggage')
                        }

                    normalized_fares.append({
                        "fare_id": fare_id,
                        "refundable": refundable,
                        "seats_available": seats_available,
                        "food_onboard": food_onboard,
                        "gst_mandatory": gst_mandatory,
                        "price_details": price_details,
                        "baggage": baggage_details
                    })

                normalized_list.append({
                    "airline_code": airline_code,
                    "origin": computed_origin,
                    "destination": computed_destination,
                    "block_ticket_allowed": block_ticket_allowed,
                    "cached": cached,
                    "segments": normalized_segments,
                    "fares": normalized_fares
                })

        return normalized_list
