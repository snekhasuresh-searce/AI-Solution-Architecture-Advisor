# Japan Ride-Hailing Taxi Platform

**Status:** Escalated - needs human architect review  
**Run:** 3b89b340 - 2026-10-09 16:13  
**Domains:** mobile, backend, cloud, fullstack

## 1. Executive summary

Design an end-to-end solution architecture for a ride-hailing taxi platform for the Japanese market. It covers native iOS and Android apps for riders and drivers, the backend services for dispatch, pricing and payments, and the cloud infrastructure needed to run the platform reliably at scale.

**Project type:** Multi-sided ride-hailing platform: rider and driver mobile apps (iOS/Android), event-driven microservice backend, admin/operator web console and multi-region GCP infrastructure for Japan - enterprise complexity. The platform combines two React Native apps, about 13 backend services (Go and NestJS), real-time dispatch at tens of thousands of location updates per second, Japanese payment and partner-meter integrations, Tokyo/Osaka DR and regulated compliance (APPI, PCI DSS, MLIT, qualified invoices).

**At a glance:** 35.8 FTE team, about 5480 person-days of effort, about 58 weeks to deliver.

**Reviewer:** The solution covers the full brief well: rider and driver apps, microservices, admin console, Japanese payments, qualified invoices, multilingual UI, Japan-region GCP with Tokyo/Osaka DR, observability and APPI/PCI controls. It cannot be approved yet because the agents' outputs still contradict each other on decisions that were meant to be settled. The UI/UX agent still specifies Flutter and Material UI, while frontend has confirmed React Native and shadcn/ui. The backend agent still uses Identity Platform for riders and Cloud SQL for accounts, fleet and pricing, which conflicts with security's switch to Keycloak and with the database ownership matrix. The database agent still declares Spanner asia1 (Seoul witness) with RPO 0 / RTO ≤1 min, while cloud rejects asia1 and commits to a Japan-only Option A or B with RTO of 30 or 60 min. Security's Keycloak puts customer login on Cloud SQL, which breaks the database rule that booking must not depend on Cloud SQL. Smaller inconsistencies remain in compute placement, static hosting, the real-time transport protocol and the IC card payment flow.

## 2. Solution architecture

A Japan-hosted taxi booking platform with separate React Native apps for riders and drivers and a web console for taxi operators and administrators. It works only with licensed taxi companies. Backend microservices on Google Cloud in Tokyo, with a warm standby in Osaka, match riders to nearby taxis within seconds, calculate fares and handle Japanese payment methods. The platform issues qualified-invoice receipts and keeps all personal data in Japan.

### 2.1 High-level solution architecture diagram

![High-level solution architecture](/api/runs/3b89b340/diagram.svg)

**Cloud:** Google Cloud Platform (asia-northeast1 Tokyo primary, asia-northeast2 Osaka warm standby). Boxes are grouped by layer and coloured by type (client system, proposed component, third-party, managed cloud service, AI, data store). Dashed boxes are recommended additions that the requirement did not state.

### 2.2 End-to-end data flow

**Ride booking and dispatch request**

- **1.** Riders → Rider App: Set pickup and destination
- **2.** Rider App → Global Load Balancer & CDN: HTTPS request with JWT
- **3.** Global Load Balancer & CDN → API Gateway / BFFs: WAF-filtered request
- **4.** API Gateway / BFFs → Core Business Services: Idempotent booking request
- **5.** Core Business Services → Maps & Geolocation: Route and fare estimate
- **6.** Core Business Services → Dispatch & Location Services: Match request (gRPC)
- **7.** Dispatch & Location Services → Live Geo Cache: GEOSEARCH nearby taxis
- **8.** Dispatch & Location Services → Core Transactional Store: Commit driver assignment
- **9.** API Gateway / BFFs → Rider App: Driver and ETA (WebSocket)
- **10.** Rider App → Riders: Show assigned taxi

### 2.3 Major components

| Layer | Component | Technology | Type | Status | Purpose |
| --- | --- | --- | --- | --- | --- |
| Users & stakeholders | Riders | - | actor | required | Japanese residents and inbound tourists who request, track and pay for licensed taxis. |
| Users & stakeholders | Taxi Drivers | - | actor | required | Licensed taxi drivers who go online, accept rides, navigate and view their earnings. |
| Users & stakeholders | Fleet Operators | - | actor | required | Licensed taxi companies that manage their own drivers, vehicles, fares and trips through tenant-scoped console access. |
| Users & stakeholders | Admins & Support | - | actor | required | Platform administrators and support staff who handle onboarding, pricing, promotions, tickets, SOS escalations and analytics. |
| User / application layer | Rider App | React Native | proposed | required | iOS/Android app for login, JA/EN place search, fare estimates, booking and reservations, live tracking, masked chat/call, payments via native payment-adapter modules, receipts, safety features and ratings, in four languages. |
| User / application layer | Driver App | React Native | proposed | required | iOS/Android app for the online/offline toggle, accept/decline, navigation handoff, background location every 3-5 s, earnings and offline-tolerant trip state. |
| User / application layer | Admin/Operator Console | Next.js | proposed | required | Role-based web console for driver onboarding, fleet management, pricing and surcharge configuration, promotions, support tickets, a live operations map and analytics. |
| User / application layer | Keycloak Identity (CIAM) | Keycloak | proposed | required | Japan-hosted authentication with separate customer and staff realms. Customers sign in with SMS OTP, email or Apple/Google/LINE via OpenID Connect; staff use mandatory MFA. It issues short-lived JWTs, and identity data stays in Japan. |
| API & application services | API Gateway / BFFs | NestJS (REST/OpenAPI, WebSocket) | proposed | recommended | Rider, driver and admin BFFs that validate JWTs, enforce rate limits and locale negotiation, and expose WebSocket channels for live trip and location events. |
| API & application services | Dispatch & Location Services | Go (gRPC) | proposed | recommended | Low-latency services that ingest driver GPS every 3-5 s, keep the geo-index current, match riders to the nearest available taxi within 3 s and fan out positions and ETA to riders. |
| API & application services | Core Business Services | NestJS | proposed | required | Domain microservices for accounts, ride lifecycle and reservations, pricing/fare, operator and fleet, ratings and support, and communications (push, SMS, masked chat/call). |
| API & application services | Payment & Invoice Service | NestJS | proposed | required | Tokenized payment orchestration (cards with 3DS, Apple/Google Pay, PayPay/d払い, corporate billing, cash recording) with a double-entry ledger and qualified-invoice receipts carrying operator T-numbers. |
| API & application services | Partner Integration Adapter | Go | proposed | required | Anti-corruption layer with pluggable connectors that normalizes partner taxi-meter fares, IC card payments and fleet dispatch status into platform events. |
| Data layer | Core Transactional Store | Spanner | data store | required | Strongly consistent system of record for accounts, drivers, fleets, rate cards, rides, reservations, payments, ledger and invoices. Its Japan-only topology (Option A dual-region or Option B regional plus Osaka standby) is set at a decision gate. |
| Data layer | Live Geo Cache | Memorystore | data store | required | Redis GEO index of driver positions and availability, dispatch offer locks, and caches of rate cards and eligibility for sub-millisecond matching. |
| Data layer | Back-office & Identity DB | Cloud SQL | data store | required | PostgreSQL store for off-path support tickets, lost items, onboarding review and campaign drafts, plus the Keycloak identity store, with an Osaka replica. |
| Data layer | Analytics Warehouse | BigQuery | data store | required | Japan-located warehouse fed by change streams for operator dashboards, MLIT and tax reporting, and console analytics. |
| Data layer | Document & Archive Storage | Cloud Storage | data store | required | Dual-region Tokyo/Osaka storage for invoice PDFs, driver documents, chat attachments and retention-locked archives. |
| External integrations | Maps & Geolocation | Google Maps Platform / Zenrin | third party | required | Japanese/English address search, routing, ETA and fixed-fare route calculation, and driver navigation handoff. |
| External integrations | Payment Gateways & Wallets | Japan PCI DSS PSP (e.g. GMO-PG/Stripe JP), PayPay, d払い, Apple Pay, Google Pay | third party | recommended | Card tokenization with EMV 3DS, digital wallets and QR payments, keeping card data out of the platform's PCI scope. |
| External integrations | SMS, Telephony & Push | Japan-resident SMS/telephony provider, APNs, FCM | third party | recommended | SMS OTP and alerts, masked calling with in-Japan processing, and push notifications whose payloads contain no PII. |
| External integrations | Social Login Providers | LINE Login, Sign in with Apple, Google | third party | recommended | OIDC federation brokered by Keycloak for the login methods the brief requires. |
| External integrations | Partner Meters & Dispatch | Partner vendor systems | third party | recommended | Taxi meters and fleet dispatch systems of licensed partner taxi companies, used for final fares, IC payments and overflow dispatch. |
| Cloud infrastructure & networking | Global Load Balancer & CDN | Cloud Load Balancing, Cloud CDN | cloud service | required | Single anycast entry point with TLS, WebSocket support and health-checked Tokyo/Osaka failover. Static console assets are served from the CDN. |
| Cloud infrastructure & networking | GKE Regional Clusters | GKE | cloud service | required | Multi-zone Tokyo cluster with a warm Osaka standby for dispatch, location streaming, ride state, the partner adapter and Keycloak, with HPA on custom metrics. |
| Cloud infrastructure & networking | Serverless Services | Cloud Run | cloud service | required | Autoscaled hosting in both regions for stateless business, payment, notification, support and admin backend services. |
| Cloud infrastructure & networking | Event Backbone | Pub/Sub, Dataflow | cloud service | required | Japan-pinned asynchronous events with a transactional outbox and change streams, feeding notifications, receipts, cache invalidation, analytics and Option B Spanner replication. |
| Cloud infrastructure & networking | Private Networking | VPC | cloud service | required | Shared VPC with private GKE nodes, private IP for managed services, and Cloud NAT egress to allowlisted gateway, maps and SMS endpoints. |
| Security | WAF & DDoS Protection | Cloud Armor | cloud service | required | OWASP rules, adaptive DDoS protection and rate limits, with stricter policies on login, OTP and booking endpoints. |
| Security | IAM & Org Policies | IAM | cloud service | required | Least-privilege Workload Identity per service and resource-location Org Policies that restrict deployment to Tokyo and Osaka. |
| Security | Encryption Keys | Cloud KMS | cloud service | required | Japan keyrings for CMEK on all stores, Keycloak signing keys and per-user PII envelope encryption, which enables APPI crypto-shredding. |
| Security | Secrets Management | Secret Manager | cloud service | required | Rotated, Japan-replicated storage for payment, maps, SMS, LINE and OIDC credentials. |
| Security | Data Perimeters | VPC Service Controls | cloud service | recommended | Isolates the payment, PII and identity projects to keep PCI DSS scope small and prevent data exfiltration. |
| Monitoring & operations | Monitoring & Alerting | Cloud Monitoring | cloud service | required | SLO dashboards (99.95% availability, dispatch p95 under 3 s) with burn-rate alerts and exemplars. |
| Monitoring & operations | Centralized & Audit Logs | Cloud Logging | cloud service | required | Japan-pinned, retention-locked application, audit and security logs, correlated by trace ID. |
| Monitoring & operations | Distributed Tracing | Cloud Trace, OpenTelemetry | cloud service | recommended | End-to-end traces across gRPC, HTTP, WebSocket and Pub/Sub, with PII redacted at the Collector. |
| Monitoring & operations | CI/CD & IaC | Cloud Build, Artifact Registry, Terraform | cloud service | required | Builds and signs images, deploys progressively per region, and keeps the Tokyo and Osaka stacks identical as code. |
| Monitoring & operations | Quality & Load Testing | k6, Playwright, axe-core, Lighthouse, OWASP ZAP | proposed | recommended | Release gates for peak load, end-to-end and accessibility checks, performance budgets and DAST security testing. |

### 2.4 Requirement traceability

| Requirement | Delivered by |
| --- | --- |
| Rider registration and login (phone/SMS, email, Apple/Google, LINE login) | Rider App, Keycloak Identity (CIAM), Social Login Providers, SMS, Telephony & Push, Core Business Services, Back-office & Identity DB |
| Pickup and destination input with map, address search in Japanese and English | Rider App, Maps & Geolocation, Core Business Services |
| Fare estimate before booking, including metered fares, fixed/pre-determined fares and surcharges such as late-night or pickup fees | Rider App, Core Business Services, Maps & Geolocation, Live Geo Cache, Core Transactional Store |
| Real-time dispatch matching riders to nearest available taxis | Dispatch & Location Services, Live Geo Cache, Core Transactional Store, Driver App, GKE Regional Clusters |
| Live driver location tracking and ETA for riders | Driver App, Dispatch & Location Services, Live Geo Cache, API Gateway / BFFs, Rider App |
| In-app chat/call between rider and driver with masked phone numbers | Rider App, Driver App, Core Business Services, SMS, Telephony & Push, Core Transactional Store |
| Scheduled/advance reservations | Rider App, Core Business Services, Core Transactional Store, SMS, Telephony & Push |
| Multiple payment methods: credit cards, Apple Pay/Google Pay, QR payments (PayPay, d払い, etc.), IC cards where supported, corporate billing and cash | Rider App, Payment & Invoice Service, Payment Gateways & Wallets, Partner Integration Adapter, Core Transactional Store |
| Digital receipts compliant with Japanese invoice rules (qualified invoice system) | Payment & Invoice Service, Core Transactional Store, Document & Archive Storage |
| Driver app: go online/offline, accept/decline requests, turn-by-turn navigation, earnings view | Driver App, Dispatch & Location Services, Core Business Services, Maps & Geolocation |
| Integration with taxi meters / fleet dispatch systems of partner taxi companies | Partner Integration Adapter, Partner Meters & Dispatch, Event Backbone |
| Ratings, feedback and lost-item reporting | Rider App, Core Business Services, Core Transactional Store, Back-office & Identity DB |
| Ride history and favorite places | Rider App, Core Business Services, Core Transactional Store |
| Push notifications and SMS alerts | Core Business Services, Event Backbone, SMS, Telephony & Push |
| Multilingual UI (Japanese primary, English, Chinese, Korean for tourists) | Rider App, Driver App, Admin/Operator Console, API Gateway / BFFs |
| Admin console for driver onboarding, fleet management, pricing configuration, promotions/coupons, support tickets and analytics | Admin/Operator Console, Keycloak Identity (CIAM), API Gateway / BFFs, Core Business Services, Back-office & Identity DB, Analytics Warehouse |
| Safety features: emergency contact, trip sharing | Rider App, Core Business Services, SMS, Telephony & Push, Admins & Support |
| High availability (target 99.95% or higher) for booking and dispatch paths | Global Load Balancer & CDN, GKE Regional Clusters, Serverless Services, Core Transactional Store, Live Geo Cache |
| Low latency: dispatch matching within a few seconds; location updates every 3-5 seconds | Dispatch & Location Services, Live Geo Cache, GKE Regional Clusters, Driver App, Event Backbone |
| Horizontal scalability to handle peak demand (rush hours, rain, events, New Year) | GKE Regional Clusters, Serverless Services, Core Transactional Store, Live Geo Cache, Event Backbone |
| Disaster recovery across regions given earthquake risk (e.g., Tokyo and Osaka regions), with defined RPO/RTO | Core Transactional Store, Back-office & Identity DB, Document & Archive Storage, Global Load Balancer & CDN, GKE Regional Clusters |
| Data residency in Japan | IAM & Org Policies, Keycloak Identity (CIAM), Core Transactional Store, Encryption Keys, SMS, Telephony & Push |
| Strong security: encryption in transit and at rest, PCI DSS-scoped payment handling via tokenization | Payment Gateways & Wallets, Payment & Invoice Service, Encryption Keys, Data Perimeters, WAF & DDoS Protection |
| Observability: centralized logging, metrics, tracing and alerting | Centralized & Audit Logs, Monitoring & Alerting, Distributed Tracing |
| Mobile apps performant on a range of devices and resilient to poor connectivity | Rider App, Driver App, API Gateway / BFFs, Quality & Load Testing |
| Accessibility support and localization quality | Rider App, Driver App, Admin/Operator Console, Quality & Load Testing |

