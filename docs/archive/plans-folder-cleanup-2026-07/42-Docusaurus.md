# **Fabrik Platform Documentation Architecture: Docusaurus Implementation and Governance Report**

## **1\. Executive Summary**

The deployment of a centralized developer hub and documentation platform for the Fabrik ecosystem necessitates a highly durable, low-maintenance, and performant architectural approach. Given the severe operational constraints of a solo developer environment—characterized by a strict allocation of approximately fifty focused working hours per week—the chosen documentation framework must minimize ongoing operational and DevOps overhead while simultaneously providing a premium, interactive developer experience. Following an exhaustive technical evaluation of available static site generators (SSGs), Docusaurus v3 has been identified as the optimal foundational framework for this purpose. Docusaurus natively supports React 18, leverages the MDX v3 compiler for embedding interactive components within Markdown, and integrates seamlessly with the existing Fabrik technology stack, which relies heavily on TypeScript and React Native.1

This report establishes the definitive architectural guidelines, deployment paradigms, and content governance strategies required to implement Docusaurus securely and efficiently within the Fabrik platform. The infrastructure detailed herein is specifically tailored for deployment on an ARM64 Ubuntu Virtual Private Server (VPS) managed via Coolify. It enforces strict utilization of Docker Compose pipelines and relies exclusively on slim-bookworm Debian base images, permanently outlawing Alpine Linux to ensure absolute parity with the Windows Subsystem for Linux (WSL) Ubuntu 24.04 primary development environment.4

It is equally critical to establish the operational boundaries of this technology. Docusaurus is engineered specifically for content-driven, statically generated documentation sites.1 The deployment of Docusaurus is strongly contraindicated—and therefore prohibited within the Fabrik architecture—under three specific scenarios. First, if the primary content editors are non-technical stakeholders requiring a graphical, database-driven Content Management System (CMS), platforms such as WordPress must be utilized instead. Second, if the application relies heavily on dynamic, user-generated content (UGC), real-time database mutations, or complex server-side state, a full-stack framework like Next.js 14 is required. Finally, for trivial, single-page utility scripts or internal micro-tools, spinning up a complete React-based SSG represents unjustifiable overhead; a standard Markdown README.md or a single vanilla HTML file is the correct architectural choice in those instances.

By adhering to the principles of static compilation, immutable version archiving, client-side API rendering, and post-build WebAssembly search indexing, the Fabrik platform can maintain a sprawling, multi-product documentation ecosystem without incurring the compounding technical debt typically associated with enterprise developer portals.

## **2\. Deep Architectural Analysis and Mechanisms**

To ensure the Fabrik documentation ecosystem remains robust and highly performant over a two-to-three-year horizon, every underlying mechanism of the Docusaurus framework must be strictly controlled. The following subsections dissect the core architectural domains, evaluating the origin of standard practices, their underlying mechanisms, and the tailored solutions required for a solo developer.

### **2.1 Monorepo Architecture vs. Multi-Instance Documentation**

The Fabrik platform encompasses multiple evolving tools, ranging from backend Application Programming Interfaces (APIs) to client-side mobile Software Development Kits (SDKs). As these products scale, the organization of their respective documentation repositories dictates the long-term maintainability of the entire system. Docusaurus provides a native @docusaurus/plugin-content-docs plugin, which supports multi-instance configurations. This feature allows distinct documentation sets—such as an iOS SDK and an Android SDK—to reside within a single Docusaurus application, configured via multiple plugin declarations in docusaurus.config.js.5

However, implementing multi-instance documentation within a single, monolithic repository creates tightly coupled build lifecycles that scale poorly. If a developer corrects a minor typographical error in the mobile SDK documentation, the Webpack bundler must recompile the entire project, including the massive backend API documentation that remained entirely unchanged.5 For a solo developer managing distinct, large-scale products, aggregating entirely separate projects into a single Docusaurus instance represents an architectural anti-pattern that wastes Continuous Integration and Continuous Deployment (CI/CD) resources and significantly inflates build times.

The mandated approach for the Fabrik platform leverages a monorepo architecture, utilizing tools such as Turborepo or npm workspaces, where multiple independent Docusaurus sites coexist securely within isolated directories.7 In this structure, shared assets—such as custom React components, Infima CSS variable configurations, and internal ESLint plugins—are extracted into shared monorepo packages (e.g., @fabrik/docs-ui).7 Each distinct documentation site is built and deployed independently via localized Coolify webhooks.5 This ensures that deployments remain isolated, build times remain blazingly fast, and the caching mechanisms of the Node.js package manager operate at peak efficiency.

### **2.2 MDX Compilation, Component Interactivity, and Content Portability**

Docusaurus v3 introduces the MDX v3 compiler, a major architectural shift that enforces strict JSX parsing within Markdown files.3 The primary advantage of MDX is the ability to seamlessly interleave interactive React components directly within technical prose. For a developer platform like Fabrik, this capability is invaluable, allowing the embedding of live code editors, terminal simulators, and interactive API payload builders directly alongside explanatory text.3

Despite these capabilities, the excessive use of custom JSX tags within documentation files severely degrades content portability, hinders readability for non-technical contributors, and complicates automated markdown linting.9 The architectural standard for Fabrik dictates that standard documentation prose must be written in strict CommonMark.8 JSX must be reserved exclusively for highly interactive elements that cannot be represented natively.

