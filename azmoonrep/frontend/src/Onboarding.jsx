import React, { useEffect, useState } from 'react'
import JalaliDate from './JalaliDate'
import { get, patch } from './api'
import { fa, GRADE_FA, jalali } from './ui'
import { LOADS } from './Settings'

// DESIGN §9.2: a 2-minute setup. Books -> chapters -> daily load and exam date.
// Finishing starts today's session (the plan), not free practice.
export default function Onboarding({ onDone, edit = false, initialBooks = [], initialChapters = [] }) {
  const [books, setBooks] = useState(null)
  const [step, setStep] = useState(1)
  const [bookSel, setBookSel] = useState({})
  const [chSel, setChSel] = useState({})
  const [load, setLoad] = useState(20)
  const [exam, setExam] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const steps = edit ? 2 : 3

  useEffect(() => {
    get('/curriculum/book-cards').then(bs => {
      if (edit) {
        const ch = {}, bk = {}
        for (const b of bs) {
          for (const c of b.chapters) ch[c.chapter_id] = initialChapters.includes(c.chapter_id)
          bk[b.book_id] = initialBooks.includes(b.book_id) || b.chapters.some(c => initialChapters.includes(c.chapter_id))
        }
        setChSel(ch); setBookSel(bk)
        if (Object.values(bk).some(Boolean)) setStep(2)
      }
      setBooks(bs)
    }).catch(e => setError(e.message))
  }, [])

  const selBooks = (books || []).filter(b => bookSel[b.book_id])
  const selChapters = selBooks.flatMap(b => b.chapters).filter(c => chSel[c.chapter_id])
  const totalQ = selChapters.reduce((s, c) => s + c.question_count, 0)

  function toggleBook(id) {
    const on = !bookSel[id]
    setBookSel(s => ({ ...s, [id]: on }))
    const b = books.find(x => x.book_id === id)
    setChSel(ch => {
      const n = { ...ch }
      for (const c of b.chapters) n[c.chapter_id] = on
      return n
    })
  }

  async function finish() {
    setBusy(true); setError('')
    try {
      const body = { book_ids: selBooks.map(b => b.book_id),
                     chapter_ids: selChapters.map(c => c.chapter_id), onboarded: true }
      if (!edit) { body.daily_load = load; if (exam) body.exam_date = exam }
      await patch('/auth/scope', body)
      onDone({ startDaily: !edit })
    } catch (e) { setError(e.message); setBusy(false) }
  }

  if (!books) return error
    ? <div className="center-screen"><div className="card"><p className="error">{error}</p></div></div>
    : <div className="center-screen"><div className="spinner" /></div>

  return (
    <div className="page onboarding">
      <div className="onboard-head">
        <h1>{edit ? 'برنامهٔ مطالعه' : 'به آزمون‌ریپ خوش آمدی 👋'}</h1>
        <p className="muted">گام {fa(step)} از {fa(steps)}: {
          step === 1 ? 'کتاب‌هایی که می‌خواهی کار کنی را انتخاب کن'
            : step === 2 ? 'فصل‌های موردنظرت را تیک بزن'
              : 'هر روز چقدر وقت داری؟'}</p>
        <div className="steps">{Array.from({ length: steps }, (_, i) => <span key={i} className={step > i ? 'on' : ''} />)}</div>
      </div>

      {step === 1 && (
        <>
          <div className="book-grid">
            {books.map(b => (
              <button key={b.book_id} type="button" aria-pressed={!!bookSel[b.book_id]}
                      className={`book-card ${bookSel[b.book_id] ? 'selected' : ''}`}
                      onClick={() => toggleBook(b.book_id)}>
                <img src={b.cover} alt="" loading="lazy" onError={e => { e.target.style.display = 'none' }} />
                <div className="book-name">{b.name}</div>
                <div className="muted">پایهٔ {GRADE_FA[b.grade] || b.grade}</div>
                <span className={`tick ${bookSel[b.book_id] ? 'on' : ''}`} aria-hidden="true">✓</span>
              </button>
            ))}
          </div>
          <button className="primary wide cta" disabled={!selBooks.length} onClick={() => setStep(2)}>
            ادامه ({fa(selBooks.length)} کتاب)
          </button>
        </>
      )}

      {step === 2 && (
        <>
          <div className="card">
            {selBooks.map(b => (
              <div key={b.book_id} className="chapter-group">
                <h3>{b.name}</h3>
                {b.chapters.map(c => (
                  <label key={c.chapter_id} className={`chapter-row ${chSel[c.chapter_id] ? 'on' : ''}`}>
                    <input type="checkbox" checked={!!chSel[c.chapter_id]}
                           onChange={() => setChSel(s => ({ ...s, [c.chapter_id]: !s[c.chapter_id] }))} />
                    <span className="concept-title">فصل {fa(c.number)}: {c.title}</span>
                    {c.question_count > 0
                      ? <span className="badge">{fa(c.question_count)} سؤال</span>
                      : <span className="badge zero">به‌زودی</span>}
                  </label>
                ))}
              </div>
            ))}
          </div>
          <div className="card sticky-bar">
            <div className="bar-info">{fa(selChapters.length)} فصل · {fa(totalQ)} سؤال در دسترس</div>
            {edit
              ? <button className="primary wide" disabled={busy || !selChapters.length} onClick={finish}>ذخیرهٔ برنامه</button>
              : <button className="primary wide" disabled={!selChapters.length} onClick={() => setStep(3)}>ادامه</button>}
            <button className="ghost" onClick={() => setStep(1)}>→ تغییر کتاب‌ها</button>
          </div>
        </>
      )}

      {step === 3 && (
        <div className="card">
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
            <p className="muted">هر وقت خواستی از تنظیمات عوضش کن.</p>
          </fieldset>
          <label htmlFor="o-exam">تاریخ آزمون یا کنکور (اختیاری)</label>
          <JalaliDate id="o-exam" value={exam} onChange={setExam} label="تاریخ آزمون" />
          {exam && <p className="muted">{jalali(exam, { day: 'numeric', month: 'long', year: 'numeric' })}</p>}
          <button className="primary wide cta" disabled={busy} onClick={finish}>
            {totalQ === 0 ? 'ذخیره (برای این فصل‌ها هنوز سؤالی نیست)' : 'ذخیره و شروع جلسهٔ امروز'}
          </button>
          <button className="ghost" onClick={() => setStep(2)}>→ برگشت به فصل‌ها</button>
          {error && <p className="error" role="alert">{error}</p>}
        </div>
      )}
      {error && step !== 3 && <p className="error" role="alert">{error}</p>}
    </div>
  )
}
