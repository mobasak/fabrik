This Technical Implementation Addendum provides the raw code, specific CLI commands, and configuration parameters required to execute a production-grade WordPress deployment.1. The Master wp-config.php Code BlockThis template must be placed in the WordPress root directory. For maximum security, the file should be set to permissions 400 or 440 and ideally moved one directory above the public web root.PHP<?php
/**
 * PRODUCTION MASTER CONFIGURATION
 */

// --- 1. Database Settings ---
define( 'DB_NAME',     'production_db_name' );
define( 'DB_USER',     'production_db_user' );
define( 'DB_PASSWORD', 'secure_password_here' );
define( 'DB_HOST',     'localhost' );
define( 'DB_CHARSET',  'utf8mb4' );
define( 'DB_COLLATE',  '' );

/**
 * Custom Database Prefix: Use unique strings to mitigate SQL injection.
 * Do not use 'wp_'.
 */
$table_prefix = 'agency_prod_72_'; [3]

// --- 2. Security Salts (Generate at https://api.wordpress.org/secret-key/1.1/salt/) ---
define('AUTH_KEY',         'put_your_unique_phrase_here');
define('SECURE_AUTH_KEY',  'put_your_unique_phrase_here');
define('LOGGED_IN_KEY',    'put_your_unique_phrase_here');
define('NONCE_KEY',        'put_your_unique_phrase_here');
define('AUTH_SALT',        'put_your_unique_phrase_here');
define('SECURE_AUTH_SALT', 'put_your_unique_phrase_here');
define('LOGGED_IN_SALT',   'put_your_unique_phrase_here');
define('NONCE_SALT',       'put_your_unique_phrase_here'); [1, 2, 4]

// --- 3. Persistence & Caching ---
define( 'WP_CACHE', true );
define( 'WP_REDIS_HOST', '127.0.0.1' );
define( 'WP_REDIS_PORT', 6379 );
define( 'WP_REDIS_DATABASE', 0 ); // Default database for isolation
define( 'WP_REDIS_PREFIX', 'site_slug_prod:' ); [5, 6]

// --- 4. Security Hardening ---
define( 'FORCE_SSL_ADMIN', true );         // Encrypt all admin/login traffic
define( 'DISALLOW_FILE_EDIT', true );      // Disable theme/plugin editor
define( 'DISALLOW_FILE_MODS', true );      // Disable plugin/theme installs/updates in UI
define( 'WP_HTTP_BLOCK_EXTERNAL', true );  // Block unauthorized external requests
define( 'WP_ACCESSIBLE_HOSTS', 'api.wordpress.org,*.wordpress.org' ); [2, 3]

// --- 5. Performance & Resource Limits ---
define( 'WP_MEMORY_LIMIT', '256M' );       // Frontend memory allocation
define( 'WP_MAX_MEMORY_LIMIT', '512M' );   // Admin/background memory allocation
define( 'WP_POST_REVISIONS', 5 );          // Limit database bloat from revisions
define( 'AUTOSAVE_INTERVAL', 120 );        // Increase autosave to 2 minutes
define( 'EMPTY_TRASH_DAYS', 7 );           // Auto-purge trash every week [7, 3]

// --- 6. Cron Implementation ---
define( 'DISABLE_WP_CRON', true );         // Disable pseudo-cron for system cron

// --- 7. Hardened Debugging (Silent Logging) ---
define( 'WP_DEBUG', true );
define( 'WP_DEBUG_LOG', true );            // Logs to /wp-content/debug.log
define( 'WP_DEBUG_DISPLAY', false );       // Never show errors to visitors
@ini_set( 'display_errors', 0 ); [7, 3]

// --- 8. Core Updates ---
define( 'WP_AUTO_UPDATE_CORE', 'minor' );  // Auto-update security/minor releases [2, 3]

/* That's all, stop editing! Happy publishing. */
if (! defined( 'ABSPATH' ) ) {
	define( 'ABSPATH', __DIR__. '/' );
}
require_once ABSPATH. 'wp-settings.php';
2. Nginx Server-Level Hardening & Caching RulesThe following directives should be integrated into the site's server {} block to neutralize common attack vectors and optimize high-traffic delivery.A. Security Hardening: Block PHP and XML-RPCNginx# 1. Block PHP execution in Uploads directory
location ~* /(?:uploads|files)/.*\.php$ {
    deny all;
    access_log off;
    log_not_found off;
}

# 2. Drop XML-RPC requests immediately
location = /xmlrpc.php {
    deny all;
    access_log off;
    log_not_found off;
}

