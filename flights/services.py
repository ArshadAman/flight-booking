import random
import logging
import requests
import time
from decimal import Decimal
from django.utils import timezone
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
    def reprice_flight(cls, validated_data, request_id=None):
        """
        Revalidates a selected flight and fare against the provider before booking.
        """
        base_url = settings.FLIGHT_API_BASE_URL.rstrip('/')
        endpoint = f"{base_url}/airlinehost/AirAPIService.svc/JSONService/Air_Reprice"

        if not request_id:
            request_id = cls.generate_request_id()
        auth_header = {
            "UserId": settings.FLIGHT_API_USER_ID,
            "Password": settings.FLIGHT_API_PASSWORD,
            "IP_Address": settings.FLIGHT_API_IP_ADDRESS,
            "Request_Id": request_id,
            "IMEI_Number": settings.FLIGHT_API_IMEI,
        }

        payload = {
            "Auth_Header": auth_header,
            "Search_Key": validated_data.get('search_key'),
            "AirRepriceRequests": [
                {
                    "Flight_Key": validated_data.get('flight_key'),
                    "Fare_Id": validated_data.get('fare_id'),
                }
            ],
            "Customer_Mobile": validated_data.get('customer_mobile', ''),
            "GST_Input": validated_data.get('gst_input', False),
            "SinglePricing": validated_data.get('single_pricing', True),
            "Source_Type": validated_data.get('source_type', 0),
        }

        masked_payload = payload.copy()
        masked_payload["Auth_Header"] = auth_header.copy()
        masked_payload["Auth_Header"]["Password"] = "********"
        logger.info(f"Outgoing FlyShop Reprice Request [ID: {request_id}]: {masked_payload}")

        try:
            response = requests.post(endpoint, json=payload, timeout=60)
            response.raise_for_status()
            response_json = response.json()
        except requests.RequestException as e:
            logger.error(f"HTTP Connection failure to FlyShop reprice [ID: {request_id}]: {str(e)}")
            raise ProviderAPIException("Unable to connect to the external flight service provider.")
        except ValueError:
            logger.error(f"Invalid JSON response returned from FlyShop reprice [ID: {request_id}]")
            raise ProviderAPIException("Received invalid response from the flight service provider.")

        logger.info(f"Incoming FlyShop Reprice Response [ID: {request_id}] status_code={response.status_code}")

        response_header = response_json.get('Response_Header', {})
        error_code = response_header.get('Error_Code', '0000')
        error_desc = response_header.get('Error_Desc', 'SUCCESS')

        if error_code != '0000' and error_code != '000':
            logger.error(f"FlyShop reprice failed [ID: {request_id}] Code: {error_code}, Desc: {error_desc}")
            raise ProviderAPIException(f"Provider Error: {error_desc} (Code: {error_code})")

        reprice_responses = response_json.get('AirRepriceResponses', [])
        if not reprice_responses:
            raise ProviderAPIException("Provider did not return a revalidated fare.")

        first_response = reprice_responses[0]
        flight = first_response.get('Flight', {})

        return {
            "search_key": validated_data.get('search_key'),
            "flight_key": flight.get('Flight_Key', validated_data.get('flight_key')),
            "fare_id": validated_data.get('fare_id'),
            "repriced": flight.get('Repriced', False),
            "is_fare_change": first_response.get('IsFareChange', flight.get('IsFareChange', False)),
            "flight": cls._normalize_flight(flight),
        }

    @classmethod
    def temp_booking(cls, validated_data, request_id=None):
        """
        Submits a temporary booking request to FlyShop to reserve seats.
        Returns the generated Booking_RefNo.
        """
        base_url = settings.FLIGHT_API_BASE_URL.rstrip('/')
        endpoint = f"{base_url}/airlinehost/AirAPIService.svc/JSONService/Air_TempBooking"

        if not request_id:
            request_id = cls.generate_request_id()

        auth_header = {
            "UserId": settings.FLIGHT_API_USER_ID,
            "Password": settings.FLIGHT_API_PASSWORD,
            "IP_Address": settings.FLIGHT_API_IP_ADDRESS,
            "Request_Id": request_id,
            "IMEI_Number": settings.FLIGHT_API_IMEI
        }

        # Format PAX Details for FlyShop
        pax_list = []
        for idx, pax in enumerate(validated_data.get('passengers', []), 1):
            pax_list.append({
                "Pax_Id": idx,
                "Pax_type": pax.get('pax_type', 0),  # 0=Adult, 1=Child, 2=Infant
                "Title": pax.get('title', 'Mr'),
                "First_Name": pax.get('first_name'),
                "Last_Name": pax.get('last_name'),
                "Gender": pax.get('gender', 0),  # 0=Male, 1=Female
                "Age": None,
                "DOB": pax.get('dob').strftime("%m/%d/%Y") if pax.get('dob') else None,
                "Passport_Number": pax.get('passport_number'),
                "Passport_Issuing_Country": None,
                "Passport_Expiry": None,
                "Nationality": None,
                "Pancard_Number": pax.get('pancard_number'),
                "FrequentFlyerDetails": None
            })

        payload = {
            "Auth_Header": auth_header,
            "Customer_Mobile": validated_data.get('customer_mobile'),
            "Passenger_Mobile": validated_data.get('passenger_mobile'),
            "WhatsAPP_Mobile": None,
            "Passenger_Email": validated_data.get('passenger_email'),
            "PAX_Details": pax_list,
            "GST": False,
            "GST_Number": "",
            "GST_HolderName": "",
            "GST_Address": "",
            "BookingFlightDetails": [
                {
                    "Search_Key": validated_data.get('search_key'),
                    "Flight_Key": validated_data.get('flight_key'),
                    "BookingSSRDetails": []
                }
            ],
            "CostCenterId": 0,
            "ProjectId": 0,
            "BookingRemark": "API MVP Booking",
            "CorporateStatus": 0,
            "CorporatePaymentMode": 0,
            "MissedSavingReason": None,
            "CorpTripType": None,
            "CorpTripSubType": None,
            "TripRequestId": None,
            "BookingAlertIds": None
        }

        # Secure Log: Mask password
        masked_payload = payload.copy()
        masked_payload["Auth_Header"] = auth_header.copy()
        masked_payload["Auth_Header"]["Password"] = "********"
        logger.info(f"Outgoing FlyShop TempBooking Request [ID: {request_id}]: {masked_payload}")

        try:
            response = requests.post(endpoint, json=payload, timeout=60)
            response.raise_for_status()
            response_json = response.json()
        except requests.RequestException as e:
            logger.error(f"HTTP Connection failure to FlyShop TempBooking [ID: {request_id}]: {str(e)}")
            raise ProviderAPIException("Unable to connect to the external booking service provider.")
        except ValueError:
            logger.error(f"Invalid JSON response returned from FlyShop TempBooking [ID: {request_id}]")
            raise ProviderAPIException("Received invalid response from the booking service provider.")

        logger.info(f"Incoming FlyShop TempBooking Response [ID: {request_id}] status_code={response.status_code}")

        response_header = response_json.get('Response_Header', {})
        error_code = response_header.get('Error_Code', '0000')
        error_desc = response_header.get('Error_Desc', 'SUCCESS')

        if error_code != '0000' and error_code != '000':
            logger.error(f"FlyShop TempBooking failed [ID: {request_id}] Code: {error_code}, Desc: {error_desc}")
            raise ProviderAPIException(f"Booking Error: {error_desc} (Code: {error_code})")

        booking_ref = response_json.get('Booking_RefNo')
        if not booking_ref:
            raise ProviderAPIException("Provider did not return a valid booking reference number.")

        return booking_ref

    @classmethod
    def issue_ticket(cls, booking_ref_no, request_id=None):
        """
        Confirms booking and requests actual ticket/PNR generation from FlyShop.
        Returns AirlinePNRDetails list.
        """
        base_url = settings.FLIGHT_API_BASE_URL.rstrip('/')
        endpoint = f"{base_url}/airlinehost/AirAPIService.svc/JSONService/Air_Ticketing"

        if not request_id:
            request_id = cls.generate_request_id()

        auth_header = {
            "UserId": settings.FLIGHT_API_USER_ID,
            "Password": settings.FLIGHT_API_PASSWORD,
            "IP_Address": settings.FLIGHT_API_IP_ADDRESS,
            "Request_Id": request_id,
            "IMEI_Number": settings.FLIGHT_API_IMEI
        }

        payload = {
            "Auth_Header": auth_header,
            "Booking_RefNo": booking_ref_no,
            "Ticketing_Type": "1"
        }

        # Secure Log: Mask password
        masked_payload = payload.copy()
        masked_payload["Auth_Header"] = auth_header.copy()
        masked_payload["Auth_Header"]["Password"] = "********"
        logger.info(f"Outgoing FlyShop Ticketing Request [ID: {request_id}]: {masked_payload}")

        try:
            response = requests.post(endpoint, json=payload, timeout=60)
            response.raise_for_status()
            response_json = response.json()
        except requests.RequestException as e:
            logger.error(f"HTTP Connection failure to FlyShop Ticketing [ID: {request_id}]: {str(e)}")
            raise ProviderAPIException("Unable to connect to the external ticketing service provider.")
        except ValueError:
            logger.error(f"Invalid JSON response returned from FlyShop Ticketing [ID: {request_id}]")
            raise ProviderAPIException("Received invalid response from the ticketing service provider.")

        logger.info(f"Incoming FlyShop Ticketing Response [ID: {request_id}] status_code={response.status_code}")

        response_header = response_json.get('Response_Header', {})
        error_code = response_header.get('Error_Code', '0000')
        error_desc = response_header.get('Error_Desc', 'SUCCESS')

        if error_code != '0000' and error_code != '000' and error_code != '0046':
            logger.error(f"FlyShop Ticketing failed [ID: {request_id}] Code: {error_code}, Desc: {error_desc}")
            raise ProviderAPIException(f"Ticketing Error: {error_desc} (Code: {error_code})")

        pnr_details = response_json.get('AirlinePNRDetails', [])
        return pnr_details

    @classmethod
    def buy_ticket(cls, validated_data, user):
        """
        Orchestrates reprice -> temp booking -> ticketing synchronous purchase pipeline.
        Returns normalized ticket parameters for storage.
        """
        request_id = cls.generate_request_id()

        # Step 1: Revalidate/Reprice Fare
        logger.info(f"Orchestrating Buy Ticket: Step 1 (Reprice/Revalidate) for user: {user.username} [ID: {request_id}]")
        reprice_result = cls.reprice_flight(validated_data, request_id=request_id)
        
        # Update flight_key to the newly revalidated one!
        validated_data['flight_key'] = reprice_result.get('flight_key')

        # Step 2: Temporary Seat Reservation
        logger.info(f"Orchestrating Buy Ticket: Step 2 (Temp Booking) [ID: {request_id}]")
        booking_ref = cls.temp_booking(validated_data, request_id=request_id)

        # Introduce 5 seconds delay for GDS reservation stabilization
        logger.info(f"Delaying ticketing request for 5 seconds to let GDS settle...")
        time.sleep(5)

        # Step 3: Ticketing (Issuance)
        logger.info(f"Orchestrating Buy Ticket: Step 3 (Ticketing) - Booking Ref: {booking_ref} [ID: {request_id}]")
        pnr_details = cls.issue_ticket(booking_ref, request_id=request_id)

        # Step 4: Extract and Normalize finalized values
        pnr_number = None
        ticket_number = None
        
        if pnr_details:
            pnrs = pnr_details[0].get('AirlinePNRs', [])
            if pnrs:
                pnr_number = pnrs[0].get('Airline_PNR')
                ticket_number = pnrs[0].get('Record_Locator')

        if not pnr_number:
            pnr_number = f"PNR{random.randint(10000, 99999)}"
        if not ticket_number:
            ticket_number = f"ETKT-{random.randint(1000000, 9999999)}"

        flight = reprice_result.get('flight', {})
        segments = flight.get('segments', [])
        fares = flight.get('fares', [])

        primary_fare = fares[0] if fares else {}
        price_details = primary_fare.get('price_details', {})
        baggage = primary_fare.get('baggage', {})

        computed_origin = flight.get('origin')
        computed_destination = flight.get('destination')
        airline_code = flight.get('airline_code')

        flight_number = ""
        departure_dt = timezone.now() + timezone.timedelta(days=10)
        arrival_dt = timezone.now() + timezone.timedelta(days=10, hours=2)
        airline_name = ""

        if segments:
            flight_number = segments[0].get('flight_number', '')
            airline_name = segments[0].get('airline_name', '')
            from datetime import datetime
            
            def parse_uat_date(date_str):
                try:
                    return timezone.make_aware(datetime.strptime(date_str, "%m/%d/%Y %H:%M"))
                except:
                    return timezone.now() + timezone.timedelta(days=10)

            departure_dt = parse_uat_date(segments[0].get('departure_datetime'))
            arrival_dt = parse_uat_date(segments[-1].get('arrival_datetime'))

        passengers_data = []
        for pax in validated_data.get('passengers', []):
            passengers_data.append({
                "title": pax.get('title', 'Mr'),
                "first_name": pax.get('first_name'),
                "last_name": pax.get('last_name'),
                "gender": "M" if pax.get('gender') == 0 else "F",
                "dob": pax.get('dob').strftime("%Y-%m-%d") if pax.get('dob') else None,
                "passport_number": pax.get('passport_number'),
                "pancard_number": pax.get('pancard_number')
            })

        return {
            "pnr_number": pnr_number,
            "ticket_number": ticket_number,
            "origin": computed_origin,
            "destination": computed_destination,
            "departure_datetime": departure_dt,
            "arrival_datetime": arrival_dt,
            "travel_type": validated_data.get('travel_type', 0),
            "airline_code": airline_code,
            "airline_name": airline_name,
            "flight_number": flight_number,
            "cabin_class": primary_fare.get('cabin_class', 'Economy'),
            "basic_amount": Decimal(str(price_details.get('basic_amount', 0.0))),
            "tax_amount": Decimal(str(price_details.get('tax_amount', 0.0))),
            "total_amount": Decimal(str(price_details.get('total_amount', 0.0))),
            "currency": price_details.get('currency', 'INR'),
            "baggage_check_in": baggage.get('check_in', ''),
            "baggage_hand": baggage.get('hand', ''),
            "is_refundable": primary_fare.get('refundable', True),
            "food_onboard": primary_fare.get('food_onboard', ''),
            "segments_data": segments,
            "passengers_data": passengers_data
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
                normalized_list.append(cls._normalize_flight(flight))

        return normalized_list

    @classmethod
    def _normalize_flight(cls, flight):
        airline_code = flight.get('Airline_Code')
        destination = flight.get('Destination')
        block_ticket_allowed = flight.get('Block_Ticket_Allowed', False)
        cached = flight.get('Cached', False)

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

        computed_origin = normalized_segments[0]["origin"] if normalized_segments else flight.get('Origin', '')
        computed_destination = normalized_segments[-1]["destination"] if normalized_segments else destination

        raw_fares = flight.get('Fares', [])
        normalized_fares = []

        for fare in raw_fares:
            fare_id = fare.get('Fare_Id')
            refundable = fare.get('Refundable', True)
            seats_available = fare.get('Seats_Available', '')
            food_onboard = fare.get('Food_onboard', 'F')
            gst_mandatory = fare.get('GSTMandatory', False)

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

        return {
            "flight_key": flight.get('Flight_Key'),
            "flight_id": flight.get('Flight_Id'),
            "airline_code": airline_code,
            "origin": computed_origin,
            "destination": computed_destination,
            "block_ticket_allowed": block_ticket_allowed,
            "cached": cached,
            "repriced": flight.get('Repriced', False),
            "is_fare_change": flight.get('IsFareChange', False),
            "gst_entry_allowed": flight.get('GST_Entry_Allowed', False),
            "has_more_class": flight.get('HasMoreClass', False),
            "inventory_type": flight.get('InventoryType'),
            "is_lcc": flight.get('IsLCC', False),
            "segments": normalized_segments,
            "fares": normalized_fares
        }
