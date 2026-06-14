# Implementation Plan: Group Travel Booking Flow

## Overview

Implement the complete group travel booking flow by: (1) creating a centralized state machine module, (2) refactoring `GroupBookingViewSet` to use it and add missing endpoints, (3) updating the `GroupBooking` model with the `CANCELLED` status, and (4) updating the frontend context and views to use real JWT auth and proper state-gated rendering guards.

## Tasks

- [ ] 1. Create the centralized state machine module
  - [ ] 1.1 Implement `bookings/state_machine.py`
    - Create the new file `bookings/state_machine.py`
    - Define `InvalidTransition` exception class
    - Define `VALID_TRANSITIONS` dict with all 13 allowed `(current, target)` pairs from the design
    - Implement `transition(booking, target_status)` — mutates `booking.status` in memory, does NOT call `.save()`
    - Implement `can_transition(current_status, target_status)` — pure boolean predicate, no side effects
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ]* 1.2 Write property test for state machine transition table (Property 1)
    - **Property 1: State Machine Transition Table Completeness**
    - Use `hypothesis` to generate `(current_status, target_status)` pairs; assert `transition()` succeeds iff the pair is in `VALID_TRANSITIONS`, and raises `InvalidTransition` otherwise
    - **Validates: Requirements 1.1, 1.2, 1.3**

  - [ ]* 1.3 Write unit tests for `state_machine.py`
    - Assert `can_transition()` returns `True` for every valid pair and `False` for every invalid pair
    - Assert `transition()` mutates only `booking.status` in memory and does not trigger a DB save
    - _Requirements: 1.2, 1.3_

- [ ] 2. Update `GroupBooking` model — add `CANCELLED` status choice
  - [ ] 2.1 Add `CANCELLED` to `STATUS_CHOICES` in `bookings/models.py` and create migration
    - Add `('CANCELLED', 'Cancelled')` to `STATUS_CHOICES`
    - Run `python manage.py makemigrations bookings --name add_cancelled_status` to generate the `AlterField` migration
    - _Requirements: 4.2_

- [ ] 3. Refactor `GroupBookingViewSet` — remove mock-role bypass and perform_update side-effect
  - [ ] 3.1 Remove `get_user` helper and `perform_update` override in `bookings/views.py`
    - Delete the entire `get_user` method
    - Replace every `self.get_user()` call with `request.user` (in `get_queryset`, `negotiate`, `record_payment`, `upload_passengers`, `issue_ticket`, `complete_booking`, `create_change_request`, `resolve_change_request`)
    - Remove the entire `perform_update` override; the default `ModelViewSet.perform_update` takes its place
    - Verify `GroupBookingSerializer` still lists `status` in `read_only_fields` (no serializer edit needed)
    - _Requirements: 5.1, 5.2, 5.3, 6.1, 6.3, 6.4_

  - [ ]* 3.2 Write property test for PATCH status immutability (Property 5)
    - **Property 5: PATCH Never Mutates Status**
    - For any booking in any status, PATCH with any combination of writable fields including `status` must leave `booking.status` unchanged
    - **Validates: Requirements 5.1, 5.2, 5.3**

  - [ ]* 3.3 Write property test for X-Mock-Role header being ignored (Property 6)
    - **Property 6: X-Mock-Role Header Is Ignored**
    - Any request with `X-Mock-Role` but no valid `Authorization` header must return HTTP 401
    - **Validates: Requirements 6.1, 6.2, 6.3**

- [ ] 4. Wire state machine into `upload_quote` and existing action endpoints
  - [ ] 4.1 Fix `upload_quote` role check and integrate state machine
    - Change the role guard from `ADMIN`-only to `AGENT` or `ADMIN`
    - Replace the inline `booking.status = 'FARE_QUOTED'` write with `state_machine.transition(booking, 'FARE_QUOTED')` inside `transaction.atomic()`
    - Catch `InvalidTransition` and return HTTP 400 with the exception message
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 1.2, 1.4_

  - [ ] 4.2 Replace inline status assignments with `state_machine.transition()` in all remaining action endpoints
    - Update `negotiate`, `record_payment`, `upload_passengers`, `issue_ticket`, `complete_booking` to call `state_machine.transition(booking, '<TARGET>')` instead of direct field assignment
    - Catch `InvalidTransition` in each endpoint and return HTTP 400
    - _Requirements: 1.2, 1.4_

  - [ ]* 4.3 Write property test for quote upload role enforcement (Property 2)
    - **Property 2: Quote Upload Role Enforcement**
    - For any user role in `{AGENT, ADMIN}` with a valid payload on an eligible status, the endpoint succeeds; for `CUSTOMER` it always returns HTTP 403
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

