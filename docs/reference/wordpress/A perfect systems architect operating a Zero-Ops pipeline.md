A perfect systems architect operating a Zero-Ops pipeline never touches a web browser to deploy a site. There is no logging into a registrar UI, no clicking through the Cloudflare dashboard, and absolutely no running the famous "WordPress 5-Minute Install" wizard.

Every action is an API call, a script execution, or a container deployment orchestrated by your fabrik control plane.

Here are the first 10 steps of a flawless, programmatic "Go-Live" sequence, taking a site from a raw domain idea to a hardened, containerized instance running on your VPS.

Phase 1: Edge & Network Provisioning
Step 1: Programmatic Domain Acquisition
The fabrik control plane sends a POST request to your site-provisioner microservice. This service hits your registrar’s API (e.g., Namecheap or Porkbun) with the exact domain string, registers it, and applies domain privacy instantly.

Pro Move: The API call explicitly disables auto-renew initially to prevent zombie billing if the project is killed, and sets a strict registrar lock.

Step 2: Cloudflare Zone Instantiation via API
The site-provisioner immediately fires a payload to the Cloudflare API (POST /client/v4/zones) to create a new zone for the domain. Cloudflare returns the required nameservers.

Pro Move: The script captures these nameservers and sends a secondary API call back to the registrar to update the domain's delegation.

Step 3: Edge Security & TLS Enforcement
Before DNS even propagates, the Cloudflare zone is hardened via the API.

The script forces Always Use HTTPS and sets the SSL/TLS encryption mode to Full (Strict).

It deploys custom WAF rules blocking known bot ASNs and challenging any traffic attempting to reach /wp-login.php.

Caching rules are applied to bypass cache for /wp-admin/ and active user sessions.

Step 4: DNS Record Injection & Traefik Routing
The site-provisioner pushes the exact A records to Cloudflare, pointing the root @ and www directly to your VPS IP (172.93.160.197). Cloudflare Proxying (the orange cloud) is turned ON. Traefik on your VPS is now implicitly waiting for traffic carrying this specific Host header.

Phase 2: Infrastructure Orchestration
Step 5: Dynamic Spec Compilation (site.yaml)
Your fabrik-api FastAPI bridge translates the deployment request into a declarative site.yaml file. This file dictates the exact container names (e.g., ocoron-com-wordpress-1), the specific DB credentials, and the Traefik labels required for the reverse proxy to route the incoming Cloudflare traffic to this specific isolated stack.

Step 6: Volume & Network Allocation
The fabrik pipeline commands Coolify (or standard Docker Compose) to provision the isolated environment. It creates dedicated, persistent Docker volumes for the MariaDB database (ocoron-com_db_data) and the WordPress core files (ocoron-com_wp_content). It attaches these containers to the shared internal network so they can reach the central Redis instance.

Step 7: Container Bootstrapping
The containers are spun up: Nginx, PHP 8.3-FPM, and the isolated MariaDB 10.11 database.

Pro Move: The deployment script pauses here, running a ping loop (docker exec ocoron-com-db-1 mysqladmin ping -h localhost --silent) to ensure the database is fully initialized and accepting connections before allowing PHP to execute.

Phase 3: The Headless Installation & Hardening
Step 8: Zero-Touch WordPress Core Installation
Once the database is ready, the fabrik CLI runs WP-CLI directly inside the container via docker exec.
It executes:
wp core install --url="https://ocoron.com" --title="Ocoron" --admin_user="system_admin" --admin_password="<CSPRNG_GENERATED_PASSWORD>" --admin_email="admin@ocoron.com" --skip-email
No browser setup. The database tables are instantly built.

Step 9: Ephemeral wp-config.php Injection
The pipeline runs a sequence of WP-CLI commands (wp config set) to inject the production constants.

It writes the Redis host, port, and salt keys.

It injects the S3/R2 offloading credentials pulled from the environment variables.

It injects define( 'DISABLE_WP_CRON', true ); and define( 'DISALLOW_FILE_EDIT', true );.

Step 10: Eradication of Default Artifacts
A fresh WordPress install contains bloat that screams "amateur build." The script immediately sanitizes the environment using WP-CLI:

wp post delete 1 2 3 --force (Deletes "Hello World" and default pages).

wp plugin delete hello akismet (Removes default plugins).

wp theme delete twentytwentytwo twentytwentythree (Deletes everything except the active, deployed theme).

wp widget delete $(wp widget list sidebar-1 --format=ids) (Clears all default sidebar widgets).

