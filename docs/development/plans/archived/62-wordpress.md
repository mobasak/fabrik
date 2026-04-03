# **Fabrik WordPress Architecture: Permanent Rules and Execution Standards (62-wordpress.md)**

## **1\. Executive Summary**

The deployment of WordPress within the Fabrik infrastructure necessitates a rigorous paradigm shift from traditional shared hosting environments. WordPress, historically a monolithic application reliant on mutable server states, must be coerced into a modern, immutable, containerized architecture that aligns with the constraints of a solo developer operating within a 50-hour workweek. The overarching objective is to utilize WordPress strictly as a specialized content management appliance—leveraging its superior authoring experience and robust e-commerce capabilities via WooCommerce—while stripping away the operational fragility, plugin bloat, and security vulnerabilities that plague standard deployments.

The Fabrik deployment pipeline relies on a Windows Subsystem for Linux (WSL) Ubuntu 24.04 development environment, pushing to an ARM64 Ubuntu Virtual Private Server (VPS) orchestrated by Coolify using Docker Compose. This exact topological constraint dictates several immutable architectural decisions. First, while the Fabrik default database standard is PostgreSQL 16, attempting to force WordPress to run on PostgreSQL via translation layers (such as PG4WP) introduces unacceptable instability and maintenance overhead, often breaking during core updates or when interfacing with third-party plugins.1 Therefore, MariaDB 10.6+ is established as the sole authorized database engine for WordPress workloads, fully supporting the ARM64 architecture and offering superior thread-pooling performance for high-concurrency environments.3 Furthermore, Docker base images must strictly utilize Debian slim-bookworm variants, categorically banning alpine due to musl-libc DNS resolution anomalies and PHP extension compilation complexities on ARM64 processors.5

Operational durability dictates that server-level optimizations must supersede application-level plugins. Caching is delegated entirely to Nginx FastCGI Cache and Redis Object Cache, bypassing PHP-FPM execution entirely for anonymous traffic.7 This drastically reduces CPU cycles on budget-conscious VPS hardware, providing enterprise-grade Time to First Byte (TTFB) without relying on commercial Content Delivery Networks (CDNs) or bloated caching plugins.7 Security is enforced at the immutable container layer: file permissions are locked, wp-config.php variables are injected securely at runtime via Docker environment variables, and the WordPress dashboard file editor is permanently disabled.10

Ultimately, this report defines the execution handoffs, automated verification mechanisms, and human-in-the-loop guidelines required to deploy WordPress as a low-ops, high-performance service. Whether operating as a traditional monolithic frontend or as a Headless CMS via WPGraphQL feeding a Next.js 14 App Router application, the protocols outlined herein form the permanent 62-wordpress.md rule file for Fabrik agents.

## **Architectural Deep Dive and Core Paradigms**

The following subsections provide an exhaustive analysis of the technical mechanisms that inform the Fabrik WordPress standards. Understanding the rationale guarantees that autonomous agents and human operators do not deviate into high-maintenance anti-patterns.

### **Containerization Strategy and ARM64 Compatibility**

The deployment target is an ARM64-based VPS managed via Coolify. The official WordPress Docker images support the arm64v8 architecture natively.6 However, image tagging discipline is paramount. The use of the latest tag is prohibited as it leads to unpredictable upstream updates that break container immutability and can introduce breaking changes to PHP runtimes without warning. The designated image standard must lock the PHP version and the operating system release, specifically utilizing tags such as wordpress:php8.2-fpm-bookworm or wordpress:cli-php8.2-bookworm.5

The Alpine Linux variants are explicitly banned across the Fabrik stack. While Alpine produces smaller image sizes, its reliance on musl-libc instead of the GNU C Library (glibc) introduces profound edge-case bugs when compiling complex PHP extensions or handling DNS lookups inside Docker networks, particularly on ARM64 architectures.5 The Debian slim-bookworm base provides the optimal balance of a reduced attack surface and glibc stability, ensuring that critical PHP extensions required by WordPress (such as mysqli, gd, and imagick) compile and function reliably without requiring extensive custom Dockerfile modifications.5

### **Database Selection: The MariaDB Exception**

Fabrik's default infrastructure stack relies heavily on PostgreSQL 16 due to its advanced data modeling, robust JSONB support, and superior analytics capabilities.1 However, WordPress was fundamentally engineered around the MySQL architecture.14 While community forks and plugins like pg4wp exist to translate MySQL queries to PostgreSQL dialects, they are notoriously brittle, lack full compatibility with the broader plugin ecosystem, and frequently trigger fatal errors during major core or schema updates.2 For a solo developer constrained by time, fighting the CMS's native database layer is an egregious anti-pattern that guarantees high maintenance overhead.

Consequently, MariaDB is instituted as the mandatory database for all WordPress deployments. MariaDB offers excellent multithreaded performance, a highly optimized thread-pooling architecture that excels in high-concurrency PHP environments, and seamless ARM64 container support.3 By running MariaDB 10.6+ in a dedicated container, the deployment achieves the necessary relational data persistence without compromising the stability of the WordPress core.3

### **State Management and Volume Persistence**

Docker containers are inherently ephemeral. If a container is stopped, rebuilt, or destroyed, all data written to its internal filesystem vanishes. WordPress splits its operational state between the database (which stores content, taxonomy, and configurations) and the filesystem (which stores media uploads, installed plugins, and themes located within the wp-content directory).16 To guarantee data durability across deployments and container rebuilds, the wp-content directory must be mapped to a persistent Docker volume managed by the Coolify orchestration engine.18

Bind mounting the entire /var/www/html root directory to the host system is highly discouraged. Doing so defeats the purpose of containerized core updates, as the host filesystem will override the updated core files provided by a newly pulled Docker image.16 By persisting only the wp-content directory, the WordPress core can be updated simply by pulling a newer Docker image and restarting the container, maintaining a strict separation between the immutable application core and the mutable user-generated data.16

File permissions within these persistent volumes must be strictly controlled to prevent 403 Forbidden errors or upload failures. The www-data user (typically assigned UID 33 in Debian-based images) must own the wp-content directory to allow the web server to process media uploads and install plugins.21 Core files outside of this directory must remain read-only to limit the blast radius of any potential code injection vulnerability.11

### **Performance Optimization: The Server-Side Mandate**

A pervasive anti-pattern in the WordPress ecosystem is the reliance on heavy PHP-based caching plugins (such as WP Rocket, W3 Total Cache, or WP Super Cache).23 In a low-ops, resource-constrained VPS environment, invoking the PHP-FPM interpreter merely to determine if a page should be served from a cache is a significant waste of CPU cycles and memory.23 The Fabrik standard dictates that caching must occur at the server layer, long before the application logic is engaged.

Nginx FastCGI Cache is the enforced mechanism for full-page caching. Nginx is configured to store fully rendered HTML responses in a designated memory or disk path. When an anonymous user requests a page, Nginx serves the static HTML directly, bypassing PHP-FPM and MariaDB entirely.7 This architectural shift reduces server response times (TTFB) from an average of 1500ms to approximately 40ms, allowing a single VPS to handle thousands of concurrent anonymous requests without breaking a sweat.7

