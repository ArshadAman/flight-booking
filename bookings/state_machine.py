"""Centralized status transitions for GroupBooking lifecycle."""


class InvalidTransition(Exception):
    """Raised when a requested status transition is not permitted."""


VALID_TRANSITIONS: dict[tuple[str, str], bool] = {
    ("NEW_REQUEST", "FARE_QUOTED"): True,
    ("FARE_QUOTED", "NEGOTIATION"): True,
    ("FARE_QUOTED", "PAYMENT_PENDING"): True,
    ("NEGOTIATION", "FARE_QUOTED"): True,
    ("NEGOTIATION", "PAYMENT_PENDING"): True,
    ("NEGOTIATION", "CANCELLED"): True,
    ("PAYMENT_PENDING", "PARTIALLY_PAID"): True,
    ("PAYMENT_PENDING", "PAID"): True,
    ("PARTIALLY_PAID", "PAID"): True,
    ("PAID", "PNR_CREATED"): True,
    ("PNR_CREATED", "NAME_SUBMITTED"): True,
    ("NAME_SUBMITTED", "TICKETED"): True,
    ("TICKETED", "COMPLETED"): True,
}


def transition(booking, target_status: str) -> None:
    current = booking.status
    if (current, target_status) not in VALID_TRANSITIONS:
        raise InvalidTransition(
            f"Cannot transition from '{current}' to '{target_status}'. "
            f"Current status is '{current}'."
        )
    booking.status = target_status


def can_transition(current_status: str, target_status: str) -> bool:
    return (current_status, target_status) in VALID_TRANSITIONS
