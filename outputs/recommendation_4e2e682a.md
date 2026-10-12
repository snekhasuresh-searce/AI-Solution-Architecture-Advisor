# Company Website Frontend

**Status:** Approved by reviewer  
**Run:** 4e2e682a - 2026-10-08 12:49  
**Domains:** frontend

## 1. Executive summary

A responsive frontend company website consisting of Home, About, Services, and Contact pages, compatible with both mobile and desktop devices.

**Project type:** Static marketing website frontend - small complexity. The project is a simple 4-page static website with no backend services, database storage, or user authentication requirements.

**At a glance:** 1.5 FTE team, about 18 person-days of effort, about 5 weeks to deliver.

**Reviewer:** The combined solution fully satisfies the frontend company website requirements, featuring a clean Astro and Tailwind CSS stack, solid accessibility commitments, and robust static hosting plans with no critical or high severity findings.

## 2. Solution architecture

A high-performance, responsive company website featuring Home, About, Services, and Contact pages built with Astro and Tailwind CSS. The architecture prioritizes lightning-fast load times, exceptional accessibility compliance, and secure static deployment via Netlify.

### 2.1 High-level solution architecture diagram

![High-level solution architecture](/api/runs/4e2e682a/diagram.svg)

**Cloud:** To be confirmed. Boxes are grouped by layer and coloured by type (client system, proposed component, third-party, managed cloud service, AI, data store). Dashed boxes are recommended additions that the requirement did not state.

### 2.2 End-to-end data flow

**Website Navigation Request**

- **1.** Prospective Clients → Static CDN Hosting: HTTPS Request
- **2.** Static CDN Hosting → Frontend Web App: Serve Static HTML
- **3.** Frontend Web App → UI Component Library: Render Tailwind Layout
- **4.** Frontend Web App → Prospective Clients: Return Page Content

### 2.3 Major components

| Layer | Component | Technology | Type | Status | Purpose |
| --- | --- | --- | --- | --- | --- |
| Users & stakeholders | Prospective Clients | - | actor | required | End users visiting the company website to view information and contact the business. |
| User / application layer | Frontend Web App | Astro | proposed | required | Delivers zero-JS by default static pages for Home, About, Services, and Contact ensuring fast load times. |
| User / application layer | UI Component Library | Tailwind CSS | proposed | required | Provides responsive layouts, styling, and mobile-first design using utility classes. |
| External integrations | Contact Form Handler | Netlify Forms | third party | recommended | Manages contact form submissions without requiring a dedicated custom backend. |
| Cloud infrastructure & networking | Static CDN Hosting | Netlify | cloud service | recommended | Ensures global CDN delivery and automated CI/CD deployment for the static site. |
| Security | Content Security Policy | OWASP ZAP | proposed | recommended | Enforces secure browser headers and prevents XSS vulnerabilities. |
| Monitoring & operations | Performance Audit | Lighthouse | proposed | recommended | Automates audits to maintain optimal Core Web Vitals thresholds. |

### 2.4 Requirement traceability

| Requirement | Delivered by |
| --- | --- |
| Navigation menu across all pages | Frontend Web App, UI Component Library |
| Contact form UI without backend processing | Frontend Web App, Contact Form Handler |
| Responsive layout adapting to various screen sizes | Frontend Web App, UI Component Library |
| Fast load times | Frontend Web App, Static CDN Hosting |
| Accessible design | Frontend Web App, UI Component Library |
| Cross-browser compatibility | Frontend Web App |

### 2.5 Key assumptions

- Contact form will be handled by a third-party service or mailto link.
- Static hosting will be used with CI/CD deployment pipelines.
- All copy and visual assets for the four core pages will be provided upfront.
- No dynamic backend database or custom server logic is required.

### 2.6 Recommended technology stack

| Layer | Technology | Purpose | Status |
| --- | --- | --- | --- |
| User / application layer | Astro | Static site generation and zero-JS framework | required |
| User / application layer | Tailwind CSS | Responsive styling and utility classes | required |
| External integrations | Netlify Forms | Serverless contact form processing | recommended |
| Cloud infrastructure & networking | Netlify | Global CDN static hosting and deployment | recommended |
| Security | OWASP ZAP | Security header and vulnerability scanning | recommended |
| Monitoring & operations | Lighthouse | Core Web Vitals and accessibility auditing | recommended |

### 2.7 Security considerations

- Configure strict Content Security Policy (CSP), X-Frame-Options, and X-Content-Type-Options headers.
- Sanitize all contact form inputs to prevent DOM-based XSS if user data is reflected.
- Ensure all static assets and communications are served exclusively over HTTPS.
- Utilize Subresource Integrity (SRI) for any external scripts or assets.

### 2.8 Scalability and future enhancements

**Scalability**

- Static CDN edge caching naturally handles spikes in standard business traffic without server strain.
- Purged Tailwind CSS bundles minimize bandwidth consumption on mobile devices.
- Optimized image delivery via modern formats ensures rapid Largest Contentful Paint (LCP).