### 2.5 Key assumptions

- GCP is the selected provider, using only asia-northeast1 (Tokyo, primary) and asia-northeast2 (Osaka, warm standby).
- The Spanner topology is a pre-production decision gate. Option A, a Japan-only dual-region configuration, is the target if verified; otherwise Option B, regional Tokyo plus an Osaka standby, applies. The standard asia1 configuration is rejected because of its Seoul witness replica.
- Keycloak on GKE replaces Identity Platform as the identity service so that identity data stays in Japan, and a Japan-resident SMS and telephony provider is available under a DPA.
- React Native is confirmed for both mobile apps, subject to a Phase 0 spike that validates the PayPay, d払い, IC/NFC and gateway tokenization SDKs.
- Final fare authority rests with the partner meter or the approved fixed-fare calculation. IC card payments are recorded through the meter integration.
- Rollout is phased, starting in Tokyo and then extending to Osaka and Nagoya. Console static assets are served through Cloud CDN, and dynamic rendering stays in Japan regions.

### 2.6 Recommended technology stack

| Layer | Technology | Purpose | Status |
| --- | --- | --- | --- |
| User / application layer | React Native | Rider and driver apps for iOS and Android from one TypeScript monorepo, with native payment and location modules | required |
| User / application layer | Next.js | Role-based admin, operator and support console | required |
| User / application layer | shadcn/ui, Radix UI, Tailwind CSS | Accessible console component library driven by tokens shared with mobile | recommended |
| User / application layer | TanStack Query, Zustand | Server-state caching, offline mutation queueing and high-frequency map state | recommended |
| User / application layer | Keycloak | Japan-hosted identity for customers and staff using OpenID Connect, OAuth 2.0 with PKCE and JWT | required |
| API & application services | NestJS | BFFs and business, payment and invoice microservices | recommended |
| API & application services | Go | Latency-critical dispatch, location ingest and partner adapter | recommended |
| API & application services | REST, OpenAPI, gRPC | Contract-first external APIs, plus internal calls and streaming location ingestion | recommended |
| Data layer | Spanner | System of record for booking, dispatch, payments and invoices | required |
| Data layer | Memorystore | Redis geo-index, offer locks and hot caches | required |
| Data layer | Cloud SQL | Back-office workflows and the Keycloak identity store | recommended |
| Data layer | BigQuery | Analytics and regulatory reporting | required |
| Data layer | Cloud Storage | Invoices, documents and retention-locked archives | required |
| External integrations | Google Maps Platform / Zenrin | Maps, address search, routing and ETA | required |
| External integrations | PayPay, d払い, Apple Pay, Google Pay, Japan PCI DSS PSP | Japanese payment methods and card tokenization | required |
| External integrations | LINE Login, Sign in with Apple, Google | Social login federation | required |
| External integrations | APNs, FCM, Japan SMS/telephony provider | Push notifications, SMS and masked calling | required |
| Cloud infrastructure & networking | GKE | Streaming and latency-critical workloads and Keycloak | required |
| Cloud infrastructure & networking | Cloud Run | Stateless request/response services in both regions | recommended |
| Cloud infrastructure & networking | Cloud Load Balancing, Cloud CDN | Global entry point, regional failover and static asset caching | required |
| Cloud infrastructure & networking | Pub/Sub, Dataflow | Event backbone, streaming ETL and Option B replication | required |
| Cloud infrastructure & networking | VPC | Private networking and controlled egress | required |
| Security | Cloud Armor | WAF, DDoS protection and rate limiting | required |
| Security | IAM | Least privilege, Workload Identity and location Org Policies | required |
| Security | Cloud KMS | CMEK and per-user PII encryption | required |
| Security | Secret Manager | Credential storage and rotation | required |
| Security | VPC Service Controls | Isolation of the PCI and PII projects | required |
| Monitoring & operations | Cloud Monitoring | SLOs, metrics and alerting | required |
| Monitoring & operations | Cloud Logging | Centralized and audit logging pinned to Japan | required |
| Monitoring & operations | Cloud Trace, OpenTelemetry | Distributed tracing (catalogue exception requested) | required |
| Monitoring & operations | Cloud Build, Artifact Registry, Terraform | CI/CD, signed images and infrastructure as code | required |
| Monitoring & operations | k6, Playwright, axe-core, Lighthouse, Jest, OWASP ZAP | Load, end-to-end, accessibility, performance, unit and security testing | recommended |

### 2.7 Security considerations

- Card data never reaches the platform. Gateway SDK tokenization, EMV 3DS and an isolated payment project behind VPC Service Controls target PCI DSS SAQ A or A-EP.
- Identity, SMS OTP and masked-call data are processed in Japan. A cross-border register covers Apple/Google federation, APNs/FCM and maps, and requires APPI sign-off from the client.
- Data access is enforced at object and tenant level: riders, drivers and operators see only their own data. Staff use MFA and just-in-time elevation, and all admin actions are audit-logged.
- CMEK from Japan Cloud KMS keyrings protects all stores. Application-level encryption of PII and per-user keys support APPI deletion through crypto-shredding.
- Cloud Armor applies stricter policies to login and OTP endpoints, with OTP pumping limits. Mobile apps use App Attest and Play Integrity attestation, certificate pinning and server-side GPS plausibility checks.
- Chat retention is limited to 90 days with restricted access, in line with Telecommunications Business Act secrecy rules. Qualified-invoice receipts are kept in write-once storage for 7 years.

### 2.8 Scalability and future enhancements

**Scalability**

- Dispatch and location state is partitioned by city and geo-cell across sharded Memorystore and Go workers on GKE, with HPA driven by connection count and Pub/Sub backlog.
- Locations are written to Redis first and persisted asynchronously through Pub/Sub, so ingest of 30-60k updates/s never blocks on durable storage.
- Spanner processing-unit autoscaling, plus serving rate cards and driver eligibility from cache, absorbs New Year and rain peaks.
- Capacity is pre-scaled on a schedule for rush hours and events, with 30-50% headroom on the dispatch tier and Cloud Run minimum instances on the booking path.
- Before each metro launch, k6 tests run at 2x projected peak along with soak tests. Degraded modes use cached fares and straight-line ETAs if maps or pricing services fail.
- Osaka runs as a reduced-footprint warm standby with reserved quotas and scales out on failover, which is rehearsed in game days twice a year.

**Future enhancements**

- ML demand forecasting and driver repositioning recommendations built on the BigQuery trip history.
- Dynamic pricing models within MLIT fare rules and operator approval.
- Inclusion of 'Japan Ride Share' licensed schemes if regulation and partner operators allow.
- AI-assisted multilingual support chat and automatic translation between riders and drivers.
- More QR wallets, a corporate travel-management integration and expansion to further prefectures.
- Wheelchair-accessible/UD taxi matching and accessibility-aware pickup guidance.

## 3. Solution design

### Recommended architecture

**Style:** Event-driven domain microservices on GCP, active-passive multi-region (Tokyo primary, Osaka warm standby), with a TypeScript monorepo for the clients

React Native rider and driver apps and a Next.js operator/admin console call client-specific BFFs over OpenAPI REST, plus streaming channels for live trip and location events. The edge is a global load balancer with Cloud Armor and CDN. Latency-critical Go services (dispatch, location ingest, ride state, partner adapter) run on regional GKE. NestJS business services (accounts, pricing, payments orchestration, notifications, receipts, support, admin backend) are split between GKE and Cloud Run. Services exchange gRPC internally and publish domain events to Pub/Sub through a transactional outbox. Spanner, in a Japan-only topology chosen at a decision gate (Option A dual-region or Option B regional plus Osaka standby), is the system of record for the booking and dispatch path. Memorystore holds the hot geo-index and caches, and Cloud SQL holds back-office workflows. Change streams feed Dataflow and BigQuery for analytics, and Cloud Storage holds invoices, documents and archives. Identity uses Keycloak hosted in Japan with customer and staff realms. Payments use PSP tokenization and native SDK bridges, so no card data enters the platform. Observability uses OpenTelemetry with Cloud Trace, Logging and Monitoring.

- Client layer: React Native Rider and Driver apps with a native payment adapter (Swift/Kotlin bridges), and the Next.js admin/operator console; shared monorepo packages (OpenAPI client, i18n ja/en/zh/ko, design tokens)
- Edge layer: Cloud DNS, global external Application Load Balancer, Cloud Armor WAF/rate limits, Cloud CDN for static console assets
- Identity layer: Keycloak customer and staff realms on GKE (Tokyo, warm standby in Osaka), OIDC federation for LINE, Apple and Google, Japan-resident SMS OTP, short-lived JWTs
- API/BFF layer: Rider, Driver and Admin BFFs with JWT validation, rate limiting, locale negotiation and WebSocket/streaming endpoints
- Real-time core (Go on GKE): location ingest, dispatch/matching, ride state machine, partner meter/fleet adapter
- Business services (NestJS): account, operator and fleet, pricing/fare, payments and ledger, invoice/receipt, communication (push, SMS, masked calling, chat), ratings and support
- Messaging layer: Pub/Sub event backbone with transactional outbox and idempotent consumers
- Data layer: Spanner (booking/dispatch system of record), Memorystore Redis (geo-index and caches), Cloud SQL (back office), BigQuery with Dataflow (analytics), Cloud Storage (documents, invoices, archives)
- Platform and operations layer: Terraform, Cloud Build, Artifact Registry, Secret Manager, Cloud KMS CMEK, VPC Service Controls, OpenTelemetry with Cloud Trace, Logging and Monitoring, SLO alerting and DR runbooks

### Agents used

- **frontend**: needed for mobile, needed for fullstack
- **uiux**: needed for mobile
- **backend**: needed for mobile, needed for backend, needed for fullstack
- **database**: needed for backend, needed for fullstack
- **cloud**: needed for cloud, hosting/infrastructure is in scope
- **security**: needed for mobile, needed for backend, needed for cloud, needed for fullstack
- **performance**: needed for mobile, needed for backend, needed for cloud, needed for fullstack

### Components

