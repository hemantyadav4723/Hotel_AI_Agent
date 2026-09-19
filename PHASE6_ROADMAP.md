# PHASE 6 — FASTAPI BACKEND ROADMAP

1. FastAPI Foundation
   - FastAPI application entry point
   - API versioning
   - startup/database initialization
   - health endpoint
   - Swagger/OpenAPI and ReDoc

2. API Architecture
   - routers
   - schemas
   - dependencies
   - security layer
   - common response/data helpers
   - separation from CLI menus

3. Existing SQLite Integration
   - reuse existing SQLite database
   - reuse database/business functions
   - hotel context propagation
   - connection safety
   - no parallel API database

4. Pydantic Schemas
   - request validation
   - response serialization
   - strict extra-field handling
   - typed dates, numbers and identifiers

5. Authentication
   - login endpoint
   - JWT access token
   - token expiry
   - current-user endpoint
   - password change

6. Authorization / Roles
   - hotel-scoped user identity
   - role/permission checks
   - 401/403 handling
   - existing permission architecture reuse

7. Hotel Information APIs
   - hotel profile/context
   - settings read
   - hotel master data

8. Customer / Guest APIs
   - customer list/search
   - customer detail
   - guest summaries/lifecycle
   - customer creation

9. Room & Reservation APIs
   - room list/detail
   - availability
   - reservation creation
   - reservation lookup
   - reservation status

10. Restaurant / Table APIs
   - menu
   - restaurant orders
   - order status
   - restaurant tables
   - table availability
   - table bookings

11. Billing & Payment APIs
   - invoices
   - room folio
   - room payment transactions
   - restaurant payment history
   - payment methods foundation

12. Inventory / Purchase / Supplier APIs
   - inventory items
   - low stock
   - valuation
   - categories/units
   - suppliers
   - purchase orders
   - receiving records

13. Staff / HR / Expense APIs
   - staff
   - departments
   - attendance
   - leave
   - salary
   - payroll
   - expenses

14. Feedback / Notification APIs
   - feedback
   - satisfaction
   - notification inbox/search
   - communication channels
   - mark read

15. Transportation / Maps / Media APIs
   - transportation requests
   - vehicles/drivers
   - maps/configuration
   - nearby places/routes
   - hotel media

16. Reports & Analytics APIs
   - dashboard
   - revenue
   - room/restaurant revenue
   - occupancy/ADR/RevPAR
   - booking/cancellation/no-show
   - customer/inventory/expense trends
   - department/staff/profitability

17. Audit / Activity APIs
   - audit history
   - record audit
   - request IDs
   - structured operational traceability

18. Multi-Hotel API Architecture
   - hotel_id in authenticated claims
   - active-hotel validation
   - tenant-scoped reads/writes
   - no client-controlled cross-hotel access

19. API Security & Reliability
   - JWT validation
   - permission checks
   - rate limiting
   - security headers
   - CORS configuration
   - controlled errors
   - request correlation ID

20. API Documentation
   - OpenAPI metadata
   - grouped tags
   - typed request models
   - authentication scheme documentation
   - docs and ReDoc endpoints

21. Existing CLI → Backend Integration
   - same database
   - same business/database layer
   - API does not replace CLI
   - no duplicate business database

22. API Testing
   - health
   - authentication boundary
   - OpenAPI
   - protected route boundary
   - module endpoint smoke tests

23. Cross-Module API Testing
   - customer → booking
   - booking → billing
   - restaurant → inventory foundation
   - feedback → notification foundation
   - transportation → notification foundation
   - reports from persisted business data

24. AI-Ready API Layer
   - AI tool registry exposure
   - tool definitions
   - whitelisted tool execution
   - structured JSON boundary
   - future AI agent integration point

25. Final Phase 6 Verification
   - source audit
   - roadmap mapping
   - runtime verification
   - security/tenant verification
   - API documentation verification
   - regression verification
   - final PASS before Phase 7
