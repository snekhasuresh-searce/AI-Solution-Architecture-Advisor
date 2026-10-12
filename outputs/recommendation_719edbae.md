# Database Migration from MS SQL to Google Cloud

**Status:** Approved by reviewer  
**Run:** 719edbae - 2026-10-07 15:49  
**Domains:** fullstack, backend, cloud, data

## 1. Executive summary

Design a comprehensive zero-downtime database migration strategy from MS SQL to Google Cloud, including dashboard transition, real-time data synchronization, and rigorous validation steps.

**Reviewer:** The combined solution thoroughly addresses all requirements for the zero-downtime database migration from MS SQL to Google Cloud using robust services like AlloyDB, Dataflow, Cloud VPN, and Secret Manager. Security, performance, and operational constraints are well-managed across all specialist agents with clear risk mitigations.

## 2. Solution design

### Agents used

- **frontend**: needed for fullstack
- **backend**: needed for fullstack, needed for backend
- **database**: needed for fullstack, needed for backend, needed for data
- **cloud**: needed for cloud, needed for data, hosting/infrastructure is in scope
- **security**: needed for fullstack, needed for backend, needed for cloud, needed for data
- **performance**: needed for fullstack, needed for backend, needed for cloud

### Components

| Component | Responsibility | From |
| --- | --- | --- |
| MigrationDashboard | Main layout and overview screen presenting overall migration progress, system health, and RPO/RTO metrics. | frontend |
| SyncStatusMonitor | Real-time component displaying replication lag, CDC stream health, and throughput between MS SQL and Google Cloud. | frontend |
| ValidationConsole | Interface for viewing schema verification reports, checksum discrepancies, and row-count reconciliation. | frontend |
| CutoverController | Restricted-access control panel to execute cutover steps, traffic shifting switches, and emergency rollback procedures. | frontend |
| Migration Orchestration Service | Manages schema translation mapping, initial full database dump loading, and coordinates CDC replication pipelines. | backend |
| Data Validation and Checksum Service | Executes parallel read/write data integrity verification, record count comparison, and cryptographic checksum validation between source and target. | backend |
| API and Traffic Shifting Layer | Handles gradual traffic routing, connection string updates, and failover or rollback execution for backend services and dashboards. | backend |
| Target Operational Database | Store enterprise relational data with high availability and transactional consistency in Google Cloud. | database |
| Analytical Workload Store | Handle heavy analytical queries and dashboard reporting offloaded from the transactional database. | database |
| Data Migration Pipeline | Handle initial data dump and ongoing real-time Change Data Capture (CDC) synchronization. | database |
| Target Database | High-throughput managed PostgreSQL-compatible transactional storage utilizing AlloyDB for enterprise performance. | cloud |
| Data Migration and Replication | Orchestrates initial schema dump, data load, and real-time Change Data Capture (CDC) synchronization. | cloud |
| Networking and Security | Provides encrypted tunnel from on-premises MS SQL to Google Cloud, manages database credentials and access controls. | cloud |
| Secret Management | Securely store and manage database connection strings, credentials, and TLS certificates using dedicated Google Cloud security services. | security |
| Data Encryption and Compliance | Enforce TLS 1.3 in transit and AES-256 encryption at rest to satisfy APPI and industry data protection standards. | security |
| Access Control (IAM) | Implement strict principle of least privilege across migration tools, database administrators, and application runtimes. | security |
| Database Migration Engine | Handles high-throughput initial data dumps and real-time change data capture (CDC) streaming to ensure zero data loss. | performance |
| Target Database Scalability & Caching | Ensures the Google Cloud managed database is provisioned with appropriate compute sizing, connection pooling, and caching to sustain enterprise production workloads. | performance |
| Validation and Performance Testing | Executes load and stress tests against the target database infrastructure prior to final cutover. | performance |

### Technology choices

