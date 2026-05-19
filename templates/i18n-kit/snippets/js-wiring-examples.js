// ============================================================
// i18n JavaScript Wiring Examples
// Copy-paste patterns for common JS scenarios
// ============================================================

// 1. SIMPLE STRING
const label = I18N.t('common.save');  // → "Save" or "Kaydet"

// 2. STRING WITH VARIABLES
const msg = I18N.t('dashboard.items_count', { count: 42 });
// en.json: "dashboard.items_count": "{count} items found"
// → "42 items found"

// 3. CONFIRM DIALOGS
if (!confirm(I18N.t('common.confirm_delete'))) return;

// 4. ALERT MESSAGES
alert(I18N.t('common.error') + ': ' + errorMessage);

// 5. TOAST NOTIFICATIONS
const toast = document.createElement('div');
toast.textContent = I18N.t('common.success');

// 6. DYNAMIC HTML (template literals) — use I18N.t() directly
const html = `
    <tr>
        <td>${escapeHtml(item.name)}</td>
        <td><span class="badge">${I18N.t('common.active')}</span></td>
        <td>
            <button onclick="deleteItem(${item.id})"
                    title="${I18N.t('common.delete')}">
                <i class="bi bi-trash"></i>
            </button>
        </td>
    </tr>
`;
tbody.innerHTML = html;

// 7. AFTER ANY innerHTML RENDER — re-apply data-i18n attributes
// Call this after setting innerHTML with data-i18n elements:
if (window.I18N && I18N._ready) I18N._applyToDOM();

// 8. DATE FORMATTING (locale-aware)
const dateStr = I18N.formatDate(someDate);           // "May 19, 2026" or "19 Mayıs 2026"
const dateTimeStr = I18N.formatDateTime(someDate);    // "May 19, 2026, 3:45 PM"
const relativeStr = I18N.formatRelative(someDate);    // "3 minutes ago" or "3 dakika önce"

// 9. NUMBER FORMATTING (locale-aware)
const numStr = I18N.formatNumber(1234567);            // "1,234,567" or "1.234.567"
const currStr = I18N.formatCurrency(29.99, 'USD');    // "$29.99" or "29,99 $"

// 10. CHECK CURRENT LANGUAGE
if (I18N.lang === 'tr') {
    // Turkish-specific logic
}

// 11. STATUS MAPPING (translate API values)
const statusLabel = I18N.t('status.' + item.status);
// en.json: "status.active": "Active", "status.pending": "Pending"
// Works for any enum-like value from the API

// 12. CONDITIONAL TEXT
const text = isNew
    ? I18N.t('dashboard.create_new')
    : I18N.t('dashboard.edit_existing');
