# SaaS Invoice Management Application

**Status:** Escalated - needs human architect review  
**Run:** 3ecc0a32 - 2026-10-08 12:50  
**Domains:** fullstack, cloud

## 1. Executive summary

A fullstack SaaS application built with React, Node.js, and PostgreSQL that provides small businesses with invoice management capabilities and user authentication.

**Project type:** Fullstack SaaS Invoice Management Application - medium complexity. Involves fullstack development with React, Node.js, PostgreSQL, user authentication, and secure cloud deployment.

**At a glance:** 3 FTE team, about 70 person-days of effort, about 10 weeks to deliver.

**Reviewer:** The combined solution contains critical and high severity security and architectural conflicts that must be addressed before approval, specifically regarding SQL injection vulnerabilities, authorization checks, and inconsistent cloud hosting technology choices between agents.

## 2. Solution architecture

A fullstack SaaS application built with React, Node.js, and PostgreSQL that provides small businesses with invoice management capabilities and secure user authentication. It features a responsive user interface and robust cloud hosting on Google Cloud.

### 2.1 High-level solution architecture diagram

![High-level solution architecture](/api/runs/3ecc0a32/diagram.svg)

**Cloud:** Google Cloud. Boxes are grouped by layer and coloured by type (client system, proposed component, third-party, managed cloud service, AI, data store). Dashed boxes are recommended additions that the requirement did not state.

### 2.2 End-to-end data flow

**Invoice Management Flow**

- **1.** Small Business Owner → React Frontend: Interact with UI
- **2.** React Frontend → Authentication Module: Include JWT Token
- **3.** React Frontend → Node.js Backend API: HTTPS REST Request
- **4.** Node.js Backend API → PostgreSQL Database: Parameterized SQL Query
- **5.** PostgreSQL Database → Node.js Backend API: Return Query Result
- **6.** Node.js Backend API → React Frontend: JSON Response
- **7.** React Frontend → Small Business Owner: Render Updated View

### 2.3 Major components

| Layer | Component | Technology | Type | Status | Purpose |
| --- | --- | --- | --- | --- | --- |
| Users & stakeholders | Small Business Owner | - | actor | required | Creates, views, and tracks invoices for their business operations. |
| Users & stakeholders | Billing Administrator | - | actor | required | Manages user accounts and performs administrative invoice duties. |
| User / application layer | React Frontend | React | proposed | required | Provides a responsive user interface for invoice management and user authentication. |
| User / application layer | Authentication Module | JWT | proposed | required | Manages user login, registration, and stateless session tokens. |
| API & application services | Node.js Backend API | Node.js | proposed | required | Handles business logic, invoice CRUD operations, and request validation. |
| Data layer | PostgreSQL Database | PostgreSQL | data store | required | Persists user accounts, session data, and invoice records securely with ACID guarantees. |
| Cloud infrastructure & networking | Firebase Hosting | Firebase Hosting | cloud service | recommended | Delivers the React static frontend globally with low latency. |
| Cloud infrastructure & networking | Cloud Run Container | Cloud Run | cloud service | required | Hosts the Node.js backend container with auto-scaling capabilities. |
| Cloud infrastructure & networking | Cloud SQL Database | Cloud SQL | cloud service | required | Managed PostgreSQL service providing automated backups and relational storage. |
| Security | Secret Manager | Secret Manager | cloud service | recommended | Securely stores database credentials and JWT signing keys at rest. |

### 2.4 Requirement traceability

| Requirement | Delivered by |
| --- | --- |
| Users must be able to sign up and log in securely. | React Frontend, Authentication Module, Node.js Backend API, PostgreSQL Database |
| Users can create and save new invoices with line items. | React Frontend, Node.js Backend API, PostgreSQL Database |
| Users can view a list of all past and pending invoices. | React Frontend, Node.js Backend API, PostgreSQL Database |
| System must persist data in a PostgreSQL database. | PostgreSQL Database, Cloud SQL Database |
| Responsive design for desktop and tablet users | React Frontend, Firebase Hosting |
| Secure password hashing and session management | Authentication Module, Node.js Backend API, Secret Manager |

### 2.5 Key assumptions

- Standard cloud hosting infrastructure on Google Cloud will be utilized.
- Email service for password recovery will be integrated externally.
- Initial scale remains low to medium, fitting within single-region Cloud Run and Cloud SQL limits.

### 2.6 Recommended technology stack

