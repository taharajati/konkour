import React, { useState } from 'react'
import { post, setToken } from './api'

// Username + password. New students register here; admins sign in the same way.
export default function Login({ onLoggedIn, onBack }) {
  const [mode, setMode] = useState('login')        // login | register
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (busy) return
    setBusy(true); setError('')
    try {
      if (mode === 'register') await post('/auth/register', { username: username.trim(), password })
      const res = await post('/auth/login', { username: username.trim(), password })
      setToken(res.access_token); onLoggedIn(res)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  const register = mode === 'register'

  return (
    <div className="center-screen">
      <div className="card login">
        <h1>آزمون‌ریپ</h1>
        <form onSubmit={submit}>
          <p className="muted">{register ? 'یک نام کاربری و رمز انتخاب کن.' : 'با نام کاربری و رمزت وارد شو.'}</p>
          <label htmlFor="l-user">نام کاربری</label>
          <input id="l-user" dir="ltr" autoComplete="username" autoCapitalize="none" value={username}
                 onChange={e => setUsername(e.target.value)} required />
          {register && <p className="muted">۳ تا ۳۲ حرف انگلیسی، عدد یا _ . -</p>}
          <label htmlFor="l-pass">رمز عبور</label>
          <input id="l-pass" dir="ltr" type="password" autoComplete={register ? 'new-password' : 'current-password'}
                 value={password} onChange={e => setPassword(e.target.value)} required minLength={register ? 8 : undefined} />
          {register && <p className="muted">دست‌کم ۸ کاراکتر.</p>}
          {error && <p className="error" role="alert">{error}</p>}
          <button className="primary wide" disabled={busy || !username.trim() || !password}>
            {busy ? '…' : register ? 'ثبت‌نام' : 'ورود'}
          </button>
          <div className="login-links">
            <button type="button" className="link-btn" onClick={() => { setMode(register ? 'login' : 'register'); setError('') }}>
              {register ? 'حساب داری؟ ورود' : 'حساب نداری؟ ثبت‌نام'}
            </button>
            {onBack && <button type="button" className="link-btn" onClick={onBack}>→ بازگشت</button>}
          </div>
        </form>
      </div>
    </div>
  )
}