- [ ] 5. Refactor `accept_quote` — atomic single write to `PAYMENT_PENDING`
  - [ ] 5.1 Implement atomic accept-quote flow
    - Remove the double-save pattern (ACCEPTED then PAYMENT_PENDING)
    - Wrap the entire flow in `transaction.atomic()`: set `is_selected = True` on selected quote, copy deadlines to booking, call `state_machine.transition(booking, 'PAYMENT_PENDING')`, call `booking.save()` once
    - Return HTTP 400 if booking status is not `FARE_QUOTED` or `NEGOTIATION`
    - Return HTTP 404 if `quote_option_id` not found
    - _Requirements: 10.1, 10.2, 10.3_

  - [ ]* 5.2 Write property test for accept quote atomic transition (Property 11)
    - **Property 11: Accept Quote Atomic Transition to PAYMENT_PENDING**
    - For any eligible booking and quote, the final persisted status must be `PAYMENT_PENDING`; `ACCEPTED` must never appear in the DB at any point
    - **Validates: Requirements 10.1, 10.2, 10.3**

- [ ] 6. Add `/pnr/` endpoint to `GroupBookingViewSet`
  - [ ] 6.1 Implement `submit_pnr` action
    - Add `@action(detail=True, methods=['post'], url_path='pnr')` decorated method
    - Enforce AGENT or ADMIN role (HTTP 403 for others)
    - Validate `pnr_number` is non-empty (HTTP 400 if blank or absent)
    - Call `state_machine.transition(booking, 'PNR_CREATED')` (HTTP 400 on `InvalidTransition`)
    - Set `booking.pnr_number` and call `booking.save()`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 6.2 Write property test for PNR submission (Property 3)
    - **Property 3: PNR Submission Stores Value and Advances Status**
    - For any non-empty PNR string submitted by Agent/Admin on a PAID booking, `pnr_number` is persisted and status becomes `PNR_CREATED`
    - **Validates: Requirements 3.2, 3.3, 3.4**

- [ ] 7. Add `/cancel/` endpoint to `GroupBookingViewSet`
  - [ ] 7.1 Implement `cancel_booking` action
    - Add `@action(detail=True, methods=['post'], url_path='cancel')` decorated method
    - Return HTTP 403 if `user.role == 'CUSTOMER'`
    - Call `state_machine.transition(booking, 'CANCELLED')` (HTTP 400 on `InvalidTransition`)
    - Call `booking.save()` on success; return status and confirmation message
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [ ]* 7.2 Write property test for cancel endpoint gate (Property 4)
    - **Property 4: Cancel Endpoint Gate**
    - NEGOTIATION booking + Agent/Admin → CANCELLED; non-NEGOTIATION booking → HTTP 400; CUSTOMER → HTTP 403
    - **Validates: Requirements 4.2, 4.3**

- [ ] 8. Verify agent broadcast `get_queryset` (no logic change needed)
  - [ ] 8.1 Confirm `get_queryset` uses `request.user` and existing Q-filter is correct
    - Verify the Q-filter `Q(user=user) | Q(status__in=['NEW_REQUEST', 'FARE_QUOTED', 'NEGOTIATION'])` remains unchanged
    - Only replace `self.get_user()` → `self.request.user` (already done in Task 3.1)
    - _Requirements: 9.1, 9.2_

  - [ ]* 8.2 Write property test for agent broadcast listing (Property 10)
    - **Property 10: Agent Broadcast Listing**
    - For any set of bookings, an Agent's GET response must equal exactly the union of broadcast-eligible bookings and that agent's own bookings
    - **Validates: Requirements 9.1, 9.2**

- [ ] 9. Checkpoint — Backend complete
  - Ensure all backend tests pass, ask the user if questions arise.