| Layer | Technology | Purpose | Status |
| --- | --- | --- | --- |
| User / application layer | React | Frontend UI framework | required |
| User / application layer | Tailwind CSS | Utility-first CSS styling | recommended |
| User / application layer | TanStack Query | Server state management and caching | recommended |
| API & application services | Node.js | Backend runtime environment | required |
| API & application services | Express | REST API routing framework | recommended |
| Data layer | PostgreSQL | Relational data store for invoices and users | required |
| Cloud infrastructure & networking | Cloud Run | Serverless container compute platform | required |
| Cloud infrastructure & networking | Cloud SQL | Managed PostgreSQL database service | required |
| Cloud infrastructure & networking | Firebase Hosting | Static asset CDN hosting | recommended |
| Security | JWT | Stateless session authentication | required |
| Security | Secret Manager | Encrypted credential storage | recommended |

### 2.7 Security considerations

- Enforce HTTPS across all frontend and backend endpoints for secure data in transit.
- Hash all user passwords using bcrypt prior to storing them in PostgreSQL.
- Use parameterized queries to prevent SQL injection vulnerabilities.
- Implement strict CORS policies and tenant-level authorization checks to protect invoice data.

### 2.8 Scalability and future enhancements

**Scalability**

- Cloud Run automatically scales the Node.js backend containers up and down based on incoming traffic.
- Connection pooling is utilized in the backend to manage PostgreSQL connection limits efficiently.
- Pagination and cursor-based loading are implemented for large invoice history tables.

**Future enhancements**

- Direct payment gateway integrations for online invoice settlement.
- Automated multi-currency and complex tax calculation engines.
- Export capabilities for accounting software integrations.

## 3. Solution design

### Recommended architecture

**Style:** Modular Monolith / Serverless Container architecture

The solution implements a responsive React single-page application communicating via REST APIs with a Node.js Express backend service. The backend handles business logic, JWT authentication, and persists relational data securely in a PostgreSQL database hosted on Cloud SQL. Static assets are served globally via modern cloud hosting services.

- Frontend Presentation Layer: React single-page application with Tailwind CSS and TanStack Query
- API & Business Logic Layer: Node.js and Express REST API service deployed on Cloud Run
- Data & Security Layer: PostgreSQL relational database on Cloud SQL and Secret Manager for credentials

### Agents used

- **frontend**: needed for fullstack
- **backend**: needed for fullstack
- **database**: needed for fullstack
- **cloud**: needed for cloud, hosting/infrastructure is in scope
- **security**: needed for fullstack, needed for cloud
- **performance**: needed for fullstack, needed for cloud

### Components

| Component | Responsibility | From |
| --- | --- | --- |
| InvoiceDashboard | Displays the list of past and pending invoices with filtering and sorting capabilities. | frontend |
| InvoiceEditor | Form component for creating and updating invoices with dynamic line items. | frontend |
| AuthenticationModule | Manages user login, registration, and session token persistence. | frontend |
| API Service | Handles HTTP requests for user authentication, invoice CRUD operations, and business logic validation. | backend |
| Data Access Layer | Interacts with the PostgreSQL database using parameterized queries and connection pooling. | backend |
| Authentication Middleware | Verifies JWT tokens and enforces role-based access control for protected routes. | backend |
| Relational Database | Persist users, authentication details, invoices, and line items with ACID guarantees. | database, cloud |
| Frontend Hosting | Serves the React single-page application globally with low latency using Vercel. | cloud |
| Backend API Service | Executes the Node.js API logic, handling invoice management and business workflows via Cloud Run. | cloud |
| Authentication and Authorization | Handles secure user registration, credential verification, and stateless session management via JWT. | security |
| Secret Manager | Securely stores database connection strings, API keys, and JWT signing secrets at rest. | security |
| Frontend Performance Optimization | Ensuring fast initial load times, minimal bundle sizes, and optimal Core Web Vitals for the React UI. | performance |
| Data Caching and State Management | Minimizing redundant API calls for invoice lists and profile data using smart caching strategies. | performance |
| Backend and Database Scaling | Optimizing PostgreSQL query execution plans and Node.js throughput for invoice generation and retrieval. | performance |

### Recommended technology stack

