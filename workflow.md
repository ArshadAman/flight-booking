# Flight Booking System — Workflow Documentation
# B2B + B2C MVP Backend

---

# 1. System Overview

The system is a backend-driven flight booking platform supporting:
- B2C Customers
- B2B Travel Agents
- Admin Operations

The backend communicates with:
- Frontend application
- Flight API Provider
- Razorpay payment gateway

Core workflow:
```text
User → Frontend → Backend → Flight API Provider
                          ↓
                    Payment Gateway
```

---

# 2. User Roles

| Role | Description |
|---|---|
| CUSTOMER | End customer booking flights |
| AGENT | B2B travel agent |
| ADMIN | System administrator |

---

# 3. High-Level Workflow

```text
Authentication
    ↓
Flight Search
    ↓
Fare Selection
    ↓
Fare Revalidation
    ↓
Booking Creation
    ↓
Payment Initiation
    ↓
Payment Verification
    ↓
Ticket Confirmation
    ↓
Booking History / Ticket Download
```

---

# 4. Authentication Workflow

# 4.1 Registration Flow

```text
User submits registration form
    ↓
Backend validates input
    ↓
Password hashed
    ↓
User stored in database
    ↓
JWT tokens generated
    ↓
Response returned
```

---

# 4.2 Login Flow

```text
User submits credentials
    ↓
Backend validates credentials
    ↓
JWT access + refresh tokens generated
    ↓
Tokens returned to frontend
```

---

# 4.3 Protected Route Access

```text
Frontend sends JWT token
    ↓
Backend validates token
    ↓
User role checked
    ↓
Request processed
```

---

# 5. Flight Search Workflow

# 5.1 Flight Search Flow

```text
User enters:
- source
- destination
- date
- passengers

    ↓

Frontend sends request to backend

    ↓

Backend validates payload

    ↓

Backend calls flight API provider

    ↓

Provider returns available flights

    ↓

Backend normalizes response

    ↓

Frontend receives standardized response
```

---

# 5.2 Fare Revalidation Workflow

IMPORTANT:
Fare must be revalidated before payment.

```text
User selects flight
    ↓
Frontend sends fare revalidation request
    ↓
Backend calls provider API
    ↓
Latest fare checked
    ↓
Updated fare returned
```

Purpose:
- prevent stale pricing
- prevent booking failures

---

# 6. Booking Workflow

# 6.1 Booking Creation Workflow

IMPORTANT:
Booking creation must be idempotent.

---

## Workflow

```text
User submits:
- selected flight
- passenger details
- idempotency key

    ↓

Backend validates request

    ↓

Check if idempotency key already exists

    ↓
YES ----------------→ Return existing booking
    ↓ NO

Create booking record:
status = PAYMENT_PENDING

    ↓

Store passenger data

    ↓

Generate booking reference

    ↓

Return booking response
```

---

# 6.2 Duplicate Booking Prevention

System must prevent:
- double-click bookings
- payment retries
- frontend retry duplication

Mechanism:
- idempotency key
- unique booking constraints
- transactional database operations

---

# 6.3 Booking State Lifecycle

```text
INITIATED
    ↓
PAYMENT_PENDING
    ↓
PROCESSING
    ↓
CONFIRMED
```

Failure paths:

```text
PAYMENT_FAILED
BOOKING_FAILED
CANCELLED
```

---

# 7. Payment Workflow

# 7.1 Payment Initiation

```text
Booking created
    ↓
Frontend requests payment initiation
    ↓
Backend creates Razorpay order
    ↓
Order returned to frontend
```

---

# 7.2 Payment Verification Workflow

IMPORTANT:
Never trust frontend payment success directly.

---

## Workflow

```text
Frontend sends:
- payment_id
- order_id
- signature

    ↓

Backend verifies Razorpay signature

    ↓
VALID ----------------→ Continue
    ↓ INVALID

Reject request

    ↓

Mark payment successful

    ↓

Update booking status:
PROCESSING

    ↓

Trigger async ticket confirmation task
```

