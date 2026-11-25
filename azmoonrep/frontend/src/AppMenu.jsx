import React, { useState } from 'react'
import { get } from './api'
import { fa } from './ui'
import Icon from './Icons'

// side menu opened from the avatar: everything that doesn't fit the bottom nav.
// Book switching lives in the book pill on «امروز», not here.
export default function BookMenu({ open, onClose, onNavigate, onLogout }) {
  const [wrong, setWrong] = useState(null)
  const [confirming, setConfirming] = useState(false)

  React.useEffect(() => {
    if (!open) { setConfirming(false); return }
    get('/auth/me/stats').then(st => setWrong(st.wrong_count || 0)).catch(() => {})
  }, [open])

  if (!open) return null
  const items = [
    ['mistakes', 'دفترچهٔ اشتباهات', 'notebook', wrong !== null && wrong > 0 ? fa(wrong) : null],
    ['help', 'راهنما', 'help', null],
    ['settings', 'تنظیمات', 'sliders', null],
  ]

  return (
    <>
      <div className="bm-overlay" onClick={onClose} />
      <aside className="bm" role="dialog" aria-label="منو">
        <header className="bm-head"><b>منو</b>
          <button className="link-btn" onClick={onClose}>بستن</button>
        </header>
        <div className="bm-list">
          {items.map(([route, label, icon, badge]) => (
            <button key={route} type="button" className="bm-item" onClick={() => { onClose(); onNavigate(route) }}>
              <Icon name={icon} size={20} />
              <span>{label}</span>
              {badge && <span className="bm-badge num">{badge}</span>}
            </button>
          ))}
        </div>
        <div className="bm-logout">
          {confirming
            ? <>
                <span className="bm-hint">از حساب خارج می‌شوی؟</span>
                <button className="bm-item danger" onClick={() => { onClose(); onLogout() }}>خروج</button>
                <button className="link-btn" onClick={() => setConfirming(false)}>انصراف</button>
              </>
            : <button type="button" className="bm-item" onClick={() => setConfirming(true)}>
                <Icon name="cross" size={20} /><span>خروج از حساب</span>
              </button>}
        </div>
      </aside>
    </>
  )
}
