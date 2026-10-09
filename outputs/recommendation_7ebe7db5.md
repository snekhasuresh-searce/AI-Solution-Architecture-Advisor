# Responsive Company Website

**Status:** Approved by reviewer  
**Run:** 7ebe7db5 - 2026-10-08 12:18  
**Domains:** frontend

## 1. Executive summary

A responsive frontend-only corporate website featuring Home, About, Services, and Contact pages, optimized for both mobile and desktop devices.

**Project type:** Static marketing website (frontend only) - small complexity. The project consists of four static informational pages with no backend database or user authentication required.

**At a glance:** 1 FTE team, about 16 person-days of effort, about 5 weeks to deliver.

**Reviewer:** The combined solution fully satisfies the requirements for a responsive, frontend-only corporate website using Astro, Tailwind CSS, and Netlify hosting. All technology choices are appropriate, well-aligned, and secure without any critical or high findings.

## 2. Solution architecture

A lightweight, high-performance static corporate website providing Home, About, Services, and Contact pages built with Astro and Tailwind CSS. It is hosted on a global edge CDN via Netlify, featuring seamless cross-device responsiveness and integrated form handling without requiring a dedicated backend server.

### 2.1 High-level solution architecture diagram

![High-level solution architecture](/api/runs/7ebe7db5/diagram.svg)

**Cloud:** To be confirmed. Boxes are grouped by layer and coloured by type (client system, proposed component, third-party, managed cloud service, AI, data store). Dashed boxes are recommended additions that the requirement did not state.

### 2.2 End-to-end data flow

**Website Navigation Request**

- **1.** Prospective Clients → Static CDN: HTTPS request
- **2.** Static CDN → Security Headers: Apply security headers
- **3.** Security Headers → Corporate Website: Serve static HTML
- **4.** Corporate Website → Prospective Clients: Render responsive pages

**Contact Form Submission**

- **1.** Prospective Clients → Corporate Website: Submit message UI
- **2.** Corporate Website → Form Handler: Send form data
- **3.** Form Handler → Prospective Clients: Return success response

### 2.3 Major components

| Layer | Component | Technology | Type | Status | Purpose |
| --- | --- | --- | --- | --- | --- |
| Users & stakeholders | Prospective Clients | Web Browser | actor | recommended | End users browsing company information and submitting inquiries. |
| User / application layer | Corporate Website | Astro | proposed | required | Renders pre-built static HTML pages for Home, About, Services, and Contact. |
| User / application layer | Styling Engine | Tailwind CSS | proposed | required | Applies utility-first responsive layout rules for desktop and mobile viewports. |
| External integrations | Form Handler | Formspree | third party | recommended | Processes contact form submissions securely without a custom backend server. |
| Cloud infrastructure & networking | Static CDN | Netlify | cloud service | recommended | Delivers global edge caching and atomic deployments for static assets. |
| Security | Security Headers | Netlify Security | proposed | recommended | Enforces HTTPS transport and strict Content Security Policy headers. |

### 2.4 Requirement traceability

| Requirement | Delivered by |
| --- | --- |
| Navigation menu across all pages | Corporate Website |
| Contact page with a message submission UI | Corporate Website, Form Handler |
| Responsive layout adjusting to screen sizes | Corporate Website, Styling Engine |
| Fast page load times | Corporate Website, Static CDN |
| Cross-browser compatibility | Corporate Website |
| Accessible UI design | Corporate Website |

### 2.5 Key assumptions

- Contact form submissions can be handled via a third-party service like Formspree or static mailto links since there is no backend.
- Branding guidelines and finalized copywriting will be supplied prior to development.
- Users will access the site primarily via modern browsers supporting CSS Grid and Flexbox.

### 2.6 Recommended technology stack

| Layer | Technology | Purpose | Status |
| --- | --- | --- | --- |
| User / application layer | Astro | Static site generation delivering zero JavaScript by default for high performance. | required |
| User / application layer | Tailwind CSS | Utility-first CSS framework for rapid and responsive design implementation. | required |
| External integrations | Formspree | Serverless contact form message processing service. | recommended |
| Cloud infrastructure & networking | Netlify | Global edge CDN and continuous deployment for static frontend assets. | recommended |
| Security | Netlify Security Headers | Enforces HTTPS and strict Content Security Policy headers. | recommended |

### 2.7 Security considerations

- Apply strict Content Security Policy (CSP) headers to prevent unauthorized script execution.
- Ensure all third-party integrations use HTTPS and validate inputs safely.
- Avoid storing sensitive credentials or API keys in client-side code.
- Protect against Cross-Site Scripting (XSS) via framework-level automatic escaping.

### 2.8 Scalability and future enhancements

**Scalability**

- Leverage global edge caching to effortlessly handle standard corporate website traffic spikes.
- Serve pre-rendered static HTML to minimize compute overhead and guarantee fast load times.
- Optimize media assets using modern formats like WebP or AVIF to preserve bandwidth.

