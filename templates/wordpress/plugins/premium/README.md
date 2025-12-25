# Premium Plugins

Place your premium plugin ZIP files here.

## Expected Files

| Plugin | Filename | Source |
|--------|----------|--------|
| Rank Math Pro | `rank-math-pro.zip` | rankmath.com |
| GeneratePress Premium | `gp-premium.zip` | generatepress.com |
| Astra Premium Sites | `astra-premium-sites.zip` | wpastra.com |

## How to Get ZIPs

1. Log into your account on the plugin website
2. Download the latest ZIP file
3. Place it here with the exact filename above
4. The preset loader will install it automatically

## Usage

Presets reference these by filename:

```yaml
plugins:
  premium:
    - rank-math-pro.zip
    - gp-premium.zip
```

## Notes

- Keep ZIPs updated periodically
- Do NOT commit to git (add to .gitignore if needed)
- License keys are entered in WordPress admin after installation