For dynamic requests (e.g., logged-in administrators, users with active WooCommerce cart sessions), Nginx is instructed to bypass the HTML cache.7 To accelerate these dynamic requests, Redis Object Cache is deployed via a dedicated Docker container.7 Redis operates as an in-memory data structure store, holding the results of complex database queries in RAM.7 When WordPress requires data, it first checks the Redis cache; if the data is present, the database query is skipped, reducing database load and query execution times to sub-millisecond levels.7 This dual-layer caching topology completely eliminates the need for third-party performance plugins, reducing maintenance overhead and minimizing the plugin vulnerability attack surface. Furthermore, image optimization (such as WebP conversion) should be handled prior to upload or via lightweight CLI tools, avoiding bloated UI-heavy plugins that drag down administrative performance.7

### **Minimum Viable Security Hardening**

WordPress is the most frequently targeted CMS globally, subject to constant automated scanning and brute-force attacks. Security cannot rely on reactive plugins; it must be baked into the infrastructure.10 The minimum viable security hardening for a solo developer on a self-hosted Docker environment focuses on reducing the attack surface through configuration management.

The wp-config.php file is the most critical asset, housing database credentials, cryptographic salts, and absolute path definitions.11 In the Fabrik architecture, no secrets are ever hardcoded into this file. Instead, the Docker Compose file passes environment variables (e.g., WORDPRESS\_DB\_PASSWORD, WORDPRESS\_AUTH\_KEY) into the container, which are dynamically read by a heavily restricted wp-config.php during execution.11 To further secure this file, Nginx is configured to explicitly deny all HTTP requests targeting wp-config.php, returning a 403 Forbidden response.10

The WordPress administrative interface contains a built-in file editor for themes and plugins. If an administrator account is compromised via credential stuffing or phishing, this editor allows attackers to execute arbitrary PHP code directly on the server.28 This vector must be neutralized by enforcing the define('DISALLOW\_FILE\_EDIT', true); constant in the configuration.10

Additionally, XML-RPC, a legacy protocol responsible for over 90% of WordPress brute-force amplification attacks, must be disabled. Rather than using a plugin to disable it, the xmlrpc.php endpoint must be blocked directly at the Nginx routing layer, dropping malicious traffic before it ever reaches the PHP interpreter.26 Finally, default administrative usernames (e.g., "admin") are strictly prohibited, and the login endpoint must be protected by rate-limiting rules at the proxy layer or via a lightweight, single-purpose login protection plugin.30

### **Plugin Selection Criteria and Bloat Avoidance**

For a solo developer managing multiple projects, plugin bloat represents the highest risk to long-term maintainability. Every added plugin introduces potential security vulnerabilities, database bloat via orphaned wp\_options transients, and frontend performance degradation through unnecessary CSS and JavaScript enqueuing.32

Plugin selection must follow strict discipline. Tools like Query Monitor must be utilized in the development environment to profile the exact impact a plugin has on database query times, memory usage, and HTTP requests.33 "All-in-one" suite plugins are banned in favor of single-purpose, highly focused tools.33 For instance, rather than installing a monolithic SEO plugin that attempts to handle redirects, analytics, and caching, the deployment should utilize a lightweight SEO framework (such as RankMath with unused modules disabled) strictly for meta-tag generation and XML sitemaps.34 Redirection should be handled at the Nginx level where possible, or via a dedicated lightweight redirection plugin if client access is required.35

### **Theme Selection and Content Workflow**

The era of heavy, monolithic page builders (such as Elementor, Divi, or WPBakery) is over for modern, performant WordPress deployments. These tools generate excessive DOM elements, rely heavily on slow JavaScript execution, and lock content into proprietary shortcodes that make future migrations nearly impossible.33 The Fabrik standard mandates the use of native Gutenberg Block Themes and Full Site Editing (FSE) capabilities, or highly optimized, lightweight framework themes like GeneratePress.33 By leveraging native CSS Grid and Flexbox controls integrated directly into the block editor, developers can achieve complex layouts without the performance penalties of third-party builders.37

When customizations are necessary, direct modification of parent theme files is strictly forbidden. A Child Theme must always be utilized to ensure that custom PHP functions, template overrides, and CSS styling survive upstream theme updates.33

Content workflows must also be disciplined to prevent database bloat. WordPress natively stores an infinite number of revisions for every post and page, which can rapidly inflate the wp\_posts table and slow down database queries.38 The configuration must enforce a hard limit on revisions by adding define('WP\_POST\_REVISIONS', 5); to the wp-config.php file.39 For database cleanup, automated WP-CLI cron jobs should be preferred over heavy database optimization plugins.40

### **WooCommerce Integration: Lowest-Maintenance Patterns**

Deploying e-commerce introduces significant operational complexity. Calculating sales tax across multiple state or international jurisdictions, managing live shipping rates, and handling payment gateways can consume immense amounts of development time. To align with the budget-conscious, low-ops constraints of the Fabrik environment, WooCommerce must be heavily automated.

Manual tax table management is strictly prohibited. For small stores, the Automattic WooCommerce Shipping & Tax extension is mandatory.41 This plugin offloads all tax nexus calculations and shipping label generation to external API endpoints, transforming a complex legal and operational burden into a hands-off, automated process.41 By shifting the computational load to external servers, the local database remains lean and compliance is guaranteed without manual intervention.41 Payment processing should be centralized through a reliable, low-maintenance gateway such as Stripe, utilizing their officially supported integration plugins.43

### **Multi-Language Setup and Architecture**

When a project requires multilingual content delivery, the choice of translation architecture drastically impacts database performance and server overhead.

| Plugin | Architecture | Performance Impact | Fabrik Status |
| :---- | :---- | :---- | :---- |
| **WPML** | Monolithic, custom database tables. | Heavy. Known for database bloat and complex configuration.44 | **Banned** |
| **TranslatePress** | Frontend visual editor, string replacement on the fly. | High CPU overhead. Requires aggressive caching to remain performant on large sites.46 | **Banned** |
| **Polylang** | Native WordPress taxonomies, creates separate posts per language. | Extremely lightweight. Sub-second load times natively, scales linearly with the database.46 | **Enforced** |

Polylang is the enforced standard for Fabrik. By utilizing native WordPress data structures rather than abstracting translations into custom tables or parsing the DOM on the fly, Polylang ensures that multilingual sites remain as fast as their single-language counterparts.46

### **Backup and Restore Discipline**

Relying on PHP-based backup plugins (e.g., UpdraftPlus, BackWPup) in a Dockerized environment is a critical anti-pattern. These plugins rely on the PHP execution lifecycle, which is prone to timeout limits and memory exhaustion when archiving large wp-content directories or massive databases. Furthermore, if the server itself is compromised, local backups managed by plugins may be deleted or encrypted by ransomware.48

The Fabrik backup discipline mandates an independent, server-level approach. Backups must be executed via a dedicated bash script scheduled via the host's cron daemon or Coolify's built-in scheduled tasks.50 This script utilizes raw binary commands: mysqldump to extract the database schema and content, and tar to compress the wp-content persistent volume.50 Once compressed, the archive is immediately synced to an immutable, off-site S3-compatible storage bucket (e.g., AWS S3, Cloudflare R2, or Backblaze B2) utilizing the AWS CLI or a lightweight Go binary like Restic.50 This approach guarantees zero-touch, high-speed backups that operate entirely outside the WordPress application layer, ensuring durability even in the event of total container failure.50

### **WP-CLI Automation Patterns**

Manual administration via the WordPress dashboard is inefficient and prone to human error. WP-CLI, the command-line interface for WordPress, must be bundled into the deployment stack to automate routine maintenance, updates, and configuration tasks.52

