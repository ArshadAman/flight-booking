# Requirements Document

## Introduction

This feature implements the complete group travel booking flow for the FlightBooking platform. The flow covers the full lifecycle of a group booking — from a customer submitting a request through agent quoting, customer negotiation/acceptance, payment, PNR creation, passenger name submission, ticketing, and completion. The work addresses a set of confirmed gaps in the current codebase: quote upload being incorrectly restricted to ADMIN instead of AGENT, missing `/pnr/` and `/cancel/` endpoints, the absence of a centralized state machine, a dangerous `perform_update` side-effect, an `X-Mock-Role` authentication bypass, and missing auth headers and state-gated UI guards on the frontend.

## Glossary

- **Booking**: A `GroupBooking` database record representing one group travel request and its full lifecycle state.
- **State Machine**: The centralized, server-side authority that validates and executes all status transitions for a Booking. No view or serializer may mutate `status` directly except through the State Machine.
- **Customer**: An authenticated `User` with `role == 'CUSTOMER'`. Submits requests, views quotes, accepts or negotiates, pays, and uploads passenger names.
- **Agent**: An authenticated `User` with `role == 'AGENT'`. Picks up new requests, uploads quotes, may re-quote during negotiation, and submits PNR numbers after payment.
- **Admin**: An authenticated `User` with `role == 'ADMIN'`. Issues tickets and marks bookings complete.
- **JWT**: JSON Web Token stored in `localStorage` under the key `access_token`, used to authenticate all API requests via the `Authorization: Bearer <token>` header.
- **Quote**: A `GroupQuote` record containing airline, flight number, fare, tax, deposit, deadlines, and terms for one flight option within a Booking.
- **PNR**: Passenger Name Record — the airline booking reference code. Submitted by an Agent after the Booking reaches `PAID` status.
- **Negotiation Remarks**: Free-text notes attached to the Booking's `remarks` field when a Customer requests a different fare or routing.

---

## Requirements

### Requirement 1 — Centralized State Machine

**User Story:** As a platform operator, I want all booking status transitions enforced in one place, so that no endpoint can skip a step or set an invalid status.

#### Acceptance Criteria

1. THE State Machine SHALL define the following and only the following valid transitions:
   - `NEW_REQUEST` → `FARE_QUOTED` (trigger: Agent uploads quote)
   - `FARE_QUOTED` → `NEGOTIATION` (trigger: Customer submits negotiation)
   - `FARE_QUOTED` → `ACCEPTED` (trigger: Customer accepts quote)
   - `NEGOTIATION` → `FARE_QUOTED` (trigger: Agent re-uploads quote)
   - `NEGOTIATION` → `CANCELLED` (trigger: Agent cancels)
   - `ACCEPTED` → `PAYMENT_PENDING` (trigger: system, immediately after ACCEPTED)
   - `PAYMENT_PENDING` → `PARTIALLY_PAID` (trigger: partial payment recorded)
   - `PAYMENT_PENDING` → `PAID` (trigger: full payment recorded)
   - `PARTIALLY_PAID` → `PAID` (trigger: remaining payment recorded)
   - `PAID` → `PNR_CREATED` (trigger: Agent submits PNR)
   - `PNR_CREATED` → `NAME_SUBMITTED` (trigger: Customer uploads passengers)
   - `NAME_SUBMITTED` → `TICKETED` (trigger: Admin issues ticket)
   - `TICKETED` → `COMPLETED` (trigger: Admin marks complete)

2. WHEN a request to transition a Booking arrives at any endpoint, THE State Machine SHALL validate that the requested transition is in the allowed set before persisting any changes.

3. IF a requested transition is not in the allowed set, THEN THE State Machine SHALL return HTTP 400 with a message identifying the current status and the disallowed transition.

4. THE State Machine SHALL be implemented as a single importable module (e.g., `bookings/state_machine.py`) referenced by all action endpoints in `GroupBookingViewSet`.

---

### Requirement 2 — Agent Quote Upload

**User Story:** As an agent, I want to upload flight quotes for group requests I have picked up, so that customers can review and respond to my offers.

