import React, { useEffect, useRef, useState } from 'react'
import { post, setToken } from './api'
import { fa } from './ui'

// Phone + one-time code is the main way in (Iranian standard); username/password
// stays for admins and existing accounts.
export default function Login({ onLoggedIn, onBack }) {
  const [mode, setMode] = useState('phone')        // phone | code | password | register
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [wait, setWait] = useState(0)              // seconds until a new code can be sent
  const codeRef = useRef(null)

  useEffect(() => {
    if (wait <= 0) return
    const t = setTimeout(() => setWait(w => w - 1), 1000)
    return () => clearTimeout(t)
  }, [wait])
  useEffect(() => { if (mode === 'code') codeRef.current?.focus() }, [mode])

  async function run(fn) {
    setBusy(true); setError('')
    try { await fn() } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const sendCode = (e) => { e?.preventDefault(); run(async () => {
    const res = await post('/auth/otp/request', { phone })
    setPhone(res.phone); setMode('code'); setCode(''); setWait(60)
  }) }

  const verify = (e) => { e.preventDefault(); run(async () => {
    const res = await post('/auth/otp/verify', { phone, code })
    setToken(res.access_token); onLoggedIn(res)
  }) }

  const passwordLogin = (e) => { e.preventDefault(); run(async () => {
    if (mode === 'register') await post('/auth/register', { username, password })
    const res = await post('/auth/login', { username, password })
    setToken(res.access_token); onLoggedIn(res)
  }) }

  return (
    <div className="center-screen">
      <div className="card login">
        <h1>آزمون‌ریپ</h1>

        {mode === 'phone' && (
          <form onSubmit={sendCode}>
            <p className="muted">با شمارهٔ موبایلت وارد شو؛ اگر حساب نداری، همین‌جا ساخته می‌شود.</p>
            <label htmlFor="l-phone">شمارهٔ موبایل</label>
            <input id="l-phone" dir="ltr" inputMode="tel" autoComplete="tel" placeholder="09121234567"
                   value={phone} onChange={e => setPhone(e.target.value)} required />
            {error && <p className="error" role="alert">{error}</p>}
            <button className="primary wide" disabled={busy || !phone.trim()}>{busy ? '…' : 'ارسال کد'}</button>
          </form>
        )}

        {mode === 'code' && (
          <form onSubmit={verify}>
            <p className="muted">کد ۵ رقمی را که به <span dir="ltr">{phone}</span> پیامک شد وارد کن.</p>
            <label htmlFor="l-code">کد تأیید</label>
            <input id="l-code" ref={codeRef} dir="ltr" inputMode="numeric" autoComplete="one-time-code"
                   maxLength={8} className="otp-input" value={code} onChange={e => setCode(e.target.value)} required />
            {error && <p className="error" role="alert">{error}</p>}
            <button className="primary wide" disabled={busy || code.trim().length < 5}>{busy ? '…' : 'ورود'}</button>
            <div className="login-links">
              <button type="button" className="link-btn" disabled={wait > 0 || busy} onClick={sendCode}>
                {wait > 0 ? `ارسال دوباره تا ${fa(wait)} ثانیهٔ دیگر` : 'ارسال دوبارهٔ کد'}
              </button>
              <button type="button" className="link-btn" onClick={() => { setMode('phone'); setError('') }}>تغییر شماره</button>
            </div>
          </form>
        )}

        {(mode === 'password' || mode === 'register') && (
          <form onSubmit={passwordLogin}>
            <label htmlFor="l-user">نام کاربری</label>
            <input id="l-user" dir="ltr" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required />
            <label htmlFor="l-pass">رمز عبور</label>
            <input id="l-pass" dir="ltr" type="password" autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
                   value={password} onChange={e => setPassword(e.target.value)} required minLength={mode === 'register' ? 8 : undefined} />
            {error && <p className="error" role="alert">{error}</p>}
            <button className="primary wide" disabled={busy}>{busy ? '…' : mode === 'register' ? 'ثبت‌نام' : 'ورود'}</button>
            <div className="login-links">
              <button type="button" className="link-btn" onClick={() => setMode(mode === 'register' ? 'password' : 'register')}>
                {mode === 'register' ? 'حساب داری؟ ورود' : 'ساخت حساب با نام کاربری'}
              </button>
            </div>
          </form>
        )}

        <div className="login-links">
          {mode === 'phone' || mode === 'code'
            ? <button type="button" className="link-btn" onClick={() => { setMode('password'); setError('') }}>ورود با نام کاربری و رمز</button>
            : <button type="button" className="link-btn" onClick={() => { setMode('phone'); setError('') }}>ورود با شمارهٔ موبایل</button>}
          {onBack && <button type="button" className="link-btn" onClick={onBack}>→ بازگشت</button>}
        </div>
      </div>
    </div>
  )
}
