# Design Document — Group Travel Booking Flow

## Overview

This document describes the implementation design for the group travel booking flow. The changes span three areas:

1. **Backend — `bookings/state_machine.py`**: a new, centralized module that owns all status-transition logic.
2. **Backend — `bookings/views.py` (`GroupBookingViewSet`)**: refactored to delegate every status mutation to the state machine, gain two new endpoints (`/pnr/` and `/cancel/`), fix the quote-upload role check, remove the `perform_update` side-effect, and remove the `get_user` X-Mock-Role bypass.
3. **Frontend — `GroupTravelContext` + views**: add missing JWT auth headers, remove all `X-Mock-Role` header usage, and add state-gated rendering guards in `OperatorDashboardView` and the view-request page.

---

## Architecture

### High-Level Booking Lifecycle

```
Customer submits request
        │
        ▼
  NEW_REQUEST
        │  Agent uploads quote  (/quote/)
        ▼
  FARE_QUOTED ◄──────────────────────────────┐
        │                                     │ Agent re-uploads quote (/quote/)
        ├──[Customer negotiates] (/negotiate/) │
        ▼                                     │
  NEGOTIATION ──────────────────────────────►┘
        │  Agent cancels (/cancel/)
        ▼
   CANCELLED  (terminal)

  FARE_QUOTED or NEGOTIATION
        │  Customer accepts quote (/accept/)
        ▼
  PAYMENT_PENDING  (ACCEPTED is never persisted — single atomic write)
        │
        ├──[partial payment] (/payment/)
        ▼
 PARTIALLY_PAID
        │  [remaining payment]
        ▼
     PAID
        │  Agent submits PNR (/pnr/)
        ▼
  PNR_CREATED
        │  Customer uploads passengers (/passengers/)
        ▼
 NAME_SUBMITTED
        │  Admin issues ticket (/ticket/)
        ▼
   TICKETED
        │  Admin marks complete (/complete/)
        ▼
  COMPLETED  (terminal)
```

### Data Flow — Quote Upload

```
Agent Frontend
    │  POST /api/group-bookings/{id}/quote/
    │  Authorization: Bearer <token>
    ▼
GroupBookingViewSet.upload_quote()
    │  check request.user.role in ['AGENT', 'ADMIN']
    │  call state_machine.transition(booking, 'FARE_QUOTED')
    │  save GroupQuote records
    ▼
state_machine.py
    │  validate NEW_REQUEST or NEGOTIATION → FARE_QUOTED
    │  raise InvalidTransition if not valid
    ▼
Database
    GroupQuote rows created + booking.status = FARE_QUOTED
```

### Data Flow — Accept Quote (Atomic)

```
Customer Frontend
    │  POST /api/group-bookings/{id}/accept/
    │  { "quote_option_id": "OPT-XYZ" }
    ▼
GroupBookingViewSet.accept_quote()
    │  within transaction.atomic():
    │    mark quote is_selected = True
    │    set booking.payment_deadline, balance_deadline
    │    state_machine.transition(booking, 'PAYMENT_PENDING')
    │      └─ internally: validates FARE_QUOTED/NEGOTIATION → ACCEPTED → PAYMENT_PENDING
    │         writes only PAYMENT_PENDING to DB
    ▼
Database  booking.status = PAYMENT_PENDING  (ACCEPTED never written)
```

### Data Flow — PNR Submission (New Endpoint)

```
Agent Frontend
    │  POST /api/group-bookings/{id}/pnr/
    │  Authorization: Bearer <token>
    │  { "pnr_number": "PNRX1052" }
    ▼
GroupBookingViewSet.submit_pnr()
    │  check role in ['AGENT', 'ADMIN']
    │  validate booking.status == PAID
    │  state_machine.transition(booking, 'PNR_CREATED')
    │  booking.pnr_number = pnr_number
    ▼
Database  booking.status = PNR_CREATED, pnr_number stored
```

---

## Module Structure — `bookings/state_machine.py`

This module is the single source of truth for all valid transitions.