| Category | Choice | Rationale | Alternatives | From |
| --- | --- | --- | --- | --- |
| frontend_framework | React | Provides a robust ecosystem and component architecture ideal for complex, data-heavy enterprise dashboards. | Angular, Vue | frontend |
| styling_ui | Tailwind CSS | Enables rapid, consistent styling with built-in design tokens and responsive utility classes. | Material UI, CSS Modules | frontend |
| state_data_fetching | TanStack Query | Essential for managing server state, automatic background polling, and real-time synchronization metrics from the migration backend. | Zustand, Redux Toolkit | frontend |
| backend_runtime | Python | Provides extensive libraries and database drivers for scripting schema assessment, custom validation logic, and migration orchestration. | Go, Node.js | backend |
| api_style | REST | Standard HTTP APIs to manage migration status, run checksum triggers, and check health indicators during cutover. | gRPC, OpenAPI | backend |
| database | AlloyDB | Fully managed, PostgreSQL-compatible relational database service providing high performance, high throughput, and robust enterprise scalability required for this migration. | Cloud SQL, Spanner | backend, database, cloud, performance |
| database | BigQuery | Enables high-performance analytical queries and dashboard reporting without impacting core transactional workloads. | Cloud SQL | database |
| auth | IAM | Provides secure, role-based access control and strict security standards matching enterprise compliance needs on Google Cloud. | OAuth 2.0, Keycloak | backend |
| gcp_compute_network | Cloud Run | Serverless execution environment to host lightweight migration workers, orchestration scripts, and validation tasks on-demand. | Compute Engine, GKE | backend |
| gcp_compute_network | VPC | Establishes secure, isolated virtual network infrastructure with custom subnets and VPN connectivity to on-prem MS SQL environments. | Cloud Load Balancing | cloud |
| gcp_data_messaging | Dataflow | Enables reliable real-time change data capture (CDC) streaming and transformations from source MS SQL to Google Cloud target. | Pub/Sub, Cloud Storage, Dataproc, Cloud Composer | backend, database, cloud, performance |
| gcp_ops_security | Secret Manager | Safely stores database connection credentials, API keys, and encryption keys with auditing capabilities. | HashiCorp Vault | backend, cloud, security |
| gcp_ops_security | IAM | Enforces principle of least privilege for database administrators, applications, and migration pipelines. | Identity Platform, Third-party Identity Providers | cloud, security |
| gcp_ops_security | Cloud KMS | Provides customer-managed encryption keys (CMEK) to enforce AES-256 encryption standards for data at rest on Google Cloud databases. | External Key Manager | security |
| hosting_static | Firebase Hosting | Provides secure, fast global content delivery for the enterprise dashboard with seamless integration into Google Cloud IAM. | Vercel, Netlify | frontend |
| devops | Terraform | Enables Infrastructure as Code (IaC) for reproducible target environments and network tunnels between MS SQL and Google Cloud. | GitHub Actions, Docker | backend |
| testing_quality | Playwright | Ensures reliable end-to-end testing for critical cutover workflows and dashboard state transitions. | Cypress, Vitest | frontend |
| testing_quality | pytest | Robust testing framework to automate data consistency, schema validation, and migration script verification steps. | Jest | backend |
| testing_quality | k6 | Allows scriptable, high-concurrency load and performance testing to validate target database performance characteristics and query latencies under enterprise transaction volumes. | Jest | performance |

## 3. Specialist findings

### frontend

Frontend architecture recommendations for the Database Migration dashboard application, ensuring robust real-time monitoring of migration status, data synchronization metrics, and cutover controls with strict WCAG 2.2 AA compliance.

- Adopt a single-page application (SPA) architecture for snappy interactions during high-stress cutover windows.
- Implement WCAG 2.2 AA compliance standards, ensuring sufficient contrast for status indicators (green/yellow/red replication health) and full keyboard navigation support.
- Utilize strict role-based view rendering to restrict cutover and rollback triggers to authorized SREs and Database Administrators.

### backend

Architecture design for zero-downtime database migration from MS SQL to Google Cloud using managed cloud database services and real-time data replication.

- Establish secure VPN or Dedicated Interconnect between on-premise/source MS SQL and Google Cloud VPC.
- Perform schema conversion mapping addressing T-SQL specific constructs into PostgreSQL / AlloyDB compatible syntax.
- Execute initial bulk snapshot loading, followed by continuous CDC stream to achieve RPO = 0.
- Run dual-write or dual-read validation phases with automated checksum verification before final DNS cutover.

### database

Design for database migration from MS SQL to Google Cloud featuring zero-downtime replication, schema transformation, and strict data validation.

- Perform schema conversion mapping from T-SQL to PostgreSQL syntax prior to initial data load.
- Establish secure VPN or Interconnect tunnels between source MS SQL environment and Google Cloud VPC.
- Implement dual-write or CDC replication pipeline using Dataflow to ensure RPO = 0 during migration.
- Execute rigorous row-count and checksum validation checks before finalizing cutover.

### cloud

Cloud architecture design for zero-downtime database migration from MS SQL to Google Cloud using AlloyDB, Dataflow for replication pipelines, Cloud VPN for secure connectivity, and IAM with Secret Manager for robust security and compliance.

- Establish a hybrid cloud connection via Cloud VPN or Partner Interconnect to secure data transit from MS SQL source.
- Execute initial full database dump and restore to AlloyDB during a low-traffic window.
- Set up continuous Change Data Capture (CDC) replication to maintain zero RPO during the synchronization phase.
- Perform dual-writes or read-redirection tests to validate data consistency prior to final cutover.
- Maintain RTO under 30 minutes via automated DNS switching and rollback procedures.

### security

Security and compliance review for zero-downtime database migration from MS SQL to Google Cloud, ensuring adherence to APPI, TLS 1.3, AES-256 encryption at rest, and robust secret management.

- Mandate TLS 1.3 for all database connection strings and active replication tunnels between MS SQL and Google Cloud.
- Ensure all migrated tables and backups in Cloud SQL or AlloyDB are encrypted using customer-managed keys via Cloud KMS.
- Audit all cross-network replication streams to prevent unauthorized data interception.