| Component | Responsibility | From |
| --- | --- | --- |
| Rider App (React Native) | Login (SMS, Apple, Google, LINE); JA/EN place search; fare estimate; booking and reservations; live tracking with ETA; masked chat and call; payments UI through the payment-adapter native modules; receipts; history and favorites; SOS and trip share; ratings. | frontend |
| Driver App (React Native) | Online/offline toggle; accept/decline with countdown; handoff to navigation; native-module background location every 3–5 s; earnings; trip state; offline queueing and reconnect. | frontend |
| Payment adapter (native modules) | A single TypeScript interface (startPayment, tokenizeCard, handleReturn) backed by thin Swift and Kotlin bridges. The bridges wrap the PayPay and d払い SDKs or app-switch flows, the gateway card tokenization SDK, the Apple Pay/Google Pay sheets and IC/NFC where supported. Raw card data never reaches JS code. | frontend |
| Admin/Operator Console (Next.js) | Role-scoped screens for driver onboarding, fleet management, pricing and surcharge configuration, promotions, support tickets, a live operations map and analytics. | frontend |
| Shared packages (monorepo) | Shared by all apps: OpenAPI-generated TypeScript client, domain types, JPY/era/Asia-Tokyo formatting, ICU i18n catalogs (ja, en, zh-Hans, zh-Hant, ko), validation schemas and design tokens. | frontend |
| Real-time layer | WebSocket client for location and trip events. Feeds TanStack Query caches and Zustand map stores, uses throttled rendering and marker interpolation, and reconnects with backoff, falling back to polling. | frontend |
| Design system (aligned with UI/UX) | Defines tokens once in the shared package. On mobile, it is a React Native component library (replacing the previously assumed Flutter design system) with accessible patterns and CJK typography. On web, it uses shadcn/ui on Radix UI with Tailwind, consuming the same tokens. | frontend |
| Rider app IA | Bottom tabs: Home (map and booking), Activity (ride history, reservations, receipts), Payment (wallet, QR pay, corporate profile), Account (profile, favourite places, language, safety contacts, help). The booking flow is a stack of map overlay bottom sheets so that riders do not lose map context. | uiux |
| Booking flow screens | 1. Pickup confirmation with a draggable pin, suggested pickup points and Japanese building/landmark names. 2. Destination search (Japanese and romaji, plus favourites and recents). 3. Fare estimate sheet showing metered range versus fixed fare and itemised surcharges (late-night, pickup, reservation). 4. Payment method and coupon selection. 5. Matching state with cancel. 6. Driver assigned: car plate, taxi company, ETA, chat/call. 7. In-trip view with share-trip and SOS. 8. Completion screen with a qualified-invoice receipt, rating and tip-free feedback. | uiux |
| Scheduled reservation flow | Date and time picker in the JST calendar format, a confirmation screen with operator policy and cancellation fees, and reminders via push and SMS. Upcoming reservations are pinned at the top of Home. | uiux |
| Rider safety and support | An always-visible safety shield during trips (emergency 110/119 call, trip sharing link, emergency contact). The help centre offers lost-item reporting from a specific ride in history and support ticket chat. | uiux |
| Driver app IA | A single primary screen consisting of a map, a large Online/Offline toggle and a status bar. Incoming requests appear as a full-screen card with pickup distance, fare type and a 15s countdown, using large Accept/Decline buttons. Remaining tabs are Trip (navigation handoff, rider chat, arrived/start/end) and Earnings (daily/weekly figures and trip list). The layout supports dark mode and landscape mounting. | uiux |
| Operator/Admin web console | Role-based side navigation: Dashboard (live map of fleet supply and demand plus KPIs), Drivers (onboarding pipeline, document verification, status), Fleet/Vehicles, Rides (search and trip replay), Pricing (fare tables per prefecture/zone, surcharge rules with preview), Promotions/Coupons, Support tickets (queue with ride context panel), Analytics, and Settings/Users (RBAC). Data-dense tables offer filters and CSV export, and the console is desktop-first with tablet support. | uiux |
| Localization and content layer | Japanese is the source locale, with en, zh-Hans, zh-Hant and ko. It covers locale-aware formatting for ¥ amounts, dates and address order (prefecture to building), a font stack that supports CJK, and copy length testing. Language is switchable in-app independently of the OS setting, which serves tourists. | uiux |
| Design system | Shared tokens (colour, typography, spacing) across mobile and web. Accessible colour contrast, minimum touch targets of 44pt/48dp, and component states for loading, offline, error and empty. | uiux |
| API Gateway / BFFs (Rider, Driver, Admin) | Client-specific REST endpoints with OpenAPI contracts. Handles JWT validation, rate limiting, request shaping, locale negotiation (ja/en/zh/ko) and API versioning. Exposes WebSocket/streaming endpoints for live trip state. | backend |
| Identity & Account Service | Rider and driver profiles, phone/SMS/email/Apple/Google/LINE login via Identity Platform, favorites, emergency contacts, APPI consent records and data-subject requests. | backend |
| Operator & Fleet Service | Taxi companies, vehicles, driver onboarding (licence and 2-shu menkyo checks), shifts, operator-scoped RBAC, and MLIT-required records. | backend |
| Ride Request Service | Trip lifecycle state machine (requested→matched→arriving→on_trip→completed/cancelled), scheduled reservations, idempotent booking, and trip-sharing links. | backend |
| Dispatch / Matching Service (Go) | Geo-queries nearby available drivers from Memorystore. Ranks candidates by ETA, issues offers with timeouts and fallback rounds, and targets a match within 3s. Partitioned by city/geo-cell. | backend |
| Location Tracking Service (Go) | Ingests driver GPS every 3-5s over gRPC streams. Updates the geo-index and fans out positions and ETA to the rider. Publishes sampled tracks to Pub/Sub for trip records. | backend |
| Pricing / Fare Service | Metered fare tables per operator and region, fixed/pre-determined fares (事前確定運賃) computed from the maps route, late-night, pickup and reservation surcharges, coupons, and versioned admin-configured rate cards. | backend |
| Payment Service | PSP integration for cards with 3-D Secure via tokens, Apple Pay/Google Pay, PayPay/d払い QR flows, corporate invoicing and cash recording. Covers authorize/capture/refund, idempotency keys, webhook reconciliation and a double-entry ledger. | backend |
| Invoice & Receipt Service | Generates qualified-invoice-compliant receipts including the operator registration number (T-number), tax rate and consumption tax amount. Produces PDFs in Cloud Storage and corporate monthly statements. | backend |
| Communication Service | Masked calling and in-app chat via a telephony partner, push notifications (APNs/FCM), and SMS. Chat is retained under a defined policy that considers the Telecommunications Business Act. | backend |
| Ratings & Support Service | Ratings, feedback, lost-item reports, support tickets, and SOS escalation to support staff. | backend |
| Partner Integration Adapter | Anti-corruption layer for partner taxi meters and legacy fleet dispatch systems, supporting REST/webhook/file or vendor protocols. Normalizes meter fares and vehicle status into platform events. | backend |
| Event Backbone & Outbox Relay | Publishes domain events (TripCompleted, PaymentCaptured, etc.) to Pub/Sub with at-least-once delivery. Consumers are idempotent. | backend |
| Core Transactional Store (Spanner, multi-region asia1: read-write Tokyo + Osaka) | System of record for the booking/dispatch path. Owns User, RiderProfile, FavoritePlace, EmergencyContact, Driver, DriverEligibility, Vehicle, FleetOperator (status, invoice registration number), PartnerMeterMapping, RateCard and SurchargeRule versions (draft and published), FixedFareZone, ActivePromotion and CouponRedemption, Ride, RideEvent, Reservation, DispatchAssignment, FareQuote, Payment (tokens only), LedgerEntry, Invoice, Rating, ChatMessage (TTL) and TripTrace. Provides externally consistent transactions for assignment and payment capture. | database |
| Live Location & Hot Cache (Memorystore for Redis Cluster, Tokyo primary + Osaka warm standby) | Holds driver GEO sets per city/H3 cell, online/busy status with TTL, dispatch offer locks, ETA cache, and read-through caches of published rate cards, driver eligibility and operator status. The cache is ephemeral and every entry can be rebuilt from Spanner or from driver re-pings. | database |
| Back-office Store (Cloud SQL for PostgreSQL, regional HA Tokyo + cross-region replica Osaka) | Holds only off-path workflows: support tickets, lost-item cases, driver onboarding document review queue, promotion campaign drafting and approval, and admin console preferences. Outcomes are published into Spanner through the owning service APIs, for example 'driver approved' or 'campaign activated'. No booking or dispatch read touches Cloud SQL. | database |
| Analytics Warehouse (BigQuery, asia-northeast1, daily copy to asia-northeast2) | Holds trip, payment and sampled trace facts fed by Spanner change streams through Pub/Sub and Dataflow. Serves operator dashboards, MLIT and tax reporting, and future forecasting. Datasets are partitioned by date and clustered by city and operator. | database |
| Object Storage (Cloud Storage, dual-region Tokyo/Osaka with turbo replication) | Holds invoice PDFs, driver license and vehicle documents (CMEK), chat attachments, and archives of trip traces and audit logs under retention locks. | database |
| Event/CDC Pipeline (Spanner change streams + Pub/Sub + Dataflow) | Propagates changes to BigQuery, notifications, read models and Redis cache invalidation without dual writes. | database |
| Global edge | Cloud DNS, the global external Application Load Balancer, Cloud Armor (WAF, DDoS protection, rate limiting) and Cloud CDN for static assets. Health-checked backends in Tokyo and Osaka support regional failover. | cloud |
| GKE regional clusters (Tokyo primary, Osaka warm standby) | Run dispatch/matching, real-time location ingest (gRPC/WebSocket), the ride state machine and partner meter/fleet integration. Clusters are regional across three zones with Workload Identity, the cluster autoscaler and HPA on custom metrics. Osaka runs at a reduced footprint and scales out on failover. The OpenTelemetry Collector runs as a DaemonSet/gateway and exports to Cloud Trace. | cloud |
| Cloud Run services | Run account, pricing/fare, payments orchestration (tokenized, no PAN), notifications, ratings, support, receipts/invoices and the admin backend. Services are deployed in both regions behind serverless NEGs, with minimum instances on the booking path. The built-in Cloud Trace integration is combined with OpenTelemetry SDK spans. | cloud |
| Spanner (decision gate: Option A Japan dual-region or Option B regional Tokyo + Osaka standby) | System of record for users, rides, reservations, payments ledger and invoices. Option A: Tokyo+Osaka read-write replicas with no replica outside Japan, giving RPO≈0 and RTO of 30 min or less. Option B: a regional asia-northeast1 instance (99.99% SLA). Change streams feed Dataflow, which writes to a smaller regional standby instance in asia-northeast2. Scheduled backups are copied to Osaka every 4 h. RPO is 1 min or less via the stream, or 4 h or less via backups as the last resort. RTO is 60 min or less. | cloud |
| Memorystore (Redis, per region) | Holds the live driver geo-index, availability, sessions and rate limits on the Standard/HA tier. This state is ephemeral and rebuilt from driver pings within about 10 s after failover. | cloud |
| Pub/Sub | Event backbone for location fan-out, ride lifecycle, notifications and the analytics feed. The message storage policy is restricted to asia-northeast1/2. The W3C traceparent is carried in message attributes. | cloud |
| Cloud SQL (PostgreSQL, HA) | Back-office data: console, promotions, onboarding metadata and support tickets. Runs regional HA with a cross-region read replica in Osaka (RPO of 5 min or less). | cloud |
| Data and analytics | Dataflow streams Pub/Sub data into BigQuery (asia-northeast1) for reporting. A dual-region Tokyo+Osaka Cloud Storage bucket holds receipts, documents and backup exports. | cloud |
| Networking | Shared VPC, private GKE nodes, Private Service Connect and private IP for managed services. Cloud NAT with static IPs handles egress to gateways, maps and LINE. VPC Service Controls protect the PCI and PII projects. | cloud |
| Observability (logs, metrics, traces, alerts) | Cloud Logging uses log buckets pinned to Japan, and Cloud Monitoring provides SLO dashboards, burn-rate alerts and exemplars. OpenTelemetry SDKs (Go, NestJS) and the Collector export spans to Cloud Trace. Trace IDs are injected into structured logs (logging.googleapis.com/trace) for one-click correlation between logs, metrics and traces. | cloud |
| Ops and security | Secret Manager, Cloud KMS CMEK for all stores, least-privilege IAM per service account, and Artifact Registry with Cloud Build. Terraform manages all infrastructure, including the Spanner config selected at the decision gate. | cloud |
| Customer Identity (CIAM) - Keycloak, Japan-hosted | Keycloak runs in a dedicated 'customers' realm on private GKE in asia-northeast1, with a warm standby in asia-northeast2. It handles phone/SMS OTP through a custom authenticator SPI calling a Japan-resident SMS provider. It also supports email, Sign in with Apple, Google and LINE Login as OIDC identity brokers. It issues JWT access tokens of about 15 minutes with refresh-token rotation, signed with keys stored in Cloud KMS. User records (phone, email, federated subject IDs) live only in Japan-region Cloud SQL with CMEK. | security |
| SMS OTP & Telephony Residency Control | OTP SMS and masked calling go through a Japanese carrier or aggregator contracted for in-Japan processing and log storage, under an APPI Art. 25 entrustment/DPA. Data sent is limited to the phone number plus the OTP or a proxy number. OTP sends are limited per number, device and IP, with App Check-style attestation and SMS-pumping detection. A generic global SMS service is used only after an APPI Art. 28 transfer assessment and client sign-off. | security |
| Workforce / Admin Identity | A separate Keycloak 'staff' realm, or federation to the corporate IdP over OIDC, provides SSO for admin, operator and support consoles. MFA is mandatory, using WebAuthn or TOTP. Access is role-based and tenant-scoped, so a fleet operator sees only its own drivers and trips. Support staff get just-in-time elevation, and every action is audited. | security |
| API Authorization Layer | Validates JWTs at the gateway and in each service, checking issuer, audience, expiry and scopes against cached Keycloak JWKS. Enforces object-level authorization on trips, receipts and chats. Applies per-user and per-device rate limits. Validation is stateless, so dispatch and location keep working even if Keycloak is briefly degraded. | security |
| Service-to-Service Security | Each service runs under its own Workload Identity service account. Services talk over mTLS with authenticated gRPC. Partner taxi-meter and fleet-dispatch systems connect through mTLS or OAuth 2.0 client-credentials with IP allowlisting. | security |
| Payment Tokenization Boundary | Card entry happens only in the gateway SDK or hosted fields; the platform stores only tokens and the last 4 digits. EMV 3DS 2.0 is applied in line with the Installment Sales Act security guidelines. QR wallets (PayPay, d払い) use signed webhooks with signature verification and idempotency keys. | security |
| Data Protection & Key Management | Applies CMEK from Japan-region Cloud KMS keyrings to Cloud SQL/AlloyDB, Spanner, Memorystore, Cloud Storage, BigQuery and the Keycloak database. Adds application-level envelope encryption for phone numbers, emails, licence images and emergency contacts. Keys are rotated on a schedule, and per-user keys allow crypto-shredding on deletion requests. | security |
| Data Residency Governance | Enforces the gcp.resourceLocations Org Policy for asia-northeast1/2. Maintains a register of global or non-regional services and third-party processors that the policy does not cover, covering what personal data each receives and where it goes. Each entry is assessed under APPI Art. 28 and either removed, minimised, or accepted in writing by the client. | security |
| Secrets Management | Keeps payment, map, SMS, LINE, Apple/Google OIDC client secrets, push credentials and Keycloak admin credentials in Secret Manager with Japan-only replication. Secrets are accessed through Workload Identity. None are stored in code, images or mobile binaries. Rotation is automatic and CI scans for leaked secrets. | security |
| Edge Protection | Cloud Armor sits in front of Cloud Load Balancing with OWASP CRS rules, bot and abuse rate limits and adaptive DDoS protection. Stricter policies apply to the Keycloak login and OTP endpoints. The Keycloak admin console is never exposed publicly. TLS 1.2+ is used throughout. | security |
| Network Isolation | Uses private GKE nodes and private-IP databases, with VPC Service Controls around data and identity projects. Egress goes through Cloud NAT to allowlisted payment, SMS, LINE, Apple and Google endpoints only. | security |
| Mobile App Security | Tokens are stored in Keychain or Keystore, using PKCE authorization code flow against Keycloak. Play Integrity and App Attest provide app attestation. Certificates are pinned. Driver apps check for root or jailbreak. Apps never log PII and code is obfuscated. | security |
| Privacy & Communications Controls | Covers APPI consent and purpose notices, including disclosure of any foreign processors. Handles data-subject requests across Keycloak and the service databases. Sets retention limits on location traces and pseudonymises analytics data. Masked calling is used, and chat access and retention follow the secrecy-of-communications rules in the Telecommunications Business Act. | security |
| Security Monitoring & Audit | Collects Cloud Audit Logs, Keycloak admin and login events, and application security events in Japan-region Cloud Logging buckets. Logs are retention-locked. Cloud Monitoring alerts on auth anomalies, OTP spikes, fraud signals and privileged access. | security |
| Location Ingest Service | Receives driver GPS every 3-5s over gRPC streams and batches writes into the Redis GEO index. It publishes deltas to Pub/Sub for history and analytics without blocking on durable storage. Target: 50k updates/s with headroom. | performance |
| Geo Index Cache (Memorystore) | Holds the hot driver location and status in sharded Redis GEO sets, keyed by city/geohash cell. Supports nearest-driver queries with sub-10ms p99 and TTL eviction of stale drivers. | performance |
| Dispatch Matcher | Runs stateless matching workers, partitioned by region cell. It queries the geo cache and scores candidates on ETA, rating and acceptance probability, then offers rides in parallel waves. Target: p95 match under 3s, with a 15s overall timeout before re-dispatch. | performance |
| Rider Tracking Fan-out | Pushes the assigned driver's location and ETA to the rider over a server-streaming connection. Falls back to adaptive polling on poor networks. Clients interpolate positions to smooth the map. | performance |
| Fare/ETA Cache | Caches fare tables, surcharge rules and route/ETA results (short TTL, rounded origin/destination) to cut Maps API latency and cost on estimate requests. | performance |
| Admin Console Delivery | Serves the Next.js console via Cloud CDN with code-splitting, a route-level JS budget of 200KB gzip or less, and lazy-loaded maps and charts. | performance |
| Load & Performance Test Harness | Runs k6 scenarios for peak dispatch and location load and Lighthouse budgets for the console in CI, and gates releases on the SLOs. | performance |