---

# 8. Ticket Confirmation Workflow

# 8.1 Async Ticket Processing

Handled using Celery.

```text
Payment verified
    ↓
Celery task triggered
    ↓
Backend calls flight provider booking API
    ↓
Provider returns:
- PNR
- ticket details
- confirmation status

    ↓

Booking updated:
CONFIRMED

    ↓

Ticket stored
```

---

# 8.2 Failure Handling

If provider fails:

```text
Booking status:
FAILED

    ↓

Log error

    ↓

Admin can manually review
```

MVP does NOT include:
- automated reconciliation engine
- automatic refunds

---

# 9. Ticket Download Workflow

```text
User opens booking
    ↓
Frontend requests ticket
    ↓
Backend fetches stored ticket
    ↓
PDF/response returned
```

---

# 10. Booking History Workflow

```text
User requests booking history
    ↓
Backend filters bookings by user
    ↓
Paginated response returned
```

---

# 11. Cancellation Workflow

# 11.1 Cancellation Request

```text
User requests cancellation
    ↓
Backend validates booking ownership
    ↓
Backend calls provider cancellation API
    ↓
Provider returns cancellation status
    ↓
Booking updated
```

---

# 11.2 MVP Limitation

MVP cancellation flow:
- only provider-triggered cancellation
- no automated refund calculation
- no wallet refunds

---

# 12. B2B Agent Workflow

# 12.1 Agent Booking Flow

Same as customer flow with:
- markup percentage applied

---

## Workflow

```text
Agent searches flight
    ↓
Backend applies markup
    ↓
Modified fare returned
    ↓
Booking flow continues normally
```

---

# 13. Admin Workflow

Admin operations handled using Django Admin.

Admin can:
- manage users
- manage agents
- view bookings
- view payments
- monitor failures

---

# 14. Celery Workflow

# 14.1 Async Tasks

Celery handles:
- ticket confirmation
- booking polling
- email sending
- retry operations

---

# 14.2 Retry Workflow

```text
Task fails
    ↓
Celery retry triggered
    ↓
Retry count checked
    ↓
Task retried
```

Simple retry strategy only.

No distributed event bus.

---

# 15. Error Handling Workflow

# API Error Handling

```json
{
  "success": false,
  "message": "Validation failed",
  "errors": {
    "email": ["This field is required"]
  }
}
```

---

# 16. Security Workflow

# Authentication Security

```text
JWT Validation
    ↓
Permission Check
    ↓
Role Authorization
    ↓
API Access
```

---

# Payment Security

```text
Verify signature
    ↓
Validate booking
    ↓
Update transaction atomically
```

---

# 17. Logging Workflow

System logs:
- API failures
- payment failures
- booking failures
- authentication events

Logs stored for:
- debugging
- operational monitoring

---

# 18. Deployment Workflow

```text
Docker Containers
    ↓
Django App
    ↓
Gunicorn
    ↓
Nginx
```

Services:
- backend
- postgres
- redis
- celery

---

# 19. API Workflow Summary

| Module | Workflow |
|---|---|
| Auth | JWT authentication |
| Flights | Provider API integration |
| Bookings | Idempotent transactional flow |
| Payments | Verified payment flow |
| Tickets | Async confirmation |
| Agents | Markup-based booking |
| Admin | Django Admin operations |

---

# 20. MVP Operational Boundaries

The system intentionally excludes:
- multi-provider aggregation
- enterprise event systems
- advanced analytics
- wallet systems
- loyalty systems
- airline-grade scaling

Goal:
Deliver a stable and maintainable MVP backend within budget constraints.

---

# 21. Final Architecture Philosophy

This backend should behave as:

```text
Frontend
   ↓
Backend Orchestrator
   ↓
Flight Provider APIs
```

The backend is responsible for:
- orchestration
- validation
- transactional consistency
- security
- payment verification

The provider handles:
- flight inventory
- pricing
- ticket issuance
- airline operations