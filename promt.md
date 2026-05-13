# ROLE

You are a senior backend engineer and system architect.

Your task is to build a production-oriented MVP backend for a Flight Booking System using Django and Django REST Framework.

IMPORTANT:
This is NOT an enterprise airline infrastructure system.
This is a budget-constrained MVP (~₹50k scope).

Do NOT overengineer.
Do NOT introduce unnecessary microservices.
Do NOT use Kubernetes.
Do NOT build distributed event buses.
Do NOT create massive abstractions.

However:
The backend MUST still follow strong engineering practices:
- clean architecture
- secure REST APIs
- idempotent booking flow
- proper payment verification
- event-driven async tasks using Celery
- transactional consistency
- clean API design
- scalable enough for MVP traffic
- maintainable codebase

---

# PROJECT OVERVIEW

Build a Flight Booking Backend for:
- B2C customers
- B2B travel agents

Frontend already exists.

Backend responsibilities:
- authentication
- flight search
- fare revalidation
- booking creation
- payment verification
- ticket retrieval
- booking history
- simple B2B markup support
- admin management

The backend will integrate with ONE third-party flight API provider.

---

# TECH STACK

Use exactly:

- Django
- Django REST Framework
- PostgreSQL
- Redis
- Celery
- JWT Authentication
- Docker
- Nginx-ready configuration

Avoid unnecessary technologies.

---

# ARCHITECTURE REQUIREMENTS

Use a modular monolith architecture.

Suggested Django apps:
- accounts
- flights
- bookings
- payments
- agents
- tickets
- core

Use:
- service layer pattern
- repository abstraction only where useful
- serializers separated cleanly
- business logic outside views
- thin controllers/views

Avoid:
- fat views
- business logic in serializers
- tightly coupled APIs

---

# SECURITY REQUIREMENTS

Implement proper backend security.

Must include:
- JWT auth
- password hashing
- role-based access
- secure environment variables
- rate limiting
- input validation
- SQL injection protection
- XSS-safe APIs
- CSRF handling where needed
- secure payment verification
- request validation
- logging of critical failures

Never expose:
- secrets
- provider credentials
- internal stack traces

Use:
- Django security best practices
- DRF permissions
- environment-based settings

---

# API DESIGN REQUIREMENTS

Design clean REST APIs.

Requirements:
- versioned APIs (/api/v1/)
- proper HTTP methods
- proper status codes
- pagination where needed
- consistent response structure
- proper validation errors

Response format:

Success:
```json
{
  "success": true,
  "message": "Request successful",
  "data": {}
}
```

Error:
```json
{
  "success": false,
  "message": "Validation failed",
  "errors": {}
}
```

---

# AUTHENTICATION MODULE

Features:
- register
- login
- refresh token
- logout
- profile endpoint

Roles:
- CUSTOMER
- AGENT
- ADMIN

Use JWT auth.

Endpoints:
- POST /api/v1/auth/register/
- POST /api/v1/auth/login/
- POST /api/v1/auth/refresh/
- POST /api/v1/auth/logout/
- GET /api/v1/auth/profile/

---

# FLIGHT SEARCH MODULE

Features:
- one-way flight search
- round-trip search
- fare details
- fare revalidation before booking

Endpoints:
- POST /api/v1/flights/search/
- POST /api/v1/flights/revalidate/
- GET /api/v1/flights/{id}/

The backend should:
- validate search payloads
- call external provider APIs
- normalize provider response
- return frontend-friendly data

Do NOT build:
- caching engine
- fare prediction
- multi-provider aggregation

Single provider only.

---

# BOOKING MODULE

IMPORTANT:
Booking flow MUST be idempotent.

Prevent duplicate bookings caused by:
- double-clicks
- payment retries
- frontend retry requests
- slow network retries

Implement:
- idempotency keys
- booking transaction states
- atomic database transactions

Booking states:
- INITIATED
- PAYMENT_PENDING
- PROCESSING
- CONFIRMED
- FAILED
- CANCELLED

Endpoints:
- POST /api/v1/bookings/create/
- GET /api/v1/bookings/{id}/
- GET /api/v1/bookings/history/
- POST /api/v1/bookings/cancel/

Requirements:
- transactional booking creation
- passenger validation
- audit logging
- booking reference generation
- prevent race conditions

Use:
- select_for_update where appropriate
- database transactions
- unique constraints

---

# PAYMENT MODULE

Use Razorpay integration abstraction.

Features:
- payment initiation
- payment verification
- webhook verification

Endpoints:
- POST /api/v1/payments/initiate/
- POST /api/v1/payments/verify/
- POST /api/v1/payments/webhook/

Requirements:
- verify payment signatures
- prevent duplicate payment processing
- link payment to booking safely
- transactional consistency

Do NOT trust frontend payment success blindly.

---

# EVENT-DRIVEN TASKS WITH CELERY

Use Celery only for async operational tasks.

Do NOT build a complex distributed event architecture.

Use Celery for:
- ticket retrieval
- booking confirmation polling
- email sending
- payment reconciliation retries
- failed booking recovery

Requirements:
- retry policies
- exponential backoff where useful
- task logging
- dead-simple queue setup

Keep architecture simple and maintainable.

---

# B2B AGENT MODULE

Features:
- agent accounts
- simple markup percentage
- agent booking history

Do NOT build:
- wallet system
- credit system
- commission engine
- sub-agent hierarchy

Endpoints:
- GET /api/v1/agents/bookings/
- GET /api/v1/agents/profile/

---

# ADMIN REQUIREMENTS

Use Django Admin only.

Admin should manage:
- users
- agents
- bookings
- payments
- logs

Do NOT build custom admin frontend.

---

# DATABASE REQUIREMENTS

Use PostgreSQL.

Core tables:
- users
- agents
- bookings
- passengers
- payments
- flight_search_logs

Requirements:
- proper indexing
- UUIDs where appropriate
- created_at/updated_at timestamps
- soft delete only if truly necessary

Avoid premature optimization.

---

# CODE QUALITY REQUIREMENTS

Code must include:
- clean folder structure
- type hints where useful
- docstrings
- reusable services
- centralized exception handling
- proper logging
- environment-based configs
- lint-friendly code

Use:
- DRF serializers
- custom exception middleware
- service layer architecture

---

# DEPLOYMENT REQUIREMENTS

Project should support:
- Docker setup
- docker-compose
- PostgreSQL service
- Redis service
- Celery worker service

Include:
- .env.example
- requirements.txt
- production settings template

Do NOT include:
- Kubernetes
- Terraform
- AWS infrastructure automation

---

# TESTING REQUIREMENTS

Implement:
- unit tests for services
- API tests for critical flows
- booking flow tests
- payment verification tests

Focus especially on:
- duplicate booking prevention
- auth security
- payment consistency

---

# IMPORTANT CONSTRAINTS

This is an MVP.

DO:
- keep architecture clean
- keep APIs professional
- implement proper security
- handle transactional consistency
- handle idempotency correctly

DO NOT:
- overengineer
- build airline-scale infra
- introduce microservices
- create unnecessary abstractions
- build massive event systems

Balance:
pragmatism + good engineering.

---

# FINAL DELIVERABLES

Generate:
- complete Django project structure
- all models
- serializers
- views
- services
- Celery tasks
- API routes
- permissions
- middleware
- Docker setup
- environment configs
- sample tests
- README
- setup instructions

The final codebase should feel like:
“A senior engineer built a scalable MVP responsibly within budget constraints.”