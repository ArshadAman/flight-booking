from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from tickets.models import Ticket

class BookingReportsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        tickets = Ticket.objects.filter(user=user).order_by("-created_at")[:100]
        items = []
        for idx, t in enumerate(tickets):
            dt = t.created_at
            pax = t.passengers_data if isinstance(t.passengers_data, list) else []
            lead_name = "Passenger"
            if pax and isinstance(pax[0], dict):
                first = pax[0].get("first_name", "")
                last = pax[0].get("last_name", "")
                lead_name = f"{first} {last}".strip() or "Passenger"
            elif user.first_name:
                lead_name = f"{user.first_name} {user.last_name}".strip()
            items.append({
                "id": str(t.id),
                "date": dt.strftime("%d, %b %Y"),
                "time": dt.strftime("%I:%M %p"),
                "pnr": t.pnr_number or f"PNR{str(t.id)[:5]}",
                "booking_id": t.booking_ref or t.pnr_number or f"BK{str(t.id)[:6]}",
                "passenger_name": lead_name,
                "lead_passenger": lead_name,
                "airline": t.airline_name or "IndiGo",
                "flight_number": t.flight_number or "6E-101",
                "trip_type": "Oneway" if t.travel_type == 0 else "Roundtrip",
                "sector": f"{t.origin} → {t.destination}",
                "pax_count": len(pax) or t.passenger_count or 1,
                "fare": float(t.total_amount or 0),
                "total_amount": float(t.total_amount or 0),
                "status": t.status,
                "journey": "Domestic",
                "cabin": t.cabin_class or "Economy",
                "payment_status": "Paid" if t.status == Ticket.STATUS_CONFIRMED else "Pending",
            })
        return Response(items)

class FinancialReportsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        tickets = Ticket.objects.filter(user=user).order_by("-created_at")[:100]
        items = []
        for idx, t in enumerate(tickets):
            dt = t.created_at
            pax = t.passengers_data if isinstance(t.passengers_data, list) else []
            lead_name = "Passenger"
            if pax and isinstance(pax[0], dict):
                first = pax[0].get("first_name", "")
                last = pax[0].get("last_name", "")
                lead_name = f"{first} {last}".strip() or "Passenger"
            elif user.first_name:
                lead_name = f"{user.first_name} {user.last_name}".strip()
            base_fare = float(t.basic_amount or t.total_amount or 0)
            taxes = float(t.tax_amount or 0)
            total_fare = float(t.total_amount or 0)
            net_rev = max(total_fare - base_fare, 500.0)
            items.append({
                "id": str(t.id),
                "date": dt.strftime("%d, %b %Y"),
                "time": dt.strftime("%I:%M %p"),
                "pnr": t.pnr_number or f"PNR{str(t.id)[:5]}",
                "passenger_name": lead_name,
                "booking_id": t.booking_ref or t.pnr_number or f"BK{str(t.id)[:6]}",
                "airline": t.airline_name or "IndiGo",
                "flight_number": t.flight_number or "6E-101",
                "trip_type": "Oneway" if t.travel_type == 0 else "Roundtrip",
                "sector": f"{t.origin} → {t.destination}",
                "pax_count": len(pax) or t.passenger_count or 1,
                "base_fare": base_fare,
                "taxes": taxes,
                "discount": 0.0,
                "markup": net_rev,
                "total_fare": total_fare,
                "net_revenue": net_rev,
                "airline_fee": 100.0,
                "agent_fee": 50.0,
                "refund": 0.0,
                "status": t.status,
                "payment_status": "Paid" if t.status == Ticket.STATUS_CONFIRMED else "Pending",
            })
        return Response(items)