### performance

Performance optimization, scalability planning, and zero-downtime execution strategy for migrating core databases from MS SQL to Google Cloud with RPO=0 and RTO<30 minutes.

- Utilize connection pooling on the target Google Cloud database layer to prevent connection spikes from upstream backend services during cutover.
- Implement asynchronous CDC streaming via Dataflow to mirror MS SQL transaction logs with near-zero latency, protecting source database performance.
- Perform parallel read/write verification phases to confirm data consistency without introducing blocking locks.

## 4. Alternatives

Listed per technology choice in section 2.

## 5. Risks

| Risk | Severity | Likelihood | Mitigation | From |
| --- | --- | --- | --- | --- |
| Data drift or synchronization lag during the CDC replication phase. | critical | medium | Perform continuous automated checksum validations and pause write traffic briefly for final sync during the maintenance window. | backend |
| Replication lag causing data inconsistency during the dual-write or CDC window. | critical | low | Monitor replication lag continuously via Cloud Monitoring, and perform final cutover only when replication lag is zero and read-only mode is engaged on the source. | database |
| Data drift or sync lag during the CDC replication phase before cutover. | critical | medium | Execute automated periodic checksum validation checks and dual-read validation before final traffic shift. | cloud |
| Credentials for MS SQL or Google Cloud exposed in migration configuration scripts or logs. | critical | medium | Utilize Secret Manager for all credentials and sanitize pipeline logs. | security |
| Stale dashboard state during critical cutover phases leading to incorrect operator actions. | high | medium | Integrate websocket or aggressive polling intervals via TanStack Query for real-time synchronization feeds. | frontend |
| Incompatible T-SQL functions or stored procedures breaking application queries after cutover. | high | medium | Conduct rigorous schema assessment mapping and pre-migration query dry-runs in a staging environment. | backend |
| Schema incompatibility or unsupported stored procedures causing application errors post-migration. | high | medium | Conduct rigorous schema assessment and refactor complex T-SQL stored procedures into application logic or PostgreSQL-compatible functions prior to cutover. | database |
| Schema incompatibility or syntax conversion errors between MS SQL and PostgreSQL. | high | high | Perform extensive pre-migration schema assessment, schema conversion mapping, and validation testing. | cloud |
| Data leakage or unauthorized access during the real-time change data capture (CDC) replication phase. | high | low | Enforce TLS 1.3 encryption across all replication tunnels and restrict network routing via secure VPC configurations. | security |
| Replication lag during peak transaction hours causing synchronization delays between MS SQL and Google Cloud. | high | medium | Scale out the Dataflow streaming workers and provision high-throughput network paths with provisioned IOPS on the target database. | performance |
| Connection exhaustion on the target database instance when dependent dashboards and backends switch over simultaneously. | high | low | Deploy built-in connection poolers (e.g., PgBouncer) and execute gradual traffic shifting. | performance |
| Accessibility failures for color-blind operators monitoring alert states. | medium | medium | Ensure all status indicators utilize distinct icons and text labels alongside color coding to meet WCAG 2.2 AA requirements. | frontend |

## 6. Quality score

**Overall: 91.9/100**

| Dimension | Weight % | Score |
| --- | --- | --- |
| requirement_fit | 22.5 | 95 |
| architecture | 18.75 | 90 |
| security | 17.5 | 95 |
| reliability | 12.5 | 90 |
| performance | 10.0 | 90 |
| cost | 7.5 | 85 |
| maintainability | 6.25 | 90 |
| scalability | 5.0 | 95 |

## 7. Assumptions

- Source MS SQL database is accessible via secure network tunnels or VPN to Google Cloud
- Target Google Cloud database can accommodate schema differences or appropriate schema refactoring has been planned
- Dashboard and backend applications can be updated to point to the new connection endpoints with minimal reconfiguration
- Dashboard users access the application via modern browsers over secure networks.
- Backend APIs provide structured JSON endpoints for real-time migration metrics and CDC status.
- Network connectivity with sufficient bandwidth is available between source MS SQL environment and Google Cloud.
- Upstream application code changes are strictly limited to updating database connection strings and syntax adjustments.
- Maintenance windows can be scheduled for final DNS switch and application cutover if necessary.
- Source MS SQL database network allows secure inbound connections from Google Cloud migration tools.
- Target database can accommodate schema differences or appropriate refactoring has been scheduled.
- Source MS SQL database allows CDC or transaction log reading for real-time replication.
- Applications can tolerate minimal connection resets during final configuration switch.
- Source MS SQL environment supports secure TLS 1.3 connections.
- Network tunnels between on-premises/source and Google Cloud comply with corporate security baselines.
- Source MS SQL database network bandwidth is sufficient to support concurrent CDC streams without degrading source application performance.
- Target Google Cloud database tier is scaled to handle peak enterprise transaction throughput from day one.

## 8. Review history

| Round | Decision | Score | Findings (severity) |
| --- | --- | --- | --- |
| 1 | APPROVED | 91.9 | none |
