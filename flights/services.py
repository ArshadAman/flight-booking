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
    def format_local_flight(cls, lf, is_return=False):
        segs = []
        if lf.segments:
            for idx, s in enumerate(lf.segments):
                segs.append({
                    "Segment_Id": s.get('segment_id', idx),
                    "Airline_Code": s.get('airline_code', lf.airline_code),
                    "Airline_Name": s.get('airline_name', lf.airline_name),
                    "Flight_Number": s.get('flight_number', lf.flight_number),
                    "Aircraft_Type": s.get('aircraft_type', 'Airbus A320'),
                    "Origin": s.get('origin', lf.origin),
                    "Origin_City": s.get('origin_city', ''),
                    "Origin_Terminal": s.get('origin_terminal', 'Terminal 3'),
                    "Destination": s.get('destination', lf.destination),
                    "Destination_City": s.get('destination_city', ''),
                    "Destination_Terminal": s.get('destination_terminal', 'Terminal 3'),
                    "Departure_DateTime": s.get('departure_datetime', lf.departure_datetime.isoformat()),
                    "Arrival_DateTime": s.get('arrival_datetime', lf.arrival_datetime.isoformat()),
                    "Duration": s.get('duration', lf.duration),
                    "Stop_Over": s.get('stop_over', None),
                    "Return_Flight": is_return
                })
        else:
            segs.append({
                "Segment_Id": 0,
                "Airline_Code": lf.airline_code,
                "Airline_Name": lf.airline_name,
                "Flight_Number": lf.flight_number,
                "Aircraft_Type": "Airbus A320",
                "Origin": lf.origin,
                "Origin_City": "",
                "Origin_Terminal": "Terminal 3",
                "Destination": lf.destination,
                "Destination_City": "",
                "Destination_Terminal": "Terminal 3",
                "Departure_DateTime": lf.departure_datetime.isoformat(),
                "Arrival_DateTime": lf.arrival_datetime.isoformat(),
                "Duration": lf.duration,
                "Stop_Over": None,
                "Return_Flight": is_return
            })
            
        fare_details = {
            "Currency_Code": "INR",
            "Basic_Amount": float(lf.price),
            "AirportTax_Amount": 0.0,
            "Total_Amount": float(lf.price),
            "Free_Baggage": {
                "Check_In_Baggage": lf.baggage_check_in,
                "Hand_Baggage": lf.baggage_hand
            },
            "FareClasses": [
                {
                    "FareBasis": "E",
                    "Class_Desc": "Economy"
                }
            ]
        }
        
        return {
            "flight_key": f"local-{lf.id}",
            "id": f"local-{lf.id}",
            "Airline_Code": lf.airline_code,
            "Airline_Name": lf.airline_name,
            "Flight_Number": lf.flight_number,
            "Origin": lf.origin,
            "Destination": lf.destination,
            "Departure_DateTime": lf.departure_datetime.isoformat(),
            "Arrival_DateTime": lf.arrival_datetime.isoformat(),
            "Duration": lf.duration,
            "is_agent_flight": True,
            "agent_flight_id": lf.id,
            "Segments": segs,
            "Fares": [
                {
                    "Fare_Id": f"local-{lf.id}-fare",
                    "Refundable": lf.is_refundable,
                    "Seats_Available": str(lf.seats_available),
                    "Food_onboard": "F",
                    "GSTMandatory": False,
                    "ProductClass": "PUB",
                    "FareDetails": [fare_details]
                }
            ]
        }

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
        student_fare_search = validated_data.get('student_fare_search', False)
        defence_fare_search = validated_data.get('defence_fare_search', False)

        request_id = cls.generate_request_id()
        auth_header = {
            "UserId": settings.FLIGHT_API_USER_ID,
            "Password": settings.FLIGHT_API_PASSWORD,
            "IP_Address": settings.FLIGHT_API_IP_ADDRESS,
            "Request_Id": request_id,
            "IMEI_Number": settings.FLIGHT_API_IMEI
        }

        # Build TripInfo list
        trip_segments = validated_data.get('trip_segments', [])
        explicit_travel_type = validated_data.get('travel_type', None)

        if explicit_travel_type == 2 and trip_segments:
            # Multi-city: each segment becomes a TripInfo leg
            travel_type = 2
            trip_info = [
                {
                    "Origin": seg['origin'],
                    "Destination": seg['destination'],
                    "TravelDate": seg['travel_date'].strftime("%m/%d/%Y"),
                    "Trip_Id": idx
                }
                for idx, seg in enumerate(trip_segments)
            ]
        else:
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
            "SrCitizen_Search": False,
            "StudentFare_Search": student_fare_search,
            "DefenceFare_Search": defence_fare_search,
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

        # Fetch local inventory flights and merge them
        try:
            from flights.models import FlightInventory
            from datetime import timedelta
            import datetime as dt_module
            
            # Query a 3-day range of departure dates in database to account for any timezone rollover
            local_outbound_qs = FlightInventory.objects.filter(
                origin=origin,
                destination=destination,
                departure_datetime__date__range=[travel_date - timedelta(days=1), travel_date + timedelta(days=1)]
            )
            
            local_return_qs = []
            if return_date:
                local_return_qs = FlightInventory.objects.filter(
                    origin=destination,
                    destination=origin,
                    departure_datetime__date__range=[return_date - timedelta(days=1), return_date + timedelta(days=1)]
                )
                
            # Filter the queryset in python using local timezone offset (IST: +5:30)
            matching_outbound = []
            for lf in local_outbound_qs:
                local_dep = lf.departure_datetime + dt_module.timedelta(hours=5, minutes=30)
                if local_dep.date() == travel_date:
                    matching_outbound.append(lf)
                    
            matching_return = []
            for lf in local_return_qs:
                local_dep = lf.departure_datetime + dt_module.timedelta(hours=5, minutes=30)
                if local_dep.date() == return_date:
                    matching_return.append(lf)
                
            local_outbound_raw = [cls.format_local_flight(lf, is_return=False) for lf in matching_outbound]
            local_return_raw = [cls.format_local_flight(lf, is_return=True) for lf in matching_return]
            
            if not raw_trip_details:
                raw_trip_details = [{"Trip_Id": 0, "Flights": []}]
                if return_date:
                    raw_trip_details.append({"Trip_Id": 1, "Flights": []})
                    
            if raw_trip_details:
                outbound_trip = raw_trip_details[0]
                if 'Flights' not in outbound_trip:
                    outbound_trip['Flights'] = []
                outbound_trip['Flights'].extend(local_outbound_raw)
                
                if len(raw_trip_details) > 1 and local_return_raw:
                    return_trip = raw_trip_details[1]
                    if 'Flights' not in return_trip:
                        return_trip['Flights'] = []
                    return_trip['Flights'].extend(local_return_raw)
                    
        except Exception as local_err:
            logger.error(f"Failed to query/merge local inventory flights: {str(local_err)}")

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
        flight_key = validated_data.get('flight_key', '')
        if flight_key and flight_key.startswith("local-"):
            try:
                local_id = flight_key.replace("local-", "")
                from flights.models import FlightInventory
                lf = FlightInventory.objects.get(id=local_id)
            except (IndexError, ValueError, FlightInventory.DoesNotExist):
                raise ProviderAPIException("Selected local flight inventory not found.")
            
            raw_local = cls.format_local_flight(lf, is_return=False)
            normalized = cls._normalize_flight(raw_local)
            return {
                "search_key": validated_data.get('search_key'),
                "flight_key": flight_key,
                "fare_id": validated_data.get('fare_id'),
                "repriced": True,
                "is_fare_change": False,
                "flight": normalized,
            }

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
        flight_key = validated_data.get('flight_key', '')
        if flight_key and flight_key.startswith("local-"):
            booking_ref = f"FBA{random.randint(100000, 999999)}"
            return booking_ref, request_id

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
            dob_val = pax.get('dob')
            dob_str = dob_val.strftime("%m/%d/%Y") if dob_val else None

            defence_issue_val = pax.get('defence_issue_date')
            defence_issue_str = defence_issue_val.strftime("%m/%d/%Y") if hasattr(defence_issue_val, 'strftime') else (defence_issue_val or None)

            defence_expiry_val = pax.get('defence_expiry_date')
            defence_expiry_str = defence_expiry_val.strftime("%m/%d/%Y") if hasattr(defence_expiry_val, 'strftime') else (defence_expiry_val or None)

            pax_list.append({
                "Pax_Id": idx,
                "Pax_type": pax.get('pax_type', 0),  # 0=Adult, 1=Child, 2=Infant
                "Title": pax.get('title', 'Mr'),
                "First_Name": pax.get('first_name'),
                "Last_Name": pax.get('last_name'),
                "Gender": pax.get('gender', 0),  # 0=Male, 1=Female
                "Age": None,
                "DOB": dob_str,
                "Passport_Number": pax.get('passport_number'),
                "Passport_Issuing_Country": None,
                "Passport_Expiry": None,
                "Nationality": None,
                "Pancard_Number": pax.get('pancard_number'),
                "FrequentFlyerDetails": None,
                "Student_Id": pax.get('student_id') or None,
                "DefenceServiceId": pax.get('defence_service_id') or None,
                "DefenceIssueDate": defence_issue_str,
                "DefenceExpiryDate": defence_expiry_str,
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
                    "BookingSSRDetails": validated_data.get('booking_ssr_details', [])
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

        return booking_ref, request_id

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
        flight_key = reprice_result.get('flight_key')
        validated_data['flight_key'] = flight_key
        
        is_local = flight_key and flight_key.startswith("local-")
        local_flight_obj = None

        if is_local:
            booking_ref = f"FBA{random.randint(100000, 999999)}"
            # Decrement seats in local inventory
            try:
                local_id = flight_key.replace("local-", "")
                from flights.models import FlightInventory
                lf = FlightInventory.objects.get(id=local_id)
                local_flight_obj = lf
                pax_count = len(validated_data.get('passengers', []))
                if lf.seats_available >= pax_count:
                    lf.seats_available -= pax_count
                    lf.save()
                else:
                    raise ProviderAPIException("Not enough seats available in local flight inventory.")
            except FlightInventory.DoesNotExist:
                raise ProviderAPIException("Selected flight inventory does not exist.")
            
            pnr_details = []
            pnr_number = None
            ticket_number = None
            flight_id = flight_key
        else:
            # Step 2: Temporary Seat Reservation
            logger.info(f"Orchestrating Buy Ticket: Step 2 (Temp Booking) [ID: {request_id}]")
            booking_ref, request_id = cls.temp_booking(validated_data, request_id=request_id)

            # Introduce 5 seconds delay for GDS reservation stabilization
            logger.info(f"Delaying ticketing request for 5 seconds to let GDS settle...")
            time.sleep(5)

            # Step 3: Ticketing (Issuance)
            logger.info(f"Orchestrating Buy Ticket: Step 3 (Ticketing) - Booking Ref: {booking_ref} [ID: {request_id}]")
            pnr_details = cls.issue_ticket(booking_ref, request_id=request_id)

            pnr_number = None
            ticket_number = None
            flight_id = None
            
            if pnr_details:
                pnrs = pnr_details[0].get('AirlinePNRs', [])
                if pnrs:
                    pnr_number = pnrs[0].get('Airline_PNR')
                    ticket_number = pnrs[0].get('Record_Locator')
                flight_id = pnr_details[0].get('Flight_Id')

        # Step 4: Extract and Normalize finalized values
        flight = reprice_result.get('flight', {})
        if not flight_id:
            flight_id = flight.get('flight_id')

        if not is_local:
            if not pnr_number:
                pnr_number = f"PNR{random.randint(10000, 99999)}"
            if not ticket_number:
                ticket_number = f"ETKT-{random.randint(1000000, 9999999)}"
        segments = flight.get('segments', [])
        fares = flight.get('fares', [])

        primary_fare = fares[0] if fares else {}
        price_details = primary_fare.get('price_details', {}).copy()

        if is_local and local_flight_obj:
            try:
                cabin = (local_flight_obj.cabin_class or "Economy").lower()
                is_premium = "business" in cabin or "first" in cabin or "premium" in cabin
                tax_rate = 0.12 if is_premium else 0.05
                basic_pax = float(local_flight_obj.price)
                tax_pax = round(basic_pax * tax_rate, 2)
                total_pax = basic_pax + tax_pax
                price_details["basic_amount"] = basic_pax
                price_details["tax_amount"] = tax_pax
                price_details["total_amount"] = total_pax
            except Exception as e:
                logger.error(f"Error calculating local ticket pricing: {e}")
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
                    try:
                        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        if timezone.is_naive(dt):
                            return timezone.make_aware(dt)
                        return dt
                    except:
                        return timezone.now() + timezone.timedelta(days=10)

            departure_dt = parse_uat_date(segments[0].get('departure_datetime'))
            arrival_dt = parse_uat_date(segments[-1].get('arrival_datetime'))

        passengers_data = []
        for pax in validated_data.get('passengers', []):
            dob_val = pax.get('dob')
            dob_str = dob_val.strftime("%Y-%m-%d") if dob_val else None

            pax_entry = {
                "title": pax.get('title', 'Mr'),
                "first_name": pax.get('first_name'),
                "last_name": pax.get('last_name'),
                "gender": "M" if pax.get('gender') == 0 else "F",
                "dob": dob_str,
                "passport_number": pax.get('passport_number'),
                "pancard_number": pax.get('pancard_number')
            }
            if pax.get('student_id'):
                pax_entry['student_id'] = pax.get('student_id')
            if pax.get('defence_service_id'):
                pax_entry['defence_service_id'] = pax.get('defence_service_id')

            defence_issue = pax.get('defence_issue_date')
            if defence_issue:
                pax_entry['defence_issue_date'] = defence_issue.strftime("%Y-%m-%d") if hasattr(defence_issue, 'strftime') else defence_issue

            defence_expiry = pax.get('defence_expiry_date')
            if defence_expiry:
                pax_entry['defence_expiry_date'] = defence_expiry.strftime("%Y-%m-%d") if hasattr(defence_expiry, 'strftime') else defence_expiry

            # Preserve meal choices if present
            if pax.get('outbound_meal'):
                pax_entry['outbound_meal'] = pax.get('outbound_meal')
            if pax.get('return_meal'):
                pax_entry['return_meal'] = pax.get('return_meal')
            if pax.get('meal_code'):
                pax_entry['meal_code'] = pax.get('meal_code')

            passengers_data.append(pax_entry)

        return {
            "pnr_number": pnr_number,
            "ticket_number": ticket_number,
            "booking_ref": booking_ref,
            "flight_id": flight_id,
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
            "passengers_data": passengers_data,
            "ssr_data": {"BookingSSRDetails": validated_data.get('booking_ssr_details', [])}
        }

    @classmethod
    def cancel_ticket(cls, pnr, booking_ref, cancel_details=None, flight_id="0", passenger_id="1", segment_id="0", remarks="Customer requested cancellation", cancellation_type=0):
        """
        Sends a ticket cancellation request to the GDS Air_TicketCancellation endpoint.
        Returns True on success, raises ProviderAPIException on failure.
        """
        base_url = settings.FLIGHT_API_BASE_URL.rstrip('/')
        endpoint = f"{base_url}/airlinehost/AirAPIService.svc/JSONService/Air_TicketCancellation"

        request_id = cls.generate_request_id()
        auth_header = {
            "UserId": settings.FLIGHT_API_USER_ID,
            "Password": settings.FLIGHT_API_PASSWORD,
            "IP_Address": settings.FLIGHT_API_IP_ADDRESS,
            "Request_Id": request_id,
            "IMEI_Number": settings.FLIGHT_API_IMEI,
        }

        if not cancel_details:
            cancel_details = [
                {
                    "FlightId": flight_id,
                    "PassengerId": passenger_id,
                    "SegmentId": segment_id,
                }
            ]

        payload = {
            "Auth_Header": auth_header,
            "AirTicketCancelDetails": cancel_details,
            "Airline_PNR": pnr,
            "RefNo": booking_ref or "",
            "CancelCode": "005",
            "ReqRemarks": remarks,
            "CancellationType": cancellation_type,
        }

        masked_payload = payload.copy()
        masked_payload["Auth_Header"] = auth_header.copy()
        masked_payload["Auth_Header"]["Password"] = "********"
        logger.info(f"Outgoing FlyShop Cancellation Request [ID: {request_id}]: {masked_payload}")

        try:
            response = requests.post(endpoint, json=payload, timeout=60)
            response.raise_for_status()
            response_json = response.json()
        except requests.RequestException as e:
            logger.error(f"HTTP Connection failure to FlyShop Cancellation [ID: {request_id}]: {str(e)}")
            raise ProviderAPIException("Unable to connect to the external cancellation service provider.")
        except ValueError:
            logger.error(f"Invalid JSON response returned from FlyShop Cancellation [ID: {request_id}]")
            raise ProviderAPIException("Received invalid response from the cancellation service provider.")

        logger.info(f"Incoming FlyShop Cancellation Response [ID: {request_id}] status_code={response.status_code}")

        response_header = response_json.get('Response_Header', {})
        error_code = response_header.get('Error_Code', '0000')
        error_desc = response_header.get('Error_Desc', 'SUCCESS')

        if error_code != '0000' and error_code != '000':
            logger.error(f"FlyShop Cancellation failed [ID: {request_id}] Code: {error_code}, Desc: {error_desc}")
            raise ProviderAPIException(f"Cancellation Error: {error_desc} (Code: {error_code})")

        logger.info(f"FlyShop Cancellation succeeded [ID: {request_id}] PNR: {pnr}")
        return True

    @classmethod
    def get_pre_ssr(cls, search_key, flight_key, request_id=None):
        """
        Retrieves pre-booking SSR options (seats, meals, baggage, etc.) from FlyShop GDS.
        Queries both Air_GetSSR and Air_GetSeatMap and combines their responses.
        """
        if not request_id:
            request_id = cls.generate_request_id()

        # 1. Fetch main SSR details (meals, baggage, wheelchair)
        base_url = settings.FLIGHT_API_BASE_URL.rstrip('/')
        endpoint = f"{base_url}/airlinehost/AirAPIService.svc/JSONService/Air_GetSSR"

        auth_header = {
            "UserId": settings.FLIGHT_API_USER_ID,
            "Password": settings.FLIGHT_API_PASSWORD,
            "IP_Address": settings.FLIGHT_API_IP_ADDRESS,
            "Request_Id": request_id,
            "IMEI_Number": settings.FLIGHT_API_IMEI
        }

        payload = {
            "Auth_Header": auth_header,
            "Search_Key": search_key,
            "AirSSRRequestDetails": [
                {
                    "Flight_Key": flight_key
                }
            ]
        }

        masked_payload = payload.copy()
        masked_payload["Auth_Header"] = auth_header.copy()
        masked_payload["Auth_Header"]["Password"] = "********"
        logger.info(f"Outgoing FlyShop GetSSR Request [ID: {request_id}]: {masked_payload}")

        try:
            response = requests.post(endpoint, json=payload, timeout=60)
            response.raise_for_status()
            ssr_response = response.json()
        except requests.RequestException as e:
            logger.error(f"HTTP Connection failure to FlyShop GetSSR [ID: {request_id}]: {str(e)}")
            raise ProviderAPIException("Unable to connect to the external flight service provider.")
        except ValueError:
            logger.error(f"Invalid JSON response returned from FlyShop GetSSR [ID: {request_id}]")
            raise ProviderAPIException("Received invalid response from the flight service provider.")

        logger.info(f"Incoming FlyShop GetSSR Response [ID: {request_id}] status_code={response.status_code}")

        response_header = ssr_response.get('Response_Header', {})
        error_code = response_header.get('Error_Code', '0000')
        error_desc = response_header.get('Error_Desc', 'SUCCESS')

        if error_code != '0000' and error_code != '000':
            logger.error(f"FlyShop GetSSR failed [ID: {request_id}] Code: {error_code}, Desc: {error_desc}")
            raise ProviderAPIException(f"Provider Error: {error_desc} (Code: {error_code})")

        # 2. Fetch Seat Map details (with graceful degradation on failure)
        air_seat_maps = []
        try:
            seat_map_res = cls.get_seat_map(search_key, flight_key, request_id=request_id)
            air_seat_maps = seat_map_res.get("AirSeatMaps") or []
        except Exception as e:
            logger.warning(f"Failed to fetch seat map for pre-booking GDS SSR [ID: {request_id}]. Gracefully degrading: {str(e)}")

        # 3. Combine response payload
        combined_response = {
            "AirSeatMaps": air_seat_maps,
            "SSRFlightDetails": ssr_response.get("SSRFlightDetails") or [],
            "Response_Header": response_header
        }
        return combined_response

    @classmethod
    def get_seat_map(cls, search_key, flight_key, request_id=None):
        """
        Retrieves pre-booking Seat Map from FlyShop GDS.
        """
        base_url = settings.FLIGHT_API_BASE_URL.rstrip('/')
        endpoint = f"{base_url}/airlinehost/AirAPIService.svc/JSONService/Air_GetSeatMap"

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
            "Search_Key": search_key,
            "Flight_Keys": [flight_key],
            "PAX_Details": [
                {
                    "Pax_Id": 1,
                    "Pax_type": 0,
                    "Title": "Mr",
                    "First_Name": "Testing",
                    "Last_Name": "Sample",
                    "Gender": 0,
                    "Age": None,
                    "DOB": None,
                    "Passport_Number": None,
                    "Passport_Issuing_Country": None,
                    "Passport_Expiry": None,
                    "Nationality": None,
                    "FrequentFlyerDetails": None
                }
            ]
        }

        masked_payload = payload.copy()
        masked_payload["Auth_Header"] = auth_header.copy()
        masked_payload["Auth_Header"]["Password"] = "********"
        logger.info(f"Outgoing FlyShop GetSeatMap Request [ID: {request_id}]: {masked_payload}")

        try:
            response = requests.post(endpoint, json=payload, timeout=60)
            response.raise_for_status()
            response_json = response.json()
        except requests.RequestException as e:
            logger.error(f"HTTP Connection failure to FlyShop GetSeatMap [ID: {request_id}]: {str(e)}")
            raise ProviderAPIException("Unable to connect to the external flight seat map service provider.")
        except ValueError:
            logger.error(f"Invalid JSON response returned from FlyShop GetSeatMap [ID: {request_id}]")
            raise ProviderAPIException("Received invalid response from the seat map service provider.")

        logger.info(f"Incoming FlyShop GetSeatMap Response [ID: {request_id}] status_code={response.status_code}")

        response_header = response_json.get('Response_Header', {})
        error_code = response_header.get('Error_Code', '0000')
        error_desc = response_header.get('Error_Desc', 'SUCCESS')

        if error_code != '0000' and error_code != '000':
            logger.error(f"FlyShop GetSeatMap failed [ID: {request_id}] Code: {error_code}, Desc: {error_desc}")
            raise ProviderAPIException(f"Provider Error: {error_desc} (Code: {error_code})")

        return response_json

    @classmethod
    def get_post_ssr(cls, booking_ref_no, airline_pnr=None, request_id=None):
        """
        Retrieves post-booking SSR options (seats, meals, baggage, etc.) from FlyShop GDS.
        """
        base_url = settings.FLIGHT_API_BASE_URL.rstrip('/')
        endpoint = f"{base_url}/airlinehost/AirAPIService.svc/JSONService/Air_GetPostSSR"

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
            "Airline_PNR": airline_pnr or ""
        }

        masked_payload = payload.copy()
        masked_payload["Auth_Header"] = auth_header.copy()
        masked_payload["Auth_Header"]["Password"] = "********"
        logger.info(f"Outgoing FlyShop GetPostSSR Request [ID: {request_id}]: {masked_payload}")

        try:
            response = requests.post(endpoint, json=payload, timeout=60)
            response.raise_for_status()
            response_json = response.json()
        except requests.RequestException as e:
            logger.error(f"HTTP Connection failure to FlyShop GetPostSSR [ID: {request_id}]: {str(e)}")
            raise ProviderAPIException("Unable to connect to the external flight service provider.")
        except ValueError:
            logger.error(f"Invalid JSON response returned from FlyShop GetPostSSR [ID: {request_id}]")
            raise ProviderAPIException("Received invalid response from the flight service provider.")

        logger.info(f"Incoming FlyShop GetPostSSR Response [ID: {request_id}] status_code={response.status_code}")

        response_header = response_json.get('Response_Header', {})
        error_code = response_header.get('Error_Code', '0000')
        error_desc = response_header.get('Error_Desc', 'SUCCESS')

        if error_code != '0000' and error_code != '000':
            logger.error(f"FlyShop GetPostSSR failed [ID: {request_id}] Code: {error_code}, Desc: {error_desc}")
            raise ProviderAPIException(f"Provider Error: {error_desc} (Code: {error_code})")

        return response_json

    @classmethod
    def initiate_post_ssr(cls, booking_ref_no, booking_ssr_details, airline_pnr=None, request_id=None):
        """
        Initiates the addition of selected SSRs for passengers in GDS.
        """
        base_url = settings.FLIGHT_API_BASE_URL.rstrip('/')
        endpoint = f"{base_url}/airlinehost/AirAPIService.svc/JSONService/Air_InitiatePostSSR"

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
            "Airline_PNR": airline_pnr or "",
            "BookingSSRDetails": booking_ssr_details
        }

        masked_payload = payload.copy()
        masked_payload["Auth_Header"] = auth_header.copy()
        masked_payload["Auth_Header"]["Password"] = "********"
        logger.info(f"Outgoing FlyShop InitiatePostSSR Request [ID: {request_id}]: {masked_payload}")

        try:
            response = requests.post(endpoint, json=payload, timeout=60)
            response.raise_for_status()
            response_json = response.json()
        except requests.RequestException as e:
            logger.error(f"HTTP Connection failure to FlyShop InitiatePostSSR [ID: {request_id}]: {str(e)}")
            raise ProviderAPIException("Unable to connect to the external flight service provider.")
        except ValueError:
            logger.error(f"Invalid JSON response returned from FlyShop InitiatePostSSR [ID: {request_id}]")
            raise ProviderAPIException("Received invalid response from the flight service provider.")

        logger.info(f"Incoming FlyShop InitiatePostSSR Response [ID: {request_id}] status_code={response.status_code}")

        response_header = response_json.get('Response_Header', {})
        error_code = response_header.get('Error_Code', '0000')
        error_desc = response_header.get('Error_Desc', 'SUCCESS')

        if error_code != '0000' and error_code != '000':
            logger.error(f"FlyShop InitiatePostSSR failed [ID: {request_id}] Code: {error_code}, Desc: {error_desc}")
            raise ProviderAPIException(f"Provider Error: {error_desc} (Code: {error_code})")

        return True

    @classmethod
    def confirm_post_ssr(cls, booking_ref_no, booking_ssr_details, airline_pnr=None, request_id=None):
        """
        Confirms the added SSRs for passengers in GDS.
        """
        base_url = settings.FLIGHT_API_BASE_URL.rstrip('/')
        endpoint = f"{base_url}/airlinehost/AirAPIService.svc/JSONService/Air_ConfirmPostSSR"

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
            "Airline_PNR": airline_pnr or "",
            "BookingSSRDetails": booking_ssr_details
        }

        masked_payload = payload.copy()
        masked_payload["Auth_Header"] = auth_header.copy()
        masked_payload["Auth_Header"]["Password"] = "********"
        logger.info(f"Outgoing FlyShop ConfirmPostSSR Request [ID: {request_id}]: {masked_payload}")

        try:
            response = requests.post(endpoint, json=payload, timeout=60)
            response.raise_for_status()
            response_json = response.json()
        except requests.RequestException as e:
            logger.error(f"HTTP Connection failure to FlyShop ConfirmPostSSR [ID: {request_id}]: {str(e)}")
            raise ProviderAPIException("Unable to connect to the external flight service provider.")
        except ValueError:
            logger.error(f"Invalid JSON response returned from FlyShop ConfirmPostSSR [ID: {request_id}]")
            raise ProviderAPIException("Received invalid response from the flight service provider.")

        logger.info(f"Incoming FlyShop ConfirmPostSSR Response [ID: {request_id}] status_code={response.status_code}")

        response_header = response_json.get('Response_Header', {})
        error_code = response_header.get('Error_Code', '0000')
        error_desc = response_header.get('Error_Desc', 'SUCCESS')

        if error_code != '0000' and error_code != '000':
            logger.error(f"FlyShop ConfirmPostSSR failed [ID: {request_id}] Code: {error_code}, Desc: {error_desc}")
            raise ProviderAPIException(f"Provider Error: {error_desc} (Code: {error_code})")

        return True

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
            product_class = fare.get('ProductClass', '') or ''
            fare_basis = ""
            class_desc = ""

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
                fare_classes = detail.get('FareClasses', [])
                if fare_classes:
                    fare_basis = fare_classes[0].get('FareBasis', '') or ''
                    class_desc = fare_classes[0].get('Class_Desc', '') or ''

            # Map GDS flags: SF -> STU, DD -> DEF, CP -> CORP, otherwise fallback to description checks
            product_class_upper = product_class.upper()
            if product_class_upper == 'SF':
                fare_type_str = 'STU'
            elif product_class_upper == 'DD':
                fare_type_str = 'DEF'
            elif product_class_upper == 'CP':
                fare_type_str = 'CORP'
            else:
                class_desc_upper = class_desc.upper()
                fare_basis_upper = fare_basis.upper()
                if 'STU' in class_desc_upper or 'STUDENT' in class_desc_upper or 'SF' in class_desc_upper or 'USPF' in fare_basis_upper:
                    fare_type_str = 'STU'
                elif 'DEF' in class_desc_upper or 'DEFENCE' in class_desc_upper or 'MILITARY' in class_desc_upper or 'DD' in class_desc_upper:
                    fare_type_str = 'DEF'
                elif 'CORP' in class_desc_upper or 'CP' in class_desc_upper:
                    fare_type_str = 'CORP'
                else:
                    fare_type_str = 'PUB'

            normalized_fares.append({
                "fare_id": fare_id,
                "refundable": refundable,
                "seats_available": seats_available,
                "food_onboard": food_onboard,
                "gst_mandatory": gst_mandatory,
                "price_details": price_details,
                "baggage": baggage_details,
                "fare_type": fare_type_str,
                "product_class": product_class,
                "fare_basis": fare_basis,
                "class_desc": class_desc
            })

        return {
            "flight_key": flight.get('Flight_Key') or flight.get('flight_key'),
            "flight_id": flight.get('Flight_Id') or flight.get('id'),
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
            "is_agent_flight": flight.get('is_agent_flight', False),
            "agent_flight_id": flight.get('agent_flight_id'),
            "segments": normalized_segments,
            "fares": normalized_fares
        }