### Recommended technology stack

| Category | Choice | Rationale | Alternatives | From |
| --- | --- | --- | --- | --- |
| frontend_framework | Next.js | The App Router's route groups and middleware suit role-based console areas and auth redirects, and its i18n routing and code-splitting fit a multilingual console. It uses the same React skills as the mobile apps. | React, Angular, Vue | frontend, uiux |
| styling_ui | shadcn/ui | Components are owned in our codebase and customizable for dense tables and forms, built on Radix UI and Tailwind CSS. |  | frontend |
| styling_ui | Radix UI | Accessible primitives handle focus, ARIA and keyboard behaviour for WCAG 2.2 AA. |  | frontend |
| styling_ui | Tailwind CSS | Token-driven utilities whose values are shared with the React Native theme, giving consistent spacing and contrast-checked colors across web and mobile. | CSS Modules | frontend |
| styling_ui | Material UI | Mature data grid, form and date-picker components with built-in accessibility and theming, which suits a data-dense admin console and keeps parity with Material patterns on Android. |  | uiux |
| state_data_fetching | TanStack Query | Server-state caching, retries and offline mutation persistence work in both React Native and Next.js. | Redux Toolkit | frontend, uiux |
| state_data_fetching | Zustand | A lightweight store with selector-based re-rendering suits high-frequency map and trip-phase state. | Redux Toolkit | frontend |
| mobile | React Native | Confirmed framework for both apps, aligned with UI/UX. It shares TypeScript domain, OpenAPI client, i18n and tokens with the Next.js console and the NestJS backend, so one language and skill set covers the whole stack. Native modules cover background location, payment SDKs and NFC. The New Architecture and Hermes engine reduce the performance gap on low-end devices. | Kotlin, Swift | frontend |
| mobile | Flutter | A single codebase for the Rider and Driver apps on iOS and Android, with consistent custom map/bottom-sheet UI, strong performance on low-end Android devices and mature i18n (ARB) support for 4+ languages. | Swift, Kotlin | uiux |
| backend_runtime | Go | Low-latency, high-concurrency handling for dispatch and tens of thousands of location updates per second, with a small memory footprint. | Java, Spring Boot, Node.js | backend, performance |
| backend_runtime | NestJS | Structured modular TypeScript framework for CRUD-heavy business services and BFFs. Shares types with the admin console. | Spring Boot, FastAPI | backend |
| api_style | OpenAPI | A contract-first spec generates typed clients shared by all three frontends and the NestJS backend. | GraphQL | frontend, backend |
| api_style | REST | Simple, cacheable, and widely tooled for mobile and admin clients. | GraphQL | backend |
| api_style | gRPC | Efficient typed internal service calls, plus bidirectional streaming for driver location ingestion. |  | backend, performance |
| database | Memorystore | Redis geo-index for driver availability and positions, offer locks and session state, with sub-millisecond reads. | Redis, Firestore | backend, database, cloud, performance |
| database | Spanner | Multi-region strong consistency (Tokyo/Osaka) for trips, payments and the ledger. Supports DR with near-zero RPO. | AlloyDB | backend, database, cloud, performance |
| database | Cloud SQL | PostgreSQL for less critical bounded contexts: accounts, fleet, support and pricing config. | AlloyDB, PostgreSQL | backend, database, cloud, security |
| database | BigQuery | A serverless, region-pinned warehouse that keeps analytics and regulatory reporting off OLTP. | AlloyDB, Dataproc | database, cloud |
| auth | Identity Platform | Managed phone/SMS, Apple and Google sign-in, with OIDC provider support for LINE Login. Scales to millions of riders. | Auth0, Firebase Authentication | backend |
| auth | OpenID Connect | Standard federation for LINE login and for operator SSO. |  | backend, security |
| auth | JWT | Short-lived access tokens validated statelessly at the gateway and in services. Claims carry role and operator_id. |  | backend, security |
| auth | Keycloak | Workforce identity for admins and operators with fine-grained RBAC, MFA and per-operator realms/groups. | Auth0, Identity Platform (only with a documented APPI cross-border transfer and client sign-off), Auth0 (only if a Japan-region tenant and data location are confirmed in the contract) | backend, security |
| auth | OAuth 2.0 | Authorization code flow with PKCE for mobile and web, plus client-credentials for partner fleet and meter integrations. |  | security |
| gcp_compute_network | GKE | Long-lived gRPC/WebSocket streams, fine-grained autoscaling for dispatch and location, and regional clusters in Tokyo and Osaka. | Compute Engine | backend, cloud, security, performance |
| gcp_compute_network | Cloud Run | Low-ops autoscaling for bursty request/response services, deployable in both regions behind the global load balancer. | App Engine | cloud |
| gcp_compute_network | Cloud Load Balancing | Single anycast IP with health-checked Tokyo/Osaka failover, TLS termination, HTTP/2 and WebSocket support. It propagates trace headers. | Cloud DNS | cloud |
| gcp_compute_network | Cloud Armor | Edge WAF, DDoS protection and per-client rate limiting on the login and booking endpoints. |  | cloud, security |
| gcp_compute_network | Cloud CDN | Caches console assets and static config, reducing origin load and latency. | Firebase Hosting | cloud, performance |
| gcp_compute_network | VPC | Private networking and segmentation for the PCI and PII workloads. | Cloud DNS | cloud, security |
| gcp_data_messaging | Pub/Sub | Decoupled async events for notifications, receipts, analytics and partner sync, with retry and dead-letter queues. |  | backend, database, cloud, performance |
| gcp_data_messaging | Cloud Storage | Dual-region storage with turbo replication (15-minute RPO), lifecycle tiering and retention locks for 7-year invoice retention. | Firestore | database, cloud |
| gcp_data_messaging | Dataflow | Streaming ETL into BigQuery. Under Option B it also runs the Spanner change-stream replication to the Osaka standby. | Dataproc | cloud |
| gcp_ops_security | Secret Manager | Stores PSP, telephony and maps API keys with rotation and IAM-scoped access. |  | backend, cloud, security |
| gcp_ops_security | Cloud KMS | CMEK on all stores plus per-user keys for application-level PII encryption, which enables APPI crypto-shredding. |  | database, cloud, security |
| gcp_ops_security | Cloud Monitoring | SLOs (booking availability, dispatch p95 under 3 s), burn-rate alerting and exemplars that link latency metrics to Cloud Trace spans. |  | cloud, performance |
| gcp_ops_security | Cloud Logging | Centralized logs pinned to Japan, with structured logs carrying trace and span IDs for correlation. |  | cloud, security |
| gcp_ops_security | IAM | Least-privilege per-service accounts, Workload Identity, and Org Policies (resourceLocations restricted to asia-northeast1/2). | Keycloak | cloud, security |
| gcp_ops_security | Cloud Build | Builds images and progressively deploys them per region. |  | cloud |
| gcp_ops_security | Artifact Registry | Regional Japan registry with vulnerability scanning and signed-image deploy gating, including for Keycloak images. |  | security |
| hosting_static | Firebase Hosting | Serves console static assets only. Dynamic rendering stays on in-region compute chosen by the cloud agent, to respect Japan data residency. | Vercel, Netlify | frontend |
| devops | Terraform | Identical, reproducible Tokyo and Osaka stacks, including the Spanner config and the Org Policies. | Kubernetes, GitHub Actions | cloud, security |
| testing_quality | Playwright | Console end-to-end tests across browsers, run per locale and with axe-core scans. |  | frontend, uiux |
| testing_quality | axe-core | WCAG 2.2 AA checks in CI that fail the build on serious violations. |  | frontend, uiux |
| testing_quality | Jest | Unit and component tests for React Native, the shared packages and the payment-adapter JS layer, with native modules mocked. | Vitest | frontend |
| testing_quality | Lighthouse | Performance and accessibility budgets for console pages. |  | frontend, performance |
| testing_quality | k6 | Load-tests dispatch and location paths against peak scenarios (rain, New Year). |  | backend, performance |
| testing_quality | OWASP ZAP | DAST in CI against the APIs, admin console and Keycloak login flows. |  | security |

## 4. Resources and estimate

### Required human resources

| Role | FTE | Seniority | Responsibilities | Phases |
| --- | --- | --- | --- | --- |
| Project / delivery manager | 1 | lead | Programme plan, multi-team coordination, vendor and partner-operator contracts timeline, risk and decision-gate tracking, stakeholder reporting, release and launch coordination. | Programme management & architecture governance, Discovery, design reconciliation & decision gates, Tokyo pilot launch & hypercare, Osaka & Nagoya rollout with DR validation |
| Solution architect | 1 | lead | Resolve the open review conflicts (identity, data ownership, Spanner topology, compute placement, real-time protocol, IC flow). Own the architecture decision records and service contracts, review NFR compliance and lead DR design. | Programme management & architecture governance, Discovery, design reconciliation & decision gates, Technical spikes & decision-gate validation, Backend core services build |
| Product owner / business analyst (Japan taxi domain) | 1 | senior | Backlog, fare rules (metered, fixed, surcharges per prefecture), MLIT and operator requirements, partner-operator onboarding requirements, acceptance criteria and UAT with taxi companies. | Discovery, design reconciliation & decision gates, Mobile apps build, Admin/operator console build, Tokyo pilot launch & hypercare |
| UI/UX designer | 2 | senior | Rider, driver and console IA and flows. React Native component library spec from shared tokens, accessibility (WCAG 2.2 AA, VoiceOver/TalkBack), CJK typography and usability testing with locals and tourists. | Discovery, design reconciliation & decision gates, Mobile apps build, Admin/operator console build |
| Mobile developer (React Native) | 5 | senior | Rider and driver apps, real-time map layer, offline queueing, background location, i18n, React Navigation deep links, performance profiling on low-end Android, app store releases. | Technical spikes & decision-gate validation, Mobile apps build, Tokyo pilot launch & hypercare |
| Native mobile engineer (Swift/Kotlin) | 1 | senior | Payment adapter native bridges (PayPay, d払い, card tokenization SDK, Apple Pay/Google Pay, IC/NFC feasibility), background location modules, App Attest and Play Integrity. | Technical spikes & decision-gate validation, Mobile apps build, Payments, receipts & partner integrations |
| Frontend web developer (Next.js) | 2 | mid | Admin/operator console: role-scoped route groups, live operations map, pricing editor with diff preview, onboarding, support, analytics views, Playwright and axe-core tests. | Admin/operator console build |
| Backend developer (Go) | 4 | senior | Location ingest, dispatch/matching, ride state machine, partner meter adapter, gRPC streaming, Redis geo sharding, Spanner assignment transactions. | Backend core services build, Testing, performance & DR validation, Tokyo pilot launch & hypercare |
| Backend developer (NestJS) | 6 | mid | BFFs, account, operator/fleet, pricing/fare, notifications, ratings/support, invoice/receipt, admin backend, outbox relay, OpenAPI contracts. | Backend core services build, Testing, performance & DR validation, Tokyo pilot launch & hypercare |
| Integration engineer (payments & partner systems) | 2 | senior | PSP integration (3-D Secure, authorize/capture/refund, webhooks, reconciliation), QR wallet flows, corporate billing, masked calling/SMS provider, LINE/Apple/Google federation, partner taxi meter and fleet dispatch connectors. | Technical spikes & decision-gate validation, Payments, receipts & partner integrations |
| Data engineer | 1.5 | senior | Spanner schema, keys and indexes, change streams, Dataflow pipelines to BigQuery and (Option B) the Osaka standby, Cloud SQL back-office schema, MLIT and tax reporting datasets, retention and crypto-shredding. | Platform foundation & environments, Backend core services build, Data, analytics & reporting |
| DevOps / SRE engineer (GCP) | 3 | senior | Terraform landing zone and Org Policies, GKE and Cloud Run in Tokyo and Osaka, CI/CD with Cloud Build, observability with OpenTelemetry, SLOs and alerting, autoscaling and pre-scaling, DR runbooks and game days, on-call setup. | Platform foundation & environments, Testing, performance & DR validation, Tokyo pilot launch & hypercare, Osaka & Nagoya rollout with DR validation |
| Security engineer | 1.5 | senior | Keycloak CIAM and staff realms, KMS/CMEK, VPC Service Controls, Cloud Armor, PCI SAQ scoping, threat modelling, OWASP ZAP and API fuzzing, data residency register, breach runbook. | Discovery, design reconciliation & decision gates, Platform foundation & environments, Security, compliance & localization |
| QA engineer (automation & performance) | 4 | mid | Test strategy, API contract tests, mobile E2E on a device farm, console E2E, k6 peak and soak tests, localization and accessibility testing, payment and DR scenario testing. | Testing, performance & DR validation, Tokyo pilot launch & hypercare |
| Localization coordinator | 0.5 | mid | Manage ja/en/zh-Hans/zh-Hant/ko catalogs, professional translation and review, pseudo-localization and per-locale visual checks. | Security, compliance & localization |
| Legal / compliance advisor (Japan) | 0.3 | senior | APPI cross-border assessments, Spanner and identity residency sign-off, Road Transportation Act/MLIT, Telecommunications Business Act, qualified invoice rules, PSP and telephony DPAs. | Discovery, design reconciliation & decision gates, Security, compliance & localization |