```python
# bookings/state_machine.py

from django.db import models


class InvalidTransition(Exception):
    """Raised when a requested status transition is not permitted."""
    pass


# Transition table: maps (current_status, target_status) → True for allowed transitions.
# All transitions that require an intermediate step (ACCEPTED → PAYMENT_PENDING)
# are handled as compound transitions within the accept_quote helper below.
VALID_TRANSITIONS: dict[tuple[str, str], bool] = {
    ("NEW_REQUEST",     "FARE_QUOTED"):     True,
    ("FARE_QUOTED",     "NEGOTIATION"):     True,
    ("FARE_QUOTED",     "PAYMENT_PENDING"): True,   # accept quote (compound, skips ACCEPTED)
    ("NEGOTIATION",     "FARE_QUOTED"):     True,
    ("NEGOTIATION",     "PAYMENT_PENDING"): True,   # accept quote from negotiation state
    ("NEGOTIATION",     "CANCELLED"):       True,
    ("PAYMENT_PENDING", "PARTIALLY_PAID"):  True,
    ("PAYMENT_PENDING", "PAID"):            True,
    ("PARTIALLY_PAID",  "PAID"):            True,
    ("PAID",            "PNR_CREATED"):     True,
    ("PNR_CREATED",     "NAME_SUBMITTED"):  True,
    ("NAME_SUBMITTED",  "TICKETED"):        True,
    ("TICKETED",        "COMPLETED"):       True,
}


def transition(booking, target_status: str) -> None:
    """
    Validate and apply a status transition on a GroupBooking instance.

    Mutates booking.status in memory but does NOT call booking.save().
    The caller is responsible for saving within the appropriate transaction.

    Raises InvalidTransition if the (current, target) pair is not in
    VALID_TRANSITIONS.
    """
    current = booking.status
    if (current, target_status) not in VALID_TRANSITIONS:
        raise InvalidTransition(
            f"Cannot transition from '{current}' to '{target_status}'. "
            f"Current status is '{current}'."
        )
    booking.status = target_status


def can_transition(current_status: str, target_status: str) -> bool:
    """
    Return True if the transition is allowed, False otherwise.
    Useful for conditional UI logic or pre-flight checks.
    """
    return (current_status, target_status) in VALID_TRANSITIONS
```

### Design Decisions

- `transition()` mutates only the in-memory `booking.status` field; saving is the caller's responsibility so that the state machine can participate in any surrounding `transaction.atomic()` block.
- `InvalidTransition` is a plain `Exception` subclass; views catch it and convert it to HTTP 400.
- `VALID_TRANSITIONS` is a plain dict; no external dependency, easy to import and test.
- The `ACCEPTED` state is intentionally absent from the transition table as a _persisted_ state. The accept-quote endpoint writes `PAYMENT_PENDING` in one atomic DB write (see `accept_quote` view below).

---

## Changes to `GroupBookingViewSet`

### 1. Remove `get_user` / X-Mock-Role Bypass

The entire `get_user` helper method is deleted. Every place that previously called `self.get_user()` now uses `self.request.user` directly. The `permission_classes = [permissions.IsAuthenticated]` class-level declaration remains, meaning DRF's JWT authentication backend provides a verified `request.user` before any view logic runs.

```python
# BEFORE (removed)
def get_user(self):
    user = self.request.user
    if user and user.is_authenticated and not user.is_anonymous:
        return user
    # ... mock user fallback ...

# AFTER — not present; all references replaced with self.request.user
```

### 2. Fix `upload_quote` Role Check

The role check is changed from `ADMIN`-only to `AGENT` or `ADMIN`. The state machine replaces the inline `booking.status = 'FARE_QUOTED'` write.

```python
@action(detail=True, methods=['post'], url_path='quote')
def upload_quote(self, request, pk=None):
    user = request.user
    if user.role not in ('AGENT', 'ADMIN'):
        return Response(
            {"detail": "Only agents and administrators can upload quotes."},
            status=status.HTTP_403_FORBIDDEN
        )

    booking = self.get_object()
    if booking.status not in ('NEW_REQUEST', 'NEGOTIATION', 'FARE_QUOTED'):
        return Response(
            {"detail": f"Cannot upload quotes in current status: {booking.status}."},
            status=status.HTTP_400_BAD_REQUEST
        )

    data = request.data
    is_many = isinstance(data, list)
    serializer = GroupQuoteSerializer(data=data, many=is_many)
    if serializer.is_valid():
        with transaction.atomic():
            serializer.save(booking=booking)
            try:
                transition(booking, 'FARE_QUOTED')
            except InvalidTransition as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            booking.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
```

### 3. Fix `accept_quote` — Atomic Single-Write to `PAYMENT_PENDING`