Every Fabrik WordPress project must include a Makefile that wraps common WP-CLI commands executed via Docker exec.54 Standard Makefile targets must include commands to update the WordPress core, plugins, and themes (wp core update, wp plugin update \--all), flush the Redis object cache (wp cache flush), and safely execute search-and-replace operations across the database during domain migrations (wp search-replace).54 By standardizing these operations into a Makefile, solo developers can perform complex maintenance routines with a single command, ensuring consistency across the entire fleet of managed sites.53

### **WordPress as a Headless CMS**

WordPress does not make sense when custom application logic, complex state management, or tight API-first architectures are required. In such cases, the Fabrik stack defaults to Next.js 14 and Python FastAPI.1 However, when clients demand the superior editorial experience of WordPress but require the performance and security of a modern frontend, WordPress operates effectively as a Headless CMS.

In a Headless architecture, the traditional monolithic frontend is disabled, and content is exposed via APIs to a Next.js 14 App Router application.57 To prevent over-fetching and payload bloat associated with the native REST API, the WPGraphQL plugin is enforced to provide a strongly typed, efficient GraphQL schema.57 The native REST API endpoints must be restricted to authenticated traffic only to prevent unauthorized data scraping.60

A major technical challenge in Headless WordPress is the preview functionality. Editors expect to click "Preview" and see how their unpublished drafts will look on the frontend.62 To resolve this, Next.js Draft Mode must be integrated alongside the WPGraphQL JWT Authentication plugin.57 When a preview is requested, WordPress generates a short-lived JSON Web Token (JWT) encoding the post ID and redirecting to a specific Next.js API route.62 The Next.js server validates the token, bypasses static generation, and securely fetches the draft content directly from the GraphQL endpoint, providing a seamless editorial experience while maintaining strict frontend security.62

## **2\. Canonical Rules for this Rule File**

These 15 canonical rules represent the immutable foundation of WordPress deployments within the Fabrik ecosystem. They must be strictly adhered to by all autonomous agents and human developers, serving as the definitive criteria for automated code review.

1. **Enforce MariaDB over PostgreSQL:** WordPress deployments must exclusively use MariaDB 10.6+ containers; utilizing PostgreSQL via translation plugins is strictly prohibited due to severe stability and compatibility issues.2
2. **Strict Debian Base Images:** Docker configurations must utilize slim-bookworm tags (e.g., wordpress:php8.2-fpm-bookworm). Alpine images are permanently banned due to arm64 musl-libc compilation errors and DNS resolution vulnerabilities.5
3. **Ephemeral Core, Persistent State:** The WordPress container itself must remain ephemeral. Only the /var/www/html/wp-content directory and the MariaDB data directory may be mapped to persistent Coolify Docker volumes.16
4. **Decoupled Web Server:** The standard wordpress:latest (Apache) image is banned. Deployments must use the php-fpm variant positioned behind a dedicated Nginx container to enable advanced server-side caching topologies.7
5. **Server-Level Caching Exclusivity:** All frontend HTML page caching must be handled by Nginx FastCGI Cache. PHP-based caching plugins (e.g., WP Rocket, W3 Total Cache) are strictly prohibited to conserve CPU cycles.7
6. **Redis Object Caching:** A dedicated Redis container must be deployed to offload database queries, integrated seamlessly via the Redis Object Cache plugin and configured via wp-config.php constants.7
7. **Immutable Secrets Management:** Cryptographic salts and database credentials must never be hardcoded into PHP files. They must be injected into the container via Coolify environment variables and dynamically read.11
8. **Disable Dashboard Execution:** The wp-config.php file must contain define('DISALLOW\_FILE\_EDIT', true); to categorically prevent malicious PHP execution if an administrator account is compromised.10
9. **XML-RPC Eradication:** The legacy xmlrpc.php file must be blocked at the Nginx configuration level to neutralize automated brute-force botnets before they reach the application layer.26
10. **Taxonomy-Based Translation:** Multilingual sites must utilize Polylang. WPML and TranslatePress are banned due to excessive database bloat and severe CPU rendering overhead, respectively.46
11. **Automated E-Commerce Compliance:** WooCommerce installations must utilize the Automattic WooCommerce Shipping & Tax plugin to offload nexus and rate calculations; manual tax table management is prohibited.41
12. **WP-CLI Automation:** All repetitive administrative tasks (core updates, plugin installations, cache flushing) must be scripted in a Makefile utilizing WP-CLI commands executed inside the container.53
13. **Headless Endpoint Security:** When functioning as a Headless CMS via WPGraphQL, the default WordPress REST API endpoints must be restricted to authenticated traffic only.60
14. **Headless Draft Previews:** Next.js 14 App Router integrations must implement Next.js Draft Mode alongside WPGraphQL JWT tokens to securely render unpublished draft content for editors.62
15. **Independent Backup Infrastructure:** Backups must be executed at the server level via a bash script utilizing mysqldump and tar, syncing directly to S3 storage. Over-reliance on PHP-based backup plugins is banned.50

## **3\. Anti-Patterns / Banned Patterns**

The following practices introduce severe technical debt, degrade performance, or compromise the security posture of the Fabrik infrastructure. Agents must flag and remove these patterns immediately during the code generation or review phases.

| Anti-Pattern | Description and Rationale | Fabrik Standard Alternative |
| :---- | :---- | :---- |
| **Alpine Base Images** | Using wordpress:alpine or php:alpine tags causes musl-libc compatibility errors on ARM64 processors, specifically breaking image processing extensions like Imagick. 5 | Strictly use slim-bookworm Debian images for all PHP and WordPress containers. |
| **PostgreSQL Integration** | Attempting to force WP onto Postgres using pg4wp leads to profound plugin incompatibility, degraded performance, and broken core updates. 2 | Use MariaDB 10.6+ natively. Reserve PostgreSQL for Next.js/FastAPI custom applications. |
| **Full Root Bind Mounts** | Mounting the entire /var/www/html to the host system breaks container immutability, complicates updates, and frequently causes file permission conflicts. 16 | Mount only /var/www/html/wp-content as a named Coolify Docker volume. 19 |
| **PHP Caching Plugins** | Using WP Rocket, W3 Total Cache, or SuperCache consumes excessive PHP-FPM workers just to serve static files, defeating the purpose of caching on budget hardware. 23 | Use Nginx FastCGI Cache to intercept and serve requests before they hit the PHP interpreter. 7 |
| **Hardcoded wp-config.php** | Placing DB passwords or salt strings directly into version-controlled PHP files exposes critical infrastructure to credential theft. 27 | Use getenv('WORDPRESS\_DB\_PASSWORD') populated dynamically from Coolify environment variables. 11 |
| **Manual WooCommerce Taxes** | Attempting to maintain complex state, country, or VAT tax tables manually leads to massive legal and operational maintenance burdens. 41 | Use the automated WooCommerce Shipping & Tax API to offload calculations. 42 |
| **TranslatePress/WPML** | Heavy plugins that parse the DOM on every load (TranslatePress) or create massive proprietary database tables (WPML) slowing down queries. 44 | Use Polylang for native, lightweight post-based taxonomy translation. 47 |
| **Active XML-RPC** | Leaving xmlrpc.php accessible allows massive brute force credential stuffing attacks that exhaust server resources. 26 | Block xmlrpc.php aggressively via Nginx server blocks. |
| **Dashboard File Editing** | Allowing administrators to edit functions.php via the WP dashboard provides a direct vector for remote code execution if an account is compromised. 28 | Enforce DISALLOW\_FILE\_EDIT=true in the configuration. 10 |
| **Heavy Page Builders** | Using Elementor, Divi, or WPBakery generates excessive DOM bloat, slows load times, and locks content into proprietary shortcodes. 33 | Use native Gutenberg Block Themes (FSE), lightweight frameworks like GeneratePress, or a Next.js Headless frontend. 37 |

