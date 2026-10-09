# MS SQL to Google Cloud Database Migration

**Status:** Approved by reviewer  
**Run:** b24faab1 - 2026-10-07 16:31  
**Domains:** fullstack, backend, cloud, data

## 1. Executive summary

Design a comprehensive zero-downtime database migration strategy from MS SQL to Google Cloud, incorporating real-time data synchronization, dashboard transition to Looker or Power BI, and rigorous validation steps to ensure data integrity.

**Reviewer:** The combined solution rigorously addresses all core requirements for a zero-downtime MS SQL to Google Cloud database migration. It leverages AlloyDB and BigQuery appropriately, establishes a robust CDC replication pipeline using Dataflow, ensures enterprise security via TLS 1.3, AES-256, IAM, and Secret Manager, and maintains clear alignment with performance and compliance goals. No critical or high severity findings exist.

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
| Migration Orchestration Service | Manage schema conversion, initial bulk data load, and coordinate cutover steps from source MS SQL to target Google Cloud database. | backend |
| Real-time CDC Synchronization Pipeline | Capture change data from source transaction logs or CDC tables and stream low-latency updates to the target database. | backend |
| Data Validation and Reconciliation Engine | Execute automated row counts, cryptographic checksums, and parallel read/write validation to ensure zero data loss. | backend |
| Transactional Target Database | Store core relational transactional data with high performance compatibility. | database |
| Analytical Data Warehouse | Handle intensive BI reporting workloads and dashboard connectivity for Looker or Power BI. | database |
| Data Replication Pipeline | Execute continuous real-time Change Data Capture (CDC) from MS SQL to Google Cloud. | database |
| Target Database | High-performance PostgreSQL-compatible operational database hosted on Google Cloud. | cloud |
| Data Migration & Sync Pipeline | Real-time change data capture (CDC) and initial load synchronization from MS SQL to Google Cloud. | cloud |
| Operational Security & Management | Enforce encryption, least-privilege IAM controls, and secure hybrid connectivity. | cloud |
| Identity and Access Management | Enforce strict least-privilege role-based access control for database administrators, data engineers, and BI consumers. | security |
| Data Protection in Transit and At Rest | Ensure all database traffic is encrypted using TLS 1.3 and stored data is protected using AES-256 via customer-managed or Google Cloud-managed encryption keys. | security |
| Secret Management | Securely store and manage database connection strings, credentials, and replication keys. | security |
| Data Synchronization Pipeline | Handle real-time change data capture (CDC) streaming from MS SQL to target Google Cloud databases with minimal replication lag. | performance |
| Analytical Reporting Optimization | Ensure high-performance query execution for migrated BI workloads (Looker/Power BI) via proper indexing and scaling. | performance |

### Technology choices

| Category | Choice | Rationale | Alternatives | From |
| --- | --- | --- | --- | --- |
| backend_runtime | Python | Extensive library ecosystem for data processing, database connectivity, and automated validation scripts. | Go, Java | backend |
| api_style | REST | Simple and standard interface style for orchestrating migration control plane operations and status checks. | gRPC | backend |
| database | AlloyDB | High-performance PostgreSQL-compatible managed database service on Google Cloud suited for demanding enterprise transactional and analytical workloads. | Cloud SQL, Spanner | backend, database, cloud, performance |
| database | BigQuery | Enterprise data warehouse ideal for offloading heavy analytical workloads and connecting downstream BI dashboards like Looker. | Cloud SQL | backend, database, performance |
| gcp_compute_network | VPC | Provides secure, isolated networking infrastructure and private connectivity via Cloud VPN or Interconnect from the source environment. | Cloud Load Balancing, Compute Engine | cloud |
| gcp_data_messaging | Dataflow | Managed stream and batch data processing service built on Apache Beam for reliable real-time change data capture pipelines. | Pub/Sub, Dataproc | backend, database, cloud, performance |
| gcp_ops_security | Secret Manager | Securely store database connection strings, credentials, and cryptographic keys required during migration. | HashiCorp Vault, Environment Variables | backend, cloud, security |
| gcp_ops_security | IAM | Enforce least-privilege access control across migration services and Google Cloud database instances. | Keycloak, VPC Service Controls, Cloud Identity | backend, security |
| gcp_ops_security | Cloud KMS | Ensures robust AES-256 encryption at rest for target databases (AlloyDB/Cloud SQL) using managed keys satisfying compliance mandates. | External Key Manager, Default Google-managed keys | security |
| devops | Terraform | Infrastructure as Code to provision Google Cloud database, networking, and migration pipelines reproducibly. | Kubernetes, Docker, GitHub Actions | backend, cloud |
| testing_quality | pytest | Robust testing framework for running automated data reconciliation and schema validation checks. | Jest | backend |
| testing_quality | k6 | Validates database and pipeline performance under simulated peak transaction loads prior to production cutover. |  | performance |

## 3. Specialist findings

### frontend

No frontend application or UI deliverables are included in this architecture as custom management dashboard development is out of scope for this database migration project.

- None stated

### backend

Backend architecture design for zero-downtime database migration from MS SQL to Google Cloud AlloyDB using Dataflow for real-time CDC, Python for migration tooling and validation, and IAM/Secret Manager for enterprise security compliance.

- Establish secure VPC network connectivity via Cloud VPN or Interconnect between the on-premises or source MS SQL environment and Google Cloud.
- Implement a phased migration pattern: schema conversion, initial snapshot load, continuous CDC synchronization, validation, and final DNS/connection string cutover.
- Configure TLS 1.3 for all in-flight data replication streams and AES-256 for data at rest on AlloyDB.