The current code writes `ACCEPTED` then immediately overwrites with `PAYMENT_PENDING` — two separate saves. The new code performs a single write inside one transaction. `ACCEPTED` is never persisted.

```python
@action(detail=True, methods=['post'], url_path='accept')
def accept_quote(self, request, pk=None):
    booking = self.get_object()
    if booking.status not in ('FARE_QUOTED', 'NEGOTIATION'):
        return Response(
            {"detail": "Booking must be in FARE_QUOTED or NEGOTIATION status to accept a quote."},
            status=status.HTTP_400_BAD_REQUEST
        )

    quote_option_id = request.data.get('quote_option_id')
    if not quote_option_id:
        return Response({"detail": "quote_option_id is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        quote = booking.quotes.get(quote_option_id=quote_option_id)
    except GroupQuote.DoesNotExist:
        return Response({"detail": "Quote option not found."}, status=status.HTTP_404_NOT_FOUND)

    with transaction.atomic():
        booking.quotes.update(is_selected=False)
        quote.is_selected = True
        quote.save()
        booking.payment_deadline = quote.payment_deadline
        booking.balance_deadline = quote.balance_deadline
        try:
            transition(booking, 'PAYMENT_PENDING')   # single write — no ACCEPTED intermediate
        except InvalidTransition as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        booking.save()

    return Response({
        "message": "Quote accepted and payment pending.",
        "status": booking.status,
        "payment_deadline": booking.payment_deadline,
        "balance_deadline": booking.balance_deadline,
    })
```

### 4. Remove `perform_update` Side-Effect

The entire `perform_update` override is deleted. The default `ModelViewSet.perform_update` (which just calls `serializer.save()`) is used. The `GroupBookingSerializer` already lists `status` in `read_only_fields`, so PATCH requests cannot mutate the status field at all.

```python
# Removed entirely:
# def perform_update(self, serializer):
#     instance = self.get_object()
#     old_status = instance.status
#     old_pnr = instance.pnr_number
#     updated_instance = serializer.save()
#     if old_status == 'PAID' and updated_instance.pnr_number and not old_pnr:
#         updated_instance.status = 'PNR_CREATED'
#         updated_instance.save()
```

### 5. New `/pnr/` Endpoint

```python
@action(detail=True, methods=['post'], url_path='pnr')
def submit_pnr(self, request, pk=None):
    user = request.user
    if user.role not in ('AGENT', 'ADMIN'):
        return Response(
            {"detail": "Only agents and administrators can submit PNR numbers."},
            status=status.HTTP_403_FORBIDDEN
        )

    booking = self.get_object()
    pnr_number = request.data.get('pnr_number', '').strip()

    if not pnr_number:
        return Response({"detail": "pnr_number is required and cannot be blank."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        transition(booking, 'PNR_CREATED')
    except InvalidTransition as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    booking.pnr_number = pnr_number
    booking.save()

    return Response({
        "message": "PNR submitted successfully.",
        "pnr_number": booking.pnr_number,
        "status": booking.status,
    })
```

### 6. New `/cancel/` Endpoint

```python
@action(detail=True, methods=['post'], url_path='cancel')
def cancel_booking(self, request, pk=None):
    user = request.user
    if user.role == 'CUSTOMER':
        return Response(
            {"detail": "Customers cannot cancel group bookings."},
            status=status.HTTP_403_FORBIDDEN
        )

    booking = self.get_object()
    try:
        transition(booking, 'CANCELLED')
    except InvalidTransition as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    booking.save()

    return Response({
        "message": "Booking cancelled successfully.",
        "status": booking.status,
    })
```

### 7. Updated `get_queryset` — Agent Broadcast

The existing logic already implements Requirement 9 correctly via the `Q(status__in=['NEW_REQUEST', 'FARE_QUOTED', 'NEGOTIATION']) | Q(user=user)` filter. No change needed here beyond replacing `self.get_user()` with `self.request.user`.

```python
def get_queryset(self):
    user = self.request.user
    if user.role == 'ADMIN':
        return GroupBooking.objects.all().order_by('-created_at')
    if user.role == 'AGENT':
        from django.db.models import Q
        return GroupBooking.objects.filter(
            Q(user=user) | Q(status__in=['NEW_REQUEST', 'FARE_QUOTED', 'NEGOTIATION'])
        ).order_by('-created_at')
    return GroupBooking.objects.filter(user=user).order_by('-created_at')
```