# 3. Block sensitive files (Dotfiles, backups, logs)
location ~* /\.(?!well-known\/) { deny all; }
location ~* (?:\.(?:bak|conf|dist|fla|in[ci]|log|psd|sh|sql|sw[op])|~)$ { deny all; }
B. FastCGI Caching & WooCommerce BypassPlace the fastcgi_cache_path outside the server block (in nginx.conf or http block).Nginx# In http block:
fastcgi_cache_path /var/run/nginx-cache levels=1:2 keys_zone=WORDPRESS:100m inactive=60m;
fastcgi_cache_key "$scheme$request_method$host$request_uri";

# Inside server block:
set $skip_cache 0;

# POST requests and URLs with query strings should always go to PHP
if ($request_method = POST) { set $skip_cache 1; }
if ($query_string!= "") { set $skip_cache 1; }

# Bypass cache for WordPress Admin and specific WooCommerce paths
if ($request_uri ~* "/wp-admin/|/xmlrpc.php|wp-.*.php|/feed/|index.php|sitemap(_index)?.xml") {
    set $skip_cache 1;
}

# WooCommerce Bypass: Cart, Checkout, My Account
if ($request_uri ~* "/cart/|/checkout/|/my-account/|/addons/|/\?add-to-cart=") {
    set $skip_cache 1;
}

# Bypass cache when WooCommerce cart contains items or user is logged in
if ($http_cookie ~* "comment_author|wordpress_[a-f0-9]+|wp-postpass|wordpress_no_cache|wordpress_logged_in|woocommerce_items_in_cart") {
    set $skip_cache 1;
}

location ~ \.php$ {
    include snippets/fastcgi-php.conf;
    fastcgi_pass unix:/var/run/php/php8.2-fpm.sock;
    
    fastcgi_cache WORDPRESS;
    fastcgi_cache_valid 200 301 302 60m;
    fastcgi_cache_bypass $skip_cache;
    fastcgi_no_cache $skip_cache;
    add_header X-FastCGI-Cache $upstream_cache_status;
}
3. System-Level Cron ImplementationProfessional implementations disable the native "pseudo-cron" and utilize the server's task scheduler to ensure accuracy and prevent page-load delays.Step 1: Add the constant to wp-config.php (included in the Master block above):define( 'DISABLE_WP_CRON', true );Step 2: Add the crontab entry for the web-server user (e.g., www-data):Bash# Run crontab -e -u www-data and add:
*/5 * * * * /usr/local/bin/wp cron event run --due-now --path=/var/www/html > /dev/null 2>&1
Note: Using wp-cli is preferred over curl or wget as it bypasses the HTTP stack and provides direct terminal output for debugging errors.4. Database Pruning & Maintenance CommandsManual database maintenance is required to prevent wp_options and wp_postmeta from slowing down queries. Run these via wp db query or direct MySQL terminal.TargetCommand (WP-CLI or SQL)ObjectiveOld Revisionswp post delete $(wp post list --post_type='revision' --format=ids) --forceWipe all non-essential revisions.Orphaned MetaDELETE pm FROM wp_postmeta pm LEFT JOIN wp_posts wp ON wp.ID = pm.post_id WHERE wp.ID IS NULL;Remove meta data for posts that no longer exist.Expired Transientswp transient delete --expiredClear temporary cache data that has surpassed its TTL.Spam Commentswp comment delete $(wp comment list --status=spam --format=ids)Permanently purge the spam queue.Optimize Tableswp db optimizeReclaim unused space and defragment tables.5. Child Theme & Asset Pipeline SOPFor a production build, use a minimal child theme structure that prevents render-blocking while enqueuing styles correctly.Directory Structure:/themes/agency-child/├── style.css├── functions.php└── /assets/├── /css/└── /js/functions.php Implementation:PHP<?php
// Enqueue Parent and Child Styles
add_action( 'wp_enqueue_scripts', 'agency_enqueue_assets' );
function agency_enqueue_assets() {
    // 1. Enqueue Parent Styles with versioning
    wp_enqueue_style( 'parent-style', get_template_directory_uri(). '/style.css' );

    // 2. Enqueue Child Styles, dependent on Parent
    wp_enqueue_style( 'child-style', get_stylesheet_directory_uri(). '/style.css', array( 'parent-style' ), wp_get_theme()->get('Version') );

    // 3. Enqueue Custom JS with Defer implementation
    wp_enqueue_script( 'agency-custom-js', get_stylesheet_directory_uri(). '/assets/js/main.js', array(), '1.0.0', true );
}

/**
 * DEFER non-critical JavaScript to improve INP/LCP
 */