## **4\. What to Enforce in Execute Handoffs**

During the CI/CD pipeline and deployment phase (Execute Handoffs), specific configurations must be definitively established before the application is permitted to transition to a running state. Agents must verify these parameters proactively.

* **Docker Volumes Provisioning:** Enforce the creation of wordpress-content and mariadb-data as Coolify named volumes prior to deployment. Never rely on arbitrary host paths or local directories that bypass Coolify's management orchestration.66
* **Permissions Injection:** The wp-content directory within the persistent volume must be forcefully chowned to www-data:www-data (UID 33). Failure to do so will result in media upload failures and plugin installation errors. This must be handled via a custom entrypoint script or a brief initialization container command prior to the main application boot.21
* **Environment Variable Validation:** Ensure the deployment orchestrator (Coolify) injects the following mandatory variables into both the WordPress and MariaDB containers: MYSQL\_ROOT\_PASSWORD, MYSQL\_DATABASE, MYSQL\_USER, MYSQL\_PASSWORD, alongside the 8 cryptographic WordPress salts (e.g., WP\_AUTH\_KEY, WP\_SECURE\_AUTH\_SALT). The application must halt if these are missing.27
* **Nginx Configuration Delivery:** Ensure the custom Nginx configuration file, which explicitly defines the fastcgi\_cache\_path directives and block rules, is properly mounted as a read-only (:ro) file into the Nginx container at /etc/nginx/conf.d/default.conf.7
* **WP-CLI Initialization Sequence:** Upon the very first successful boot, the handoff process must trigger a WP-CLI script (via the defined Makefile) to automatically configure URL structures (wp option update siteurl), set standard permalinks (wp rewrite flush \--hard), and activate required core plugins like the Redis Object Cache.54

## **5\. What to Verify in final\_gate.py**

The final\_gate.py script serves as the ultimate automated compliance checker within the Fabrik pipeline. It must parse the project codebase utilizing Abstract Syntax Trees (AST) and regular expressions to ensure no anti-patterns are merged into the main branch.

* **Base Image Verification:** Parse the Dockerfile and docker-compose.yml configurations. Raise a critical build failure if the string alpine is detected in any WordPress, PHP, or Nginx image tag. The script must explicitly require slim-bookworm or bookworm signatures.5
* **Database Engine Scrutiny:** Parse docker-compose.yml. Fail the build if postgres or mysql is specified instead of mariadb for the WordPress backend database service. Ensure the version specified is 10.6 or higher.3
* **Volume Mapping Checks:** Parse docker-compose.yml. Ensure the wordpress service only mounts specific subdirectories (e.g., ./wp-content or a named volume) to /var/www/html/wp-content. Throw an error if the entire /var/www/html root is mapped.16
* **Security Constants Check:** Perform a regex search on wp-config.php (or the initialization script generating it). Ensure the exact presence of define('DISALLOW\_FILE\_EDIT', true);. Furthermore, ensure that database variables are utilizing getenv() or $\_ENV rather than containing raw, hardcoded string credentials.10
* **Nginx FastCGI Validation:** Parse the custom nginx.conf file. Verify the presence of the fastcgi\_cache\_path directive and a corresponding location block mapping PHP requests to the php-fpm container on port 9000\.7
* **XML-RPC Blocking Affirmation:** Parse nginx.conf to verify the presence of a location \~\* ^/xmlrpc.php block that returns a 403 or 444 HTTP response code, ensuring brute-force protection is active.29
* **GraphQL Endpoint Check (If Headless):** If the project metadata flags it as a Headless Next.js deployment, parse the plugin installation manifest to ensure wp-graphql and wp-graphql-jwt-authentication are listed as required dependencies.

## **6\. What belongs in AGENTS.md / AGENTS-compact.md**

Autonomous agents require clear, contextual boundaries regarding *when* to deploy WordPress versus alternative stacks in the Fabrik repertoire. The following heuristics must be embedded into the agent routing guidelines:

**When to deploy WordPress:**

* The project is heavily reliant on frequent editorial content creation (blogs, digital magazines, robust documentation) where end-clients demand a familiar, highly accessible WYSIWYG authoring experience.
* The project requires out-of-the-box e-commerce (WooCommerce) for physical or digital goods, especially when complex, automated shipping matrices and tax compliance are required immediately.42
* The client requires a decoupled architecture where a Next.js frontend is fed by an easily manageable, non-technical backend (Headless WP via WPGraphQL).57
* The system requires multi-language content architectures (using Polylang) but does not possess highly complex custom application logic.47

**When NOT to deploy WordPress:**

* The application requires complex, custom, user-specific business logic (e.g., a SaaS dashboard with custom data visualizations, complex state management). Route immediately to Next.js \+ FastAPI \+ PostgreSQL.1
* The underlying data model requires highly relational queries, vector embeddings for AI integrations, or complex JSONB operations. Route to PostgreSQL 16\.1
* The primary objective is to serve as an API-first microservice for mobile applications. Route to Python FastAPI.

**General Operational Guidance for Agents:**

* Always approach WordPress as a inherently fragile ecosystem. Contain and isolate it strictly via Docker; never install it directly on the host OS.
* Never attempt to solve a performance or security problem with a WordPress plugin if the issue can be resolved at the Nginx or Docker infrastructure configuration level.
* Maintain a strict budget-conscious mindset: leverage native Linux server capabilities (cron, bash scripts, WP-CLI) instead of paying recurring fees for premium SaaS plugins.

## **7\. Minimal Practical Examples for Fabrik Stack**

To ensure rapid, standardized deployment, agents must utilize the following code archetypes as the foundation for any new WordPress environment.

### **7.1. High-Performance docker-compose.yml (Coolify / ARM64)**

This configuration decouples the web server from PHP, utilizes MariaDB, and implements Redis for high-speed object caching.

YAML

version: "3.8"
services:
  nginx:
    image: nginx:1.25-alpine \# Nginx can safely use Alpine; WP/PHP cannot
    container\_name: wp-nginx
    restart: unless-stopped
    ports:
      \- "80:80"
    volumes:
      \- wp\_content:/var/www/html/wp-content:ro \# Serve static media directly, read-only
      \-./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
      \- fastcgi\_cache:/var/cache/nginx/fastcgi
    depends\_on:
      \- wordpress
    networks:
      \- wp\_network

  wordpress:
    image: wordpress:6.4-php8.2-fpm-bookworm \# Strict Debian slim-bookworm requirement
    container\_name: wp-php
    restart: unless-stopped
    volumes:
      \- wp\_content:/var/www/html/wp-content \# Persistent uploads/plugins
    environment:
      WORDPRESS\_DB\_HOST: wp-mariadb:3306
      WORDPRESS\_DB\_NAME: ${MYSQL\_DATABASE}
      WORDPRESS\_DB\_USER: ${MYSQL\_USER}
      WORDPRESS\_DB\_PASSWORD: ${MYSQL\_PASSWORD}
      WP\_REDIS\_HOST: wp-redis
    networks:
      \- wp\_network

  wp-mariadb:
    image: mariadb:10.11-jammy \# ARM64 compatible MariaDB
    container\_name: wp-mariadb
    restart: unless-stopped
    command: '--default-authentication-plugin=mysql\_native\_password'
    volumes:
      \- db\_data:/var/lib/mysql
    environment:
      MYSQL\_ROOT\_PASSWORD: ${MYSQL\_ROOT\_PASSWORD}
      MYSQL\_DATABASE: ${MYSQL\_DATABASE}
      MYSQL\_USER: ${MYSQL\_USER}
      MYSQL\_PASSWORD: ${MYSQL\_PASSWORD}
    networks:
      \- wp\_network

  wp-redis:
    image: redis:7-bookworm
    container\_name: wp-redis
    restart: unless-stopped
    volumes:
      \- redis\_data:/data
    networks:
      \- wp\_network