Furthermore, when custom interactive components—such as a \<TerminalSimulator\>—are required across multiple documentation files, developers must avoid importing them manually via relative paths (e.g., import Terminal from '../../components/Terminal') in every single .mdx file.10 Instead, components must be registered globally by swizzling and wrapping the @theme/MDXComponents module.9 By defining components in this global scope, they become natively available to the MDX compiler across the entire project, ensuring that the raw Markdown files remain clean, maintainable, and devoid of fragile relative file paths.

For complex formatting, the framework utilizes Abstract Syntax Tree (AST) transformations. The MDX compilation pipeline passes the document through Remark (for the Markdown AST) and Rehype (for the Hypertext AST) plugins.11 When custom formatting is required, developers should write custom Remark plugins to intercept standard Markdown shortcodes and compile them into React components, keeping the source text completely decoupled from the React ecosystem.11

### **2.3 Archival Versioning Strategy for Solo Maintainers**

Software documentation must evolve alongside the product it describes. Native document versioning in Docusaurus operates by duplicating the entire contents of the docs/ directory into a newly generated versioned\_docs/version-\[X.X.X\]/ folder, while simultaneously duplicating the navigation configuration into a versioned\_sidebars/ directory.13 While this mechanism is highly functional for heavily resourced enterprise teams requiring parallel updates to multiple legacy versions, it results in exponential repository bloat, massive Git diffs, and severely degraded Webpack build times for solo developers.13

Maintaining parallel, synchronized directories represents an unacceptable maintenance burden for the Fabrik platform. Therefore, the use of Docusaurus's native versioning CLI commands is permanently banned. The mandated versioning strategy relies exclusively on Git branch-based immutable archiving.14

Under this strategy, the main branch of the repository serves as the single source of truth for the current, active documentation. When a major version of a Fabrik tool is deprecated (e.g., transitioning from v1 to v2), a Git branch is cut (e.g., release/v1.x). This branch is deployed via Coolify as an immutable static snapshot to a dedicated Nginx subpath (e.g., docs.fabrik.com/v1/).15 In the main branch, the docusaurus.config.js file utilizes the versions.json configuration to populate the version dropdown menu, providing an external, absolute URL link to the archived static deployment.13

This methodology yields massive operational benefits. The primary repository remains incredibly lightweight, ensuring that CI/CD pipelines run in seconds rather than minutes. Furthermore, older versions require absolutely zero ongoing maintenance or dependency updates, as they are served as completely static, frozen HTML artifacts that are isolated from the active Webpack build process.16

### **2.4 Search Infrastructure: The WebAssembly Advantage**

A developer hub is entirely reliant on the quality and speed of its search functionality. The Docusaurus ecosystem generally presents three avenues for search integration, each with distinct operational mechanisms and trade-offs.

Algolia DocSearch is the industry standard, heavily promoted by the Docusaurus maintainers. It operates by utilizing external cloud crawlers to parse the documentation site weekly, storing the index in Algolia's proprietary databases, and querying that data via a client-side API call.17 While powerful, Algolia introduces a critical external dependency, requires the documentation site to be publicly accessible to the internet (which is problematic for internal Fabrik tools), and carries the risk of future pricing alterations.17

Alternatively, local search plugins—most notably @easyops-cn/docusaurus-search-local—build an inverted search index during the npm run build phase and bundle this index directly into the site's client-side JavaScript payload.19 For small sites, this is acceptable. However, as the documentation grows, this search index severely inflates the initial bundle size, degrading Time to Interactive (TTI) and First Contentful Paint (FCP) metrics, ultimately resulting in a sluggish user experience.21

The mandated search architecture for the Fabrik platform utilizes **Pagefind**, integrated via the @getcanary/docusaurus-theme-search-pagefind package.23 Pagefind represents a paradigm shift in static site search. It is a Rust-based, WebAssembly (WASM) powered search engine designed explicitly for large-scale static sites.24 Instead of inflating the initial JavaScript bundle during Webpack compilation, Pagefind runs entirely post-build. It crawls the fully generated HTML files within the build/ directory and generates highly compressed, heavily chunked WASM indexes.23

During runtime, the client browser downloads only the specific index chunks relevant to the user's specific query.23 This delivers sub-millisecond search execution with zero server-side infrastructure, zero SaaS dependencies, and absolutely zero impact on the initial page load speed.25 It perfectly aligns with the budget-conscious, low-ops constraints of the Fabrik ecosystem.

| Search Architecture | Operational Mechanism | Maintenance Overhead | Client Bundle Impact | Verdict |
| :---- | :---- | :---- | :---- | :---- |
| **Algolia DocSearch** | External SaaS Cloud Crawler | Low | Minimal | Banned (External dependency, requires public exposure) |
| **Local Search (EasyOps)** | Webpack bundled inverted index | Low | High (Large, monolithic JS payload) | Banned (Severe performance degradation at scale) |
| **Pagefind** | Post-build WASM chunk generation | Zero | Zero (Chunks are dynamically loaded on demand) | **Mandated** |

### **2.5 Git-Based Internationalization (i18n)**