add_filter( 'script_loader_tag', 'agency_defer_scripts', 10, 3 );
function agency_defer_scripts( $tag, $handle, $src ) {
    $defer_scripts = array( 'agency-custom-js' );
    if ( in_array( $handle, $defer_scripts ) ) {
        return str_replace( ' src', ' defer="defer" src', $tag );
    }
    return $tag;
}
6. Plugin Toggle States: Wordfence & WP RocketWordfence: Firewall & Scan Checklist[Firewall] Basic Firewall Options: Status = Enabled and Protecting. Do not leave in Learning Mode for more than 7 days.[Firewall] Brute Force Protection:Lock out after how many login failures = 5.Lock out after how many forgot password attempts = 3.Immediately lock out invalid usernames = ON.Immediately block the IP of users who try to sign in as 'admin' = ON.** General Scan Options:**Scan for publicly accessible configuration, backup, or log files = ON.Scan images, binary, and other files as if they were executable = ON (High sensitivity).Check if this website is on a domain blocklist = ON (Premium).WP Rocket: Core Web Vitals Checklist[File Optimization] CSS:Minify CSS files = ON.Optimize CSS delivery = ON (Select Remove Unused CSS for maximum LCP impact).[File Optimization] JS:Minify JavaScript files = ON.Load JavaScript deferred = ON.Delay JavaScript execution = ON (Essential for passing INP; ensures JS only runs on user interaction).[Media] LazyLoad:Enable for images = ON.Enable for iframes and videos = ON.Add missing image dimensions = ON (Crucial to prevent Cumulative Layout Shift).

This Part 2 Technical Implementation Addendum provides the remaining granular configurations for SEO, Media Offloading, Transactional Email, and Core Hardening. These instructions are designed for direct application to a production environment.

1. SEO Plugin Toggle States (Rank Math SEO)
To maintain a "lean" database and high performance, agencies must disable high-overhead modules and configure crawl optimization settings strictly.

A. Module Checklist (Rank Math Dashboard)
ENABLE: ACF, Image SEO, Instant Indexing, Redirections, Schema (Structured Data), Sitemap.

DISABLE:

Analytics: This module is notorious for causing database bloat. Use Google Search Console/Analytics directly instead.

Link Counter: Disabling this prevents continuous background counting of internal/external links which stresses the database.

AMP: Unless specifically required, as AMP adds significant complexity and is often deprecated in favor of high Core Web Vitals.

bbPress/BuddyPress: Unless the site is a forum/social network.

B. Titles & Meta Configuration (Agency SOP)
Global Meta:

Robots Meta: index.

Noindex Empty Category and Tag Archives: ON.

Separator Character: - or |.

Links:

Strip Category Base: ON (Removes /category/ from URLs for cleaner structure).

Redirect Attachments: ON (Redirects image URLs to their parent posts).

Redirect Orphan Attachments: ON (Redirects to homepage if no parent exists).

Remove Generator Tag: ON (Obscures WordPress footprint).

C. XML Sitemap Settings for Performance
Links Per Sitemap: Set to 200. (Google handles smaller sitemap pages more efficiently; default is often 1,000+).

Images in Sitemaps: OFF unless the site is an image-heavy portfolio (saves significant crawl budget and server load).

2. Media Offloading Implementation (S3 / Cloudflare R2)
Store credentials in wp-config.php to prevent them from being saved in the database or exposed via dashboard exports.

A. Master Credentials (wp-config.php)
Place these above the /* That's all, stop editing! */ line. This example uses Advanced Media Offloader constants.

PHP
// --- Media Offloading (Cloudflare R2 Example) ---
define( 'ADVMO_CLOUDFLARE_R2_KEY', 'your-access-key-id' );
define( 'ADVMO_CLOUDFLARE_R2_SECRET', 'your-secret-access-key' );
define( 'ADVMO_CLOUDFLARE_R2_BUCKET', 'agency-prod-bucket-name' );
define( 'ADVMO_CLOUDFLARE_R2_DOMAIN', 'https://media.yourdomain.com' );
define( 'ADVMO_CLOUDFLARE_R2_ENDPOINT', 'https://account-id.r2.cloudflarestorage.com' );
define( 'ADVMO_DELETE_LOCAL_FILE', true ); // Purge server storage after upload
B. Nginx Map for Dynamic WebP/AVIF Support
Use Nginx to detect browser support and serve the correct format from the S3/R2 bucket URL.

Nginx
# Add to nginx.conf http block:
map $http_accept $img_suffix {
    "~*image/avif" ".avif";
    "~*image/webp" ".webp";
    default "";
}