volumes:
  wp\_content:
    name: ${COOLIFY\_RESOURCE\_UUID}\_wp\_content \# Coolify automated prefixing
  db\_data:
    name: ${COOLIFY\_RESOURCE\_UUID}\_db\_data
  redis\_data:
    name: ${COOLIFY\_RESOURCE\_UUID}\_redis\_data
  fastcgi\_cache:
    driver\_opts:
      type: tmpfs \# Store cache in RAM for blazing fast TTFB
      device: tmpfs

networks:
  wp\_network:
    name: wp\_network

### **7.2. Nginx FastCGI and Security Configuration (default.conf)**

This configuration intercepts requests, caches HTML, and explicitly blocks malicious attack vectors before they reach PHP.

Nginx

fastcgi\_cache\_path /var/cache/nginx/fastcgi levels=1:2 keys\_zone=WORDPRESS:100m inactive=60m max\_size=512m;
fastcgi\_cache\_key "$scheme$request\_method$host$request\_uri";

server {
    listen 80;
    server\_name \_;
    root /var/www/html;
    index index.php;

    \# Security: Block XML-RPC completely
    location \= /xmlrpc.php {
        deny all;
        access\_log off;
        log\_not\_found off;
    }

    \# Cache bypass rules for dynamic content
    set $skip\_cache 0;
    if ($request\_method \= POST) { set $skip\_cache 1; }
    if ($query\_string\!= "") { set $skip\_cache 1; }
    if ($request\_uri \~\* "/wp-admin/|/xmlrpc.php|wp-.\*.php|^/feed/\*|/tag/.\*/feed/\*|index.php|/.\*sitemap.\*\\.(xml|xsl)") {
        set $skip\_cache 1;
    }
    if ($http\_cookie \~\* "comment\_author|wordpress\_\[a-f0-9\]+|wp-postpass|wordpress\_no\_cache|wordpress\_logged\_in") {
        set $skip\_cache 1;
    }

    location / {
        try\_files $uri $uri/ /index.php?$args;
    }

    location \~ \\.php$ {
        try\_files $uri \=404;
        fastcgi\_split\_path\_info ^(.+\\.php)(/.+)$;
        fastcgi\_pass wordpress:9000; \# Route to PHP-FPM container
        fastcgi\_index index.php;
        include fastcgi\_params;
        fastcgi\_param SCRIPT\_FILENAME $document\_root$fastcgi\_script\_name;

        \# FastCGI Cache Directives
        fastcgi\_cache\_bypass $skip\_cache;
        fastcgi\_no\_cache $skip\_cache;
        fastcgi\_cache WORDPRESS;
        fastcgi\_cache\_valid 200 301 302 60m;
        add\_header X-FastCGI-Cache $upstream\_cache\_status;
    }
}

### **7.3. WP-CLI Automation (Makefile)**

A standardized Makefile simplifies tedious maintenance by routing WP-CLI commands through Docker exec.

Makefile

**.PHONY**: update cache-flush scaffold backup

CONTAINER\_NAME=wp-php

update:
	@echo "Updating WordPress Core, Themes, and Plugins..."
	docker exec \-it $(CONTAINER\_NAME) wp core update \--allow-root
	docker exec \-it $(CONTAINER\_NAME) wp plugin update \--all \--allow-root
	docker exec \-it $(CONTAINER\_NAME) wp theme update \--all \--allow-root

cache-flush:
	@echo "Flushing Redis Object Cache..."
	docker exec \-it $(CONTAINER\_NAME) wp cache flush \--allow-root

scaffold:
	@echo "Configuring production defaults..."
	docker exec \-it $(CONTAINER\_NAME) wp rewrite flush \--hard \--allow-root
	docker exec \-it $(CONTAINER\_NAME) wp plugin install redis-cache \--activate \--allow-root
	docker exec \-it $(CONTAINER\_NAME) wp redis enable \--allow-root

backup:
	@echo "Executing S3 Backup script..."
	bash./scripts/s3\_backup.sh

### **7.4. Server-Level Backup to S3 (s3\_backup.sh)**

This script bypasses heavy PHP plugins, utilizing raw mysqldump and tar to synchronize data directly to S3-compatible storage.

Bash

\#\!/bin/bash
\# s3\_backup.sh \- Executed via host cron or Coolify scheduler
TIMESTAMP=$(date \+"%Y%m%d\_%H%M%S")
DB\_CONTAINER="wp-mariadb"
WP\_CONTAINER="wp-php"
BACKUP\_DIR="/tmp/wp\_backups"
S3\_BUCKET="s3://fabrik-wp-backups/my-site"

mkdir \-p $BACKUP\_DIR

\# 1\. Dump Database directly from MariaDB container
docker exec $DB\_CONTAINER sh \-c 'exec mysqldump \-u"$MYSQL\_USER" \-p"$MYSQL\_PASSWORD" "$MYSQL\_DATABASE"' \> $BACKUP\_DIR/db\_$TIMESTAMP.sql

\# 2\. Archive wp-content volume
docker cp $WP\_CONTAINER:/var/www/html/wp-content $BACKUP\_DIR/wp-content
tar \-czf $BACKUP\_DIR/wp\_content\_$TIMESTAMP.tar.gz \-C $BACKUP\_DIR wp-content

\# 3\. Sync to S3 using AWS CLI
aws s3 cp $BACKUP\_DIR/db\_$TIMESTAMP.sql $S3\_BUCKET/db/
aws s3 cp $BACKUP\_DIR/wp\_content\_$TIMESTAMP.tar.gz $S3\_BUCKET/files/

\# 4\. Cleanup local temporary files
rm \-rf $BACKUP\_DIR
echo "Backup $TIMESTAMP completed and pushed to S3."

## **8\. Recommended Final Content for the Rule File**

# **Fabrik Rule: WordPress Architecture & Deployment (62-wordpress.md)**

## **Context**

Applies to all WordPress workloads deployed on Fabrik's Coolify ARM64 VPS infrastructure. The architecture is designed for a low-ops, solo-developer environment, prioritizing extreme durability, cache-level performance, and strict container immutability over traditional shared-hosting paradigms.

## **1\. Database & Image Enforcement**

* **MariaDB Exclusivity**: WordPress runs natively on MySQL/MariaDB. Never force WordPress onto PostgreSQL via translation layers. Use mariadb:10.6+ images.
* **Strict Debian Base**: Always utilize wordpress:php8.x-fpm-bookworm. **Alpine Linux is strictly banned** for PHP/WP containers due to ARM64 DNS failures and musl-libc compilation errors.