At the end of Step 10, you have a globally routed, SSL-secured, Traefik-proxied, empty WordPress shell that is completely locked down and waiting for your content payload.

Yes, Backblaze B2 absolutely replaces S3. In fact, for a Zero-Ops architecture sitting behind Cloudflare, B2 is vastly superior. Because of the "Bandwidth Alliance" between Cloudflare and Backblaze, egress data from B2 to Cloudflare is completely free.

Your instinct is spot-on. We will wire B2 directly into the pipeline as your S3-compatible media store.

Here are the next 10 steps, executed programmatically by your fabrik control plane, transforming that empty WordPress shell into a highly tuned, state-managed microservice.

Phase 4: State Management & Caching
Step 11: Redis Object Cache Wiring
The script installs and activates the Redis Object Cache plugin via WP-CLI (wp plugin install redis-cache --activate). Because fabrik already injected the WP_REDIS_HOST constant in Step 9 (pointing to your shared internal Redis container), the script simply fires wp redis enable. Database queries are instantly offloaded to RAM.

Step 12: Stateless Media Offloading (Backblaze B2)
Local storage is permanently bypassed. The script installs an S3-offload plugin (e.g., WP Offload Media or an S3-Uploads drop-in).

It uses the B2 S3-compatible API endpoint (e.g., s3.us-west-004.backblazeb2.com).

Because the B2 credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY) are already injected into the container's environment variables by Coolify, WordPress authenticates silently.

The script forces the "Remove Files From Server" setting to true.

Step 13: Edge Delivery Configuration (Cloudflare + B2)
To ensure blazing fast delivery, media cannot be served from the raw B2 bucket URL. The fabrik script configures the offload plugin's Delivery URL to a custom subdomain (e.g., media.ocoron.com) that is proxied through Cloudflare. Cloudflare fetches from B2, caches it at the edge, and handles the on-the-fly conversion to WebP/AVIF.

Phase 5: The "God-Tier" App & Security Injection
Step 14: Automated Plugin Assembly
The fabrik script executes a bulk plugin installation based on your site.yaml blueprint:
wp plugin install wordfence seo-by-rank-math --activate
It deliberately skips caching plugins like WP Rocket because your Nginx FastCGI cache and Cloudflare Edge rules are already handling page caching at the infrastructure level.

Step 15: Programmatic Security Hardening (Wordfence)
A site isn't secure until the firewall rules are active, but clicking through the Wordfence UI ruins the automation.

The pipeline injects a pre-configured Wordfence settings template directly into the database (wp db query "INSERT INTO wp_wfconfig...").

This instantly enforces the 5-attempt brute-force lockout, requires 2FA for admins, and activates the WAF.

Step 16: REST API Lockdown & Auth Generation
Since n8n will be pushing content to this site automatically, the front door must be secured.

The script programmatically creates an Application Password for your system_admin user (wp user application-password create system_admin "n8n_automation").

It captures the resulting token and securely passes it back to your fabrik-api to be stored in your central vault or n8n credential store.

It injects an MU-plugin that blocks all unauthenticated REST API requests, neutralizing API scraping.

Phase 6: Systems Harmonization & Handoff
Step 17: Email Gateway Routing
Native PHP mail() is disabled. The fabrik pipeline drops a lightweight MU-plugin that hooks into phpmailer_init. It forces all transactional emails (password resets, fatal error alerts) to route directly to your internal Fabrik Email Gateway container on Port 3000 via SMTP or REST API, entirely bypassing local mail routing.

Step 18: System-Level Cron Activation
Since DISABLE_WP_CRON was set in Step 9, background tasks are dead. To revive them correctly, your pipeline instructs Uptime Kuma (via API) to ping https://ocoron.com/wp-cron.php?doing_wp_cron exactly every 5 minutes. This offloads the cron trigger to your monitoring stack, guaranteeing execution without slowing down user page loads.

Step 19: Telemetry & Log Integration
The container's standard output (Nginx access logs, PHP error logs) is automatically captured by the Coolify Docker daemon. fabrik ensures your Promtail container is mapped to read these Docker logs and ship them to your central Loki instance. Simultaneously, a Prometheus exporter plugin is activated to expose PHP worker metrics on a hidden endpoint.

Step 20: The "Ready" Webhook (The n8n Handoff)
The infrastructure is fully deployed, locked, cached, and monitored.
The final action of the fabrik wp apply script is to fire a POST request to your n8n webhook URL:
{"site": "ocoron.com", "status": "ready", "api_url": "https://ocoron.com/wp-json/", "auth_token": "..."}