# Add to site-specific server block:
location ~* ^/wp-content/uploads/.+\.(png|jpe?g)$ {
    add_header Vary Accept;
    # Rewrite to look for next-gen file extension first
    try_files $uri$img_suffix $uri =404;
}
3. Transactional Email Routing (phpmailer_init)
Stop relying on the unreliable mail() function. Force all outgoing mail through an authenticated SMTP relay or API using this MU-plugin code.

File: /wp-content/mu-plugins/agency-smtp.php

PHP
<?php
/**
 * Force Authenticated Transactional Email (SES/Postmark)
 */
add_action( 'phpmailer_init', 'agency_force_smtp_config' );
function agency_force_smtp_config( $phpmailer ) {
    $phpmailer->isSMTP();
    $phpmailer->Host       = 'email-smtp.us-east-1.amazonaws.com'; // e.g., Amazon SES
    $phpmailer->SMTPAuth   = true;
    $phpmailer->Port       = 587;
    $phpmailer->SMTPSecure = 'tls';
    $phpmailer->Username   = 'YOUR_SES_SMTP_USERNAME';
    $phpmailer->Password   = 'YOUR_SES_SMTP_PASSWORD';
    
    // Force specific 'From' address to align with SPF/DKIM
    $phpmailer->From       = 'noreply@yourdomain.com';
    $phpmailer->FromName   = 'Your Brand Name';
}
4. Core Header Cleanup & Obscurity
Standard WordPress installations leak too much metadata in the <head>. Use these remove_action calls in functions.php to clean the DOM and obscure the CMS footprint.

PHP
/**
 * Core Head Cleanup - Agency Standard
 */
add_action( 'init', 'agency_cleanup_head' );
function agency_cleanup_head() {
    remove_action( 'wp_head', 'wp_generator' );                // Removes WP version
    remove_action( 'wp_head', 'rsd_link' );                    // Removes RSD link
    remove_action( 'wp_head', 'wlwmanifest_link' );            // Removes Windows Live Writer manifest
    remove_action( 'wp_head', 'wp_shortlink_wp_head' );        // Removes shortlinks
    remove_action( 'wp_head', 'print_emoji_detection_script', 7 ); // Removes emoji JS
    remove_action( 'wp_print_styles', 'print_emoji_styles' );      // Removes emoji CSS
    remove_action( 'wp_head', 'feed_links', 2 );               // Removes main RSS feeds
    remove_action( 'wp_head', 'feed_links_extra', 3 );         // Removes extra RSS feeds
    
    // Obscure WP Version from scripts/styles
    add_filter( 'script_loader_src', 'agency_remove_wp_ver', 15 );
    add_filter( 'style_loader_src', 'agency_remove_wp_ver', 15 );
}

function agency_remove_wp_ver( $src ) {
    if ( strpos( $src, 'ver='. get_bloginfo( 'version' ) ) ) {
        $src = remove_query_arg( 'ver', $src );
    }
    return $src;
}
5. Caching-Compatible GDPR Compliance
Agencies must use a Client-Side/Cookie-based consent mechanism to avoid "Cache Poisoning" (where a user's consent state is cached and served to others) or breaking Nginx FastCGI caching.

A. The Nginx Cookie Check
Implement a rule to check for a consent cookie at the edge. If the cookie is not present, we can bypass cache for the banner script or use a custom header to force the browser to handle the banner logic.

Nginx
# Add to Nginx server block to prevent cache poisoning
if ($http_cookie ~* "cookie_consent_accepted") {
    set $skip_cache 0;
}
# Optional: Force bypass for users who haven't decided yet to ensure banner shows
if ($http_cookie!~* "cookie_consent") {
    set $skip_cache 1;
}
B. JavaScript Implementation (Google Consent Mode v2)
Use an auto-blocking script that utilizes gtag to signal consent status to third-party pixels after the page has been cached and served.

JavaScript
// Initialize Consent Mode (Denied by default)
window.dataLayer = window.dataLayer ||;
function gtag(){dataLayer.push(arguments);}
gtag('consent', 'default', {
  'ad_storage': 'denied',
  'analytics_storage': 'denied',
  'wait_for_update': 500
});

// Update consent upon user interaction (e.g., clicking 'Accept')
function onConsentAccepted() {
    gtag('consent', 'update', {
      'ad_storage': 'granted',
      'analytics_storage': 'granted'
    });
    // Set a long-lived cookie for Nginx to recognize the state
    document.cookie = "cookie_consent_accepted=true; path=/; max-age=31536000";
}
This completes the Technical Implementation Addendum. All code blocks are designed to be environment-agnostic while adhering to the strict hardening and performance standards of an elite agency.