**Future enhancements**

- Integrate a headless CMS for easy non-technical content management.
- Add multi-language localization support for international audiences.
- Implement automated visual regression testing within the CI/CD pipeline.

## 3. Solution design

### Recommended architecture

**Style:** Jamstack static site

The architecture utilizes Astro to pre-render static HTML pages with zero JavaScript by default, styled with Tailwind CSS for rapid and responsive UI development. Static assets are built and deployed globally via Netlify for low latency and high availability. Contact form submissions are offloaded to a serverless third-party service without requiring a dedicated backend server.

- Presentation Layer: Astro components and Tailwind CSS responsive templates
- Hosting and Delivery Layer: Netlify global CDN and static edge caching
- Third-Party Integration Layer: Serverless form submission handling

### Agents used

- **frontend**: needed for frontend
- **uiux**: needed for frontend
- **security**: needed for frontend
- **performance**: needed for frontend

### Components

| Component | Responsibility | From |
| --- | --- | --- |
| Navbar | Responsive navigation header providing links across Home, About, Services, and Contact pages with mobile drawer menu. | frontend |
| HeroSection | Prominent landing banner on the Home page for value proposition delivery. | frontend |
| ContactForm | Client-side validated message submission UI integrating with a third-party service. | frontend |
| Footer | Global footer containing copyright, sitemap links, and social links. | frontend |
| Navigation Bar | Consistent site-wide navigation with responsive mobile hamburger menu. | uiux |
| Hero Section | Engaging introductory banner on the Home page with clear value proposition and primary call-to-action. | uiux |
| Service Card Grid | Structured presentation of company services on the Services page. | uiux |
| Contact Form | Interactive form UI for user message submission with client-side validation. | uiux |
| Static Hosting Security | Ensure secure transport via HTTPS and configure strict Content Security Policy (CSP) headers. | security |
| Input Handling & Sanitization | Mitigate client-side injection risks on the contact form UI before submission to third-party handlers. | security |
| Static Hosting and CDN | Deliver pre-rendered static assets globally with low latency and high availability. | performance |
| Frontend Bundle Optimizer | Ensure minimal JavaScript payload size and fast initial page load times. | performance |

### Recommended technology stack

| Category | Choice | Rationale | Alternatives | From |
| --- | --- | --- | --- | --- |
| frontend_framework | Astro | Delivers zero JavaScript by default for maximum static performance on informational corporate sites. | Next.js, React, SvelteKit | frontend, uiux, performance |
| styling_ui | Tailwind CSS | Enables rapid styling with built-in responsive utilities and small production CSS footprints. | CSS Modules, shadcn/ui | frontend, uiux |
| hosting_static | Netlify | Provides fast global CDN distribution and seamless continuous deployment for static frontend sites. | Vercel, Firebase Hosting | frontend, uiux, security, performance |
| testing_quality | Playwright | Ensures robust cross-browser end-to-end testing of the responsive layout and contact form. | Vitest, Jest | frontend, uiux |
| testing_quality | OWASP ZAP | Enables automated vulnerability scanning of the deployed static site to detect missing headers and XSS configurations. | axe-core | security |
| testing_quality | Lighthouse | Enables automated auditing of performance, accessibility, and best practices during development. | Vitest | performance |

## 4. Resources and estimate

### Required human resources

| Role | FTE | Seniority | Responsibilities | Phases |
| --- | --- | --- | --- | --- |
| Frontend Developer | 1 | mid | Build the Astro pages, navigation, components, and Tailwind styles, and implement Playwright tests. | Discovery & Design, Frontend Build, Testing & Hardening, Launch |

**Team size:** 1 FTE across 1 roles.

### Required AI and technical resources

| Type | Resource | Purpose | Sizing |
| --- | --- | --- | --- |
| dev tooling | Astro | Static site generation and component framework | v4+ |
| dev tooling | Tailwind CSS | Utility-first styling and responsive design | v3+ |
| hosting | Netlify | Global CDN distribution, atomic deployments, and static hosting | Free / Starter tier |
| testing | Playwright | Cross-browser end-to-end and responsive UI testing | Latest |
| testing | Lighthouse | Performance, accessibility, and best practices auditing | Built-in |
| third party service | Formspree | Contact form submission processing | Free / Standard tier |

_No AI models or services are needed for this solution._

### Estimated development effort

| Phase | Roles | Low | Likely | High |
| --- | --- | --- | --- | --- |
| Discovery & Design | Frontend Developer | 2 | 3 | 5 |
| Frontend Build | Frontend Developer | 5 | 8 | 12 |
| Testing & Hardening | Frontend Developer | 2 | 3 | 4 |
| Launch | Frontend Developer | 1 | 2 | 3 |
| **Total (person-days)** | | **10** | **16** | **24** |

About **0.8 person-months** likely (20 working days per month).

### Estimated timeline