| Category | Choice | Rationale | Alternatives | From |
| --- | --- | --- | --- | --- |
| frontend_framework | React | Mandated by the project requirements, offering a rich ecosystem and component-driven development. | Next.js, Vue | frontend, cloud |
| styling_ui | Tailwind CSS | Provides utility-first styling to rapidly build responsive desktop and tablet interfaces. | CSS Modules, Material UI | frontend |
| state_data_fetching | TanStack Query | Efficiently manages server state, caching, synchronization, and background updates for invoice data. | Zustand, Redux Toolkit | frontend, performance |
| backend_runtime | Node.js | Explicitly required in the brief and constraint checklist; excellent ecosystem for REST APIs. | Python, Go | backend, cloud |
| backend_runtime | Express | Lightweight and flexible web framework for Node.js to build RESTful routing rapidly. | NestJS | backend |
| api_style | REST | Standard HTTP methods match CRUD operations for invoices effectively. | GraphQL | backend |
| database | PostgreSQL | Mandatory database constraint with robust relational integrity for invoices, line items, and users. | MySQL, AlloyDB | backend, database, cloud |
| database | Cloud SQL | Fully managed PostgreSQL database service handling automated backups, replication, and maintenance. | AlloyDB, Spanner | cloud |
| auth | JWT | Stateless session management fulfilling the non-functional requirement for secure authentication. | Auth0, OAuth 2.0, Firebase Authentication, Keycloak | backend, cloud, security |
| gcp_compute_network | Cloud Run | Serverless container hosting ideal for small-to-medium Node.js backend scaling effortlessly. | Compute Engine, App Engine, GKE | backend, cloud |
| gcp_compute_network | Cloud Load Balancing | Ensures low-latency traffic routing and SSL termination at the edge for the Node.js backend API. | Compute Engine, App Engine | performance |
| gcp_ops_security | Secret Manager | Securely stores database connection strings and API keys away from source code. | Cloud KMS, IAM, Environment variables | cloud, security |
| hosting_static | Firebase Hosting | Aligns with cloud hosting requirements, providing fast global content delivery and secure static asset hosting. | Netlify | frontend, performance |
| hosting_static | Vercel | Provides fast global edge distribution and seamless CI/CD integration for the React frontend application. | Netlify | cloud |
| devops | Docker | Containerizes the Node.js application for consistent local execution and Cloud Run deployment. | Terraform, GitHub Actions | cloud |
| testing_quality | Playwright | Enables robust end-to-end testing of critical user journeys like authentication and invoice creation. | Vitest | frontend |
| testing_quality | axe-core | Ensures compliance with WCAG 2.2 AA accessibility requirements through automated testing. | Lighthouse | frontend |
| testing_quality | Jest | Industry-standard testing framework for Node.js unit and integration tests. | Vitest | backend |
| testing_quality | OWASP ZAP | Enables automated vulnerability scanning to detect common OWASP Top 10 risks in the web application. |  | security |
| testing_quality | k6 | Enables robust load and performance testing of Node.js endpoints and PostgreSQL queries under simulated peak business hours traffic. |  | performance |

**Unresolved conflicts:**

- hosting_static: frontend chose Firebase Hosting but cloud (owner of this decision) chose Vercel.
- hosting_static: performance chose Firebase Hosting but cloud (owner of this decision) chose Vercel.

## 4. Resources and estimate

### Required human resources

| Role | FTE | Seniority | Responsibilities | Phases |
| --- | --- | --- | --- | --- |
| Frontend Developer | 1 | mid | Build responsive React UI, components for invoice dashboards and editors, state management, and accessibility compliance. | Frontend build, Testing & hardening, Launch |
| Backend Developer | 1 | senior | Develop Node.js Express REST API, JWT authentication middleware, parameterized database queries, and cloud containerization. | Backend build, Testing & hardening, Launch |
| DevOps / Cloud Engineer | 0.5 | mid | Configure Google Cloud Run, Cloud SQL PostgreSQL, Vercel/Firebase hosting, CI/CD pipelines, and Secret Manager. | Discovery & design, Backend build, Launch |
| QA Engineer | 0.5 | mid | Perform E2E testing with Playwright, accessibility auditing with axe-core, security scans, and load testing with k6. | Testing & hardening |

**Team size:** 3 FTE across 4 roles.

### Required AI and technical resources