**Future enhancements**

- Integrate a headless CMS for dynamic content and blog management.
- Add multi-language localization support for international audiences.
- Implement advanced analytics and conversion tracking on the contact form.

## 3. Solution design

### Recommended architecture

**Style:** Jamstack static site

The architecture utilizes Astro to render static HTML pages by default, ensuring fast load times and zero unnecessary JavaScript overhead. Tailwind CSS is applied using a mobile-first approach with utility classes for rapid, responsive design across all viewports. The entire static site is deployed to Netlify via a continuous integration pipeline, leveraging global CDN distribution for fast asset delivery.

- Presentation Layer: Astro components rendering static HTML and Tailwind CSS styles
- Hosting Layer: Netlify global CDN delivering static assets and handling edge caching

### Agents used

- **frontend**: needed for frontend
- **uiux**: needed for frontend
- **security**: needed for frontend
- **performance**: needed for frontend

### Components

| Component | Responsibility | From |
| --- | --- | --- |
| NavigationHeader | Provides global responsive navigation across Home, About, Services, and Contact pages. | frontend |
| ContactForm | Renders contact inputs with client-side validation and form state handling. | frontend |
| Footer | Displays copyright information, links, and secondary navigation. | frontend |
| Navigation Bar | Provide consistent header navigation across Home, About, Services, and Contact pages with responsive mobile drawer. | uiux |
| Hero Section | Engage visitors on the Home page with a primary value proposition and call-to-action. | uiux |
| Services Grid | Display company service offerings in a responsive card layout. | uiux |
| Contact Form UI | Collect user inquiries via standard form inputs without server-side processing. | uiux |
| Content Security Policy | Enforce strict browser-side resource loading policies to mitigate XSS risks. | security |
| Static Hosting Security | Ensure secure transport via HTTPS and secure headers on static assets. | security |
| Static Asset Delivery | Ensuring fast load times and global distribution of static assets. | performance |
| Bundle Optimization | Minimizing JavaScript and CSS footprint for optimal Core Web Vitals. | performance |

### Recommended technology stack

| Category | Choice | Rationale | Alternatives | From |
| --- | --- | --- | --- | --- |
| frontend_framework | Astro | Optimized for content-driven static marketing sites with zero-JS by default, ensuring fast load times. | Next.js, React | frontend, uiux, performance |
| styling_ui | Tailwind CSS | Enables rapid, consistent responsive design using utility classes without heavy runtime CSS overhead. | CSS Modules, shadcn/ui | frontend, uiux, performance |
| hosting_static | Netlify | Ideal for static site deployments with continuous integration and global CDN delivery. | Vercel, Firebase Hosting | frontend, uiux, performance |
| testing_quality | Playwright | Ensures cross-browser compatibility and end-to-end user flow correctness. | Vitest | frontend, uiux |
| testing_quality | axe-core | Automates accessibility checks to guarantee WCAG 2.2 AA compliance. |  | frontend |
| testing_quality | OWASP ZAP | Used to scan the frontend deployment for common web vulnerabilities such as missing security headers. |  | security |
| testing_quality | Lighthouse | Automated performance auditing to track and maintain Core Web Vitals thresholds. |  | performance |

## 4. Resources and estimate

### Required human resources

| Role | FTE | Seniority | Responsibilities | Phases |
| --- | --- | --- | --- | --- |
| Frontend Developer | 1 | mid | Develops the Astro pages, navigation, components, and Tailwind styling. | Discovery & design, Frontend build, Testing & hardening, Launch |
| UI/UX Designer | 0.5 | mid | Provides wireframes, visual design guidelines, and accessibility checks. | Discovery & design, Testing & hardening |

**Team size:** 1.5 FTE across 2 roles.

### Required AI and technical resources

| Type | Resource | Purpose | Sizing |
| --- | --- | --- | --- |
| dev tooling | Astro | Frontend framework for generating fast static HTML with zero-JS by default | Latest stable release |
| dev tooling | Tailwind CSS | Utility-first CSS framework for responsive design | Latest stable release with purging enabled |
| hosting | Netlify | Static site hosting with continuous integration and global CDN delivery | Free / Starter tier, suitable for standard business traffic |
| testing | Playwright | End-to-end testing and cross-browser compatibility verification | Local development and CI pipeline execution |
| testing | axe-core | Automated accessibility testing for WCAG 2.2 AA compliance | Integrated into testing suite |

_No AI models or services are needed for this solution._

### Estimated development effort

| Phase | Roles | Low | Likely | High |
| --- | --- | --- | --- | --- |
| Discovery & design | Frontend Developer, UI/UX Designer | 3 | 5 | 7 |
| Frontend build | Frontend Developer, UI/UX Designer | 5 | 8 | 12 |
| Testing & hardening | Frontend Developer, UI/UX Designer | 2 | 3 | 5 |
| Launch | Frontend Developer | 1 | 2 | 3 |
| **Total (person-days)** | | **11** | **18** | **27** |