### 8. All Other Action Endpoints — Replace `self.get_user()` with `request.user`

Every call to `self.get_user()` in `negotiate`, `record_payment`, `upload_passengers`, `issue_ticket`, `complete_booking`, `create_change_request`, and `resolve_change_request` is replaced with `request.user`. The state machine's `transition()` call replaces every inline `booking.status = '<VALUE>'` + `booking.save()` pair.

---

## URL Registration — New Endpoints

The existing `DefaultRouter` registration covers `/api/group-bookings/{id}/pnr/` and `/api/group-bookings/{id}/cancel/` automatically because both are declared as `@action(detail=True, ...)` on the viewset. No changes to `bookings/urls.py` are needed.

---

## Frontend Changes

### `GroupTravelContext.tsx` — Remove X-Mock-Role, Add Missing Auth Headers

**Rule**: Every fetch call must include `...getAuthHeaders()`. No fetch call may include `X-Mock-Role`.

The following functions currently **missing** `getAuthHeaders()` must be updated:

| Function | Current state | Fix |
|---|---|---|
| `issueTicket` | No `getAuthHeaders()`, has `X-Mock-Role: ADMIN` | Add `...getAuthHeaders()`, remove X-Mock-Role |
| `completeBooking` | No `getAuthHeaders()`, has `X-Mock-Role: ADMIN` | Add `...getAuthHeaders()`, remove X-Mock-Role |
| `updateRequest` | No `getAuthHeaders()`, has `X-Mock-Role: <role>` | Add `...getAuthHeaders()`, remove X-Mock-Role |

All other functions (`refreshRequests`, `addRequest`, `negotiateRequest`, `acceptQuote`, `recordPayment`, `uploadPassengers`, `createChangeRequest`, `resolveChangeRequest`, `uploadQuotes`) already call `...getAuthHeaders()` but still include `X-Mock-Role`. These `X-Mock-Role` headers must be removed from every fetch call.

The `refreshRequests` function signature currently accepts `role?: "AGENT" | "ADMIN"` and uses it only for the now-removed `X-Mock-Role` header. After removal the `role` parameter is unused and can be dropped. All call sites (including `useEffect` on mount and every `await refreshRequests("ADMIN")` / `await refreshRequests("AGENT")` call) should be updated to `await refreshRequests()`.

```typescript
// BEFORE — issueTicket
const response = await fetch(`/api/group-bookings/${dbId}/ticket/`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-Mock-Role": "ADMIN",       // ← remove
                                   // ← missing getAuthHeaders()
  },
  body: JSON.stringify({ pnr_number: pnrNumber }),
});

// AFTER
const response = await fetch(`/api/group-bookings/${dbId}/ticket/`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    ...getAuthHeaders(),            // ← added
  },
  body: JSON.stringify({ pnr_number: pnrNumber }),
});
```

### New Context Function — `submitPnr`

Add a function for the new `/pnr/` endpoint:

```typescript
const submitPnr = async (bookingId: string, pnrNumber: string): Promise<boolean> => {
  try {
    const dbId = resolveDbId(bookingId);
    const response = await fetch(`/api/group-bookings/${dbId}/pnr/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ pnr_number: pnrNumber }),
    });
    if (!response.ok) throw new Error(await response.text());
    await refreshRequests();
    return true;
  } catch (e) {
    console.error("Error submitting PNR:", e);
    return false;
  }
};
```

### New Context Function — `cancelBooking`

```typescript
const cancelBooking = async (bookingId: string): Promise<boolean> => {
  try {
    const dbId = resolveDbId(bookingId);
    const response = await fetch(`/api/group-bookings/${dbId}/cancel/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
    });
    if (!response.ok) throw new Error(await response.text());
    await refreshRequests();
    return true;
  } catch (e) {
    console.error("Error cancelling booking:", e);
    return false;
  }
};
```

Both new functions must be added to `GroupTravelContextType` and the provider value.

---

### `OperatorDashboardView.tsx` — State-Gated Action Guards

The existing component already conditionally renders most action panels based on `selectedRequest.status`. The following table shows the current state vs. required state:

| Action Panel | Current guard | Required guard |
|---|---|---|
| Upload Quote | `["NEW_REQUEST", "NEGOTIATION", "FARE_QUOTED"].includes(status)` | No change |
| Change Request Resolution | `changeRequests.length > 0` | No change |
| Submit PNR ("Assign PNR Code") | `status === "PAID"` | **Correct — no change** |
| Issue E-Ticket | `status === "NAME_SUBMITTED"` | **Correct — no change** |
| Complete Booking | `status === "TICKETED"` | **Correct — no change** |
| **Cancel Booking** | **Not present** | **Add: `status === "NEGOTIATION"`** |

Add the Cancel Booking panel between the Change Request panel and the Assign PNR panel:

```tsx
{/* ACTION: Cancel Booking (NEGOTIATION only) */}
{selectedRequest.status === "NEGOTIATION" && (
  <div className="bg-red-50 border border-red-200 rounded-xl p-5 flex items-center justify-between shadow-sm">
    <div>
      <h4 className="font-bold text-sm text-red-800">Cancel This Booking</h4>
      <p className="text-xs text-red-600 mt-1">
        This will move the booking to CANCELLED status. The customer will be notified.
      </p>
    </div>
    <Button
      onClick={handleCancelBookingClick}
      disabled={isActionLoading}
      className="bg-red-600 hover:bg-red-700 text-white font-bold px-6 py-2.5 rounded-full text-xs shadow"
    >
      Cancel Booking
    </Button>
  </div>
)}
```

The component needs:
- `cancelBooking` destructured from `useGroupTravel()`
- A `handleCancelBookingClick` handler following the same pattern as `handleCompleteBookingClick`

---

### `view-request/page.tsx` — State-Gated Action Guards

The existing page already conditionally renders:
- **"Proceed to Payment" button** when `status === "PAYMENT_PENDING" || status === "PARTIALLY_PAID"` — **correct, no change**
- **"Passenger Manifest Needed" redirect** when `status === "PAID" || status === "PNR_CREATED"` — **must be narrowed to `PNR_CREATED` only**

Per Requirement 8.6, the "Upload Passenger Names" section should appear only when `status === "PNR_CREATED"`. The current guard includes `PAID`, which is wrong because the `/passengers/` endpoint requires `PNR_CREATED` status (not `PAID`).

```tsx
{/* BEFORE */}
{(selectedRequest.status === "PAID" || selectedRequest.status === "PNR_CREATED") && (
  // passenger upload redirect
)}

{/* AFTER */}
{selectedRequest.status === "PNR_CREATED" && (
  // passenger upload redirect
)}
```

The make-payment button guard (`PAYMENT_PENDING || PARTIALLY_PAID`) is already correct.

---

## `GroupBookingSerializer` — Confirm `status` is Read-Only

`status` is already in `read_only_fields` in `GroupBookingSerializer`. This ensures PATCH requests cannot supply a new status value through the generic update endpoint, satisfying Requirement 5.3 without any code change needed to the serializer.

---

## `GroupBooking` Model — Add `CANCELLED` Status Choice

The `CANCELLED` status must be added to the model's `STATUS_CHOICES` list and a migration created:

```python
STATUS_CHOICES = [
    ('NEW_REQUEST',     'New Request'),
    ('FARE_QUOTED',     'Fare Quoted'),
    ('NEGOTIATION',     'Negotiation'),
    ('ACCEPTED',        'Accepted'),       # retained for historical records
    ('PAYMENT_PENDING', 'Payment Pending'),
    ('PARTIALLY_PAID',  'Partially Paid'),
    ('PAID',            'Paid'),
    ('PNR_CREATED',     'PNR Created'),
    ('NAME_SUBMITTED',  'Name Submitted'),
    ('TICKETED',        'Ticketed'),
    ('COMPLETED',       'Completed'),
    ('CANCELLED',       'Cancelled'),      # ← new
]
```

---

## Components and Interfaces

### Backend Components

#### `bookings/state_machine.py` (new file)

| Symbol | Kind | Description |
|---|---|---|
| `VALID_TRANSITIONS` | `dict[tuple[str,str], bool]` | Immutable map of all allowed (current, target) status pairs |
| `InvalidTransition` | `Exception` | Raised when a requested transition is not in `VALID_TRANSITIONS` |
| `transition(booking, target_status)` | `function` | Validates and applies a status mutation in memory; caller saves |
| `can_transition(current, target)` | `function` | Pure predicate; returns bool; no side effects |

#### `bookings/views.py` — `GroupBookingViewSet`

| Method | HTTP | URL | Roles | Description |
|---|---|---|---|---|
| `list` / `retrieve` | GET | `/group-bookings/` `/group-bookings/{id}/` | All authenticated | Unchanged |
| `create` / `create_booking` | POST | `/group-bookings/` `/group-bookings/create/` | All authenticated | Unchanged |
| `partial_update` | PATCH | `/group-bookings/{id}/` | All authenticated | No `perform_update` override; status is read-only |
| `upload_quote` | POST | `/group-bookings/{id}/quote/` | AGENT, ADMIN | Role fixed (was ADMIN-only) |
| `negotiate` | POST | `/group-bookings/{id}/negotiate/` | CUSTOMER, AGENT | Delegates status to state machine |
| `accept_quote` | POST | `/group-bookings/{id}/accept/` | CUSTOMER | Single atomic write to PAYMENT_PENDING |
| `record_payment` | POST | `/group-bookings/{id}/payment/` | All authenticated | Delegates status to state machine |
| `upload_passengers` | POST | `/group-bookings/{id}/passengers/` | All authenticated | Delegates status to state machine |
| `submit_pnr` | POST | `/group-bookings/{id}/pnr/` | AGENT, ADMIN | **New** — stores PNR, transitions to PNR_CREATED |
| `issue_ticket` | POST | `/group-bookings/{id}/ticket/` | ADMIN | Delegates status to state machine |
| `complete_booking` | POST | `/group-bookings/{id}/complete/` | ADMIN | Delegates status to state machine |
| `cancel_booking` | POST | `/group-bookings/{id}/cancel/` | AGENT, ADMIN | **New** — transitions NEGOTIATION → CANCELLED |
| `create_change_request` | POST | `/group-bookings/{id}/change-request/` | All authenticated | Unchanged |
| `resolve_change_request` | PATCH | `/group-bookings/{id}/change-request/{cr_id}/resolve/` | ADMIN | Unchanged |

### Frontend Components

#### `GroupTravelContext.tsx`

| Symbol | Change |
|---|---|
| `getAuthHeaders()` | Unchanged — reads `access_token` from localStorage |
| `refreshRequests()` | Remove `role` parameter; remove `X-Mock-Role` header |
| `addRequest()` | Remove `X-Mock-Role: AGENT` header |
| `negotiateRequest()` | Remove `X-Mock-Role: AGENT` header |
| `acceptQuote()` | Remove `X-Mock-Role: AGENT` header |
| `recordPayment()` | Remove `X-Mock-Role: AGENT` header |
| `uploadPassengers()` | Remove `X-Mock-Role: AGENT` header |
| `createChangeRequest()` | Remove `X-Mock-Role: AGENT` header |
| `resolveChangeRequest()` | Remove `X-Mock-Role: ADMIN` header |
| `uploadQuotes()` | Remove `X-Mock-Role: ADMIN` header |
| `issueTicket()` | Remove `X-Mock-Role: ADMIN`; **add** `...getAuthHeaders()` |
| `completeBooking()` | Remove `X-Mock-Role: ADMIN`; **add** `...getAuthHeaders()` |
| `updateRequest()` | Remove `X-Mock-Role: <role>`; **add** `...getAuthHeaders()` |
| `submitPnr()` | **New** — POST to `/pnr/` with auth headers |
| `cancelBooking()` | **New** — POST to `/cancel/` with auth headers |
| `GroupTravelContextType` | Add `submitPnr` and `cancelBooking` to the interface |

#### `OperatorDashboardView.tsx`

| Change | Detail |
|---|---|
| Import `cancelBooking` from context | Destructure from `useGroupTravel()` |
| Add `handleCancelBookingClick` handler | Calls `cancelBooking(selectedRequest.id)` |
| Add Cancel Booking action panel | Rendered only when `status === "NEGOTIATION"` |
| Replace `refreshRequests("ADMIN")` calls | Remove role argument |

#### `view-request/page.tsx`

| Change | Detail |
|---|---|
| Narrow passenger upload guard | Change `status === "PAID" \|\| status === "PNR_CREATED"` to `status === "PNR_CREATED"` |
| Replace `refreshRequests("AGENT")` calls | Remove role argument (from context's internal calls) |

---

## Data Models

### `GroupBooking` (existing model — one field addition)

| Field | Type | Change |
|---|---|---|
| `status` | `CharField(choices=STATUS_CHOICES)` | Add `('CANCELLED', 'Cancelled')` to `STATUS_CHOICES` |
| All other fields | — | Unchanged |

A new Django migration is needed: `bookings/migrations/000X_add_cancelled_status.py`. Because `STATUS_CHOICES` is a Django `TextChoices`-style list and the column is a `VARCHAR`, adding a new choice value does not require an `ALTER TABLE` — only the migration file metadata changes. Django generates this as a `AlterField` migration with no DDL.

### `GroupQuote` (no changes)

| Field | Type | Notes |
|---|---|---|
| `booking` | FK → GroupBooking | |
| `quote_option_id` | CharField | |
| `airline`, `flight_number` | CharField | |
| `departure_time`, `arrival_time` | DateTimeField | |
| `fare_per_pax`, `tax_per_pax`, `deposit_per_pax` | DecimalField | |
| `payment_deadline`, `balance_deadline` | DateTimeField | Copied to booking on accept |
| `is_selected` | BooleanField | Set True on accept; all others set False atomically |
| `terms_and_conditions` | TextField | Optional |

### `GroupPassenger` (no changes)

| Field | Type |
|---|---|
| `booking` | FK → GroupBooking |
| `first_name`, `last_name` | CharField |
| `gender` | CharField |
| `date_of_birth` | DateField |
| `passport_number` | CharField (optional) |

### `GroupChangeRequest` (no changes)

| Field | Type | Notes |
|---|---|---|
| `booking` | FK → GroupBooking | |
| `change_request_id` | CharField (unique, auto-generated) | |
| `change_type` | `UPSIZE` / `DOWNSIZE` | |
| `pax_delta` | IntegerField | |
| `status` | `PENDING_REVIEW` / `APPROVED` / `REJECTED` | |
| `agent_notes`, `admin_remarks` | TextField (optional) | |
| `adjusted_fare_per_pax` | DecimalField (optional) | |

---

## Testing Strategy

### Unit Tests (example-based)

- `test_state_machine.py`: Import `state_machine.py` and assert every transition in `VALID_TRANSITIONS` succeeds and every invalid pair raises `InvalidTransition`.
- `test_views_role_enforcement.py`: Confirm CUSTOMER cannot POST to `/quote/`, `/cancel/`, `/pnr/`; AGENT cannot POST to `/ticket/`, `/complete/`.
- `test_accept_quote_no_accepted_status.py`: After calling `/accept/`, query the DB and assert `booking.status == 'PAYMENT_PENDING'` and no historical record shows `ACCEPTED`.
- `test_patch_status_ignored.py`: PATCH a booking with `{"status": "COMPLETED"}`; assert status is unchanged.

### Property-Based Tests

Using `hypothesis` (Python) for backend, and `fast-check` (TypeScript) for frontend:

- **Backend**: For each action endpoint, generate random valid payloads and assert the invariants described in Properties 1–11 above.
- **Frontend**: Mock `fetch` and `localStorage`; for each context function, generate random token strings and assert every mock call includes `Authorization: Bearer <token>` and excludes `X-Mock-Role`.
- **UI gates**: For each of the 11 possible status values, render `OperatorDashboardView` and `ViewRequestPage` with a mock booking and assert the correct set of action panels is visible.

### Integration Tests

- End-to-end: create a booking, upload a quote as an Agent (not Admin), accept it as a Customer, submit a PNR, upload passengers, issue ticket, complete — assert final status is `COMPLETED`.
- Cancel flow: create booking, quote it, negotiate, cancel — assert status is `CANCELLED` and further transitions are rejected (HTTP 400).

---

## Error Handling

| Scenario | HTTP Status | Response body |
|---|---|---|
| Invalid state transition | 400 | `{"detail": "Cannot transition from 'X' to 'Y'. Current status is 'X'."}` |
| Wrong role for endpoint | 403 | `{"detail": "Only <roles> can <action>."}` |
| No JWT supplied | 401 | DRF default: `{"detail": "Authentication credentials were not provided."}` |
| Invalid/expired JWT | 401 | DRF default |
| Blank PNR number | 400 | `{"detail": "pnr_number is required and cannot be blank."}` |
| Quote not found | 404 | `{"detail": "Quote option not found."}` |

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: State Machine Transition Table Completeness

*For any* (current_status, target_status) pair, `state_machine.transition()` allows the transition if and only if the pair is listed in `VALID_TRANSITIONS`; for every pair not in the table it raises `InvalidTransition`.

**Validates: Requirements 1.1, 1.2, 1.3**

---

### Property 2: Quote Upload Role Enforcement

*For any* authenticated user whose role is `AGENT` or `ADMIN`, a POST to the `/quote/` endpoint with a valid payload on a booking in an eligible status (`NEW_REQUEST`, `NEGOTIATION`, or `FARE_QUOTED`) should succeed and transition the booking to `FARE_QUOTED`. *For any* user whose role is `CUSTOMER`, the endpoint must return HTTP 403.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

---

### Property 3: PNR Submission Stores Value and Advances Status

*For any* non-empty PNR string submitted by an Agent or Admin to the `/pnr/` endpoint when the Booking is in `PAID` status, the booking's `pnr_number` field is set to the submitted value and the booking's status is `PNR_CREATED` after the call.

**Validates: Requirements 3.2, 3.3, 3.4**

---

### Property 4: Cancel Endpoint Gate

*For any* booking in `NEGOTIATION` status, calling `/cancel/` as an Agent transitions the booking to `CANCELLED`. *For any* booking not in `NEGOTIATION` status, the endpoint returns HTTP 400.

**Validates: Requirements 4.2, 4.3**

---

### Property 5: PATCH Never Mutates Status

*For any* `GroupBooking` in any status, issuing a PATCH request to `/api/group-bookings/{id}/` with any combination of writable fields (including a `status` field) leaves `booking.status` unchanged from its value before the request.

**Validates: Requirements 5.1, 5.2, 5.3**

---

### Property 6: X-Mock-Role Header Is Ignored

*For any* request that includes an `X-Mock-Role` header but no valid `Authorization` header, the API returns HTTP 401 regardless of the role value in the header.

**Validates: Requirements 6.1, 6.2, 6.3**

---

### Property 7: All Context Functions Include Authorization Header

*For any* token stored in `localStorage` under `access_token`, every fetch call emitted by any function in `GroupTravelContext` includes the header `Authorization: Bearer <token>`, and no fetch call in the context includes a header named `X-Mock-Role`.

**Validates: Requirements 7.1, 7.2, 7.3, 7.4**

---

### Property 8: Operator Dashboard State-Gated Panels

*For any* `TravelRequest` object with any status value, when `OperatorDashboardView` renders its detail modal, each action panel appears if and only if the booking is in its required status:
- "Submit PNR" panel ↔ status is `PAID`
- "Cancel Booking" panel ↔ status is `NEGOTIATION`
- "Issue Ticket" panel ↔ status is `NAME_SUBMITTED`
- "Complete Booking" panel ↔ status is `TICKETED`

**Validates: Requirements 8.1, 8.2, 8.3, 8.4**

---

### Property 9: Customer View-Request State-Gated Panels

*For any* `TravelRequest` object with any status value, when the `ViewRequestPage` renders the booking detail modal:
- The "Make Payment" / "Proceed to Payment" button appears if and only if status is `PAYMENT_PENDING` or `PARTIALLY_PAID`.
- The "Upload Passenger Names" section appears if and only if status is `PNR_CREATED`.

**Validates: Requirements 8.5, 8.6**

---

### Property 10: Agent Broadcast Listing

*For any* set of `GroupBooking` records in the database and *for any* authenticated Agent, the response to `GET /api/group-bookings/` contains exactly the union of:
- all bookings with `status` in `{'NEW_REQUEST', 'FARE_QUOTED', 'NEGOTIATION'}`, and
- all bookings created by that Agent regardless of status.

**Validates: Requirements 9.1, 9.2**

---

### Property 11: Accept Quote Atomic Transition to PAYMENT_PENDING

*For any* booking in `FARE_QUOTED` or `NEGOTIATION` status with at least one associated `GroupQuote`, when the `/accept/` endpoint is called with a valid `quote_option_id`, the booking's final persisted status is `PAYMENT_PENDING`, `payment_deadline` and `balance_deadline` are set from the selected quote, the selected quote has `is_selected = True`, and the booking is never persisted with status `ACCEPTED` at any point.

**Validates: Requirements 10.1, 10.2, 10.3**