**Team size:** 35.8 FTE across 16 roles.

### Required AI and technical resources

| Type | Resource | Purpose | Sizing |
| --- | --- | --- | --- |
| cloud compute | GKE (regional clusters) | Run the Go real-time services (dispatch, location ingest, ride state, partner adapter), Keycloak and the OpenTelemetry Collector | Tokyo regional, 3 zones: system pool plus a real-time pool of about 6–20 n2-standard-8 nodes with HPA and scheduled pre-scaling. Osaka warm standby at about 25% footprint. Smaller clusters for dev and staging |
| cloud compute | Cloud Run | Stateless NestJS business services and the admin backend in both regions behind serverless NEGs | About 10 services, 1–2 vCPU / 1–2 GB each; minimum 2–3 instances on booking-path services in Tokyo and minimum 1 in Osaka |
| cloud compute | Dataflow | Spanner change streams and Pub/Sub into BigQuery; under Option B, replication to the Osaka standby | 2–3 streaming jobs with autoscaling, 2–10 workers each |
| cloud storage | Cloud Storage | Invoice PDFs (7-year retention lock), driver and vehicle documents (CMEK), trace and audit archives, backups | Dual-region Tokyo/Osaka with turbo replication; about 1–10 TB growing, lifecycle tiering |
| database | Spanner | System of record for accounts, drivers, fleet, rate cards, rides, reservations, payments ledger and invoices | Prod starts at about 2,000–3,000 processing units with autoscaling. Japan-only topology chosen at the gate: Option A dual-region, or Option B regional Tokyo plus an Osaka standby of about 1,000 PU. Dev/staging at 100–500 PU |
| database | Memorystore (Redis Cluster) | Driver geo-index per city/H3 cell, offer locks, ETA, rate card and eligibility caches, sessions and rate limits | Tokyo HA cluster of about 3–6 shards with replicas (about 30–60 GB total). Osaka standby cluster at a smaller size |
| database | Cloud SQL for PostgreSQL | Back-office workflows (support tickets, lost items, onboarding review, campaign drafts) and the Keycloak identity store | 2 HA instances in Tokyo (back office: 4 vCPU/16 GB; Keycloak: 4–8 vCPU/16–32 GB), each with an Osaka cross-region replica |
| database | BigQuery | Analytics, operator dashboards, MLIT and tax reporting | asia-northeast1 dataset with a daily copy to asia-northeast2, partitioned by date; about 1–5 TB in year 1, on-demand or small reservation |
| dev tooling | Terraform, Cloud Build, Artifact Registry | Infrastructure as code for identical Tokyo/Osaka stacks, CI/CD and progressive per-region deploys, signed and scanned images | Monorepo pipelines for about 15 deployables plus 2 mobile apps; regional registry in Japan |
| dev tooling | Mobile build and distribution (Apple Developer Program, Google Play Console, TestFlight / internal testing tracks) | Build, sign and distribute rider and driver apps | 2 apps × 2 stores, internal, beta and production tracks |
| environment | Environments | Separate projects for development, integration, pre-production and DR rehearsal | dev + staging + prod (Tokyo) + DR (Osaka); staging mirrors prod topology at reduced scale |
| hosting | Cloud Load Balancing, Cloud Armor, Cloud CDN, Cloud DNS | Global anycast entry with Tokyo/Osaka failover, WAF, DDoS and rate limits, static console asset caching | 1 global external ALB, Cloud Armor Enterprise or standard policies on login, OTP and booking, CDN for console assets |
| hosting | Firebase Hosting | Static console assets as proposed by frontend (overlaps with Cloud CDN; to be confirmed during design reconciliation) | Static assets only; no dynamic rendering or PII |
| monitoring | Cloud Logging, Cloud Monitoring, Cloud Trace with OpenTelemetry | Centralized logs pinned to Japan, SLO dashboards and burn-rate alerts, distributed tracing with trace/log correlation | Japan log buckets, location pings excluded; trace sampling 10% booking, ≤1% location, 100% errors and slow requests |
| other | Pub/Sub | Domain event backbone, location fan-out and history, notification and analytics feeds | Message storage limited to asia-northeast1/2; about 30–60k msgs/s peak (sampled location plus trip events) |
| other | VPC, Cloud NAT, Private Service Connect, VPC Service Controls | Private networking, egress allowlisting and perimeters around PCI and PII projects | Shared VPC per environment, static NAT IPs per region, perimeters for the payments and identity/data projects |
| other | Keycloak | Japan-hosted CIAM (customers realm) and workforce SSO (staff realm, MFA) | 3+ replicas in Tokyo with distributed cache and 2 in Osaka standby; sized for login peaks verified by k6 |
| other | Cloud KMS and Secret Manager | CMEK for all stores, per-user keys for crypto-shredding, JWT signing keys and integration secrets | Japan keyrings, per-environment keys, Japan-only secret replication |
| other | Professional translation services | Translation and review for ja/en/zh-Hans/zh-Hant/ko UI, legal and receipt texts | About 15–25k source strings across apps and console, plus ongoing updates |
| testing | k6 | Load and soak tests for dispatch, location ingest and login at 2x projected peak | Distributed load generators of about 60k location updates/s and 5k ride requests/min, 4-hour soak runs before each metro launch |
| testing | Playwright, axe-core, Lighthouse, Jest | Console E2E per locale, WCAG 2.2 AA checks, performance budgets, unit and component tests for apps and shared packages | Run in CI on every PR; nightly full locale matrix |
| testing | OWASP ZAP | DAST against the APIs, console and Keycloak login flows | Weekly in staging plus pre-release scans |
| testing | Mobile device farm (e.g., Firebase Test Lab or equivalent) | E2E and performance profiling on reference low-end and mid-range Android and iOS devices | About 15–25 device models, nightly runs |
| third party service | Google Maps Platform or Zenrin | Maps, Japanese address search (kanji/kana/romaji), routing and ETA for fixed fares, navigation handoff | Several million API calls/month at launch, reduced via route/ETA caching; quota headroom negotiated |
| third party service | Payment gateway (e.g., GMO-PG or Stripe JP) | Card tokenization, 3-D Secure, Apple Pay/Google Pay, authorize/capture/refund, webhooks | Japan-hosted PCI DSS Level 1 gateway; volume-based fees |
| third party service | PayPay and d払い merchant integrations | QR wallet payments via SDK or app-switch with deep-link return | Merchant contracts plus sandbox and production credentials |
| third party service | Japan-resident SMS and masked-calling provider | SMS OTP, SMS alerts and masked rider-driver calls with in-Japan processing | Hundreds of thousands of SMS/month at launch, proxy number pool per metro |
| third party service | APNs, FCM, LINE Login, Sign in with Apple, Google Sign-In | Push notifications and federated login | Standard developer accounts; no PII in push payloads |
| third party service | Partner taxi meter / fleet dispatch systems | Final meter fare, vehicle status and fallback partner dispatch | 2–4 vendor connectors for the Tokyo pilot, more for Osaka and Nagoya |

_No AI models or services are needed for this solution._

### Estimated development effort

| Phase | Roles | Low | Likely | High |
| --- | --- | --- | --- | --- |
| Programme management & architecture governance | Project / delivery manager, Solution architect | 300 | 360 | 430 |
| Discovery, design reconciliation & decision gates | Project / delivery manager, Solution architect, Product owner / business analyst (Japan taxi domain), UI/UX designer, Security engineer, Legal / compliance advisor (Japan) | 140 | 175 | 230 |
| Technical spikes & decision-gate validation | Solution architect, Mobile developer (React Native), Native mobile engineer (Swift/Kotlin), Integration engineer (payments & partner systems) | 90 | 120 | 165 |
| Platform foundation & environments | DevOps / SRE engineer (GCP), Security engineer, Data engineer | 200 | 245 | 320 |
| Backend core services build | Backend developer (Go), Backend developer (NestJS), Data engineer, Solution architect | 1050 | 1280 | 1650 |
| Payments, receipts & partner integrations | Integration engineer (payments & partner systems), Native mobile engineer (Swift/Kotlin) | 260 | 330 | 450 |
| Mobile apps build | Mobile developer (React Native), Native mobile engineer (Swift/Kotlin), UI/UX designer, Product owner / business analyst (Japan taxi domain) | 720 | 880 | 1150 |
| Admin/operator console build | Frontend web developer (Next.js), UI/UX designer, Product owner / business analyst (Japan taxi domain) | 250 | 310 | 410 |
| Data, analytics & reporting | Data engineer | 95 | 120 | 160 |
| Security, compliance & localization | Security engineer, Legal / compliance advisor (Japan), Localization coordinator | 230 | 290 | 380 |
| Testing, performance & DR validation | QA engineer (automation & performance), DevOps / SRE engineer (GCP), Backend developer (Go), Backend developer (NestJS) | 620 | 760 | 980 |
| Tokyo pilot launch & hypercare | Project / delivery manager, Product owner / business analyst (Japan taxi domain), Mobile developer (React Native), Backend developer (Go), Backend developer (NestJS), DevOps / SRE engineer (GCP), QA engineer (automation & performance) | 260 | 340 | 450 |
| Osaka & Nagoya rollout with DR validation | Project / delivery manager, DevOps / SRE engineer (GCP), Backend developer (Go), Backend developer (NestJS), Integration engineer (payments & partner systems), QA engineer (automation & performance) | 200 | 270 | 380 |
| **Total (person-days)** | | **4415** | **5480** | **7155** |

About **274.0 person-months** likely (20 working days per month).

### Estimated timeline

| Phase | Weeks | Duration | Depends on | Schedule |
| --- | --- | --- | --- | --- |
| Programme management & architecture governance | 1–58 | 58 wk | - | ████████████████████████ |
| Discovery, design reconciliation & decision gates | 1–6 | 6 wk | - | ██░░░░░░░░░░░░░░░░░░░░░░ |
| Technical spikes & decision-gate validation | 3–8 | 6 wk | - | ░██░░░░░░░░░░░░░░░░░░░░░ |
| Platform foundation & environments | 5–14 | 10 wk | Discovery, design reconciliation & decision gates | ░░████░░░░░░░░░░░░░░░░░░ |
| Backend core services build | 9–36 | 28 wk | Discovery, design reconciliation & decision gates | ░░░████████████░░░░░░░░░ |
| Payments, receipts & partner integrations | 12–37 | 26 wk | Technical spikes & decision-gate validation, Platform foundation & environments | ░░░░░███████████░░░░░░░░ |
| Mobile apps build | 10–37 | 28 wk | Technical spikes & decision-gate validation | ░░░░████████████░░░░░░░░ |
| Admin/operator console build | 12–35 | 24 wk | Discovery, design reconciliation & decision gates | ░░░░░██████████░░░░░░░░░ |
| Data, analytics & reporting | 16–33 | 18 wk | Platform foundation & environments | ░░░░░░███████░░░░░░░░░░░ |
| Security, compliance & localization | 10–43 | 34 wk | Platform foundation & environments | ░░░░██████████████░░░░░░ |
| Testing, performance & DR validation | 14–43 | 30 wk | Platform foundation & environments | ░░░░░████████████░░░░░░░ |
| Tokyo pilot launch & hypercare | 44–49 | 6 wk | Backend core services build, Payments, receipts & partner integrations, Mobile apps build, Admin/operator console build, Testing, performance & DR validation, Security, compliance & localization | ░░░░░░░░░░░░░░░░░░██░░░░ |
| Osaka & Nagoya rollout with DR validation | 50–57 | 8 wk | Tokyo pilot launch & hypercare | ░░░░░░░░░░░░░░░░░░░░███░ |

**Total: about 58 weeks** with the team above (range 46.7–75.7 weeks, following the effort range).

**What could change the estimate:**

- The design was escalated with unresolved contradictions (identity provider, data ownership, Spanner topology, Keycloak on Cloud SQL vs the rule that booking must not depend on Cloud SQL, compute placement, real-time protocol). Late resolution or reversals could add 4–10 weeks of rework.
- Partner taxi meter and fleet dispatch systems may lack modern APIs. Each vendor connector can vary widely in effort and is the most likely critical-path delay for the pilot.
- The payment SDK spike may show that PayPay, d払い or IC flows do not work well through React Native bridges, forcing in-app browser fallbacks or, at worst, a switch to Flutter before feature build.
- No Japan-only dual-region Spanner configuration may be available, which forces Option B. Option B adds Dataflow replication, runbook work and longer DR testing.
- Self-hosting Keycloak for millions of riders adds operational and hardening effort (SMS OTP SPI, HA, login peak testing) beyond a managed CIAM.
- Regulatory reviews (MLIT fixed-fare approval, Telecommunications Business Act, APPI cross-border sign-off, PCI) may require design changes late in the build.
- App Store and Google Play review, background-location permissions and payment policy rules may delay launch.
- Meeting the performance targets (30–60k location updates/s, dispatch p95 under 3s) may need extra tuning iterations after k6 tests reveal hotspots.
- Translation quality and CJK layout issues across 5 locales can extend UI rework and QA cycles.
- Hiring and onboarding about 36 FTE with Japanese-language and domain skills may delay ramp-up of the build squads.

## 5. Specialist findings

### frontend

Revision: React Native is the single, confirmed framework for both the rider and driver mobile apps. It replaces the earlier conflict with the UI/UX agent's Flutter assumption, and the UI/UX design system must now be implemented as a React Native component library. We chose React Native because it shares one TypeScript monorepo with the Next.js console and the NestJS backend: OpenAPI-generated clients, domain types, i18n catalogs and design tokens. Flutter remains the documented alternative and becomes the choice only if low-end Android rendering performance is ranked above code sharing. A Phase 0 spike must confirm that PayPay, d払い, IC/NFC and gateway tokenization SDKs work through React Native native modules before feature development starts. The admin/operator console uses Next.js with client-side rendering behind auth and SSR only for the login shell. It is built with TanStack Query, Zustand, and shadcn/ui on Radix UI with Tailwind CSS. WCAG 2.2 AA is enforced in CI with axe-core and Playwright. All surfaces are localized: Japanese is primary, with English, Chinese and Korean.

