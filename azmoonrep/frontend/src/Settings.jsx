import React, { useState } from 'react'
import JalaliDate from './JalaliDate'
import { patch, post, clearToken, setToken } from './api'
import { fa, jalali, daysUntil, getTheme, applyTheme } from './ui'

export const LOADS = [[10, 'سبک', 'حدود ۱۵ دقیقه'], [20, 'معمولی', 'حدود ۳۰ دقیقه'], [40, 'سنگین', 'حدود ۶۰ دقیقه']]

// DESIGN §9.5: daily capacity, exam date, plan, font size, logout
function PasswordCard() {
  const [cur, setCur] = useState('')
  const [next, setNext] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function change(e) {
    e.preventDefault()
    if (busy) return
    setBusy(true); setMsg(''); setError('')
    try {
      const r = await post('/auth/password', { current: cur, new: next })
      setToken(r.access_token)             // this device stays signed in, every other one is signed out
      setCur(''); setNext(''); setMsg('رمز عوض شد ✓ (در دستگاه‌های دیگر باید دوباره وارد شوی)')
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return (
    <form className="card" onSubmit={change}>
      <h2 className="section-title">تغییر رمز عبور</h2>
      <label htmlFor="pw-cur">رمز فعلی</label>
      <input id="pw-cur" dir="ltr" type="password" autoComplete="current-password" value={cur} onChange={e => setCur(e.target.value)} />
      <label htmlFor="pw-new">رمز تازه (دست‌کم ۸ کاراکتر)</label>
      <input id="pw-new" dir="ltr" type="password" autoComplete="new-password" value={next} onChange={e => setNext(e.target.value)} />
      {error && <p className="error" role="alert">{error}</p>}
      {msg && <p className="ok-text" role="status">{msg}</p>}
      <button className="wide" disabled={busy || !cur || next.length < 8}>{busy ? '…' : 'عوض کردن رمز'}</button>
    </form>
  )
}

export default function Settings({ user, onSaved, onEditPlan, onLogout }) {
  const [name, setName] = useState(user.display_name || '')
  const [load, setLoad] = useState(user.daily_load || 20)
  const [exam, setExam] = useState(user.exam_date || '')
  const [font, setFont] = useState(Number(localStorage.getItem('font_scale') || 1))
  const [theme, setTheme] = useState(getTheme())
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function save() {
    setBusy(true); setMsg(''); setError('')
    try {
      await patch('/auth/settings', { display_name: name, daily_load: load, exam_date: exam })
      localStorage.setItem('font_scale', String(font))
      setMsg('ذخیره شد ✓')
      onSaved()
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  const toExam = daysUntil(exam)
  return (
    <div className="page">
      <header className="topbar"><h1 className="page-title">تنظیمات</h1></header>

      <div className="card">
        <label htmlFor="s-name">نام نمایشی</label>
        <input id="s-name" value={name} maxLength={40} onChange={e => setName(e.target.value)} />

        <fieldset className="seg-field">
          <legend>حجم جلسهٔ روزانه</legend>
          <div className="segmented" role="radiogroup">
            {LOADS.map(([n, label, time]) => (
              <button key={n} type="button" role="radio" aria-checked={load === n}
                      className={load === n ? 'on' : ''} onClick={() => setLoad(n)}>
                <b>{fa(n)} سؤال</b><span>{label} · {time}</span>
              </button>
            ))}
          </div>
          <p className="muted">تغییر حجم روی جلسهٔ امروز هم اعمال می‌شود، اگر هنوز شروعش نکرده باشی.</p>
        </fieldset>

        <label htmlFor="s-exam">تاریخ آزمون (اختیاری)</label>
        <JalaliDate id="s-exam" value={exam} onChange={setExam} label="تاریخ آزمون" />
        {exam && <p className="muted">{jalali(exam, { day: 'numeric', month: 'long', year: 'numeric' })}
          {toExam !== null && toExam >= 0 && <> · {fa(toExam)} روز مانده</>}</p>}

        <fieldset className="seg-field">
          <legend>اندازهٔ پیش‌فرض متن سؤال</legend>
          <div className="font-row">
            <button type="button" onClick={() => setFont(f => Math.max(0.9, Math.round((f - 0.1) * 10) / 10))} aria-label="کوچک‌تر">A−</button>
            <span className="font-sample" style={{ fontSize: `${font}rem` }}>نمونهٔ متن سؤال</span>
            <button type="button" onClick={() => setFont(f => Math.min(1.5, Math.round((f + 0.1) * 10) / 10))} aria-label="بزرگ‌تر">A+</button>
          </div>
        </fieldset>

        <fieldset className="seg-field">
          <legend>ظاهر برنامه</legend>
          <div className="segmented" role="radiogroup">
            {[['system', 'مطابق دستگاه'], ['light', 'روشن'], ['dark', 'شب']].map(([k, label]) => (
              <button key={k} type="button" role="radio" aria-checked={theme === k}
                      className={theme === k ? 'on' : ''}
                      onClick={() => { setTheme(k); localStorage.setItem('theme_pref', k); applyTheme(k) }}>{label}</button>
            ))}
          </div>
        </fieldset>

        <button className="primary wide" disabled={busy} onClick={save}>ذخیره</button>
        {msg && <p className="ok-text" role="status">{msg}</p>}
        {error && <p className="error" role="alert">{error}</p>}
      </div>

      <div className="card">
        <h2 className="section-title">برنامهٔ مطالعه</h2>
        <p className="muted">{fa((user.scope_chapter_ids || []).length)} فصل از {fa((user.scope_book_ids || []).length)} کتاب انتخاب شده است.</p>
        <button className="wide" onClick={onEditPlan}>تغییر کتاب‌ها و فصل‌ها</button>
      </div>

      <PasswordCard />

      <div className="card">
        <h2 className="section-title">کمک</h2>
        <a className="btn-link wide" href="#/help">راهنما و پرسش‌های پرتکرار</a>
        <a className="btn-link wide" href="#/mistakes">دفترچهٔ اشتباه‌ها</a>
      </div>

      <div className="card">
        <button className="danger wide" onClick={onLogout}>خروج از حساب</button>
        <button className="wide" onClick={async () => {
          if (!window.confirm('از همهٔ دستگاه‌ها خارج می‌شوی و باید دوباره وارد شوی. ادامه می‌دهی؟')) return
          try { await post('/auth/logout-all', {}); clearToken(); window.location.reload() }
          catch (e) { setError(e.message) }
        }}>خروج از همهٔ دستگاه‌ها</button>
      </div>
    </div>
  )
}