| Type | Resource | Purpose | Sizing |
| --- | --- | --- | --- |
| cloud compute | Google Cloud Run | Serverless container hosting for the Node.js backend API. | min 0 / max 10 instances, 1 vCPU / 512 MB RAM |
| database | Google Cloud SQL (PostgreSQL) | Managed relational database for users, invoices, and line items. | db-f1-micro or db-custom-1-3840, dev + staging + prod |
| dev tooling | Docker | Containerize the Node.js application for local and Cloud Run deployment. | Standard container runtime |
| hosting | Vercel / Firebase Hosting | Serve React frontend static assets globally with low latency. | Static tier, ~hundreds of initial users |
| testing | Playwright | End-to-end testing of critical user journeys. | CI test runner |
| testing | Jest | Backend unit and integration testing. | CI test runner |
| testing | k6 | Load and performance testing of backend endpoints. | Performance testing tool |
| third party service | Secret Manager | Securely store database connection strings and JWT secrets. | Standard managed secrets store |

_No AI models or services are needed for this solution._

### Estimated development effort

| Phase | Roles | Low | Likely | High |
| --- | --- | --- | --- | --- |
| Discovery & design | Frontend Developer, Backend Developer, DevOps / Cloud Engineer | 8 | 10 | 15 |
| Backend build | Backend Developer, DevOps / Cloud Engineer | 15 | 20 | 25 |
| Frontend build | Frontend Developer | 15 | 20 | 25 |
| Testing & hardening | Frontend Developer, Backend Developer, QA Engineer | 10 | 15 | 20 |
| Launch | Frontend Developer, Backend Developer, DevOps / Cloud Engineer | 3 | 5 | 8 |
| **Total (person-days)** | | **51** | **70** | **93** |

About **3.5 person-months** likely (20 working days per month).

### Estimated timeline

| Phase | Weeks | Duration | Depends on | Schedule |
| --- | --- | --- | --- | --- |
| Discovery & design | 1–2 | 2 wk | - | █████░░░░░░░░░░░░░░░░░░░ |
| Backend build | 3–6 | 4 wk | Discovery & design | ░░░░░██████████░░░░░░░░░ |
| Frontend build | 3–6 | 4 wk | Discovery & design | ░░░░░██████████░░░░░░░░░ |
| Testing & hardening | 7–9 | 3 wk | Backend build, Frontend build | ░░░░░░░░░░░░░░███████░░░ |
| Launch | 10 | 1 wk | Testing & hardening | ░░░░░░░░░░░░░░░░░░░░░░██ |

**Total: about 10 weeks** with the team above (range 7.3–13.3 weeks, following the effort range).

**What could change the estimate:**

- Unoptimized database queries or missing indexes causing slow response times on large invoice history tables.
- SQL injection or authorization flaws if tenant ownership checks are bypassed during invoice CRUD operations.
- Third-party SMTP email integration delays during password recovery implementation.

## 5. Specialist findings

### frontend

Frontend architecture recommendations for the SaaS Invoice Management Application utilizing React, Tailwind CSS, and TanStack Query, hosted on Firebase Hosting and adhering to WCAG 2.2 AA standards.

- Ensure all interactive elements meet WCAG 2.2 AA contrast ratios and keyboard navigation standards.
- Implement responsive layouts supporting desktop and tablet viewports.
- Use semantic HTML landmarks for improved screen reader compatibility.

### backend

Backend architecture design for the SaaS Invoice Management Application, utilizing Node.js, Express, PostgreSQL, and JWT authentication deployed on Cloud Run.

- All passwords must be hashed using bcrypt before persisting in PostgreSQL.
- Database connections should use pooling to manage resource limits efficiently under load.
- API endpoints must validate incoming payload schemas prior to executing business logic.

### database

Database and data storage design utilizing PostgreSQL for reliable relational data management of users, invoices, and line items.

- Data model must include users, invoices, and invoice_items tables with proper foreign key constraints.
- Indexes should be placed on user_id and invoice status fields to optimize list views and search queries.
- Ensure strict consistency for financial operations.

### cloud

Cloud architecture design for the SaaS Invoice Management Application on Google Cloud, utilizing Cloud Run for compute, Cloud SQL for the PostgreSQL database, and Vercel for static frontend hosting to align with unified frontend and performance requirements.

- The React frontend is built as a static bundle and deployed to Vercel.
- The Node.js backend runs inside container images hosted on Artifact Registry and deployed to Cloud Run.
- Cloud SQL PostgreSQL instance uses private IP connectivity within a VPC for secure database access.

### security

Security analysis updated to standardize on JWT for authentication, aligning with backend design and non-functional requirements.

- Enforce HTTPS for all data in transit across the React frontend and Node.js backend.
- Use parameterized queries in Node.js to completely prevent SQL injection attacks against the PostgreSQL database.
- Implement strict CORS policies on the backend API to restrict cross-origin requests.

