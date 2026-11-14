// shared display helpers: Persian digits, Jalali dates, status colors (CSS tokens)

export const fa = (n) => (n === null || n === undefined || n === '') ? '—' : Number(n).toLocaleString('fa-IR')

export const pct = (x) => x === null || x === undefined ? '—' : `٪${fa(Math.round(x * 100))}`

export function jalali(iso, opts = { day: 'numeric', month: 'long' }) {
  if (!iso) return ''
  const d = new Date(String(iso).slice(0, 10) + 'T12:00:00')
  return d.toLocaleDateString('fa-IR', opts)
}

export function daysUntil(iso) {
  if (!iso) return null
  const d = new Date(String(iso).slice(0, 10) + 'T00:00:00')
  const t = new Date(); t.setHours(0, 0, 0, 0)
  return Math.round((d - t) / 86400000)
}

// one palette for learning status, defined as CSS variables (light + dark)
export const STATUS = {
  learned: { fa: 'یاد گرفته', color: 'var(--s-learned)' },
  review: { fa: 'نیاز به مرور', color: 'var(--s-review)' },
  wrong: { fa: 'اشتباه', color: 'var(--s-wrong)' },
  new: { fa: 'شروع نشده', color: 'var(--s-new)' },
}

export const MASTERY = [
  { fa: 'نیاموخته', color: 'var(--s-new)' },
  { fa: 'در حال یادگیری', color: 'var(--s-review)' },
  { fa: 'یاد گرفته', color: 'var(--primary)' },
  { fa: 'مسلط', color: 'var(--s-learned)' },
]

export const GRADE_FA = { 9: 'نهم', 10: 'دهم', 11: 'یازدهم', 12: 'دوازدهم' }

// theme: 'system' (follow the OS) | 'light' | 'dark'; stored in localStorage, applied as html[data-theme]
export function getTheme() { return localStorage.getItem('theme_pref') || 'light' }
export function applyTheme(t = getTheme()) {
  const dark = t === 'dark' || (t === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.dataset.theme = dark ? 'dark' : 'light'
}