The Fabrik platform requires bilingual documentation supporting a Turkish and English language pair. Docusaurus provides a robust, native internationalization (i18n) routing system that automatically manages HTML lang attributes, URL prefixing (e.g., /tr/docs/), and localized asset serving.26 However, the official documentation frequently recommends pairing this system with external SaaS translation platforms such as Crowdin to manage workflows.27

Integrating Crowdin introduces unnecessary SaaS dependencies, requires complex CI/CD synchronization scripts, and creates a disjointed workflow where developers must leave their Integrated Development Environment (IDE) to manage content.27 For a solo developer, this overhead is unjustifiable.

A direct, Git-based workflow is strictly enforced for Fabrik.28 The default locale (English) resides in the standard docs/ and src/ directories. Target translations (Turkish) are housed symmetrically within the i18n/tr/docusaurus-plugin-content-docs/current/ directory.28 Hardcoded strings within React theme components and the navigation sidebar are extracted into centralized JSON files using the native npm run write-translations command.29 This architecture ensures that translations are managed entirely within standard Pull Requests, utilizing the existing Git infrastructure and code review processes without introducing external vendor lock-in.28

### **2.6 Interactive API Reference Rendering**

Generating interactive API documentation from OpenAPI (Swagger) specifications typically relies on static generation plugins like docusaurus-plugin-openapi-docs paired with the Redocusaurus theme.30 These tools operate by parsing OpenAPI YAML or JSON files at build time and programmatically generating hundreds of individual, physical .mdx files representing each API endpoint.31 This methodology heavily pollutes the file system, drastically increases the Webpack compilation payload, and requires complex CSS overrides to maintain visual consistency with the broader site.32

The required API documentation standard for Fabrik is **Scalar**, integrated via the @scalar/docusaurus plugin.34 Scalar circumvents build-time generation entirely. Instead, it fetches and renders the OpenAPI specification dynamically on the client side at runtime.34 It provides an elite developer experience, featuring a fully interactive API playground, automated code snippet generation across multiple programming languages (cURL, Python, TypeScript), and a modern, dark-mode optimized UI that seamlessly integrates into a single Docusaurus route (e.g., /api).33 This approach guarantees zero build-time bloat, prevents Git repository pollution, and requires virtually zero maintenance.33

| API Rendering Tool | Rendering Mechanism | Build Time Impact | Interactive Playground | Verdict |
| :---- | :---- | :---- | :---- | :---- |
| **Redocusaurus** | Build-time MDX generation | High (Generates hundreds of physical files) | No (Read-only interface) | Banned |
| **Docusaurus-OpenAPI** | Build-time MDX generation | High | Yes (Limited interactivity) | Banned |
| **Scalar** | Client-side dynamic rendering | Zero (Fetches JSON specification at runtime) | Yes (Full Postman-like client suite) | **Mandated** |

### **2.7 Sidebar Organization and Content Scaling**

As documentation sites grow beyond a few dozen pages, the default flat sidebar becomes unmanageable. Docusaurus supports automatic sidebar generation based on the underlying file system structure (autogenerated type).36 While this is an excellent starting point, relying purely on file structures for navigation often results in poorly categorized content as the platform scales.

For Fabrik, sidebars must be manually defined in sidebars.js using a heavily nested, category-based architecture. Categories must utilize the link attribute (specifically the generated-index type) to automatically create landing pages for each documentation section. This approach allows developers to group related topics—such as "Authentication," "Webhooks," or "Deployment"—into logical, collapsible menus, preventing cognitive overload for the end user while maintaining strict editorial control over the navigation hierarchy.

### **2.8 SEO Optimization and Content Workflow Automation**

Manual verification of internal hyperlinks, markdown anchor tags, and Search Engine Optimization (SEO) metadata is impossible to scale for a solo developer operating under strict time constraints. Content validation must be relentlessly automated within the Continuous Integration pipeline.

Docusaurus generates static HTML files for every route, inherently providing an excellent foundation for SEO by ensuring content is easily discoverable by search engine crawlers.2 However, the integrity of this content relies entirely on accurate Markdown Frontmatter.

A standalone Python validation script, utilizing the python-frontmatter library, must be executed in the CI pipeline immediately prior to the build step.38 This script must recursively iterate through all Markdown files to assert that mandatory SEO metadata—specifically the title and description variables—are explicitly defined in the YAML block.38 Failure to include these fields must trigger a hard pipeline failure, guaranteeing consistent search engine indexing and preventing rendering anomalies across social media cards.39

Furthermore, link integrity must be strictly enforced at the framework level. The docusaurus.config.js file must explicitly set the onBrokenLinks and onBrokenAnchors properties to 'throw'.40 This configuration commands the Docusaurus compiler to execute a hard fail during the npm run build phase if any internal hyperlink or markdown heading anchor resolves to a non-existent path.41 This guarantees that broken documentation never reaches the production environment.

Finally, the @docusaurus/eslint-plugin must be integrated into the overarching ESLint configuration to enforce semantic rules, such as preventing untranslated text within JSX and ensuring that the native @docusaurus/Link component is utilized instead of standard HTML \<a\> tags for optimal client-side routing.43

### **2.9 ARM64 Coolify Deployment Mechanics**

Docusaurus is fundamentally a Static Site Generator. Executing commands such as npm run serve or running a live Node.js server within a production Docker container represents a catastrophic architectural failure, consuming excessive RAM and CPU resources merely to deliver static assets.36