## **2\. Infrastructure & Caching**

* **Decoupled Nginx**: Run WordPress as a php-fpm container positioned behind an nginx container to intercept traffic.
* **Nginx FastCGI Cache**: Implement full-page HTML caching via Nginx FastCGI. **Banned**: WP Rocket, W3 Total Cache, or any PHP-level page cacher that wastes CPU cycles.
* **Redis Object Cache**: Deploy a dedicated redis container and utilize the Redis Object Cache plugin to intercept and memoize database queries.

## **3\. Volume & State Management**

* **Persistent wp-content Only**: Never bind mount the entire /var/www/html root. Only map /var/www/html/wp-content to a named Coolify Docker volume.
* **Permissions**: Ensure the wp-content volume is explicitly owned by www-data:www-data (UID 33\) to allow media uploads.

## **4\. Security Hardening**

* **Dynamic Configs**: Inject all database credentials and cryptographic salts into the container via Coolify Environment Variables. Never hardcode secrets.
* **Disable Edits**: The wp-config.php file must include define('DISALLOW\_FILE\_EDIT', true); to prevent remote code execution.
* **Block XML-RPC**: Ensure nginx.conf explicitly returns 403 or 444 for /xmlrpc.php to neutralize automated brute-force attacks.

## **5\. Ecosystem Discipline**

* **Theme Selection**: Utilize native Gutenberg Block Themes or lightweight frameworks (GeneratePress). Heavy DOM builders (Elementor/Divi) are banned. Always utilize Child Themes for custom PHP.
* **WooCommerce**: Use WooCommerce Shipping & Tax for automated tax/shipping compliance via external APIs. Do not manage manual tax rate tables.
* **Multi-language**: Use Polylang (native taxonomy). **Banned**: WPML (excessive DB bloat) and TranslatePress (CPU overhead).
* **SEO**: Utilize RankMath configured strictly for sitemaps and structured data generation.
* **Automation**: Execute all maintenance (updates, DB flushes) via WP-CLI integrated into a project Makefile. Limit revisions via WP\_POST\_REVISIONS.
* **Backups**: Utilize server-level bash scripts (mysqldump \+ tar) to sync data to S3. Do not rely exclusively on PHP-based backup plugins.

## **6\. Headless Next.js Integration**

* For Headless WP architectures utilizing the Next.js 14 App Router, expose content data securely via WPGraphQL.
* Implement **Next.js Draft Mode** authenticated via short-lived WPGraphQL JWT tokens to allow editors to preview unpublished content securely. Restrict standard REST API endpoints to authenticated users only.

#### **Works cited**

