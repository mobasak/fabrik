# Plugin Activation Notes

## FlyingPress

License Key: `15faff98a76660eb2c722ab324f1339e`

## WP Staging Pro

License Key: `B5E0B5F8DD8689E6ACA49DD6E6E1A930`

## AutomatorWP

License Key: `B5E0B5F8DD8689E6ACA49DD6E6E1A930`

**Add-ons:** To use pro features, install associated add-ons:
- Download: https://drive.google.com/uc?export=download&id=1f9JZHfkr4cJg-XRGkICJQwMsACxCZIPu
- Unzip and install the ones you need
- Add-ons already in folder: FluentCRM, WhatsApp, OpenAI, ACF, CSV, Thrive Apprentice

---

## WPML WordPress Multilingual CMS Plugin

If there are activation issues:

1. Edit `classes/setup/endpoints/LicenseStep.php`
2. Change line 36 from:
   ```php
   'repository_id' => 'wpml',
   ```
   To:
   ```php
   'repository_id' => 'true',
   ```
3. At WPML Setup, add any text or the site name for the license input to activate

## Content Egg Pro Plugin

If prompted to insert a license:
- Enter any string in the license field (e.g., "123")
- Click activate

---

## General Notes

- All paid plugins have auto-update disabled
- Updates managed via custom Fabrik mechanism
- Keep ZIPs updated periodically in this folder