Deployments on the Fabrik ARM64 Ubuntu VPS must utilize a highly optimized, multi-stage Docker build pipeline orchestrated via Coolify.45

The first stage of the Dockerfile acts as the build environment. It must utilize the node:20-bookworm-slim base image to resolve dependencies via a strict npm ci command and execute npm run build to generate the final assets. Crucially, the Pagefind WASM index generation script must be executed immediately following the build command within this stage.

The second stage acts as the production server. It must utilize nginx:mainline-bookworm-slim to serve the resulting static assets directly from the build/ directory.46 Alpine Linux images (node:alpine, nginx:alpine) are strictly and permanently banned across the Fabrik ecosystem to avoid complex musl-libc compilation edge cases with Node.js native modules and to maintain absolute binary parity with the WSL Ubuntu 24.04 development environment.

Because Docusaurus operates as a Single Page Application (SPA) powered by React Router, the Nginx configuration must be explicitly tailored to handle client-side routing. Failure to do so will result in 404 Not Found errors when users navigate directly to deep links or refresh the browser. The Nginx block must include the directive try\_files $uri $uri/ /index.html;, ensuring that all unresolved URL paths elegantly fall back to the root index.html file, allowing React to assume control of the routing logic.

## ---

**3\. Canonical Rules for the Docusaurus Rule File**

The following directives constitute the permanent, non-negotiable governance policies for all Docusaurus deployments within the Fabrik ecosystem.

| Rule ID | Category | Directive |
| :---- | :---- | :---- |
| **DOC-01** | Architecture | All Docusaurus projects must be deployed purely as Static Site Generators (SSG). Server-Side Rendering (SSR) or runtime Node.js processes are strictly prohibited in production. |
| **DOC-02** | Deployment | Applications must be deployed via Coolify using a two-stage Dockerfile. The final production stage must utilize Nginx to serve the static build/ directory. |
| **DOC-03** | Infrastructure | All Docker base images must rely on Debian slim-bookworm (e.g., node:20-bookworm-slim). Alpine Linux is permanently banned to ensure cross-environment libc consistency. |
| **DOC-04** | Search | Search indexing must be handled exclusively by the post-build WebAssembly tool Pagefind (@getcanary/docusaurus-theme-search-pagefind). |
| **DOC-05** | Versioning | Native versioning (versioned\_docs/) is prohibited. Legacy versions must be archived as static, immutable deployments on separate subpaths via Git branch snapshots. |
| **DOC-06** | API Reference | OpenAPI specifications must be rendered dynamically on the client side using the @scalar/docusaurus plugin to prevent filesystem bloat and build-time degradation. |
| **DOC-07** | Localization | Internationalization must utilize the native Docusaurus Git-based folder structure (i18n/tr/). Third-party SaaS localization platforms (e.g., Crowdin) are prohibited. |
| **DOC-08** | Quality Assurance | Docusaurus configurations must strictly enforce onBrokenLinks: 'throw' and onBrokenAnchors: 'throw' to guarantee CI pipeline failures upon hyperlink regressions. |
| **DOC-09** | Authoring | Standard documentation prose must be written in CommonMark. JSX/MDX is restricted to highly interactive elements (e.g., terminal simulators or API testers). |
| **DOC-10** | React Components | Global interactive components must be mapped and registered via src/theme/MDXComponents.js rather than relying on fragile relative imports in individual Markdown files. |
| **DOC-11** | SEO Metadata | Automated Python scripts must validate the presence of title and description frontmatter attributes in all Markdown files prior to the CI build phase. |
| **DOC-12** | Theme Customization | Styling adjustments must rely on overriding Infima CSS variables in custom.css. Component swizzling is strictly limited to critical overrides to prevent breaking changes during major Docusaurus upgrades. |
| **DOC-13** | Server Configuration | Nginx configurations must implement the try\_files $uri $uri/ /index.html; directive to properly support Docusaurus's client-side React routing. |
| **DOC-14** | Repository Scale | Separate Fabrik products with distinct target audiences must utilize separate Docusaurus instances within a monorepo workspace, avoiding the multi-instance docs plugin within a single site. |

## ---

**4\. Anti-Patterns and Banned Practices**

The following patterns introduce unacceptable operational friction, bloat, or instability, and are explicitly banned from the Fabrik platform.

* **Production Node.js Runtimes:** Running npm run serve or docusaurus serve inside a Docker container for production deployment. This is an anti-pattern for static sites, wasting vital VPS memory and CPU cycles that should be allocated to dynamic backend services.
* **Alpine Linux Images:** Utilizing node:alpine or nginx:alpine. This violates the strict environment consistency requirement across the platform. The discrepancy between musl-libc (Alpine) and glibc (WSL Ubuntu 24.04) inevitably causes native module compilation failures during complex dependency updates.
* **Native Versioning Folders:** Executing npm run docusaurus docs:version. This duplicates all assets into versioned\_docs, creating a massive Git history, exponential Webpack build times, and an unbearable refactoring burden when updating global components.
* **Algolia DocSearch Dependency:** Relying on external SaaS crawlers for search functionality. This introduces external dependency risks, requires the site to be publicly accessible to the internet (precluding internal corporate tools), and requires manual API key management.
* **Heavy Webpack Search Plugins:** Utilizing local search plugins such as @easyops-cn/docusaurus-search-local. These tools bundle the entire inverted search index into the client-side JavaScript payload, severely degrading Time to Interactive metrics as the documentation scales.
* **Static OpenAPI Generators:** Using docusaurus-plugin-openapi-docs to parse Swagger specs. Generating hundreds of physical .mdx files pollutes the Git repository, triggers massive commit diffs on minor API updates, and dramatically slows down the Docusaurus build pipeline.
* **Widespread Component Swizzling:** Running npm run swizzle for complex, deeply nested internal layout components (such as DocPage or DocItem). This ejects internal Docusaurus code into the local repository, virtually guaranteeing catastrophic build failures upon upgrading to the next major Docusaurus release.

