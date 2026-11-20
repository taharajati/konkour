import React, { useEffect, useState } from 'react'
import { get, post } from './api'
import { fa } from './ui'
import Icon from './Icons'
import Mascot from './Mascot'
import Markdown from './Markdown'

// «دفترچهٔ اشتباه‌ها»: the questions whose last answer was wrong, newest first
export default function Mistakes({ onStartWrong }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const load = () => { setError(''); get('/auth/me/wrong').then(setItems).catch(e => setError(e.message)) }
  useEffect(load, [])

  async function start() {
    if (busy) return
    setBusy(true)
    try { await post('/sessions/practice', { wrong_only: true, count: 10 }); onStartWrong() }
    catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  if (error) return <div className="pk"><p className="error" role="alert">{error}</p><button onClick={load}>دوباره امتحان کن</button></div>
  if (!items) return <div className="pk"><div className="card skeleton" style={{ height: 260, marginTop: 20 }} /></div>

  return (
    <div className="pk">
      <header className="pk-top">
        <a className="link-btn" href="#/progress"><Icon name="arrow" size={16} className="back" /> پیشرفت</a>
      </header>
      <h1 className="page-title" style={{ color: 'var(--text)' }}>دفترچهٔ اشتباه‌ها</h1>
      {items.length === 0 ? (
        <div className="empty">
          <Mascot mood="happy" size={84} />
          <h2>اشتباهی در دفترچه نیست</h2>
          <p className="pk-meta">هر سؤالی که غلط بزنی، تا وقتی درستش نکنی اینجا می‌ماند.</p>
        </div>
      ) : <>
        <p className="pk-meta">{fa(items.length)} سؤال. با «مرور» ۱۰ تای آخر را دوباره می‌پرسیم؛ درست‌ها از دفترچه بیرون می‌روند.</p>
        <button className="primary wide" onClick={start} disabled={busy}>{busy ? '…' : 'مرور اشتباه‌ها'}</button>
        <ul className="mk-list">
          {items.map(q => (
            <li key={q.public_id} className="card">
              <div className="mk-head"><b>{q.concept_title || q.topic || 'سؤال'}</b>
                {q.chapter_title && <span className="muted">{q.chapter_title}</span>}</div>
              <div className="mk-stem"><Markdown text={q.stem} /></div>
            </li>
          ))}
        </ul>
      </>}
    </div>
  )
}
