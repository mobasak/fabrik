// Fabrik WordPress Hardening
// IMPORTANT: Change this prefix before first install — 62-wordpress.md: never use default wp_
// Set to a unique slug matching the site name, e.g. sitename_prod_
// This mitigates automated SQL injection attacks targeting known table names.
$table_prefix = 'CHANGE_ME_prod_';

define('DISALLOW_FILE_EDIT', true);
define('DISALLOW_FILE_MODS', true);  // Prevents plugin/theme install from dashboard — 62-wordpress.md SOP
define('FORCE_SSL_ADMIN', true);
define('WP_POST_REVISIONS', 5);
define('AUTOSAVE_INTERVAL', 120);
define('EMPTY_TRASH_DAYS', 14);
define('WP_MEMORY_LIMIT', '256M');
define('WP_MAX_MEMORY_LIMIT', '512M');
define('DISABLE_WP_CRON', true);
define('WP_HTTP_BLOCK_EXTERNAL', true);                            // Block all outbound HTTP from WP (prevents C2 exfil)
define('WP_ACCESSIBLE_HOSTS', 'api.wordpress.org,*.wordpress.org'); // Allow only WP.org API (core updates)
define('FS_METHOD', 'direct');
define('WP_AUTO_UPDATE_CORE', 'minor'); // Auto-update for security/minor releases — 62-wordpress.md

// Debug: WP_DEBUG must be TRUE for WP_DEBUG_LOG to write — never display to visitors — 62-wordpress.md SOP
define('WP_DEBUG', true);
define('WP_DEBUG_LOG', true);      // logs to /wp-content/debug.log
define('WP_DEBUG_DISPLAY', false); // never expose errors to visitors
@ini_set('display_errors', 0);

// OPcache: ensure PHP scripts are precompiled in memory — 62-wordpress.md SOP
@ini_set('opcache.memory_consumption', '256');
@ini_set('opcache.max_accelerated_files', '10000');

// Redis object cache
define('WP_CACHE', true);
define('WP_REDIS_HOST', 'redis');
define('WP_REDIS_PORT', 6379);
define('WP_REDIS_DATABASE', 0);                // Explicit DB number for isolation — change if sharing Redis
define('WP_REDIS_PREFIX', '{{ name }}:');      // Per-site prefix — prevents key collisions when sharing Redis
