# Premium Themes

Place your premium theme ZIP files here.

## Expected Files

| Theme | Filename | Source |
|-------|----------|--------|
| GeneratePress Premium | `generatepress_premium.zip` | generatepress.com |
| Astra Pro | `astra-addon.zip` | wpastra.com |

## How to Get ZIPs

1. Log into your account on the theme website
2. Download the latest ZIP file
3. Place it here with the exact filename above

## Notes

**GeneratePress workflow:**
1. Install free GeneratePress from wordpress.org (automatic)
2. Install GP Premium plugin from `plugins/premium/gp-premium.zip`
3. Activate and enter license key

**Astra workflow:**
1. Install free Astra from wordpress.org (automatic)
2. Install Astra Pro Addon from `plugins/premium/astra-addon.zip`
3. Install Starter Templates from `plugins/premium/astra-premium-sites.zip`
4. Activate and enter license key

## Preset Configuration

For GeneratePress (recommended):
```yaml
theme:
  name: generatepress
  source: wordpress.org
plugins:
  premium:
    - gp-premium.zip
```

For Astra:
```yaml
theme:
  name: astra
  source: wordpress.org
plugins:
  premium:
    - astra-addon.zip
    - astra-premium-sites.zip
```