## ---

**5\. Enforcement in Execute Handoffs**

When a deployment agent passes context, initiates a build sequence, or transfers environment variables, it must explicitly log and confirm the following operational state variables within the handoff payload:

* **Build Context Affirmation:** "Executing static build compilation via npm run build. Confirming that the Node.js runtime environment will be discarded post-build, leaving only static HTML/WASM assets."
* **Link Verification State:** "Docusaurus configuration validated: onBrokenLinks and onBrokenAnchors are explicitly set to 'throw'. CI will halt if broken references are detected."
* **Search Engine Hook Initiation:** "Confirming Pagefind post-build script (npx pagefind) is scheduled to execute against the generated build/ directory prior to Docker container finalization."
* **Base Image Verification:** "Validating Dockerfile dependencies: Base images target bookworm-slim. Confirming Alpine references are entirely absent from the build pipeline."
* **OpenAPI Rendering Confirmation:** "OpenAPI specifications are linked via remote URL for Scalar client-side rendering. Confirming no static MDX API files are being generated during the build step."

## ---

**6\. Verification within final\_gate.py**

The final\_gate.py validation script acts as the ultimate authority before a Docusaurus project is permitted to deploy. It must parse the repository state programmatically to ensure absolute architectural compliance.

1. **Regex Validation of docusaurus.config.js:**
   * Assert that onBrokenLinks: 'throw' exists within the root object.
   * Assert that onBrokenAnchors: 'throw' exists within the root object.
   * Scan the plugin and preset arrays to ensure banned packages (e.g., docusaurus-plugin-openapi-docs, algolia) are entirely absent.
2. **Regex Validation of Dockerfile:**
   * Assert the presence of FROM node:\*-bookworm-slim (or an equivalent, compliant Debian tag) in the build stage.
   * Assert the presence of FROM nginx:\*-bookworm-slim in the deployment stage.
   * Assert the absolute absence of the string alpine.
   * Assert the absence of runtime Node commands such as CMD \["npm", "run", "serve"\] or CMD \["docusaurus", "serve"\].
3. **Regex Validation of nginx.conf:**
   * Assert the presence of the critical Single Page Application routing fallback: try\_files $uri $uri/ /index.html;.
4. **AST and Frontmatter Validation:**
   * Recursively iterate through all .md and .mdx files located within the docs/ and blog/ directories.
   * Parse the YAML frontmatter blocks using the python-frontmatter library.
   * Fail the deployment gate immediately if any document lacks a defined title or description key, preserving SEO integrity.
5. **Directory Structure Constraints:**
   * Inspect the repository file tree. Fail the deployment gate immediately if the directory versioned\_docs/ or versioned\_sidebars/ is present, enforcing the immutable archiving strategy.

## ---

**7\. Context for AGENTS.md / AGENTS-compact.md**

To ensure AI agents consistently generate compliant code, the underlying philosophy of the architecture must be clearly communicated.

### **AGENTS.md (Strategic Context)**

* **Platform Philosophy:** The Fabrik Docusaurus instances are engineered for maximum long-term durability and absolute zero-maintenance operations. The system must remain statically compiled, completely decoupled from runtime dependencies, and entirely self-contained.
* **The "Why" Behind Exclusions:** Agents must understand that tools like Algolia, Crowdin, and Docusaurus's native versioning are banned not because they are inherently flawed technologies, but because they introduce unacceptable maintenance burdens, external SaaS dependencies, and build-time inflation for a solo developer operating under severe time constraints.
* **Component Strategy:** React is highly valued for injecting interactivity via MDX, but standard documentation must remain as pristine, readable CommonMark as possible to ensure future portability and ease of editing.

### **AGENTS-compact.md (Quick Reference)**

* Deploy via multi-stage Docker: Node build phase \-\> Nginx serve phase.
* Docker Base images: slim-bookworm strictly. Banish Alpine.
* Search Indexing: Pagefind WASM (post-build) only.
* API Playgrounds: Scalar client-side dynamic rendering only.
* Content Quality: Enforce onBrokenLinks: 'throw'. Frontmatter rigidly requires title and description.
* Versioning: Git branch static archiving only. Banish versioned\_docs.

## ---

**8\. Minimal Practical Examples for the Fabrik Stack**

The following configurations provide the canonical, production-ready baseline for deploying Docusaurus within the Fabrik Coolify environment.

### **8.1 Multi-Stage Deployment (Dockerfile)**

