const TOKEN_KEY = 'azmoonrep_token'

export function getToken() { return localStorage.getItem(TOKEN_KEY) }
export function setToken(t) { localStorage.setItem(TOKEN_KEY, t) }
export function clearToken() { localStorage.removeItem(TOKEN_KEY) }

const MESSAGES = {
  'not authenticated': 'لطفاً دوباره وارد شو.',
  'invalid or expired token': 'نشست تو منقضی شده؛ لطفاً دوباره وارد شو.',
  'slot already answered': 'این سؤال قبلاً پاسخ داده شده است.',
  'no questions for the selected topics': 'برای این مباحث هنوز سؤال تأییدشده‌ای نداریم.',
}

function errorText(res, body) {
  let d = body.detail
  // FastAPI validation errors (422) come as a list of objects
  if (Array.isArray(d)) d = d.map(x => x.msg || JSON.stringify(x)).join('؛ ')
  else if (d && typeof d !== 'string') d = JSON.stringify(d)
  if (!d) return res.status >= 500 ? 'خطای سرور؛ کمی بعد دوباره امتحان کن.' : res.statusText
  return MESSAGES[d] || d
}

async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
  const t = getToken()
  if (t) headers['Authorization'] = `Bearer ${t}`
  let res
  try {
    res = await fetch(`/api${path}`, { ...options, headers })
  } catch {
    throw new Error('اتصال به سرور برقرار نشد. اینترنت را بررسی کن.')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    if (res.status === 401 && t) clearToken()
    throw new Error(errorText(res, body))
  }
  if (res.status === 204) return null
  return res.json()
}

// images behind auth (e.g. admin-only scans): <img> can't send the header, so
// fetch with the token and hand back an object URL
export async function getBlobUrl(path) {
  const t = getToken()
  const res = await fetch(`/api${path}`, { headers: t ? { Authorization: `Bearer ${t}` } : {} })
  if (!res.ok) throw new Error(res.status === 404 ? 'تصویر مرجع پیدا نشد' : res.statusText)
  return URL.createObjectURL(await res.blob())
}

export const get = (p) => api(p)
export const post = (p, body) => api(p, { method: 'POST', body: JSON.stringify(body) })
export const patch = (p, body) => api(p, { method: 'PATCH', body: JSON.stringify(body) })