#### Acceptance Criteria

1. WHEN an authenticated Agent submits a POST to `/api/group-bookings/{id}/quote/`, THE Quote Endpoint SHALL accept the request and create one or more `GroupQuote` records.

2. WHEN an authenticated Admin submits a POST to `/api/group-bookings/{id}/quote/`, THE Quote Endpoint SHALL also accept the request.

3. IF a user with `role == 'CUSTOMER'` submits a POST to `/api/group-bookings/{id}/quote/`, THEN THE Quote Endpoint SHALL return HTTP 403.

4. WHEN quote upload succeeds, THE Quote Endpoint SHALL transition the Booking from `NEW_REQUEST` or `NEGOTIATION` to `FARE_QUOTED` via the State Machine.

5. IF the Booking status is not `NEW_REQUEST`, `NEGOTIATION`, or `FARE_QUOTED` at the time of upload, THEN THE Quote Endpoint SHALL return HTTP 400.

---

### Requirement 3 — PNR Submission Endpoint

**User Story:** As an agent, I want a dedicated endpoint to submit the PNR code after a booking is paid, so that the system correctly records the PNR and advances the booking to PNR_CREATED.

#### Acceptance Criteria

1. THE PNR Endpoint SHALL be accessible at `POST /api/group-bookings/{id}/pnr/`.

2. WHEN an authenticated Agent submits a non-empty PNR string to the PNR Endpoint and the Booking is in `PAID` status, THE PNR Endpoint SHALL store the PNR on the Booking and transition the status to `PNR_CREATED`.

3. IF the Booking is not in `PAID` status when the PNR Endpoint is called, THEN THE PNR Endpoint SHALL return HTTP 400.

4. IF the submitted PNR string is blank or absent, THEN THE PNR Endpoint SHALL return HTTP 400.

5. IF a user with `role != 'AGENT'` and `role != 'ADMIN'` calls the PNR Endpoint, THEN THE PNR Endpoint SHALL return HTTP 403.

---

### Requirement 4 — Negotiation Cancel Endpoint

**User Story:** As an agent, I want to cancel a booking that is under negotiation, so that customers are notified promptly and the booking does not linger in an unresolvable state.

#### Acceptance Criteria

1. THE Cancel Endpoint SHALL be accessible at `POST /api/group-bookings/{id}/cancel/`.

2. WHEN an authenticated Agent calls the Cancel Endpoint and the Booking is in `NEGOTIATION` status, THE Cancel Endpoint SHALL transition the Booking status to `CANCELLED`.

3. IF the Booking is not in `NEGOTIATION` status, THEN THE Cancel Endpoint SHALL return HTTP 400.

4. IF a user with `role == 'CUSTOMER'` calls the Cancel Endpoint, THEN THE Cancel Endpoint SHALL return HTTP 403.

---

### Requirement 5 — Remove perform_update Side-Effect

**User Story:** As a platform operator, I want the generic PATCH endpoint to never silently change booking status, so that no ad-hoc field update accidentally triggers a state transition.

#### Acceptance Criteria

1. THE `GroupBookingViewSet` SHALL NOT contain a `perform_update` override that inspects field changes and writes a new `status` value.

2. WHEN a PATCH request to `/api/group-bookings/{id}/` is processed, THE BookingViewSet SHALL update only the writable non-status fields supplied in the request body.

3. IF a PATCH request body includes a `status` field, THEN THE BookingViewSet SHALL ignore the `status` field and leave the Booking status unchanged.

---

### Requirement 6 — Remove X-Mock-Role Authentication Bypass

**User Story:** As a security-conscious operator, I want all API requests to be authenticated via JWT only, so that no request can impersonate a role by sending an HTTP header.

#### Acceptance Criteria

1. THE `get_user` helper in `GroupBookingViewSet` SHALL be removed entirely; all views SHALL use `request.user` provided by the JWT authentication backend.

2. IF a request arrives without a valid JWT, THEN THE API SHALL return HTTP 401.