This Dockerfile enforces the separation of concerns, utilizing Node.js exclusively for compilation, Pagefind for search indexing, and Nginx for highly concurrent static asset delivery.

Dockerfile

\# Stage 1: Build the static Docusaurus site and generate search index
FROM node:20\-bookworm-slim AS builder
WORKDIR /app

\# Install dependencies utilizing strict lockfile to prevent drift
COPY package.json package-lock.json./
RUN npm ci

\# Copy source code and execute static output compilation
COPY..
RUN npm run build

\# Generate Pagefind WASM search index post-build against the HTML output
RUN npx \-y pagefind \--site build

\# Stage 2: Serve via highly concurrent Nginx
FROM nginx:mainline-bookworm-slim

\# Copy the static build artifacts (including Pagefind WASM) to Nginx
COPY \--from=builder /app/build /usr/share/nginx/html

\# Apply custom SPA routing configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD \["nginx", "-g", "daemon off;"\]

### **8.2 Nginx SPA Routing (nginx.conf)**

This configuration is critical. Without the try\_files directive, any direct link to a deeply nested documentation page will result in an Nginx 404 error, bypassing the Docusaurus React router.

Nginx

server {
    listen 80;
    server\_name \_;
    root /usr/share/nginx/html;
    index index.html;

    \# Client-side routing fallback for Docusaurus/React SPA architecture
    location / {
        try\_files $uri $uri/ /index.html;
    }

    \# Cache static assets aggressively to maximize edge performance
    location \~\* \\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot|wasm)$ {
        expires 1y;
        add\_header Cache-Control "public, max-age=31536000, immutable";
    }
}

### **8.3 Scalar API Integration (docusaurus.config.js)**

This configuration demonstrates how to embed the Scalar interactive API playground without generating physical markdown files, pointing directly to the internal Fabrik OpenAPI schema.

JavaScript

plugins:,

## ---

**9\. Recommended Final Content for 42-docusaurus.md**

# **Docusaurus Architecture & Governance (Fabrik Platform)**

## **1\. Core Deployment Architecture**

* **Static Generation Only:** Docusaurus must be compiled to pure static HTML, CSS, and JS artifacts. Server-side rendering (SSR) or running docusaurus serve within a production container is permanently banned.
* **Docker Multi-Stage Pipeline:** Applications must be deployed via Coolify using a strict two-stage process:
  1. node:20-bookworm-slim for deterministic dependency resolution and execution of npm run build.
  2. nginx:mainline-bookworm-slim to serve the resulting static /build artifact at high concurrency.
* **Nginx SPA Routing:** The Nginx configuration must explicitly define try\_files $uri $uri/ /index.html; to allow the React client-side router to handle deep URL links and hard refreshes.
* **Base Image Constraint:** All Docker environments must utilize Debian bookworm-slim. Alpine Linux is strictly prohibited to guarantee libc compatibility with the WSL Ubuntu 24.04 primary development environment.

## **2\. Platform Integrations**

* **Search (Pagefind):** The @getcanary/docusaurus-theme-search-pagefind library is mandated. Algolia (SaaS dependency) and heavy JavaScript-based local search plugins (bundle bloat) are banned. Pagefind must be executed post-build (npx \-y pagefind \--site build) to generate compressed WebAssembly (WASM) index chunks.
* **API Reference (Scalar):** OpenAPI/Swagger specifications must be rendered dynamically using @scalar/docusaurus. Static generator plugins like docusaurus-plugin-openapi-docs are banned due to unacceptable file system pollution and extended Webpack compilation times.
* **Localization (Git-Based):** Turkish/English translation workflows must use the native Git directory structure (i18n/tr/). External SaaS tools like Crowdin are prohibited to minimize operational overhead.

## **3\. Content Governance & Versioning**

* **Versioning (Immutable Archives):** Docusaurus's native versioning feature (versioned\_docs/) is banned as it exponentially destroys build performance. Legacy versions must be archived by cutting a Git branch (e.g., release/v1.x) and deploying it via Coolify as a separate static snapshot to an isolated subpath (e.g., /v1/).
* **Strict Link Checking:** docusaurus.config.js must rigidly enforce onBrokenLinks: 'throw' and onBrokenAnchors: 'throw' to halt CI pipelines upon link degradation.
* **MDX Component Registration:** Highly interactive JSX components (e.g., terminal simulators) must be registered globally within src/theme/MDXComponents.js to prevent relative import path pollution inside standard Markdown files.
* **Frontmatter Standards:** Every .md and .mdx file must contain explicit title and description YAML frontmatter for optimal SEO indexing, enforced via a pre-build Python validation script.
* **Styling Customizations:** Rely exclusively on overriding Infima CSS variables in custom.css. Banish component swizzling (npm run swizzle) unless fundamentally necessary, to ensure robust forward compatibility with major Docusaurus version upgrades.

#### **Works cited**