1. Why PostgreSQL Still Reigns in 2025 Despite the AI DB Craze | by Hash Block \- Medium, accessed April 1, 2026, [https://medium.com/@connect.hashblock/why-postgresql-still-reigns-in-2025-despite-the-ai-db-craze-cbcaff49b9de](https://medium.com/@connect.hashblock/why-postgresql-still-reigns-in-2025-despite-the-ai-db-craze-cbcaff49b9de)
2. Configuring WordPress with PostgreSQL, accessed April 1, 2026, [https://wordpress.org/support/topic/configuring-wordpress-with-postgresql/](https://wordpress.org/support/topic/configuring-wordpress-with-postgresql/)
3. awesome-compose/official-documentation-samples/wordpress/README.md at master \- GitHub, accessed April 1, 2026, [https://github.com/docker/awesome-compose/blob/master/official-documentation-samples/wordpress/README.md](https://github.com/docker/awesome-compose/blob/master/official-documentation-samples/wordpress/README.md)
4. MariaDB and PostgreSQL \- A technical DeepDive into how they differ \- YouTube, accessed April 1, 2026, [https://www.youtube.com/watch?v=l\_5AgRPTa54](https://www.youtube.com/watch?v=l_5AgRPTa54)
5. Alpine, Slim, Bullseye, Bookworm, Noble — Different Docker Images Explained \- Medium, accessed April 1, 2026, [https://medium.com/@faruk13/alpine-slim-bullseye-bookworm-jammy-noble-differences-in-docker-images-explained-d9aa6efa23ec](https://medium.com/@faruk13/alpine-slim-bullseye-bookworm-jammy-noble-differences-in-docker-images-explained-d9aa6efa23ec)
6. official-images/library/python at master \- GitHub, accessed April 1, 2026, [https://github.com/docker-library/official-images/blob/master/library/python](https://github.com/docker-library/official-images/blob/master/library/python)
7. How We Achieved 40ms Server Response Time: WordPress Speed Optimization Guide 2026 \- Mazdora, accessed April 1, 2026, [https://mazdora.co.uk/wordpress-speed-optimization-40ms-response-time/](https://mazdora.co.uk/wordpress-speed-optimization-40ms-response-time/)
8. Can you critique what I think is the most performant Wordpress stack of 2024? \- Reddit, accessed April 1, 2026, [https://www.reddit.com/r/webhosting/comments/1h5miux/can\_you\_critique\_what\_i\_think\_is\_the\_most/](https://www.reddit.com/r/webhosting/comments/1h5miux/can_you_critique_what_i_think_is_the_most/)
9. The smartest way to cache/speed up a Wordpress website \- Close to static \- Reddit, accessed April 1, 2026, [https://www.reddit.com/r/Wordpress/comments/umlkdg/the\_smartest\_way\_to\_cachespeed\_up\_a\_wordpress/](https://www.reddit.com/r/Wordpress/comments/umlkdg/the_smartest_way_to_cachespeed_up_a_wordpress/)
10. Hardening WordPress – Advanced Administration Handbook | Developer.WordPress.org, accessed April 1, 2026, [https://developer.wordpress.org/advanced-administration/security/hardening/](https://developer.wordpress.org/advanced-administration/security/hardening/)
11. Hardening WordPress – A Checklist To Get Started \- Patchstack, accessed April 1, 2026, [https://patchstack.com/articles/hardening-wordpress-a-checklist-to-get-started/](https://patchstack.com/articles/hardening-wordpress-a-checklist-to-get-started/)
12. How to Install a WordPress Docker Container on ARM | by Jiuyu Zhang | Medium, accessed April 1, 2026, [https://jiuyu.medium.com/how-to-install-a-wordpress-docker-container-on-arm-861cf36fb371](https://jiuyu.medium.com/how-to-install-a-wordpress-docker-container-on-arm-861cf36fb371)
13. Running wordpress on docker-compose,nginx, mysql and php \- Reddit, accessed April 1, 2026, [https://www.reddit.com/r/docker/comments/rmellw/running\_wordpress\_on\_dockercomposenginx\_mysql\_and/](https://www.reddit.com/r/docker/comments/rmellw/running_wordpress_on_dockercomposenginx_mysql_and/)
14. WordPress | Coolify Docs, accessed April 1, 2026, [https://coolify.io/docs/services/wordpress](https://coolify.io/docs/services/wordpress)
15. How to Deploy WordPress with Highly Available PostgreSQL? \- GeeksforGeeks, accessed April 1, 2026, [https://www.geeksforgeeks.org/wordpress/how-to-deploy-wordpress-with-highly-available-postgresql/](https://www.geeksforgeeks.org/wordpress/how-to-deploy-wordpress-with-highly-available-postgresql/)
16. WordPress Containerization Best Practices \- Pantheon.io, accessed April 1, 2026, [https://pantheon.io/learning-center/wordpress/containerize](https://pantheon.io/learning-center/wordpress/containerize)
17. Volume mount when setting up Wordpress with docker \- Stack Overflow, accessed April 1, 2026, [https://stackoverflow.com/questions/49202531/volume-mount-when-setting-up-wordpress-with-docker](https://stackoverflow.com/questions/49202531/volume-mount-when-setting-up-wordpress-with-docker)
18. Migrate Applications | Coolify Docs, accessed April 1, 2026, [https://coolify.io/docs/knowledge-base/how-to/migrate-apps-different-host](https://coolify.io/docs/knowledge-base/how-to/migrate-apps-different-host)
19. Deploy Docker Compose on Coolify \- Complex multi-container applications \- AZDIGI Blog, accessed April 1, 2026, [https://azdigi.com/en/blog/self-hosted/deploy-docker-compose-on-coolify-complex-multi-container-applications](https://azdigi.com/en/blog/self-hosted/deploy-docker-compose-on-coolify-complex-multi-container-applications)
20. Docker Wordpress Linux mounting permission issue \- Reddit, accessed April 1, 2026, [https://www.reddit.com/r/docker/comments/1j0svim/docker\_wordpress\_linux\_mounting\_permission\_issue/](https://www.reddit.com/r/docker/comments/1j0svim/docker_wordpress_linux_mounting_permission_issue/)
21. permission with volume docker and wordpress \- Stack Overflow, accessed April 1, 2026, [https://stackoverflow.com/questions/60617185/permission-with-volume-docker-and-wordpress](https://stackoverflow.com/questions/60617185/permission-with-volume-docker-and-wordpress)
22. wp-uploads and changing file permissions · Issue \#162 · docker-library/wordpress \- GitHub, accessed April 1, 2026, [https://github.com/docker-library/wordpress/issues/162](https://github.com/docker-library/wordpress/issues/162)
23. WordPress Performance: Are We Over-Relying on Plugins and Sacrificing Server Health for Speed? \- Reddit, accessed April 1, 2026, [https://www.reddit.com/r/Wordpress/comments/1lgldkr/wordpress\_performance\_are\_we\_overrelying\_on/](https://www.reddit.com/r/Wordpress/comments/1lgldkr/wordpress_performance_are_we_overrelying_on/)
24. 12 Best WordPress Cache Plugins For 2026 (Best To Worst), accessed April 1, 2026, [https://onlinemediamasters.com/best-wordpress-cache-plugins/](https://onlinemediamasters.com/best-wordpress-cache-plugins/)
25. Speed Up WordPress and Improve Performance · Cloudflare Support docs, accessed April 1, 2026, [https://developers.cloudflare.com/support/third-party-software/content-management-system-cms/speed-up-wordpress-and-improve-performance/](https://developers.cloudflare.com/support/third-party-software/content-management-system-cms/speed-up-wordpress-and-improve-performance/)
26. WordPress Security Hardening Guide 2026: Complete Implementation Strategy, accessed April 1, 2026, [https://wpsecurityninja.com/wordpress-security-hardening-guide/](https://wpsecurityninja.com/wordpress-security-hardening-guide/)
27. Securing WordPress with Docker Containers \- Locol Media Portal, accessed April 1, 2026, [https://www.locol.media/blog/2023/03/15/securing-wordpress-with-docker-containers/](https://www.locol.media/blog/2023/03/15/securing-wordpress-with-docker-containers/)
28. 1.7: How to Harden Your WordPress Site From Attacks \- Wordfence, accessed April 1, 2026, [https://www.wordfence.com/learn/how-to-harden-wordpress-sites/](https://www.wordfence.com/learn/how-to-harden-wordpress-sites/)
29. Top 9 Expert-Level Advanced WordPress Security Techniques for 2025 \- Medium, accessed April 1, 2026, [https://medium.com/@michael\_53671/top-9-expert-level-advanced-wordpress-security-techniques-for-2025-1b95a5c4942f](https://medium.com/@michael_53671/top-9-expert-level-advanced-wordpress-security-techniques-for-2025-1b95a5c4942f)
30. WordPress Security in 2025: The New Rules of Protection \- Mavlers, accessed April 1, 2026, [https://www.mavlers.com/blog/wordpress-security-2025/](https://www.mavlers.com/blog/wordpress-security-2025/)
31. The 2025 WordPress Security Checklist: 16 Items to Tackle \- Melapress, accessed April 1, 2026, [https://melapress.com/wordpress-security-checklist/](https://melapress.com/wordpress-security-checklist/)
32. The Impact Of Plugin Bloat On WordPress Speed (and How To Avoid It) \- WP SitePlan, accessed April 1, 2026, [https://wpsiteplan.com/blog/impact-of-plugin-bloat-on-wordpress-speed/](https://wpsiteplan.com/blog/impact-of-plugin-bloat-on-wordpress-speed/)
33. Just discovered how much bloat some plugins add \[DISCUSSION\] : r/WordpressPlugins, accessed April 1, 2026, [https://www.reddit.com/r/WordpressPlugins/comments/1nv1k9u/just\_discovered\_how\_much\_bloat\_some\_plugins\_add/](https://www.reddit.com/r/WordpressPlugins/comments/1nv1k9u/just_discovered_how_much_bloat_some_plugins_add/)
34. 12 Must-Have WordPress Plugins for Developers in 2026 \- DEV Community, accessed April 1, 2026, [https://dev.to/thebitforge/12-must-have-wordpress-plugins-for-developers-in-2026-3kof](https://dev.to/thebitforge/12-must-have-wordpress-plugins-for-developers-in-2026-3kof)
35. Top 11 Best WordPress Plugins to Enhance Your Website in 2025 \- Fooz Agency, accessed April 1, 2026, [https://foozagency.com/blog/top-11-best-wordpress-plugins-to-enhance-your-website-in-2025/](https://foozagency.com/blog/top-11-best-wordpress-plugins-to-enhance-your-website-in-2025/)
36. 7 Best WordPress Plugins For Developers in 2025 \- GeeksforGeeks, accessed April 1, 2026, [https://www.geeksforgeeks.org/wordpress/best-wordpress-plugins-for-developers/](https://www.geeksforgeeks.org/wordpress/best-wordpress-plugins-for-developers/)
37. WordPress Development in 2026: From Full Site Editing to Flawless Deployments, accessed April 1, 2026, [https://www.deployhq.com/blog/wordpress-development-in-2025-from-full-site-editing-to-flawless-deployments](https://www.deployhq.com/blog/wordpress-development-in-2025-from-full-site-editing-to-flawless-deployments)
38. Best WordPress Database Plugins: Ultimate Guide to Optimization & Management \- Medium, accessed April 1, 2026, [https://medium.com/@eiosysseo/best-wordpress-database-plugins-ultimate-guide-to-optimization-management-0ebb8b314200](https://medium.com/@eiosysseo/best-wordpress-database-plugins-ultimate-guide-to-optimization-management-0ebb8b314200)
39. Config – WP-CLI \- Make WordPress, accessed April 1, 2026, [https://make.wordpress.org/cli/handbook/references/config/](https://make.wordpress.org/cli/handbook/references/config/)
40. WordPress Performance: Database Clean Up and Optimization \- Pressidium, accessed April 1, 2026, [https://pressidium.com/blog/wordpress-performance-database-clean-up-and-optimization/](https://pressidium.com/blog/wordpress-performance-database-clean-up-and-optimization/)
41. WooCommerce Sales Tax Plugins 2025: Edition for US Merchants \- TaxCloud, accessed April 1, 2026, [https://taxcloud.com/blog/best-sales-tax-plugins-for-woocommerce/](https://taxcloud.com/blog/best-sales-tax-plugins-for-woocommerce/)
42. WooCommerce Tax Guide Documentation, accessed April 1, 2026, [https://woocommerce.com/document/woocommerce-shipping-and-tax/woocommerce-tax/](https://woocommerce.com/document/woocommerce-shipping-and-tax/woocommerce-tax/)
43. 10 Best WooCommerce Tax Plugins to Try in 2026 \- InstaWP, accessed April 1, 2026, [https://instawp.com/woocommerce-tax-plugins/](https://instawp.com/woocommerce-tax-plugins/)
44. Polylang vs WPML: How to Choose in 2026 (+ A Great Alternative) \- TranslatePress, accessed April 1, 2026, [https://translatepress.com/polylang-vs-wpml-comparison/](https://translatepress.com/polylang-vs-wpml-comparison/)
45. WPML vs Polylang vs TranslatePress: Which Website Translation Plugin Should You Choose? \- Directorist, accessed April 1, 2026, [https://directorist.com/blog/website-translation-plugin-you-should-choose/](https://directorist.com/blog/website-translation-plugin-you-should-choose/)
46. Polylang Vs TranslatePress: 4 Factors To Consider Before You Pick \- BlogVault, accessed April 1, 2026, [https://blogvault.net/polylang-vs-translatepress/](https://blogvault.net/polylang-vs-translatepress/)
47. Comparing Polylang and TranslatePress for WordPress Translation \- Weglot, accessed April 1, 2026, [https://www.weglot.com/blog/polylang-vs-translatepress](https://www.weglot.com/blog/polylang-vs-translatepress)
48. 10 WordPress Security Best Practices for 2026: Keep Your Site Safe \- miniOrange, accessed April 1, 2026, [https://www.miniorange.com/blog/wordpress-security-best-practices/](https://www.miniorange.com/blog/wordpress-security-best-practices/)
49. Encrypted Offsite Backup With Ransomware Protection for WordPress \- Helge Klein, accessed April 1, 2026, [https://helgeklein.com/blog/encrypted-offsite-backup-with-ransomware-protection-for-wordpress/](https://helgeklein.com/blog/encrypted-offsite-backup-with-ransomware-protection-for-wordpress/)
50. Deploying a Containerized WordPress App on AWS with Docker, EBS & S3 Backups, accessed April 1, 2026, [https://dev.to/christiana\_otoboh/deploying-a-containerized-wordpress-app-on-aws-with-docker-ebs-s3-backups-38if](https://dev.to/christiana_otoboh/deploying-a-containerized-wordpress-app-on-aws-with-docker-ebs-s3-backups-38if)
51. How to Run Restic Backup Server in Docker \- OneUptime, accessed April 1, 2026, [https://oneuptime.com/blog/post/2026-02-08-how-to-run-restic-backup-server-in-docker/view](https://oneuptime.com/blog/post/2026-02-08-how-to-run-restic-backup-server-in-docker/view)
52. WP-CLI \- The command line interface for WordPress, accessed April 1, 2026, [https://wp-cli.org/](https://wp-cli.org/)
53. Managing WordPress with WP-CLI \- Pagely, accessed April 1, 2026, [https://pagely.com/blog/managing-wordpress-with-wp-cli/](https://pagely.com/blog/managing-wordpress-with-wp-cli/)
54. Simple WP-CLI Commands That Make WordPress Easier \- DEV Community, accessed April 1, 2026, [https://dev.to/muhammadmedhat/simple-wp-cli-commands-that-make-wordpress-easier-1cko](https://dev.to/muhammadmedhat/simple-wp-cli-commands-that-make-wordpress-easier-1cko)
55. Wordpress Makefile Workflow \- gists · GitHub, accessed April 1, 2026, [https://gist.github.com/pwenzel/6091976](https://gist.github.com/pwenzel/6091976)
56. Guide to WP-CLI for WordPress Developers \- DEV Community, accessed April 1, 2026, [https://dev.to/fitehal/guide-to-wp-cli-for-wordpress-developers-1h79](https://dev.to/fitehal/guide-to-wp-cli-for-wordpress-developers-1h79)
57. WordPress Headless CMS Guide 2025: JAMstack, Next.js & Modern API Integration, accessed April 1, 2026, [https://oddjar.com/wordpress-headless-cms-guide-2025-jamstack-next-js-modern-api-integration/](https://oddjar.com/wordpress-headless-cms-guide-2025-jamstack-next-js-modern-api-integration/)
58. How to Use WordPress as a Headless CMS for Next.js | by Nakiboddin Saiyad \- Medium, accessed April 1, 2026, [https://medium.com/@nakiboddin.saiyad/how-to-use-wordpress-as-a-headless-cms-for-next-js-f8b6a2067cb1](https://medium.com/@nakiboddin.saiyad/how-to-use-wordpress-as-a-headless-cms-for-next-js-f8b6a2067cb1)
59. Headless WordPress in Practice: Next.js \+ WPGraphQL Setup, Caching, and CI/CD, accessed April 1, 2026, [https://awplife.com/headless-wordpress-next-js-wpgraphql-setup/](https://awplife.com/headless-wordpress-next-js-wpgraphql-setup/)
60. How to Secure Your Headless WordPress & WPGraphQL API \- DEV Community, accessed April 1, 2026, [https://dev.to/dipankarmaikap/how-to-secure-your-headless-wordpress-wpgraphql-api-c6i](https://dev.to/dipankarmaikap/how-to-secure-your-headless-wordpress-wpgraphql-api-c6i)
61. Secure Headless WordPress with Next.js Authentication \- Muniwar Technologies, accessed April 1, 2026, [https://www.muniwar.com/secure-headless-wordpress-nextjs-authentication/](https://www.muniwar.com/secure-headless-wordpress-nextjs-authentication/)
62. Previews | HeadstartWP Docs \- Next.js Framework for WordPress \- 10up, accessed April 1, 2026, [https://headstartwp.10up.com/docs/learn/wordpress-integration/previews/](https://headstartwp.10up.com/docs/learn/wordpress-integration/previews/)
63. Guides: Preview Mode \- Next.js, accessed April 1, 2026, [https://nextjs.org/docs/pages/guides/preview-mode](https://nextjs.org/docs/pages/guides/preview-mode)
64. How to Run WordPress with Docker Compose (Nginx \+ MySQL \+ PHP) \- OneUptime, accessed April 1, 2026, [https://oneuptime.com/blog/post/2026-02-08-how-to-run-wordpress-with-docker-compose-nginx-mysql-php/view](https://oneuptime.com/blog/post/2026-02-08-how-to-run-wordpress-with-docker-compose-nginx-mysql-php/view)
65. Headless WordPress and Next.js \- DEV Community, accessed April 1, 2026, [https://dev.to/fabiancdng/headless-wordpress-and-nextjs-25bh](https://dev.to/fabiancdng/headless-wordpress-and-nextjs-25bh)
66. Persistent Storage | Coolify Docs, accessed April 1, 2026, [https://coolify.io/docs/knowledge-base/persistent-storage](https://coolify.io/docs/knowledge-base/persistent-storage)
