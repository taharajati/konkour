import React, { useEffect, useState } from 'react'
import { get, post } from './api'
import { fa, pct, STATUS, MASTERY } from './ui'

// DESIGN §9.5: quiet secondary screen. Books with progress, the wrong-answers notebook,
// free practice, and per-chapter mastery. Nothing here competes with «امروز».
export default function Progress({ onSelectBook, onStartWrong, onFreePractice }) {
  const [books, setBooks] = useState(null)
  const [stats, setStats] = useState(null)
  const [chapters, setChapters] = useState(null)
  const [error, setError] = useState('')

  const load = () => {
    setError('')
    Promise.all([get('/me/books'), get('/auth/me/stats'), get('/curriculum/progress')])
      .then(([b, s, c]) => { setBooks(b); setStats(s); setChapters(c) })
      .catch(e => setError(e.message))
  }
  useEffect(load, [])

  async function startWrong() {
    try {
      await post('/sessions/practice', { wrong_only: true, count: 10 })
      onStartWrong()
    } catch (e) { setError(e.message) }
  }

  if (error) return <div className="page"><div className="card"><p className="error">{error}</p><button onClick={load}>دوباره امتحان کن</button></div></div>
  if (!books) return <div className="page"><div className="card skeleton" style={{ height: 220 }} /></div>

  return (
    <div className="page">
      <header className="topbar"><h1 className="page-title">پیشرفت</h1></header>

      {stats && (
        <div className="stat-row">
          <Stat n={pct(stats.accuracy)} label="دقت کل" />
          <Stat n={fa(stats.week_answered)} label="سؤال این هفته" />
          <Stat n={pct(stats.week_accuracy)} label="دقت این هفته" />
        </div>
      )}

      <h2 className="section-title">کتاب‌های برنامهٔ تو</h2>
      <div className="book-progress-grid">
        {books.map(b => <BookCard key={b.book_id} b={b} onSelect={() => onSelectBook(b)} />)}
        {!books.length && <p className="muted">هنوز کتابی انتخاب نکرده‌ای. از «تنظیمات ← برنامهٔ مطالعه» انتخاب کن.</p>}
      </div>

      {stats && stats.wrong_count > 0 && (
        <div className="card wrong-card">
          <h2 className="section-title">دفترچهٔ اشتباهات</h2>
          <p className="muted">{fa(stats.wrong_count)} سؤال را آخرین بار اشتباه جواب دادی. تمرین دوباره‌شان روی برنامهٔ مرور اثری ندارد.</p>
          <button className="wide" onClick={startWrong}>مرور اشتباهات</button>
        </div>
      )}

      <div className="card">
        <h2 className="section-title">تمرین آزاد</h2>
        <p className="muted">خودت مبحث انتخاب کن و تمرین کن. روی برنامهٔ مرور اثری ندارد.</p>
        <button className="wide" onClick={onFreePractice}>انتخاب مبحث و تمرین</button>
      </div>

      {chapters && chapters.length > 0 && (
        <>
          <h2 className="section-title">نکته‌ها، فصل به فصل</h2>
          {chapters.map(ch => (
            <details key={ch.book + ch.chapter} className="card chapter-mastery">
              <summary>
                <b>{ch.book || 'بدون کتاب'} · {ch.chapter || '—'}</b>
                <span className="mastery-pill" style={{ background: MASTERY[Math.round(ch.mastery_avg)].color }}>
                  {MASTERY[Math.round(ch.mastery_avg)].fa}
                </span>
              </summary>
              {ch.concepts.map(c => (
                <div key={c.concept_id} className="concept-line">
                  <span className="concept-title">{c.title}</span>
                  <span className="dot-group" aria-label={MASTERY[c.mastery].fa}>
                    {[0, 1, 2, 3].map(l => (
                      <span key={l} className="lvl-dot" style={{ background: l <= c.mastery ? MASTERY[l].color : 'var(--border)' }} />
                    ))}
                  </span>
                  <span className="muted">{MASTERY[c.mastery].fa}</span>
                </div>
              ))}
            </details>
          ))}
        </>
      )}
    </div>
  )
}

function Stat({ n, label }) {
  return <div className="stat-chip"><span className="stat-num">{n}</span><span className="stat-label">{label}</span></div>
}

function BookCard({ b, onSelect }) {
  const p = b.progress
  return (
    <button type="button" className="card book-progress-card" onClick={onSelect}>
      <div className="bpc-head">
        <img className="bpc-cover" src={b.cover} alt="" onError={e => { e.target.style.display = 'none' }} />
        <div className="bpc-info">
          <b>{b.name}</b>
          <span className="muted">{fa(b.concepts_total)} نکته · دقت {pct(b.accuracy)}</span>
        </div>
      </div>
      <div className="stacked-bar" role="img"
           aria-label={Object.entries(STATUS).map(([k, s]) => `${s.fa} ${pct(p[k])}`).join('، ')}>
        {Object.entries(STATUS).map(([k, s]) => p[k] > 0 && <div key={k} style={{ width: `${p[k] * 100}%`, background: s.color }} />)}
      </div>
      <div className="stacked-legend">
        {Object.entries(STATUS).map(([k, s]) => p[k] > 0 && (
          <span key={k} className="legend-item"><span className="legend-dot" style={{ background: s.color }} />{s.fa} {pct(p[k])}</span>
        ))}
      </div>
    </button>
  )
}