1. Docusaurus: Build optimized websites quickly, focus on your content, accessed April 1, 2026, [https://docusaurus.io/](https://docusaurus.io/)
2. Introduction | Docusaurus, accessed April 1, 2026, [https://docusaurus.io/docs](https://docusaurus.io/docs)
3. MDX and React \- Docusaurus, accessed April 1, 2026, [https://docusaurus.io/docs/markdown-features/react](https://docusaurus.io/docs/markdown-features/react)
4. Add Dockerfile,nginx conf file and docker-compose for deploy in prod …\#11809 \- GitHub, accessed April 1, 2026, [https://github.com/facebook/docusaurus/pull/11809](https://github.com/facebook/docusaurus/pull/11809)
5. Docs Multi-instance | Docusaurus, accessed April 1, 2026, [https://docusaurus.io/docs/docs-multi-instance](https://docusaurus.io/docs/docs-multi-instance)
6. Using Plugins | Docusaurus, accessed April 1, 2026, [https://docusaurus.io/docs/next/using-plugins](https://docusaurus.io/docs/next/using-plugins)
7. Installation \- Docusaurus, accessed April 1, 2026, [https://docusaurus.io/docs/next/installation](https://docusaurus.io/docs/next/installation)
8. Markdown Features \- Docusaurus, accessed April 1, 2026, [https://docusaurus.io/docs/markdown-features](https://docusaurus.io/docs/markdown-features)
9. Preparing your site for Docusaurus v3, accessed April 1, 2026, [https://docusaurus.io/blog/preparing-your-site-for-docusaurus-v3](https://docusaurus.io/blog/preparing-your-site-for-docusaurus-v3)
10. How do I embed global React components in Docusaurus v2? \- Stack Overflow, accessed April 1, 2026, [https://stackoverflow.com/questions/62022266/how-do-i-embed-global-react-components-in-docusaurus-v2](https://stackoverflow.com/questions/62022266/how-do-i-embed-global-react-components-in-docusaurus-v2)
11. MDX Plugins | Docusaurus, accessed April 1, 2026, [https://docusaurus.io/docs/markdown-features/plugins](https://docusaurus.io/docs/markdown-features/plugins)
12. Hooking onto Docusaurus' MDX Loader \#10829 \- GitHub, accessed April 1, 2026, [https://github.com/facebook/docusaurus/discussions/10829](https://github.com/facebook/docusaurus/discussions/10829)
13. Versioning \- Docusaurus, accessed April 1, 2026, [https://docusaurus.io/docs/versioning](https://docusaurus.io/docs/versioning)
14. Documentation about versioning across branches rather than a single directory · Issue \#8373 · facebook/docusaurus \- GitHub, accessed April 1, 2026, [https://github.com/facebook/docusaurus/issues/8373](https://github.com/facebook/docusaurus/issues/8373)
15. When docs and a dinosaur Git along: enabling versioning in Docusaurus \- Spectro Cloud, accessed April 1, 2026, [https://www.spectrocloud.com/blog/when-docs-and-a-dinosaur-git-along-enabling-versioning-in-docusaurus](https://www.spectrocloud.com/blog/when-docs-and-a-dinosaur-git-along-enabling-versioning-in-docusaurus)
16. Docusaurus Versioning \- DEV Community, accessed April 1, 2026, [https://dev.to/vanigami/docusaurus-versioning-53mb](https://dev.to/vanigami/docusaurus-versioning-53mb)
17. Search | Docusaurus, accessed April 1, 2026, [https://docusaurus.io/docs/3.3.2/search](https://docusaurus.io/docs/3.3.2/search)
18. Search | Docusaurus, accessed April 1, 2026, [https://docusaurus.io/docs/search](https://docusaurus.io/docs/search)
19. easyops-cn/docusaurus-search-local \- GitHub, accessed April 1, 2026, [https://github.com/easyops-cn/docusaurus-search-local](https://github.com/easyops-cn/docusaurus-search-local)
20. Adding local search to Docusaurous Documentation \- Medium, accessed April 1, 2026, [https://medium.com/@tejasbhovad/adding-local-search-to-docusaurous-documentation-3fce8f8750a1](https://medium.com/@tejasbhovad/adding-local-search-to-docusaurous-documentation-3fce8f8750a1)
21. Docusaurus build failed due to docusaurus-search-local plugin \- Stack Overflow, accessed April 1, 2026, [https://stackoverflow.com/questions/78875820/docusaurus-build-failed-due-to-docusaurus-search-local-plugin](https://stackoverflow.com/questions/78875820/docusaurus-build-failed-due-to-docusaurus-search-local-plugin)
22. How do people usually handle search on static sites once the content grows a bit? \- Reddit, accessed April 1, 2026, [https://www.reddit.com/r/statichosting/comments/1rteyr0/how\_do\_people\_usually\_handle\_search\_on\_static/](https://www.reddit.com/r/statichosting/comments/1rteyr0/how_do_people_usually_handle_search_on_static/)
23. Getting Started with Pagefind | Pagefind — Static low-bandwidth search at scale, accessed April 1, 2026, [https://pagefind.app/docs/](https://pagefind.app/docs/)
24. Pagefind | Pagefind — Static low-bandwidth search at scale, accessed April 1, 2026, [https://pagefind.app/](https://pagefind.app/)
25. Is pagefind the endgame for static search, or is Algolia still worth the overhead? \- Reddit, accessed April 1, 2026, [https://www.reddit.com/r/statichosting/comments/1ps9cby/is\_pagefind\_the\_endgame\_for\_static\_search\_or\_is/](https://www.reddit.com/r/statichosting/comments/1ps9cby/is_pagefind_the_endgame_for_static_search_or_is/)
26. i18n \- Introduction \- Docusaurus, accessed April 1, 2026, [https://docusaurus.io/docs/i18n/introduction](https://docusaurus.io/docs/i18n/introduction)
27. i18n \- Using Crowdin \- Docusaurus, accessed April 1, 2026, [https://docusaurus.io/docs/i18n/crowdin](https://docusaurus.io/docs/i18n/crowdin)
28. i18n \- Using git \- Docusaurus, accessed April 1, 2026, [https://docusaurus.io/docs/i18n/git](https://docusaurus.io/docs/i18n/git)
29. Docusaurus/docs/guides-translation.md at master \- GitHub, accessed April 1, 2026, [https://github.com/sunnylqm/Docusaurus/blob/master/docs/guides-translation.md](https://github.com/sunnylqm/Docusaurus/blob/master/docs/guides-translation.md)
30. OpenAPI for Docusaurus\! \- DEV Community, accessed April 1, 2026, [https://dev.to/rohit\_gohri/openapi-for-docusaurus-cnf](https://dev.to/rohit_gohri/openapi-for-docusaurus-cnf)
31. OpenAPI plugin for generating API reference docs in Docusaurus v3. \- GitHub, accessed April 1, 2026, [https://github.com/PaloAltoNetworks/docusaurus-openapi-docs](https://github.com/PaloAltoNetworks/docusaurus-openapi-docs)
32. Best Open Source and Paid OpenAPI Documentation Generators (April 2024\) \- Konfig, accessed April 1, 2026, [https://konfigthis.com/blog/openapi-documentation-generators/](https://konfigthis.com/blog/openapi-documentation-generators/)
33. I spent a few days testing out every API docs platform so you don't have to : r/node \- Reddit, accessed April 1, 2026, [https://www.reddit.com/r/node/comments/1879tg4/i\_spent\_a\_few\_days\_testing\_out\_every\_api\_docs/](https://www.reddit.com/r/node/comments/1879tg4/i_spent_a_few_days_testing_out_every_api_docs/)
34. API Reference for Docusaurus \- Scalar, accessed April 1, 2026, [https://scalar.com/products/api-references/integrations/docusaurus](https://scalar.com/products/api-references/integrations/docusaurus)
35. Choosing a docs vendor: Mintlify vs Scalar vs Bump vs ReadMe vs Redocly \- Speakeasy, accessed April 1, 2026, [https://www.speakeasy.com/blog/choosing-a-docs-vendor](https://www.speakeasy.com/blog/choosing-a-docs-vendor)
36. Deployment \- Docusaurus, accessed April 1, 2026, [https://docusaurus.io/docs/deployment](https://docusaurus.io/docs/deployment)
37. Create a doc \- Docusaurus, accessed April 1, 2026, [https://docusaurus.io/docs/next/create-doc](https://docusaurus.io/docs/next/create-doc)
38. Build a Docusaurus-like Site with FastAPI: Step 4 — Parsing Frontmatter | by Leapcell, accessed April 1, 2026, [https://leapcell.medium.com/build-a-docusaurus-like-site-with-fastapi-step-4-parsing-frontmatter-422f4a9cafe8](https://leapcell.medium.com/build-a-docusaurus-like-site-with-fastapi-step-4-parsing-frontmatter-422f4a9cafe8)
39. Search engine optimization (SEO) | Docusaurus, accessed April 1, 2026, [https://docusaurus.io/docs/seo](https://docusaurus.io/docs/seo)
40. Docusaurus 3.1, accessed April 1, 2026, [https://docusaurus.io/blog/releases/3.1](https://docusaurus.io/blog/releases/3.1)
41. docusaurus.config.js, accessed April 1, 2026, [https://docusaurus.io/docs/2.x/api/docusaurus-config](https://docusaurus.io/docs/2.x/api/docusaurus-config)
42. docusaurus.config.js, accessed April 1, 2026, [https://docusaurus.io/docs/api/docusaurus-config](https://docusaurus.io/docs/api/docusaurus-config)
43. eslint-plugin | Docusaurus, accessed April 1, 2026, [https://docusaurus.io/docs/api/misc/@docusaurus/eslint-plugin](https://docusaurus.io/docs/api/misc/@docusaurus/eslint-plugin)
44. Deployment \- Docusaurus, accessed April 1, 2026, [https://docusaurus.io/docs/2.x/deployment](https://docusaurus.io/docs/2.x/deployment)
45. Docker Deployment \- Docusaurus.community, accessed April 1, 2026, [https://docusaurus.community/knowledge/deployment/docker/](https://docusaurus.community/knowledge/deployment/docker/)
46. Encapsulate an entire Docusaurus site in a Docker image \- Christophe Avonture, accessed April 1, 2026, [https://www.avonture.be/blog/docker-docusaurus-prod/](https://www.avonture.be/blog/docker-docusaurus-prod/)
47. Tiny statically-linked nginx Docker image (\~432KB, multi-arch, FROM scratch) \- Reddit, accessed April 1, 2026, [https://www.reddit.com/r/nginx/comments/1luwwnz/tiny\_staticallylinked\_nginx\_docker\_image\_432kb/](https://www.reddit.com/r/nginx/comments/1luwwnz/tiny_staticallylinked_nginx_docker_image_432kb/)