- [ ] 10. Update `GroupTravelContext.tsx` — remove `X-Mock-Role` and add missing auth headers
  - [ ] 10.1 Add missing `getAuthHeaders()` calls and strip all `X-Mock-Role` headers
    - Add `...getAuthHeaders()` to `issueTicket`, `completeBooking`, and `updateRequest` fetch calls
    - Remove `X-Mock-Role` from every fetch call in the context: `refreshRequests`, `addRequest`, `negotiateRequest`, `acceptQuote`, `recordPayment`, `uploadPassengers`, `createChangeRequest`, `resolveChangeRequest`, `uploadQuotes`, `issueTicket`, `completeBooking`, `updateRequest`
    - Remove the `role?: "AGENT" | "ADMIN"` parameter from `refreshRequests`; update all call sites to `await refreshRequests()`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 6.3_

  - [ ]* 10.2 Write property test for frontend auth headers (Property 7)
    - **Property 7: All Context Functions Include Authorization Header**
    - Using `fast-check`, for any token string in `localStorage`, mock `fetch` and assert every context function's call includes `Authorization: Bearer <token>` and excludes `X-Mock-Role`
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4**

- [ ] 11. Add `submitPnr` and `cancelBooking` to `GroupTravelContext.tsx`
  - [ ] 11.1 Implement and expose new context functions
    - Implement `submitPnr(bookingId, pnrNumber)`: POST to `/api/group-bookings/{dbId}/pnr/` with `...getAuthHeaders()`, call `refreshRequests()` on success, return boolean
    - Implement `cancelBooking(bookingId)`: POST to `/api/group-bookings/{dbId}/cancel/` with `...getAuthHeaders()`, call `refreshRequests()` on success, return boolean
    - Add `submitPnr` and `cancelBooking` to the `GroupTravelContextType` interface
    - Add both to the context provider value object
    - _Requirements: 3.1, 4.1, 7.1_

- [ ] 12. Update `OperatorDashboardView.tsx` — add Cancel Booking action panel
  - [ ] 12.1 Add Cancel Booking panel and wire `cancelBooking` context function
    - Destructure `cancelBooking` from `useGroupTravel()`
    - Add `handleCancelBookingClick` handler calling `cancelBooking(selectedRequest.id)`, following the same async loading-state pattern as `handleCompleteBookingClick`
    - Add the Cancel Booking panel with red styling rendered only when `selectedRequest.status === "NEGOTIATION"`, positioned between the Change Request panel and the Assign PNR panel
    - Replace any remaining `refreshRequests("ADMIN")` calls with `refreshRequests()`
    - _Requirements: 8.2_

  - [ ]* 12.2 Write property test for operator dashboard state-gated panels (Property 8)
    - **Property 8: Operator Dashboard State-Gated Panels**
    - Using `fast-check`, for each of the 11 possible status values render `OperatorDashboardView` with a mock booking and assert the correct subset of action panels is visible
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4**

- [ ] 13. Update `view-request/page.tsx` — narrow passenger upload guard
  - [ ] 13.1 Fix the passenger upload status guard
    - Change the guard from `status === "PAID" || status === "PNR_CREATED"` to `status === "PNR_CREATED"` only
    - Verify the "Make Payment" button guard (`PAYMENT_PENDING || PARTIALLY_PAID`) is unchanged
    - _Requirements: 8.5, 8.6_

  - [ ]* 13.2 Write property test for customer view-request state-gated panels (Property 9)
    - **Property 9: Customer View-Request State-Gated Panels**
    - Using `fast-check`, for any status value render `ViewRequestPage` and assert the "Make Payment" and "Upload Passenger Names" sections appear iff the booking is in their required status(es)
    - **Validates: Requirements 8.5, 8.6**

- [ ] 14. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Backend property tests use `hypothesis` (Python); frontend property tests use `fast-check` (TypeScript/React)
- Tasks 1–9 are backend-only; Tasks 10–13 are frontend-only — they can run in parallel after Task 1.1 is complete
- Task 2.1 generates an `AlterField` migration only — no DDL change since `STATUS_CHOICES` is a `VARCHAR` column
- `bookings/urls.py` requires no changes — `/pnr/` and `/cancel/` are auto-registered by `DefaultRouter` via `@action(detail=True, ...)`
- Each task references specific requirements for full traceability

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "2.1", "3.1", "10.1"] },
    { "id": 2, "tasks": ["3.2", "3.3", "4.1", "4.2", "5.1", "6.1", "7.1", "8.1", "11.1", "13.1"] },
    { "id": 3, "tasks": ["4.3", "5.2", "6.2", "7.2", "8.2", "10.2", "12.1"] },
    { "id": 4, "tasks": ["12.2", "13.2"] }
  ]
}
```