- Decision record (resolves the reviewer finding): React Native is chosen over Flutter. Selection criteria: (1) code sharing with the TypeScript and OpenAPI monorepo and the NestJS backend, (2) one hiring pool and skill set, (3) payment SDK bridging cost, (4) rendering on low-end devices. React Native wins on criteria 1 and 2 and is equal on 3, because both frameworks need native bridges for PayPay, d払い and IC. Flutter wins only on criterion 4. Revisit trigger: if the Phase 0 profiling fails the jank and battery budgets on reference low-end Android devices and these cannot be fixed with native map views, switch to Flutter before feature build. Shared tokens and the OpenAPI contract stay unchanged in either case.
- UI/UX alignment: the mobile design system is built as a React Native component library (themed primitives, accessible patterns, CJK typography) generated from the same token source as the web console. The UI/UX agent's Flutter design-system assumption is superseded.
- Phase 0 payment SDK spike, a gate before feature build: confirm iOS and Android SDK or app-switch/deep-link support and the contract terms for PayPay, d払い and the other selected QR providers; the card gateway's native tokenization SDK; Apple Pay and Google Pay; and IC/FeliCa feasibility per platform. Build thin Swift and Kotlin bridges behind the payment-adapter interface. If an SDK only supports web redirects, use an in-app browser flow with a return deep link.
- Console rendering: client-side rendering for authenticated screens, SSR only for the login and error shells, and no-store cache headers so no PII is cached at the edge.
- Routing: the console uses App Router groups (admin), (operator) and (support), with role middleware. Operators are scoped by fleet_id in query keys. Mobile uses React Navigation with auth, booking and in-trip stacks, and deep links for LINE login, payment returns and trip-share links.
- Component structure: feature-sliced folders (booking, tracking, payments, etc.) on top of shared ui, lib and api packages.
- Real-time map: native map views, marker updates throttled to animation frames, interpolation between updates, and batched Zustand writes.
- Poor connectivity: persisted query cache, mutations queued with idempotency keys, offline banners, and an in-trip screen that works from cached state.
- Payments: no raw card data in JS. Use gateway-hosted tokenization and native payment sheets so app code stays out of PCI DSS scope.
- Localization: ICU messages with Japanese as default plus English, Chinese and Korean. Use Noto Sans CJK, JPY without decimals, the Asia/Tokyo time zone, and both Japanese and Western address order.
- WCAG 2.2 AA (web): focus not obscured (2.4.11); targets at least 24×24 px (2.5.8); dragging alternatives for map pins (2.5.7); consistent help (3.2.6); no redundant entry (3.3.7); accessible authentication with OTP paste and passkeys (3.3.8); 4.5:1 text contrast; accessible data tables.
- Mobile accessibility: VoiceOver and TalkBack labels including map markers; live-region ETA announcements; font scaling up to 200%; haptic and audio cues for driver requests; status indicators that do not rely on color alone. Driver flows use large targets and minimal interaction.

### uiux

Mobile-first information architecture for three surfaces: the Rider app, the Driver app and the Operator/Admin web console. The Rider app centres on a single map-based booking flow that runs Home, then Set Destination, then Fare Estimate and Payment, then Matching, then Live Trip, then Receipt and Rating. It is built Japanese-first with en/zh/ko localisation, tolerates poor connectivity and meets WCAG 2.1 AA. The Driver app uses a glanceable, large-target UI suited to in-vehicle use, with an online toggle, request cards on countdown timers, navigation and earnings. The web console is a role-based dashboard with a persistent side navigation covering fleet, drivers, pricing, promotions, support and analytics.