About **0.9 person-months** likely (20 working days per month).

### Estimated timeline

| Phase | Weeks | Duration | Depends on | Schedule |
| --- | --- | --- | --- | --- |
| Discovery & design | 1 | 1 wk | - | █████░░░░░░░░░░░░░░░░░░░ |
| Frontend build | 2–3 | 2 wk | Discovery & design | ░░░░░██████████░░░░░░░░░ |
| Testing & hardening | 4 | 1 wk | Frontend build | ░░░░░░░░░░░░░░█████░░░░░ |
| Launch | 5 | 1 wk | Testing & hardening | ░░░░░░░░░░░░░░░░░░░█████ |

**Total: about 5 weeks** with the team above (range 3.1–7.5 weeks, following the effort range).

**What could change the estimate:**

- Delays in content sign-off from stakeholders may extend the build phase.
- Third-party form handler integration issues could require fallback implementation time.
- Accessibility remediation identified during testing could add minor rework effort.

## 5. Specialist findings

### frontend

Architecture and technology stack for the company website frontend, focusing on fast load times, accessibility, and responsive design across Home, About, Services, and Contact pages.

- Adopt a mobile-first responsive layout utilizing Tailwind CSS grid and flexbox utilities.
- Ensure WCAG 2.2 AA compliance by maintaining minimum color contrast ratios, proper semantic HTML structure, and keyboard-accessible navigation elements.
- Render static HTML by default to minimize time-to-interactive and maximize SEO performance.

### uiux

Information architecture, responsive structure, and usability specifications for the company website frontend featuring Home, About, Services, and Contact pages.

- Adopt mobile-first design principles ensuring readability and touch-target adequacy on small screens.
- Maintain high contrast ratios and semantic HTML for optimal accessibility compliance.
- Implement clear visual hierarchy across all four core pages to guide prospective clients toward the contact action.

### security

Security and data protection analysis for the frontend-only company website, applying client-side security controls and secure static hosting practices.

- Since this is a frontend-only application with no backend or database, server-side OWASP Top 10 risks are largely absent.
- Implement Subresource Integrity (SRI) for any external scripts or assets.
- Ensure secure handling of contact form inputs to prevent DOM-based XSS if user input is reflected.

### performance

Performance optimization strategy focusing on Core Web Vitals, fast asset delivery, and static hosting aligned with Netlify for the company website frontend.

- Leverage static site generation for all pages to eliminate server-side rendering latency.
- Implement image optimization pipelines using modern formats like WebP or AVIF.
- Utilize CDN edge caching for all static assets.

## 6. Alternatives

Listed per technology choice in section 3.

## 7. Risks

| Risk | Severity | Likelihood | Mitigation | From |
| --- | --- | --- | --- | --- |
| Contact form submissions fail due to lack of a native backend. | medium | medium | Integrate a third-party form handling service like Formspree or Netlify Forms. | frontend |
| Contact form submissions failing without backend processing. | medium | medium | Integrate a reliable third-party form handler or explicit mailto fallback. | uiux |
| Cross-Site Scripting (XSS) via unsafe rendering of user input on the contact page. | medium | low | Sanitize inputs and use framework defaults that automatically escape output. | security |
| Unoptimized high-resolution images causing slow Largest Contentful Paint (LCP). | medium | medium | Enforce automated image resizing and modern format usage during the build process. | performance |
| Missing security headers on the static hosting provider leading to clickjacking or MIME sniffing. | low | medium | Configure strict Content Security Policy, X-Frame-Options, and X-Content-Type-Options headers via the hosting provider. | security |

## 8. Quality score

**Overall: 94.2/100**

| Dimension | Weight % | Score |
| --- | --- | --- |
| requirement_fit | 25.0 | 100 |
| architecture | 20.0 | 95 |
| performance | 15.0 | 95 |
| security | 15.0 | 90 |
| accessibility | 15.0 | 90 |
| maintainability | 10.0 | 90 |

## 9. Assumptions

- Contact form will be handled by a third-party service or mailto link
- Static hosting will be used
- No backend database or custom server logic is required.
- Content updates will be handled directly via static files or markdown content.
- All content for Home, About, Services, and Contact pages will be provided ahead of development.
- No dynamic backend state management is required for the initial release.
- The contact form relies on a third-party form handler or mailto link, removing backend server vulnerability vectors.
- The hosting provider enforces HTTPS by default.
- Traffic levels will remain within standard business expectations easily handled by static CDN hosting.
- All page content and copy will be provided prior to development start.
- Contact form submissions will be handled by a third-party service like Formspree or Netlify Forms rather than a custom backend.
- No dynamic backend database or custom server-side state is required.

## 10. Review history

| Round | Decision | Score | Findings (severity) |
| --- | --- | --- | --- |
| 1 | REWORK | 95.5 | high: hosting_static: performance chose Firebase Hosting but front |
| 2 | APPROVED | 94.2 | none |
