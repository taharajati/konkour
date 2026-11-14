import React, { useEffect, useMemo, useState } from 'react'
import { get } from './api'
import { fa, GRADE_FA } from './ui'

export default function Topics({ onStart }) {
  const [tree, setTree] = useState(null)
  const [open, setOpen] = useState({})            // expanded topics
  const [selected, setSelected] = useState({})    // concept_id -> true
  const [count, setCount] = useState(10)
  const [error, setError] = useState('')

  useEffect(() => { get('/curriculum/topics').then(setTree).catch(e => setError(e.message)) }, [])

  const totalSelected = Object.values(selected).filter(Boolean).length
  const available = useMemo(() => {
    if (!tree) return 0
    return tree.flatMap(g => g.topics.flatMap(t => t.concepts))
      .filter(c => selected[c.concept_id])
      .reduce((sum, c) => sum + c.questions, 0)
  }, [tree, selected])

  function toggle(cid) {
    setSelected(s => ({ ...s, [cid]: !s[cid] }))
  }
  function toggleTopic(concepts, topic) {
    const allOn = concepts.every(c => selected[c.concept_id])
    setSelected(s => {
      const next = { ...s }
      for (const c of concepts) next[c.concept_id] = !allOn
      return next
    })
  }

  function start() {
    const ids = Object.keys(selected).filter(k => selected[k])
    localStorage.setItem('practice_concepts', JSON.stringify(ids))
    localStorage.removeItem('practice_chapters')
    localStorage.setItem('practice_count', String(count))
    onStart()
  }

  if (error) return <div className="page"><div className="card"><p className="error">{error}</p></div></div>
  if (!tree) return <div className="center-screen"><div className="spinner" /></div>
  if (!tree.length) return <div className="page"><div className="card"><p className="muted">هنوز سؤال تأییدشده‌ای برای تمرین آزاد نیست.</p></div></div>

  return (
    <div className="page">
      <div className="card">
        <h2>انتخاب مبحث برای تمرین</h2>
        <p className="muted">مباحث را انتخاب کن؛ سؤال‌ها از بین آن‌ها تصادفی داده می‌شود. تمرین روی مرور روزانه اثری ندارد.</p>
        {tree.map(g => (
          <div key={g.grade} className="grade-block">
            <h3 className="grade-title">پایهٔ {GRADE_FA[g.grade] || g.grade}</h3>
            {g.topics.map(t => (
              <div key={t.topic} className="topic-block">
                <button type="button" className="topic-row" aria-expanded={!!open[t.topic]}
                        onClick={() => setOpen(o => ({ ...o, [t.topic]: !o[t.topic] }))}>
                  <span className={`arrow ${open[t.topic] ? 'open' : ''}`} aria-hidden="true">◂</span>
                  <b>{t.topic}</b>
                  <span className="badge">{fa(t.concepts.reduce((s, c) => s + c.questions, 0))} سؤال</span>
                </button>
                {open[t.topic] && (
                  <div className="concepts">
                    {t.concepts.map(c => (
                      <label key={c.concept_id} className={`concept-row ${selected[c.concept_id] ? 'on' : ''}`}>
                        <input type="checkbox" checked={!!selected[c.concept_id]} onChange={() => toggle(c.concept_id)} />
                        <span className="concept-title">{c.title}</span>
                        <span className="badge">{c.questions}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>

      <div className="card sticky-bar">
        <div className="bar-info">
          <b>{totalSelected}</b> مفهوم انتخاب شده · <b>{available}</b> سؤال موجود
        </div>
        <div className="count-pick">
          تعداد:
          {[10, 20, 40].map(n => (
            <button key={n} className={`pill ${count === n ? 'active' : ''}`} onClick={() => setCount(n)}>{n}</button>
          ))}
        </div>
        <button className="primary wide" disabled={totalSelected === 0} onClick={start}>
          شروع تمرین
        </button>
      </div>
    </div>
  )
}
