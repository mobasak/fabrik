/**
 * i18n.js — Client-side translation loader for any SaaS product.
 *
 * Usage:
 *   HTML:  <span data-i18n="nav.queue">Queue</span>
 *   JS:    I18N.t('queue.confirm_retry')
 *   JS:    I18N.t('queue.upload_success', { video_id: 'abc123' })
 *   Date:  I18N.formatDate(someDate)
 *   Num:   I18N.formatNumber(1234)
 *
 * Copy this file + en.json to any project. Zero dependencies.
 */
const I18N = {
    _strings: {},
    _lang: 'en',
    _fallback: {},
    _supported: ['en', 'tr', 'es', 'pt-br', 'ja', 'id'],
    _ready: false,

    init() {
        // Legacy — kept for compatibility. Actual init happens at script load time (bottom of file).
        this._applyToDOM();
    },

    _detectLanguage() {
        // 1. Cookie
        const cookie = document.cookie.split(';').find(c => c.trim().startsWith('lang='));
        if (cookie) {
            const val = cookie.split('=')[1].trim().toLowerCase();
            if (this._supported.includes(val)) return val;
        }
        // 2. URL param
        const urlParam = new URLSearchParams(location.search).get('lang');
        if (urlParam && this._supported.includes(urlParam.toLowerCase())) return urlParam.toLowerCase();
        // 3. Browser
        const bl = navigator.language.toLowerCase();
        const match = this._supported.find(l => bl.startsWith(l));
        if (match) return match;
        // 4. Default
        return 'en';
    },

    _load(lang) {
        // Synchronous XHR to ensure translations are available before page JS runs.
        // This blocks for ~5-20ms (local JSON file) but prevents the flash-of-English
        // and raw-key display that async fetch causes with DOMContentLoaded race.
        try {
            const xhr = new XMLHttpRequest();
            xhr.open('GET', `/static/i18n/${lang}.json?v=${Date.now()}`, false); // synchronous, cache-bust
            xhr.send();
            if (xhr.status === 200) return JSON.parse(xhr.responseText);
            return {};
        } catch { return {}; }
    },

    _resolve(obj, path) {
        return path.split('.').reduce((o, k) => o?.[k], obj);
    },

    /**
     * Get a translated string by dot-path key.
     * @param {string} key - e.g. 'nav.queue', 'queue.confirm_retry'
     * @param {Object} vars - interpolation: { count: 5, name: 'abc' }
     * @returns {string}
     */
    t(key, vars = {}) {
        let val = this._resolve(this._strings, key);
        if (val === undefined) {
            val = this._resolve(this._fallback, key);
            if (val === undefined) {
                if (this._ready) console.warn(`[i18n] Missing key: ${key}`);
                return key;
            }
            if (this._lang !== 'en' && this._ready) {
                console.info(`[i18n] Fallback to English: ${key}`);
            }
        }
        if (typeof val === 'string' && Object.keys(vars).length) {
            for (const [k, v] of Object.entries(vars)) {
                val = val.replaceAll(`{${k}}`, v);
            }
        }
        return val;
    },

    _applyToDOM() {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const val = this.t(el.getAttribute('data-i18n'));
            if (val !== el.getAttribute('data-i18n')) el.textContent = val;
        });
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const val = this.t(el.getAttribute('data-i18n-placeholder'));
            if (val !== el.getAttribute('data-i18n-placeholder')) el.placeholder = val;
        });
        document.querySelectorAll('[data-i18n-title]').forEach(el => {
            const val = this.t(el.getAttribute('data-i18n-title'));
            if (val !== el.getAttribute('data-i18n-title')) el.title = val;
        });
        document.querySelectorAll('[data-i18n-html]').forEach(el => {
            const val = this.t(el.getAttribute('data-i18n-html'));
            if (val !== el.getAttribute('data-i18n-html')) el.innerHTML = val;
        });
    },

    setLanguage(lang) {
        if (!this._supported.includes(lang)) return;
        document.cookie = `lang=${lang};path=/;max-age=${365 * 86400};SameSite=Lax`;
        location.reload();
    },

    get lang() { return this._lang; },

    formatDate(date, style = 'medium') {
        return new Intl.DateTimeFormat(this._lang, { dateStyle: style }).format(new Date(date));
    },

    formatDateTime(date, dateStyle = 'medium', timeStyle = 'short') {
        return new Intl.DateTimeFormat(this._lang, { dateStyle, timeStyle }).format(new Date(date));
    },

    formatNumber(num) {
        return new Intl.NumberFormat(this._lang).format(num);
    },

    formatCurrency(amount, currency = 'USD') {
        return new Intl.NumberFormat(this._lang, { style: 'currency', currency }).format(amount);
    },

    formatRelative(date) {
        const seconds = Math.round((new Date(date) - new Date()) / 1000);
        const units = [
            { unit: 'year', sec: 31536000 }, { unit: 'month', sec: 2592000 },
            { unit: 'week', sec: 604800 }, { unit: 'day', sec: 86400 },
            { unit: 'hour', sec: 3600 }, { unit: 'minute', sec: 60 },
            { unit: 'second', sec: 1 },
        ];
        for (const { unit, sec } of units) {
            if (Math.abs(seconds) >= sec) {
                return new Intl.RelativeTimeFormat(this._lang, { numeric: 'auto' })
                    .format(Math.round(seconds / sec), unit);
            }
        }
        return new Intl.RelativeTimeFormat(this._lang, { numeric: 'auto' }).format(0, 'second');
    }
};

// Phase 1: Load strings immediately (runs in <head>, before body renders)
I18N._lang = I18N._detectLanguage();
I18N._fallback = I18N._load('en');
if (I18N._lang !== 'en') {
    I18N._strings = I18N._load(I18N._lang);
} else {
    I18N._strings = I18N._fallback;
}
I18N._ready = true;

// Phase 2: Apply to DOM once it's built
document.addEventListener('DOMContentLoaded', () => {
    I18N._applyToDOM();
    document.documentElement.lang = I18N._lang;
    const label = document.getElementById('currentLangLabel');
    if (label) label.textContent = I18N._strings?._meta?.nativeName || 'English';
    document.querySelectorAll('[data-lang]').forEach(el => {
        el.classList.toggle('active', el.getAttribute('data-lang') === I18N._lang);
    });
});