### database

Database storage strategy and migration design for moving from MS SQL to Google Cloud using AlloyDB for PostgreSQL, BigQuery for analytics, and Dataflow for real-time CDC synchronization.

- Use automated schema conversion tools to map T-SQL schemas, stored procedures, and triggers to PostgreSQL equivalents.
- Implement dual-write or continuous CDC replication using Dataflow with transaction log readers to ensure zero data loss.
- Perform parallel read/write data validation and cryptographic checksum verification prior to final cutover.

### cloud

Cloud architecture design for zero-downtime MS SQL to Google Cloud database migration using AlloyDB, Dataflow for CDC replication, and Looker/Power BI integration.

- Execute schema conversion from T-SQL to PostgreSQL using automated assessment tools prior to initial bulk load.
- Establish initial data snapshot load followed by continuous CDC replication to maintain minimal delta during cutover.
- Implement cryptographic checksum reconciliation routines to verify 100% data integrity between source and target.
- Repoint BI dashboards (Looker / Power BI) to the target database endpoint during a designated maintenance window with low RTO.

### security

Security, access control, and data protection strategy for zero-downtime database migration from MS SQL to Google Cloud enforcing TLS 1.3, AES-256 encryption at rest, least-privilege IAM, and APPI compliance.

- All replication traffic between MS SQL and Google Cloud must traverse secure TLS 1.3 encrypted tunnels.
- Database credentials must never be hardcoded and should be fetched dynamically via Secret Manager.
- Audit logging must be enabled for all data access and schema modification events to maintain compliance with APPI and enterprise security policies.

### performance

Performance optimization strategy for MS SQL to Google Cloud database migration, focusing on high-throughput CDC data streaming, low-latency analytical queries for BI reporting, and minimal RPO/RTO metrics.

- Utilize streaming dataflow jobs to process change logs continuously with near-zero RPO.
- Perform index rebuilding and query execution plan analysis on the target database to prevent regression on analytical dashboards.
- Implement connection pooling on backend services to handle spikes during traffic shifting.

## 4. Alternatives

Listed per technology choice in section 2.

## 5. Risks

| Risk | Severity | Likelihood | Mitigation | From |
| --- | --- | --- | --- | --- |
| Data drift or replication lag during the real-time CDC phase leading to out-of-sync records at cutover. | critical | medium | Run continuous cryptographic checksum reconciliation jobs and execute a brief read-only freeze window during final cutover if necessary. | backend |
| Schema incompatibility or T-SQL specific procedural code (stored procedures, triggers) failing during conversion to PostgreSQL. | high | high | Use automated schema assessment tools early, rewrite complex T-SQL objects into compatible PL/pgSQL or application-tier logic. | backend |
| Complex T-SQL stored procedures and triggers may fail or behave differently in PostgreSQL. | high | medium | Perform dry-run schema conversions early and refactor complex procedural logic into application tier or pl/pgSQL equivalents. | database |
| Replication lag during peak loads leading to data inconsistency at cutover. | high | low | Monitor pipeline metrics continuously and execute a scheduled brief maintenance window for final cutover after replication lag reaches zero. | database |
| Schema conversion incompatibilities between T-SQL and PostgreSQL requiring manual query and stored procedure rewrites. | high | high | Perform thorough dry-run schema translation assessments early and refactor database procedures iteratively. | cloud |
| Unauthorized access to migration pipeline or replication endpoints leading to data exposure. | high | medium | Enforce strict IAM role-based access control, IP whitelisting, and private network routing via VPC. | security |
| Exposure of database credentials during migration configuration. | high | low | Store all connection strings and credentials securely in Secret Manager with automated rotation where applicable. | security |
| High replication lag during peak transactional hours leading to stale data on BI dashboards. | high | medium | Scale Dataflow worker nodes horizontally and optimize batching sizes for CDC event streams. | performance |
| Replication lag during peak transactional load leading to data divergence during cutover. | medium | medium | Scale Dataflow worker pools appropriately and monitor replication latency continuously via Cloud Monitoring. | cloud |
| Query performance degradation on analytical dashboards after transitioning to the target cloud database. | medium | medium | Offload heavy analytical queries to BigQuery and pre-aggregate reporting data. | performance |

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

- Source MS SQL database allows CDC or transaction log reading
- Sufficient network bandwidth and secure tunnels (Cloud VPN / Interconnect) exist between source environment and Google Cloud
- Dashboard consumers can tolerate scheduled maintenance windows for final BI endpoint repointing if necessary
- No custom frontend applications need to be built or maintained for this migration.
- Source MS SQL database permits CDC activation or transaction log access.
- Network bandwidth between source and Google Cloud is adequate to sustain peak replication throughput.
- Source MS SQL database allows CDC or transaction log reading.
- Sufficient network bandwidth and secure VPN/Interconnect links exist between source environment and Google Cloud.
- Source MS SQL database allows transaction log reading and CDC configuration.
- Adequate hybrid network bandwidth exists between the on-premises or source cloud environment and Google Cloud.
- Source MS SQL environment supports secure encrypted connections and log reading permissions.
- Google Cloud environment is configured with appropriate organizational policies supporting AES-256 encryption.
- Source MS SQL database server has adequate CPU and I/O headroom to support CDC operations without impacting primary application performance.
- Network throughput between on-premises/source environment and Google Cloud meets real-time replication requirements.

## 8. Review history

| Round | Decision | Score | Findings (severity) |
| --- | --- | --- | --- |
| 1 | REWORK | 84.5 | high: The solution includes a custom frontend React application an |
| 2 | APPROVED | 91.9 | none |