- Progressive disclosure: the booking flow uses one bottom sheet that expands step by step, which keeps the rider to 3 taps to book from Home when a favourite or recent destination is used.
- Fare transparency: always label whether a fare is a 'meter estimate (range)' or a 'fixed fare (確定運賃)', show surcharges itemised before confirmation, and show the final breakdown on the receipt along with the T-number (registration number) of the taxi operator.
- Pickup precision: snap the pin to a road-side location, offer named pickup spots at stations and large buildings (e.g. specific exits of 東京駅), and let riders add a pickup note.
- Japanese address search must accept kanji, kana and romaji and handle chōme-banchi formats. Results should display place name first, then address.
- Payment UX: use the rider's last method as the default. Clearly flag methods that are paid in-car (cash, IC card) versus in-app. QR payments (PayPay, d払い) hand off to the provider app and deep-link back, and the app shows a resumable pending state.
- Corporate riders get a profile switcher (personal/business) on the payment sheet, with a cost-centre or memo field.
- Poor connectivity: queue location and actions optimistically, show a non-blocking 'reconnecting' banner, keep the last known driver position with a stale indicator, and never double-book on retry by using idempotent request UX that keeps the button disabled with a spinner.
- Masked communication: the in-app chat offers quick-reply phrases that are pre-translated (e.g. 'I'm at the north exit') to bridge language gaps between tourists and Japanese drivers. Calls are routed through masked numbers.
- Driver safety: minimise interaction while the vehicle is moving by using large targets, voice prompts and auto-dismissing non-critical notifications, and disable chat typing above a speed threshold so that only quick replies are available.
- Accessibility: support Dynamic Type and font scaling, VoiceOver and TalkBack labels on map elements (driver ETA announced as text), avoid colour-only status indicators, and offer a wheelchair-accessible / UD taxi filter as a ride option.
- Onboarding: provide a minimal first-run flow (language, then phone/LINE/Apple/Google sign-in, then location permission with a just-in-time explanation). Defer card entry until the first booking.
- Console: put a live operations map on the dashboard, require confirmation and diff preview for pricing and promotion changes, and keep an audit trail visible per record. Support staff see the ride timeline, chat log and payment status on one screen.
- Responsive behaviour: the mobile apps support phones from small to large plus tablets (with a wider map and side sheet instead of a bottom sheet). The console is desktop-first at 1280px or more and collapses the side nav to icons on tablets, while mobile web is limited to read-only dashboards.

### backend

Domain-oriented microservices on GKE with Go for latency-critical paths (dispatch, location) and NestJS/Node.js for business services (accounts, pricing, payments, notifications, support, admin BFF). External clients use REST described by OpenAPI. Internal synchronous calls use gRPC. Domain events flow over Pub/Sub using a transactional outbox. Rider and driver identity runs on Identity Platform (phone/SMS, Apple, Google, LINE via OpenID Connect) and issues JWTs. Operators and admins sign in through Keycloak with RBAC scoped per taxi company. Payments are tokenized through Japanese PSPs so card data never touches our services. Hot location and driver-availability state lives in Memorystore with geo-indexing. Transactional data lives in Cloud SQL (PostgreSQL), and globally consistent ride and payment ledgers sit in Spanner for Tokyo/Osaka DR.

- Trip lifecycle is an explicit state machine with optimistic concurrency, so double acceptance and race conditions are rejected at the store.
- Dispatch offers use a Memorystore lock with a TTL of about 15s and sequential or batched offer rounds. If no driver accepts, the search radius expands and the request falls back to partner fleet dispatch.
- All mutating client APIs require an Idempotency-Key header. Payment calls pass idempotency keys through to the PSP.
- Card data never touches the backend. Apps tokenize with the PSP SDK, so the backend stores only tokens, which keeps the system in SAQ-A-like scope. 3-D Secure is applied per the Installment Sales Act guidelines.
- Fare flow: estimate at booking (pre-determined fare locked when applicable). Final fare comes from the partner meter via the adapter or the app meter. Payment is authorized at booking and captured on completion.
- Receipts are issued in the name of the taxi operator as the service provider, with the operator's qualified invoice registration number. Platform fees are invoiced separately.
- Authorization is scope-based: riders see only their own trips, drivers only their assigned trips, and operators only their own fleet data (operator_id claim enforced in queries). Admin actions are audit-logged.
- Service-to-service traffic uses mTLS with workload identity. No shared databases between services.
- Degraded mode: if pricing or the maps service fails, use cached rate cards and straight-line ETA estimates, so booking keeps working.
- Location fan-out is sharded by city geo-cell. Riders subscribe only to their assigned driver's channel.

### database

Revised data-ownership model: Spanner (multi-region asia1, read-write in Tokyo and Osaka) is the single system of record for everything needed to book and dispatch. That covers accounts and rider profiles, drivers, vehicles, fleet operators and their operating status, active and versioned rate cards, active promotions, rides, reservations, payments, ledger and invoices. This gives RPO 0 with automatic failover. Memorystore (Redis) holds live locations and read-through caches of rate cards and driver eligibility, with a documented degraded mode. Cloud SQL (PostgreSQL) is limited to true back-office workflows: support tickets, lost items, onboarding document review and campaign drafting. Nothing in Cloud SQL is a synchronous dependency of booking or dispatch. Cloud SQL DR is reconciled to one figure, RPO ≤5 min and RTO ≤30 min. BigQuery holds analytics and Cloud Storage holds documents and archives. All data stays in Japan; one residency item about the Spanner witness replica needs legal sign-off (see risks).

- DATA-OWNERSHIP MATRIX, the single source to be adopted by the backend and cloud agents. Format: service → data → store → region → RPO / RTO.
- (1) User/Account → User, RiderProfile, FavoritePlace, EmergencyContact, identity-provider linkage → Spanner → asia1 (Tokyo+Osaka) → RPO 0 / RTO ≤1 min (automatic).
- (2) Driver & Fleet → Driver, DriverEligibility, Vehicle, FleetOperator and operating status, PartnerMeterMapping → Spanner → asia1 → RPO 0 / RTO ≤1 min.
- (3) Pricing → RateCard and SurchargeRule versions (draft and published), FixedFareZone, FareQuote → Spanner → asia1 → RPO 0 / RTO ≤1 min. Published cards are cached in Redis and in process.
- (4) Ride & Dispatch → Ride, RideEvent, Reservation, DispatchAssignment, TripTrace → Spanner → asia1 → RPO 0 / RTO ≤1 min.
- (5) Payments & Invoicing → Payment (token), LedgerEntry, Invoice → Spanner → asia1 → RPO 0 / RTO ≤1 min.
- (6) Promotions (runtime) → ActivePromotion, CouponRedemption → Spanner → asia1 → RPO 0 / RTO ≤1 min.
- (7) Ratings & Messaging → Rating, ChatMessage (90-day row deletion policy) → Spanner → asia1 → RPO 0 / RTO ≤1 min.
- (8) Location & Dispatch hot state → GEO sets, offer locks, caches → Memorystore → Tokyo primary with Osaka warm standby → RPO not applicable (ephemeral, rebuilt from pings within ≤10 s) / RTO ≤1 min.
- (9) Support & Back-office → tickets, lost items, onboarding document review, campaign drafts → Cloud SQL → Tokyo HA with Osaka async replica → RPO ≤5 min / RTO ≤30 min (manual promotion runbook). This replaces the earlier '<1 min' figure and aligns with the cloud agent.
- (10) Analytics → BigQuery → asia-northeast1 with daily copy to asia-northeast2 → RPO ≤24 h, replayable from change streams / RTO ≤24 h.
- (11) Documents & Archives → Cloud Storage → dual-region Tokyo/Osaka with turbo replication → RPO ≤15 min / RTO ≈0.
- Rule: a booking or dispatch request must not have a synchronous dependency on Cloud SQL, BigQuery or Cloud Storage. Admin console edits to Spanner-owned data, such as pricing, driver status or operator suspension, go through the owning service API and never through Cloud SQL.
- Pricing publish flow: an admin creates a RateCard draft in Spanner, approval sets status=published with effective_from, and a change stream invalidates the Redis cache. Each FareQuote stores rate_card_version for audit.
- Degraded mode if Spanner reads are slow or unavailable: the pricing service serves the last-known-good published rate card from in-process and Redis cache (TTL 10 min, hard max 24 h) and quotes are marked 'estimate'. The dispatch service checks driver eligibility and operator status from the Redis cache. The final assignment write still requires Spanner; if Spanner writes fail, the request is queued and the rider sees a retrying state rather than a silent booking.
- Degraded mode if Memorystore Tokyo is lost: traffic switches to the Osaka standby cluster. Driver apps re-ping every 3-5 s, so GEO sets refill within about 10 s. Rate card and eligibility caches warm from Spanner on miss. During the gap, dispatch falls back to Spanner DriverAvailability, which holds last-known cell and status and is written only on status change, at coarser matching accuracy.
- Degraded mode if Cloud SQL is lost: support ticketing, onboarding review and campaign authoring pause. Booking, dispatch, pricing, payments and active coupons are unaffected.
- Spanner keys and indexes: use UUIDv4 or bit-reversed sequence keys. Interleave RideEvent, Payment and Rating under Ride. Secondary indexes: (rider_id, created_at DESC), (driver_id, created_at DESC), (status, scheduled_at) for reservations, (operator_id, completed_at) for settlement, (operator_id, status) for drivers, and (city, status, effective_from) for rate cards.
- Dispatch consistency: Redis GEOSEARCH finds candidates and a SET NX offer lock (TTL about 15 s) reserves the driver. The Spanner read-write transaction is the final arbiter: it checks the driver is free, the ride is unassigned, and the driver and operator are eligible.
- Payments store tokens and last-4 digits only. Idempotency keys carry unique indexes and the ledger is append-only.
- Lifecycle: Redis locations expire after 60 s. ChatMessage is deleted after 90 days through a Spanner TTL policy. TripTrace is kept 1 year in Spanner and then moved to a Cloud Storage archive. Invoices and payments are kept 7 years under retention lock. On APPI deletion, PII is anonymized or crypto-shredded through per-user KMS keys.
- Japanese text is stored as UTF-8. Addresses are structured fields (prefecture, city, chome, banchi) with kana readings.

### cloud

Active-passive multi-region GCP design. asia-northeast1 (Tokyo) is primary and asia-northeast2 (Osaka) is warm standby. Latency-sensitive dispatch and location services run on regional GKE across three zones. Stateless APIs and the admin console run on Cloud Run. Pub/Sub is the event backbone and Memorystore holds hot geo state. The Spanner topology is now an explicit decision gate. The standard asia1 multi-region config places its witness replica in Seoul (asia-northeast3), so it is rejected by default: it breaks the Japan-only Org Policy and needs an APPI legal position. Option A (target) is a Japan-only dual-region Tokyo+Osaka Spanner configuration, subject to verification of availability, SLA and failover behaviour. It gives RPO≈0 and an RTO of 30 min or less. Option B (committed fallback) is a regional Tokyo Spanner instance with change-stream replication to an Osaka standby instance plus cross-region backup copies. It gives an RPO of 1 min or less and an RTO of 60 min or less. Observability now adds distributed tracing: OpenTelemetry in Go and NestJS services exports to Cloud Trace. Trace context propagates across gRPC, HTTP, WebSocket and Pub/Sub, and trace IDs are correlated in Cloud Logging and Cloud Monitoring exemplars.

- Spanner residency finding: the asia1 config has read-write replicas in Tokyo and Osaka plus a witness in Seoul (asia-northeast3). Witness replicas take part in write quorum and persist log data, so personal data would be processed and stored outside Japan. asia1 also violates our gcp.resourceLocations policy. It is rejected unless Legal/DPO issue a written APPI position (cross-border transfer basis and privacy notice) and the policy is formally excepted.
- Spanner decision gate (before production cut-over, owner: cloud + database + legal). Step 1: verify against current GCP docs and with the account team that a Japan-only dual-region configuration (Tokyo+Osaka, no out-of-country witness) exists, and confirm its SLA and its region-failure behaviour (automatic, or a manual switch to single-region mode). Step 2: if confirmed, choose Option A. If not, choose Option B. A custom instance config is acceptable only if all replicas stay in asia-northeast1/2.
- Option A DR: RPO≈0. RTO is 30 min or less for the platform, including any manual Spanner failover step, the GKE and Cloud Run scale-out in Osaka and the load balancer shift. The runbook includes the Spanner region-mode change if the configuration requires it.
- Option B DR: regional Tokyo Spanner (99.99% SLA, zonal faults handled automatically). Change streams feed Dataflow, which writes to a smaller Osaka standby instance with a target lag of seconds. RPO is 1 min or less and RTO is 60 min or less: stop the stream, scale up Osaka processing units, repoint services through config and shift load balancer traffic. Backup copies to Osaka every 4 h, plus the 7-day PITR in Tokyo, cover corruption; restoring from backup takes RPO of 4 h or less and RTO of 4 h or less. In-flight rides lost within the RPO window are reconciled from gateway transaction records, driver-app local trip logs and the Pub/Sub retention replay.
- Aligned platform DR table to share with the database, backend and performance agents. Booking and dispatch: RPO≈0 and RTO 30 min or less (A), or RPO 1 min or less and RTO 60 min or less (B). Back-office Cloud SQL: RPO 5 min or less, RTO 30 min or less. Redis geo-state: rebuilt in about 10 s. Analytics: RPO 24 h or less. Zonal faults: RTO under 5 min, automatic, under both options.
- Availability: three zones in Tokyo with N+1 headroom. The 99.95% monthly SLO for booking and dispatch is achievable under both options; Option B relies on the Spanner regional 99.99% SLA, and regional disasters are handled by DR rather than counted against the SLO.
- Tracing: the OpenTelemetry SDK is used in Go (dispatch, location, ride state) and NestJS (APIs, payments orchestration) services with W3C traceparent/baggage. gRPC uses otelgrpc interceptors and HTTP uses auto-instrumentation. WebSocket sends traceparent in the connect handshake and a trace field per message for ride-critical events. Pub/Sub publishers inject traceparent into message attributes and subscribers extract it as span links. Outbox rows store traceparent so that relayed events continue the originating trace.
- Trace export and sampling: the OpenTelemetry Collector exports to Cloud Trace. Sampling is parent-based, with 100% for errors and requests above the dispatch SLO threshold (tail sampling at the Collector), 10% head sampling for booking and dispatch, and 1% or less for location pings. Span attributes must not contain PII or tokens; the Collector redacts phone, email, coordinates and card fields.
- Correlation and runbooks: structured logs include trace and span IDs. Dispatch latency histograms carry exemplars. Runbook flow: SLO burn-rate alert, then exemplar trace in Cloud Trace, then filtered Cloud Logging by trace ID, then root-cause span (Spanner, Redis, Pub/Sub lag, partner API). Trace-based investigation is part of the game days.
- Backups: Spanner PITR (7 days) plus scheduled backups (copied to Osaka under Option B), Cloud SQL PITR and BigQuery time travel. Restore tests run quarterly and region-failover game days run twice a year.
- Peak handling: HPA on Pub/Sub backlog and connection counts, scheduled pre-scaling before New Year, events and rain, Cloud Run minimum instances and Spanner autoscaling.
- Cost drivers: Spanner (Option A dual-region costs more than B, but B adds the standby instance and Dataflow), GKE, Memorystore, location traffic, logging and trace volume, and Maps APIs (billed outside GCP).
- Cost optimisation: committed use discounts for baseline capacity, Spot pools for batch work, a scaled-down Osaka standby, Spanner processing-unit autoscaling, log exclusion for location pings, trace sampling, BigQuery partitioning and GCS lifecycle rules.

### security

Revised security design for the Japan ride-hailing platform on GCP Tokyo (asia-northeast1) and Osaka (asia-northeast2). This revision fixes the data residency gap in customer identity. Identity Platform is a global service: its user store is not region-pinned to Japan, and the gcp.resourceLocations Org Policy does not govern it. It therefore cannot guarantee Japan residency for millions of rider and driver identities, so it is replaced. The new CIAM is self-hosted Keycloak on GKE in Tokyo with warm standby in Osaka, backed by a Japan-region Cloud SQL (PostgreSQL) store with CMEK. SMS OTP and masked calling must use a provider whose processing and storage are in Japan. Remaining unavoidable cross-border flows are inventoried and documented under APPI with client sign-off: Apple/Google federation, APNs/FCM push and possibly maps. Other controls are unchanged: OIDC/OAuth 2.0 with short-lived JWTs, a separate staff realm with MFA, PCI scope reduced by tokenization, Cloud KMS CMEK in Japan, Secret Manager, Cloud Armor, least-privilege IAM, private VPC networking, APPI privacy controls, audit logging and OWASP testing in CI/CD.

- Residency finding resolution: Identity Platform stores and processes user accounts as a global service with no Japan region option, and resource-location Org Policies do not apply to it. Because the brief mandates data residency in Japan, Keycloak in asia-northeast1/2 is the CIAM. Identity Platform remains an option only if the client formally accepts the cross-border transfer under APPI Art. 28 and updates the privacy notice.
- Cross-border flow register: Apple and Google federation (the platform receives claims, and stores the user's identity data only in Japan), LINE Login (LY Corporation, Japan), APNs and FCM push (payloads carry no PII, only a trip ID and generic text), Google Maps Platform (send no user identifiers, only coordinates), and the payment gateway (must be Japan-hosted). Each entry records its legal basis and gets client sign-off.
- SMS OTP residency: contract a Japanese carrier or aggregator that processes and stores message logs in Japan. Only the phone number and OTP are sent, and logs are retained for 30 days or less. The same requirement applies to the masked-calling proxy.
- Keycloak hardening: the admin console is reachable only on an internal load balancer through IAP or VPN. Brute-force detection is on. Signing keys rotate. A separate realm keeps staff isolated from customers. Upgrades are regularly patched and tracked against CVEs.
- Identity availability: multi-replica Keycloak in Tokyo uses a distributed session cache. Osaka runs warm standby with a Cloud SQL cross-region replica, with RPO under 5 minutes and RTO under 30 minutes for login. Existing sessions survive failover through long-lived refresh tokens, re-issued on failover where possible.
- OWASP Top 10 mapping: A01 object-level and tenant checks; A02 TLS 1.2+ and CMEK; A03 parameterised queries; A05 Terraform and Org Policies; A07 OTP limits, MFA and Keycloak brute-force protection; A08 signed images and webhooks; A09 central audit logs; A10 egress allowlist.
- PCI DSS: no PAN ever reaches the platform. The payment service runs in an isolated project. Target SAQ A or A-EP with an annual assessment.
- Location traces: 90 days raw, then aggregated or pseudonymised. Trip-share links expire when the trip ends.
- Qualified invoice receipts are kept in write-once storage with a hash for 7 years. Driver documents use CMEK, signed URLs and role-restricted access.
- APPI breach runbook covers PPC reporting and notification of affected individuals, and includes the CIAM and SMS provider in scope.

### performance

Performance targets and design for dispatch, real-time location, mobile apps and the admin console. Key SLOs: dispatch match p95 under 3s. Location ingest of 30k+ updates/s, with p95 under 1s from driver to rider map. Booking API p95 under 300ms. Rider app cold start under 2s on mid-range devices. Admin console LCP under 2.5s. The hot geo state lives in Memorystore (Redis GEO), location fan-out runs on Pub/Sub plus streaming gRPC on autoscaled GKE, durable data sits in Spanner, and load is verified with k6 against peak scenarios (New Year, rain, events).

- SLOs: booking/dispatch availability of 99.95%. Booking API p95 under 300ms and p99 under 800ms. Fare estimate p95 under 500ms (cache hit under 50ms). Dispatch match p95 under 3s. Location end-to-end lag p95 under 1s. Push delivery p95 under 2s.
- Partition geo state by city and geohash cell (e.g., H3/geohash precision 5-6) so dispatch and ingest scale horizontally and keep hot keys bounded. Shard Redis in cluster mode.
- Write locations to Redis first and persist asynchronously via Pub/Sub. Sample trip breadcrumbs for receipts/disputes rather than storing every ping synchronously.
- The driver app adapts the update interval: 3s while on a trip or near a pickup, 5-10s when idle, and suppresses updates when stationary. Batch and compress updates on weak signal (subway, tunnels).
- Mobile: rider cold start under 2s and warm start under 1s on mid-range Android. Keep the app download under 50MB, cache map tiles, defer non-critical SDK init and render frames at 60fps on the map screen. Retry offline-tolerant requests with idempotency keys.
- Fare estimates: cache route and ETA results keyed by rounded origin/destination plus time bucket (60-120s TTL) to cut map provider calls. Precompute surcharge and tariff tables per operator in memory.
- Payments: run tokenization and gateway calls asynchronously with timeouts and circuit breakers. Never block dispatch on payment pre-auth beyond 2s; fall back to deferred auth.
- Peak readiness: pre-scale GKE node pools via scheduled scaling for rush hours and New Year. HPA on Pub/Sub backlog and active streams. Keep 30-50% headroom on the dispatch tier.
- Admin console: LCP under 2.5s, INP under 200ms, CLS under 0.1. Initial JS of 200KB gzip or less per route. Use virtualized tables for fleet lists and server-side pagination and aggregation for analytics.
- Run k6 load tests at 2x the projected peak (e.g., 60k location updates/s, 5k ride requests/min burst) before each metro launch, plus soak tests of 4h or more.

## 6. Alternatives

Listed per technology choice in section 3.

## 7. Risks

| Risk | Severity | Likelihood | Mitigation | From |
| --- | --- | --- | --- | --- |
| Double assignment or double charging from Redis/Spanner races. | critical | low | Make the Spanner transaction the final arbiter, drive the ride state machine with conditional updates, and use payment idempotency keys. | database |
| A Kanto earthquake takes out Tokyo while Osaka capacity is insufficient. | critical | low | Pre-provisioned Osaka minimums, reserved quotas, tested runbooks and game days twice a year. | cloud |
| Broken object-level authorization exposes other users' trips, locations or receipts. | critical | medium | Use central authorization middleware, non-guessable IDs, automated authorization tests and ZAP/API fuzzing. | security |
| Leakage of real-time location and personal data, violating APPI. | critical | medium | Minimise and briefly retain data, use field-level encryption, VPC Service Controls and pseudonymised analytics, and maintain a breach runbook. | security |
| Japanese payment SDKs (PayPay, d払い, IC) may lack React Native bindings or impose app-switch flows. | high | medium | Run the Phase 0 spike as a hard gate, use thin Swift and Kotlin bridges behind the payment adapter, and fall back to an in-app browser with a deep-link return. | frontend |
| Map rendering or battery performance on low-end Android under 3–5 s updates. | high | medium | Use the New Architecture with Hermes, native map views, adaptive location intervals and device-farm profiling budgets. Apply the documented Flutter revisit trigger if the budgets fail. | frontend |
| Fare confusion between meter estimates, fixed fares and surcharges causes disputes and support load. | high | medium | Use explicit fare-type labels, itemise surcharges before booking and compare the estimate with the actual fare on the receipt, and run usability testing with both locals and tourists. | uiux |
| Driver distraction from app interactions while driving creates a safety and regulatory risk. | high | medium | Lock non-essential UI while moving, use voice prompts and large targets, and keep request accept to a single tap. | uiux |
| Partner taxi meter/dispatch systems vary widely and may lack modern APIs, which delays integration. | high | high | Build an adapter layer with a pluggable connector per vendor. Phase rollout with an app-based meter fallback where legally permitted. | backend |
| Hot-spot load in the dispatch geo-index during peaks (stations, New Year, rain). | high | medium | Shard by geo-cell, autoscale on queue depth, apply backpressure with surge queueing, and run k6 peak tests. | backend |
| Payment inconsistency between authorization, meter fare and capture across PSP webhooks. | high | medium | Use a double-entry ledger, idempotent webhooks, daily reconciliation jobs and outbox-based events. | backend |
| Spanner cost rises and hotspot risk grows now that more entities (accounts, drivers, pricing) are moved into it. | high | medium | Use UUID or bit-reversed keys, Key Visualizer reviews, and k6 peak tests. Use autoscaling with processing units and serve read-heavy config (rate cards, eligibility) from Redis cache to cut Spanner reads. | database |
| The asia1 multi-region configuration places its witness replica outside Japan (Seoul), which may conflict with strict data-residency interpretation. | high | medium | Get legal and APPI review early. Witness replicas hold no full readable copy, and PII columns are application-encrypted with Japan-held KMS keys. If rejected, fall back to regional Spanner in Tokyo plus an Osaka backup/restore DR runbook, documenting the resulting RPO/RTO change. | database |
| Other agents keep older ownership assumptions, such as accounts or pricing in Cloud SQL. | high | medium | Adopt this matrix as the cross-agent contract and verify that backend service definitions and cloud DR tables match it. | database |
| APPI exposure from PII spread across stores. | high | medium | Encrypt PII columns, pseudonymize IDs in BigQuery, apply column-level policies, use CMEK, and keep audit logs. | database |
| The Spanner residency position is unresolved. asia1 stores witness data in Seoul, and a Japan-only dual-region configuration may be unavailable or behave differently from what is assumed. | high | medium | Treat it as a pre-production decision gate with documented Legal/DPO sign-off. Terraform supports both Option A and Option B, and Option B is pre-designed with stated RPO and RTO. | cloud |
| Under Option B, change-stream replication lag grows during peaks, widening RPO beyond 1 min. | high | medium | Alert on replication lag above 30 s, autoscale Dataflow, size Osaka processing units and reconcile from gateway and driver-app logs. | cloud |
| Location-update storms overwhelm ingest or Redis. | high | medium | Adaptive ping intervals, geohash sharding, HPA on connection counts and Pub/Sub backpressure. | cloud |
| PCI scope spreads across shared infrastructure. | high | medium | Gateway tokenization, a payments project isolated by VPC Service Controls, dedicated service accounts and CMEK. | cloud |
| Identity data stored or processed outside Japan, breaching the residency requirement and APPI cross-border rules. | high | medium | Use Japan-hosted Keycloak on Japan Cloud SQL and a Japan-resident SMS provider. Maintain the cross-border register with client sign-off, and include processor location clauses in DPAs. | security |
| Operational burden and vulnerabilities from self-hosting Keycloak; a misconfiguration or outage would affect all logins. | high | medium | Manage realm config with Terraform, keep the admin console private, apply CVE patching SLAs, run multi-replica HA with Osaka DR, and load-test login peaks with k6. Stateless JWT validation keeps active trips running during an outage. | security |
| Account takeover and SMS OTP abuse (SMS pumping, SIM swap). | high | high | Apply per-number, device and IP OTP limits with attestation, step-up authentication for sensitive changes, new-device alerts, and passkey or social login options. | security |
| Payment fraud or card-data exposure expanding PCI scope. | high | medium | Tokenize on the device, use EMV 3DS, verify webhook signatures, and isolate the payment project. | security |
| Tampered driver app used to spoof GPS or create fraudulent trips. | high | medium | Use Play Integrity and App Attest, run server-side location plausibility checks, and cross-check with partner meter data. | security |
| Insider misuse by support or operator staff. | high | medium | Use tenant-scoped RBAC, just-in-time access, masked PII in consoles and audit alerts. | security |
| DDoS or bot traffic at peak events degrades booking or login. | high | medium | Use Cloud Armor adaptive protection and rate limits, prioritise the booking path, and autoscale Keycloak and the APIs. | security |
| Hot spots in the geo index (e.g., Shinjuku/Tokyo Station at peak or events) overload single Redis shards and slow matching. | high | medium | Use fine-grained cell partitioning, shard hot cells and add read replicas. Cap the candidate search radius in expanding rings. | performance |
| Map provider API latency or rate limits inflate fare estimates and ETAs during surges. | high | medium | Cache aggressively, fall back to straight-line/historical ETA estimates, apply circuit breakers and negotiate quota headroom. | performance |
| Sudden demand spikes (rain, train disruptions, New Year) outpace autoscaling warm-up. | high | high | Pre-scale on a schedule, provision headroom and use queue-based admission control with graceful degradation (e.g., temporarily disable non-essential features). | performance |
| Residual misalignment between the frontend and UI/UX agents on the design system. | medium | low | Use a single token source and a single React Native component library spec, with the decision record shared with UI/UX. | frontend |
| Console SSR or edge caching could violate data residency or expose PII. | medium | medium | Keep dynamic rendering in Japan regions only, serve only static assets from the CDN, and send no-store headers. | frontend |
| Translation quality issues and CJK text truncation. | medium | high | Use professional review, pseudo-localization and per-locale visual tests. | frontend |
| Map components are hard to make accessible. | medium | high | Provide non-map equivalents: search, saved places and a textual status panel. | frontend |
| Overly long translated strings (English, Korean) break compact bottom sheets and driver cards. | medium | high | Use flexible layouts, run pseudo-localization and screenshot tests per locale, and have professional translators review the copy. | uiux |
| QR payment app-switching loses state, leading to abandoned or duplicate payments. | medium | medium | Make payment states persistent and resumable via deep-link returns, and add a clear 'payment pending' screen with a retry or change-method option. | uiux |
| Location permission denial blocks the core booking flow. | medium | medium | Show a just-in-time rationale screen and fall back to manual pickup search on the map. | uiux |
| Masked calling and chat retention may raise Telecommunications Business Act and APPI issues. | medium | medium | Use a licensed telephony partner, set minimal retention, obtain legal review and publish a privacy notice. | backend |
| Spanner multi-region cost and latency for write-heavy paths. | medium | medium | Keep high-frequency location data out of Spanner (Memorystore plus sampled archive). Use Spanner only for trips and the ledger. | backend |
| Stale cached rate cards or eligibility data during degraded mode could produce wrong quotes or dispatch to a suspended driver. | medium | low | Invalidate caches through change streams and set a hard maximum cache age. Re-check eligibility in the Spanner assignment transaction, mark quotes issued from cache, and reconcile fares at trip end against the authoritative version. | database |
| Trace data leaks PII, or Cloud Trace storage location does not meet residency expectations. | medium | medium | Redaction at the Collector, an attribute allowlist, and confirmation of the trace storage location in the residency review. If it is not acceptable, keep trace IDs in Japan-pinned logs and minimise span attributes. | cloud |
| Poor mobile connectivity causes missed dispatch offers and stale locations. | medium | high | Use stream reconnect with backoff, deliver offers via push notification as a fallback, add client-side interpolation and give offers a server-side acceptance timeout with re-offer. | performance |
| Cross-region replication to Osaka adds write latency on trip and payment data. | medium | medium | Keep the hot path in the Tokyo leader region, write async for non-critical data and set the Spanner leader placement deliberately. | performance |

## 8. Quality score

**Overall: 71.7/100**

| Dimension | Weight % | Score |
| --- | --- | --- |
| requirement_fit | 23.75 | 78 |
| architecture | 18.75 | 62 |
| security | 17.5 | 74 |
| performance | 13.75 | 80 |
| maintainability | 10.0 | 65 |
| reliability | 7.5 | 63 |
| cost | 3.75 | 62 |
| accessibility | 2.5 | 80 |
| scalability | 2.5 | 80 |

Open blockers: high-severity finding open; overall score 71.7 < 80; requirement fit 78 < 85

## 9. Assumptions

- Platform partners with licensed taxi companies rather than operating private-car ridesharing
- A major public cloud with Tokyo and Osaka regions (e.g., AWS, GCP or Azure) will be used; provider choice is open
- Mobile apps may be built cross-platform (e.g., Flutter/React Native) or native; to be decided in design
- Maps via Google Maps Platform or a Japanese map provider such as Zenrin
- A web-based admin/operator console is required in addition to mobile apps
- No specific budget or timeline was provided; design should support phased rollout
- Basic analytics and reporting are included; advanced ML (e.g., demand forecasting, dynamic pricing models) is optional future scope
- The UI/UX agent updates its design system assumption from Flutter to a React Native component library that shares tokens with the web console.
- The backend is NestJS exposing OpenAPI-described REST endpoints plus a WebSocket channel for real-time events.
- Maps use Google Maps Platform or Zenrin SDKs behind a common interface, owned by the integration team.
- Payment provider contracts and SDK access will be available in time for the Phase 0 spike.
- Rider and driver apps are separate binaries in one monorepo; the console is desktop-first with tablet support.
- Final Next.js hosting is decided by the cloud agent; Firebase Hosting serves static assets only.
- Turn-by-turn navigation in the driver app hands off to Google Maps or the in-car navigation unit instead of being built custom.
- Partner taxi operators may have their own branding, so the rider UI shows the operator name and logo on the assigned-driver card.
- A shared Flutter design system serves both the Rider and Driver apps, while the console has its own web component library that uses the same tokens.
- Accessibility target is WCAG 2.1 AA for the console and equivalent platform guidelines for the mobile apps.
- Driver-app accept timeout (15s) and the max-taps targets are initial values to be validated in usability testing.
- GCP is chosen, with asia-northeast1 (Tokyo) and asia-northeast2 (Osaka) regions, consistent with the catalogue.
- The PSP (e.g., GMO-PG/Stripe JP) and maps provider (Google Maps Platform/Zenrin) expose REST APIs and are integrated directly.
- Final fare authority rests with the licensed operator's meter or approved fixed-fare calculation.
- Masked phone numbers are provided by a third-party telephony vendor outside the catalogue.
- IC card payments depend on the in-vehicle terminal and are recorded via the meter integration rather than processed by the platform.
- The platform runs on GCP: Spanner asia1 (Tokyo and Osaka read-write) and Japan regions for all other stores.
- Credentials and login live in the auth provider. Spanner holds the user profile and identity linkage.
- A payment gateway performs tokenization, keeping databases out of PCI cardholder-data scope.
- Invoice and payment records need 7-year retention.
- Cloud SQL figures of RPO ≤5 min and RTO ≤30 min are the reconciled platform values for back-office data only.
- No vector or AI storage is needed in this phase.
- GCP is selected, using asia-northeast1 and asia-northeast2 only.
- A Japan-only dual-region Spanner configuration must be verified before Option A is adopted; otherwise Option B applies, with its stated RPO and RTO.
- Cloud Trace and OpenTelemetry are not listed in the approved catalogue. A catalogue exception is requested because the NFR mandates distributed tracing; they complement Cloud Monitoring and Cloud Logging.
- Card data is tokenized by PCI-certified gateways and never stored.
- Maps APIs are external SaaS.
- Phased rollout: Tokyo first, then Osaka and Nagoya.
- GCP is the chosen cloud, using the Tokyo and Osaka regions.
- The client prefers strict Japan residency for identity data over the convenience of a managed global CIAM. If not, Identity Platform can be reinstated with documented APPI transfer sign-off.
- A Japanese SMS and telephony provider offering in-Japan processing and log storage is available under DPA.
- The team has, or will acquire, the capacity to operate Keycloak on GKE, including patching and on-call.
- A PCI DSS-compliant, Japan-hosted payment gateway with mobile tokenization and EMV 3DS will be selected.
- Partner taxi-meter and fleet systems support mTLS or OAuth client-credentials.
- The APPI privacy policy, consent text and foreign-processor disclosures will be finalised with legal counsel.
- GCP is the chosen provider, given the catalogue, with Tokyo (asia-northeast1) as primary and Osaka (asia-northeast2) for DR.
- The peak is roughly 30k location updates/s and a few thousand concurrent ride requests across the three initial metros.
- The admin console is built with Next.js by the frontend agent, and the mobile framework is decided by the frontend/mobile agent.
- Map provider SLAs allow caching of route/ETA results within their terms of service.
- The escalated review conflicts are resolved in the first 6 weeks by the human architect. This estimate assumes the most recent specialist positions: React Native and shadcn/ui (frontend), Keycloak hosted in Japan (security), the database agent's data ownership matrix with Spanner owning booking and dispatch data, and the cloud agent's Japan-only Spanner Option A or B rather than asia1.
- GCP is the cloud provider, using asia-northeast1 (Tokyo) and asia-northeast2 (Osaka) only.
- The scope through week 57 covers a Tokyo pilot followed by Osaka and Nagoya rollout; advanced ML (demand forecasting, dynamic pricing) is excluded.
- At least 2–4 licensed taxi operators commit to the pilot and provide access to their meter/fleet systems and test environments by week 12.
- Payment provider (PSP, PayPay, d払い) and Japan-resident SMS/telephony contracts and sandbox credentials are available by week 3 for the spikes.
- Turn-by-turn navigation hands off to Google Maps or the in-car navigation unit rather than being built custom.
- IC card payments are handled by in-vehicle terminals and recorded via meter integration, not processed by the platform.
- The team is experienced with the chosen stack (React Native, Go, NestJS, GKE, Spanner, Keycloak) and works with Japanese-language capability for domain, QA and localization.
- An external penetration test and a PCI QSA assessment are procured separately; their fees are not included in the effort figures.
- Client stakeholders and Legal/DPO make decisions promptly at the defined gates (Spanner topology, identity residency, cross-border register).
- Effort excludes ongoing run and operations after week 58 and cloud/third-party usage fees.

## 10. Review history

| Round | Decision | Score | Findings (severity) |
| --- | --- | --- | --- |
| 1 | REWORK | 74.1 | high: Frontend selects React Native for both apps, with native mod, high: Database and cloud rely on a Spanner multi-region config 'sp, high: Identity Platform is the CIAM for millions of riders and dri, high: The NFR requires centralized logging, metrics, tracing and a, high: Data ownership differs across agents. Backend puts accounts,, medium: Backend places all microservices on GKE. Cloud runs dispatch, medium: Frontend selects shadcn/ui + Radix + Tailwind, while uiux se, medium: Frontend commits to WCAG 2.2 AA with 24×24px minimum targets, medium: Agents use different transports. Backend has drivers ingest , medium: Security specifies about 90 days of raw GPS retention, then , medium: Backend authorizes payment at booking and captures on comple, low: Database specifies Memorystore for Redis Cluster, while clou, low: The UI/UX wheelchair/UD taxi filter has no counterpart in th, low: The design combines Spanner multi-region, GKE in two regions |
| 2 | REWORK | 71.7 | high: The UI/UX output still chooses Flutter, a shared Flutter des, high: Backend still uses Identity Platform for rider and driver lo, high: Backend places accounts, fleet, support and pricing config i, high: The database agent still specifies Spanner multi-region asia, high: Security stores all customer identities in Keycloak on Cloud, medium: Backend runs all microservices on GKE. Cloud puts account, p, medium: Frontend selects Firebase Hosting for console static assets., medium: Frontend's real-time layer uses WebSocket for location and t, medium: Frontend's payment adapter includes IC/NFC (FeliCa) on the r, medium: Cloud Trace and OpenTelemetry need a catalogue exception, an, low: Backend uses a ~15s lock with sequential or batched rounds,  |