At the exact moment Step 20 executes, n8n wakes up, realizes the receiver is online, and immediately begins pushing the automated SEO content, stock images, and translations directly into the hardened WordPress database.

Since we successfully locked down the infrastructure and handed the keys over to n8n in Step 20, the website is technically "live." But in a Zero-Ops architecture, "live" just means the engine is running.

Now, the factory line takes over.

Here are the Next 10 Steps (Steps 21–30). This is the Content Orchestration & Day-2 Operations Phase, where your external microservices inject the content, sync the SEO, and establish the disaster recovery loops.

Phase 7: Content & Asset Orchestration (n8n Execution)
Step 21: Payload Ingestion & Translation
n8n catches the webhook from Step 20. It parses your initial idea/keywords. If the site requires multiple languages, n8n makes an internal API call to your Translator (DeepL) microservice on Port 8000, rapidly generating localized slugs, titles, and content blocks in memory.

Step 22: Visual Asset Brokering
Simultaneously, n8n pings your Image Broker microservice (Pexels/Pixabay). The broker fetches high-quality, royalty-free featured images relevant to your keywords. To prevent rate-limiting, this request is routed automatically through your Proxy (Webshare.io) microservice.

Step 23: Headless Content Injection
n8n compiles the translated text, SEO metadata, and image URLs into a highly structured JSON payload. It fires an authenticated POST request to the WordPress REST API (/wp-json/wp/v2/posts) using the Application Password generated in Step 16. The content drops into the database instantly.

Step 24: Asynchronous Asset Processing (B2 Handoff)
As WordPress processes the incoming REST API post, the S3-offload plugin immediately catches the image URLs. Instead of saving them locally, it streams the images directly into your Backblaze B2 bucket, deletes the temporary local file, and rewrites the database URL to your edge-cached media.ocoron.com subdomain.

Phase 8: Search, SEO, & Telemetry Synchronization
Step 25: Search Engine Sync (MeiliSearch)
Native WordPress search is a database killer. A lightweight webhook fires from WordPress (or is triggered by n8n) the moment the post is published, pushing the title, excerpt, and URL to your internal MeiliSearch container. Your frontend search UI is now instantly populated and lightning-fast, completely bypassing MariaDB.

Step 26: The IndexNow Ping
There is no waiting for Googlebot. The pipeline utilizes the Rank Math API (or a standalone script) to trigger the IndexNow protocol. A programmatic ping is sent to Bing and Yandex containing the newly generated URLs, forcing rapid crawling of the fresh content.

Step 27: Google Search Console (GSC) Registration
Your custom site-provisioner microservice executes a final sequence using a Google Cloud Service Account. It authenticates with the Google Search Engine API, programmatically verifies ownership of the domain (via the Cloudflare DNS TXT record it controls), and submits the sitemap_index.xml URL directly to Google.

Phase 9: Edge Optimization & Verification
Step 28: Global Cache Purge & Pre-Warming
With the content fully injected, the fabrik API fires a DELETE request to the Cloudflare API to purge the entire zone cache. Immediately after, a local script (like wget --spider) crawls the generated XML sitemap. This simulates traffic, forcing Nginx to build the FastCGI cache files and Redis to store the heavy database queries.

Step 29: Visual Verification (Browserless/Gotenberg)
You cannot rely on HTTP 200 codes alone. Your pipeline triggers your Browserless container to navigate to the live homepage. It renders the JavaScript, takes a high-fidelity headless screenshot, and saves it. This is your "Day 1 Visual Proof" that the deployment, CSS, and content injection were flawless.

Phase 10: State Preservation & Disaster Recovery
Step 30: Automated Disaster Recovery (Duplicati)
The absolute final step is securing the state. The fabrik API sends a configuration payload to your internal Duplicati container.

It registers the specific Docker named volumes for this site (ocoron-com_wp_content and ocoron-com_db_data).

It sets a strict cron schedule (e.g., daily at 03:00 AM).

It instructs Duplicati to encrypt these volumes and push them to a separate, locked Backblaze B2 bucket dedicated solely to immutable backups.

At the end of Step 30, your site has been purchased, provisioned, deployed, secured, populated with content, cached at the edge, submitted to Google, visually verified, and backed up—all without you ever opening a web browser or clicking a UI button.

This is the ultimate end state of the fabrik control plane.