| Phase | Weeks | Duration | Depends on | Schedule |
| --- | --- | --- | --- | --- |
| Discovery & Design | 1 | 1 wk | - | █████░░░░░░░░░░░░░░░░░░░ |
| Frontend Build | 2–3 | 2 wk | Discovery & Design | ░░░░░██████████░░░░░░░░░ |
| Testing & Hardening | 4 | 1 wk | Frontend Build | ░░░░░░░░░░░░░░█████░░░░░ |
| Launch | 5 | 1 wk | Testing & Hardening | ░░░░░░░░░░░░░░░░░░░█████ |

**Total: about 5 weeks** with the team above (range 3.1–7.5 weeks, following the effort range).

**What could change the estimate:**

- Delays in final copywriting and asset delivery from stakeholders.
- Third-party form submission service limitations or downtime requiring fallback configuration.
- Accessibility compliance revisions requiring additional iteration on contrast and semantic markup.

## 5. Specialist findings

### frontend

Architecture recommendation for a responsive corporate website featuring Home, About, Services, and Contact pages, built with Astro and Tailwind CSS for optimal static performance and accessibility.

- Utilize semantic HTML landmarks (header, nav, main, footer) to support screen readers.
- Ensure WCAG 2.2 AA color contrast ratios across all text and interactive elements.
- Implement fully responsive layout using CSS Grid and Flexbox with mobile-first breakpoints.

### uiux

Information architecture, page structure, responsive behavior, navigation, and usability recommendations for the responsive corporate website.

- Adopt a mobile-first design philosophy, ensuring touch-friendly targets and readable typography on small screens.
- Maintain high contrast ratios to comply with accessibility standards.
- Keep navigation concise with clear hierarchy: Home, About, Services, Contact.

### security

Security analysis and static application security recommendations for the frontend-only corporate website, aligned with Netlify hosting to resolve cross-agent conflicts.

- Apply strict Content Security Policy (CSP) headers to prevent unauthorized script execution.
- Ensure all third-party integrations (like form submission endpoints) use HTTPS and validate input safely.
- Since there is no backend, avoid storing any secrets or sensitive API keys in the client-side code.

### performance

Performance optimization strategy focusing on Core Web Vitals, minimal bundle size, and ultra-fast static asset delivery using Netlify for the responsive corporate website.

- Leverage static site generation (SSG) to serve pre-rendered HTML.
- Implement image optimization using modern formats like WebP or AVIF.
- Ensure critical CSS is inlined to eliminate render-blocking resources.

## 6. Alternatives

Listed per technology choice in section 3.

## 7. Risks

| Risk | Severity | Likelihood | Mitigation | From |
| --- | --- | --- | --- | --- |
| Third-party form submission service availability issues. | medium | low | Provide clear error handling in the UI and fallback contact methods such as a direct mailto link. | frontend |
| Contact form submissions failing without a backend server. | medium | medium | Integrate a third-party form handler such as Formspree to capture submissions seamlessly. | uiux |
| Cross-Site Scripting (XSS) via unvalidated contact form inputs rendered in the UI. | medium | low | Ensure framework-level automatic escaping is used and validate input before sending to third-party endpoints. | security |
| Large unoptimized images degrading mobile Core Web Vitals. | medium | medium | Use automated image optimization pipelines and responsive image tags. | performance |
| Missing security headers leading to clickjacking or MIME-sniffing vulnerabilities. | low | medium | Configure strict HTTP headers (X-Frame-Options, X-Content-Type-Options, CSP) via the static hosting provider settings. | security |

## 8. Quality score

**Overall: 94.2/100**

| Dimension | Weight % | Score |
| --- | --- | --- |
| requirement_fit | 25.0 | 100 |
| architecture | 20.0 | 95 |
| performance | 15.0 | 95 |
| accessibility | 15.0 | 90 |
| security | 15.0 | 90 |
| maintainability | 10.0 | 90 |

## 9. Assumptions

- Contact form can be handled via a third-party service like Formspree or static mailto links since there is no backend
- Contact form submissions are handled by a serverless third-party service like Formspree.
- Users will access the site primarily via modern browsers supporting CSS Grid and Flexbox.
- Branding guidelines and copywriting will be supplied prior to development.
- Contact form submissions are offloaded to secure third-party services like Formspree.
- No sensitive user data or Personally Identifiable Information (PII) is persisted locally on the client.
- Traffic patterns will remain standard for a corporate brochureware site without heavy burst loads.
- Branding guidelines, logos, and final copywriting are provided prior to development start.
- Contact form submissions are handled by a serverless third-party service such as Formspree.
- No complex animations or custom CMS integrations are required for initial release.

## 10. Review history

| Round | Decision | Score | Findings (severity) |
| --- | --- | --- | --- |
| 1 | REWORK | 91.0 | medium: Conflicting technology choice for static hosting: Frontend a, high: hosting_static: security chose Vercel but frontend (owner of, high: hosting_static: performance chose Vercel but frontend (owner |
| 2 | APPROVED | 94.2 | none |