3. THE API SHALL NOT read or honor the `X-Mock-Role` request header or the `mock_role` query/body parameter for any purpose.

4. THE `GroupBookingViewSet` permission class SHALL remain `IsAuthenticated` so that all endpoints require a verified JWT.

---

### Requirement 7 — Frontend JWT Authentication Headers

**User Story:** As an authenticated user, I want every API call from the frontend to include my JWT token, so that the server can verify my identity and role correctly.

#### Acceptance Criteria

1. THE `issueTicket` function in `GroupTravelContext` SHALL include the `Authorization: Bearer <token>` header on its fetch call, reading the token from `localStorage` via the existing `getAuthHeaders()` helper.

2. THE `completeBooking` function in `GroupTravelContext` SHALL include the `Authorization: Bearer <token>` header on its fetch call.

3. THE `updateRequest` function in `GroupTravelContext` SHALL include the `Authorization: Bearer <token>` header on its fetch call.

4. THE `GroupTravelContext` SHALL NOT include the `X-Mock-Role` header in any outbound fetch call.

---

### Requirement 8 — Frontend State-Gated Action Guards

**User Story:** As a user, I want the UI to show only the actions available for the current booking status, so that I cannot attempt an action that the backend would reject.

#### Acceptance Criteria

1. WHEN the Operator Dashboard displays the detail modal for a Booking, THE OperatorDashboardView SHALL render the "Submit PNR" action panel only when the Booking status is `PAID`.

2. WHEN the Operator Dashboard displays the detail modal for a Booking, THE OperatorDashboardView SHALL render the "Cancel Booking" action only when the Booking status is `NEGOTIATION`.

3. WHEN the Operator Dashboard displays the detail modal for a Booking, THE OperatorDashboardView SHALL render the "Issue Ticket" action only when the Booking status is `NAME_SUBMITTED`.

4. WHEN the Operator Dashboard displays the detail modal for a Booking, THE OperatorDashboardView SHALL render the "Complete Booking" action only when the Booking status is `TICKETED`.

5. WHEN the customer view-request page displays a Booking detail modal, THE ViewRequestPage SHALL render the "Make Payment" button only when the Booking status is `PAYMENT_PENDING` or `PARTIALLY_PAID`.

6. WHEN the customer view-request page displays a Booking detail modal, THE ViewRequestPage SHALL render the "Upload Passenger Names" section only when the Booking status is `PNR_CREATED`.

---

### Requirement 9 — Agent Broadcast of New Requests

**User Story:** As an agent, I want to see all bookings in NEW_REQUEST status regardless of who submitted them, so that any available agent can pick up and quote a new group request.

#### Acceptance Criteria

1. WHEN an authenticated Agent calls `GET /api/group-bookings/`, THE BookingViewSet SHALL return all Bookings with status `NEW_REQUEST`, `FARE_QUOTED`, or `NEGOTIATION`, plus any Booking created by that Agent, in a single response.

2. THE BookingViewSet SHALL NOT require a Booking to be created by the requesting Agent in order to appear in the Agent's listing when the Booking is in `NEW_REQUEST` status.

---

### Requirement 10 — Accept Quote Transition Integrity

**User Story:** As a platform operator, I want the accept-quote flow to transition atomically through ACCEPTED to PAYMENT_PENDING, so that the booking is never left stranded in ACCEPTED status.

#### Acceptance Criteria

1. WHEN a Customer calls `POST /api/group-bookings/{id}/accept/` with a valid `quote_option_id`, THE AcceptQuote Endpoint SHALL mark the selected Quote `is_selected = True`, set `payment_deadline` and `balance_deadline` from the Quote, and transition the Booking atomically to `PAYMENT_PENDING` within a single database transaction.

2. THE AcceptQuote Endpoint SHALL NOT persist an intermediate `ACCEPTED` status write that is immediately overwritten — the single final status written SHALL be `PAYMENT_PENDING`.

3. IF the Booking is not in `FARE_QUOTED` or `NEGOTIATION` status, THEN THE AcceptQuote Endpoint SHALL return HTTP 400.