### performance

Performance optimization strategy focusing on Core Web Vitals, efficient state caching for invoice data, API response times, and static asset delivery for the SaaS Invoice Management Application.

- Implement code-splitting in React to keep initial bundle sizes low and improve Largest Contentful Paint (LCP).
- Apply proper database indexing on foreign keys (e.g., user_id on the invoices table) to maintain fast search and filtering response times.
- Utilize HTTP caching headers for static assets and implement stale-while-revalidate patterns for client-side invoice lists.

## 6. Alternatives

Listed per technology choice in section 3.

## 7. Risks

| Risk | Severity | Likelihood | Mitigation | From |
| --- | --- | --- | --- | --- |
| SQL Injection attacks on the PostgreSQL database via unvalidated invoice search parameters. | critical | medium | Use parameterized queries and ORM query builders for all database interactions. | security |
| SQL injection vulnerability through improperly sanitized invoice search parameters. | high | medium | Use parameterized queries or an ORM with built-in protection against SQL injection. | backend |
| Broken Object Level Authorization allowing users to read or modify other businesses' invoices. | high | medium | Ensure server-side authorization checks validate that the authenticated tenant owns the requested invoice ID. | security |
| Complex invoice tables may degrade performance on lower-end tablet devices. | medium | low | Implement pagination or virtualized lists for invoice history tables. | frontend |
| Unindexed queries on invoice tables leading to poor performance as transaction volume grows. | medium | medium | Add indexes on foreign keys (user_id) and frequently queried fields (created_at, status). | database |
| Database connection exhaustion during sudden traffic spikes. | medium | low | Use connection pooling (such as PgBouncer) in the Node.js backend. | cloud |
| Slow response times when fetching large lists of past invoices for a single user. | medium | medium | Implement pagination and cursor-based loading for invoice lists instead of returning all historical records at once. | performance |
| Bundle size bloat from heavy third-party UI and utility packages in React. | low | high | Monitor bundle size during CI/CD pipelines and tree-shake unused imports. | performance |

## 8. Quality score

**Overall: 81.2/100**

| Dimension | Weight % | Score |
| --- | --- | --- |
| requirement_fit | 22.5 | 90 |
| architecture | 17.5 | 75 |
| security | 17.5 | 65 |
| reliability | 15.0 | 85 |
| performance | 12.5 | 85 |
| cost | 7.5 | 90 |
| maintainability | 7.5 | 85 |

Open blockers: critical finding open; high-severity finding open

## 9. Assumptions

- Standard cloud hosting infrastructure will be required.
- Email service for password recovery will be integrated.
- The backend API will provide standard REST endpoints for authentication and invoice CRUD operations.
- Frontend communicates with the backend via HTTPS REST endpoints.
- Database migrations are managed via a dedicated deployment script.
- PostgreSQL will be hosted on a managed cloud service.
- Backups will be configured automatically by the hosting provider.
- Initial user scale remains low to medium, fitting within single-region Cloud Run and Cloud SQL limits.
- Email delivery for password reset can be handled via an external SMTP provider.
- Standard cloud infrastructure will enforce TLS encryption for data in transit.
- Authentication tokens will be securely stored using modern browser storage best practices.
- Users will access the platform primarily on modern desktop and tablet browsers.
- Initial scale of hundreds of users will not require complex distributed caching layers like Redis immediately.
- Standard cloud hosting infrastructure and managed PostgreSQL are provisioned on Google Cloud.
- Email delivery service for password recovery will be integrated as an external third-party service.
- Initial user volume remains within hundreds of users, fitting standard single-region infrastructure limits.

## 10. Review history

| Round | Decision | Score | Findings (severity) |
| --- | --- | --- | --- |
| 1 | REWORK | 84.6 | high: Conflict in static hosting choice: Frontend and performance , high: Conflict in authentication approach: Backend agent chose sta, high: hosting_static: frontend chose Vercel but cloud (owner of th, high: hosting_static: performance chose Vercel but cloud (owner of |
| 2 | REWORK | 81.2 | critical: Unvalidated invoice search parameters present a high risk of, high: Potential Broken Object Level Authorization (BOLA) allowing , high: Conflicting technology choices for static frontend hosting b, high: hosting_static: frontend chose Firebase Hosting but cloud (o, high: hosting_static: performance chose Firebase Hosting but cloud |
