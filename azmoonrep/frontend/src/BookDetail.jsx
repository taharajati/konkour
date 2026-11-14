import React, { useEffect, useState } from 'react'
import { get, post } from './api'
import { STATUS as CAT } from './ui'

export default function BookDetail({ book, onBack, onStartToday, onStartChapter, onPracticeConcepts, onPlacement }) {
  const [chapters, setChapters] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    get(`/curriculum/books/${book.book_id}/chapters`).then(setChapters).catch(e => setError(e.message))
  }, [book.book_id])

  async function startToday() {
    setBusy(true)
    try {
      await post('/sessions/daily', { book_id: book.book_id })
      onStartToday(book)
    } catch (e) { setError(e.message); setBusy(false) }
  }

  async function practiceConcepts(concepts) {
    const ids = concepts.filter(c => c.status === 'new').map(c => c.concept_id)
    localStorage.setItem('practice_concepts', JSON.stringify(ids))
    localStorage.setItem('practice_chapters', JSON.stringify([]))
    localStorage.setItem('practice_count', String(Math.max(ids.length, 5)))
    onPracticeConcepts()
  }

  if (error) return <div className="center-screen"><div className="card"><p className="error">{error}</p><button onClick={onBack}>بازگشت</button></div></div>
  if (!chapters) return <div className="center-screen"><div className="spinner" /></div>

  return (
    <div className="page">
      <header className="topbar">
        <button className="ghost" onClick={onBack}>→ بازگشت</button>
        <b>{book.name}</b>
        <button className="primary small" disabled={busy || book.today_questions === 0}
                onClick={startToday}>
          تمرینات امروز ({book.today_questions})
        </button>
      </header>

      <div className="card">
        <div className="stacked-bar big-bar">
          {Object.entries(book.progress).map(([k, v]) =>
            v > 0 && <div key={k} style={{ width: `${v * 100}%`, background: CAT[k].color }} />)}
        </div>
        <div className="stacked-legend">
          {Object.entries(book.progress).map(([k, v]) => v > 0 && (
            <span key={k} className="legend-item">
              <span className="legend-dot" style={{ background: CAT[k].color }} />
              {CAT[k].fa} ٪{Math.round(v * 100)}
            </span>
          ))}
        </div>
        <p className="muted">مسیر زیر نشان می‌دهد هر فصل در کدام وضعیت است. برای شروع مبحث جدید، روی فصل بزن.</p>
      </div>

      <div className="path">
        {chapters.map((ch, i) => {
          const dominant = Object.entries(ch.progress).sort((a, b) => b[1] - a[1])[0]?.[0] || 'new'
          const color = CAT[dominant].color
          const complete = ch.total > 0 && ch.counts.learned === ch.total
          return (
            <div key={ch.chapter_id} className="path-item">
              <div className="path-line" />
              <div className="path-node" style={{ borderColor: color }}>
                <span className="path-num" style={{ background: color }}>{ch.number}</span>
              </div>
              <div className="path-content">
                <div className="path-title-row">
                  <b>فصل {ch.number}: {ch.title}</b>
                  {complete && <span className="badge done-badge">تکمیل ✓</span>}
                </div>
                <div className="stacked-bar slim">
                  {Object.entries(ch.progress).map(([k, v]) =>
                    v > 0 && <div key={k} style={{ width: `${v * 100}%`, background: CAT[k].color }} />)}
                </div>
                <div className="stacked-legend">
                  {Object.entries(ch.counts).map(([k, n]) => n > 0 && (
                    <span key={k} className="legend-item">
                      <span className="legend-dot" style={{ background: CAT[k].color }} />
                      {CAT[k].fa} {n}
                    </span>
                  ))}
                  {!ch.total && <span className="muted">سؤالی ندارد</span>}
                </div>
                <div className="bpc-actions">
                  {(ch.counts.review + ch.counts.wrong) > 0 && (
                    <button className="small primary" disabled={busy}
                            onClick={() => onStartChapter(book, ch.chapter_id)}>
                      تمرینات امروز ({ch.counts.review + ch.counts.wrong})
                    </button>
                  )}
                  {ch.placement_available > 1 && (
                    <button className="small" disabled={busy}
                            title="برای هر نکته یک سؤال؛ نکته‌هایی که بلدی از برنامه جلو می‌افتند"
                            onClick={() => onPlacement(ch.chapter_id)}>
                      تعیین سطح ({ch.placement_available} سؤال)
                    </button>
                  )}
                  {ch.counts.new > 0 && (
                    <button className="small" disabled={busy}
                            onClick={() => practiceConcepts(ch.concepts)}>
                      شروع مبحث جدید ({ch.counts.new})
                    </button>
                  )}
                </div>
                <details className="concepts-details">
                  <summary>{ch.total} مفهوم</summary>
                  {ch.concepts.map(c => (
                    <div key={c.concept_id} className="concept-line">
                      <span className="legend-dot" style={{ background: CAT[c.status].color }} />
                      <span className="concept-title">{c.title}</span>
                      <span className="muted">{c.mastery_fa}</span>
                    </div>
                  ))}
                </details>
              </div>
            </div>
          )
        })}
        {!chapters.length && <p className="muted">فصلی برای این کتاب انتخاب نشده؛ از «تنظیمات ← برنامهٔ مطالعه» تغییرش بده.</p>}
      </div>
    </div>
  )
}
