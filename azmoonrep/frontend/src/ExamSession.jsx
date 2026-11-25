import React, { useEffect, useRef, useState } from 'react'
import { get, post } from './api'
import { fa } from './ui'
import Icon from './Icons'
import Markdown from './Markdown'
import Figure, { FigureImage, Lightbox } from './Figure'
import { playCorrect, playFinish } from './sounds'

// آزمون آزمایشی: ۲۰ سؤال، زمان‌دار، بدون نکته و راهنما. No feedback per question —
// like the real thing. At the end the result maps back to key points to review.
const faTime = (s) => `${fa(Math.floor(s / 60))}:${fa(Math.floor(s % 60)).padStart(2, '۰')}`

export default function ExamSession({ onExit, onPracticeConcepts }) {
  const [exam, setExam] = useState(null)        // {exam_id, total, deadline}
  const [cfgCount, setCfgCount] = useState(20)  // null = custom input open
  const [cfgMinutes, setCfgMinutes] = useState(30)
  const [customCount, setCustomCount] = useState('')
  const [customMinutes, setCustomMinutes] = useState('')
  const [index, setIndex] = useState(0)
  const [question, setQuestion] = useState(null)
  const [selected, setSelected] = useState(null)
  const [answered, setAnswered] = useState(0)
  const [left, setLeft] = useState(null)        // seconds remaining
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [zoomed, setZoomed] = useState(null)
  const busy = useRef(false)

  async function start() {
    try {
      const e = await post('/sessions/exam/start', { count: cfgCount, minutes: cfgMinutes })
      setExam(e); setLeft(Math.max(0, (new Date(e.deadline) - new Date()) / 1000))
    } catch (e) { setError(e.message) }
  }

  // countdown; auto-finish when the time runs out
  useEffect(() => {
    if (!exam || result) return
    const t = setInterval(() => setLeft(l => {
      if (l === null) return l
      if (l <= 1) { clearInterval(t); finish(true); return 0 }
      return l - 1
    }), 1000)
    return () => clearInterval(t)
  }, [exam, result])

  useEffect(() => {
    if (!exam || result) return
    setQuestion(null); setSelected(null)
    if (index >= exam.total) { finish(false); return }
    get(`/sessions/exam/${exam.exam_id}/question/${index}`)
      .then(setQuestion).catch(e => setError(e.message))
  }, [index, exam])

  async function finish(timedOut) {
    if (busy.current) return
    busy.current = true
    try {
      const r = await post(`/sessions/exam/${exam.exam_id}/finish`, {})
      setResult({ ...r, timedOut })
      playFinish()
    } catch (e) { setError(e.message) } finally { busy.current = false }
  }

  async function submit() {
    if (busy.current || selected === null) return
    busy.current = true
    try {
      const r = await post(`/sessions/exam/${exam.exam_id}/answer/${index}`,
        { selected_option: selected, time_ms: 0 })
      playCorrect()          // quiet dopamine, no right/wrong reveal
      setAnswered(r.answered)
      setIndex(i => i + 1)
    } catch (e) {
      if (String(e.message).includes('زمان')) finish(true)
      else setError(e.message)
    } finally { busy.current = false }
  }

  useEffect(() => {
    const h = (e) => {
      if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return
      const n = question?.options?.length || 0
      const k = Number(e.key)
      if (!result && k >= 1 && k <= n) setSelected(k)
      if (e.key === 'Enter') { e.preventDefault(); if (selected !== null) submit() }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [question, selected, result])

  if (error) return (
    <div className="center-screen"><div className="card">
      <p className="error" role="alert">{error}</p>
      <button onClick={onExit}>بازگشت</button>
    </div></div>
  )

  if (result) {
    const pct = result.answered ? Math.round(100 * result.correct / result.answered) : 0
    return (
      <div className="center-screen">
        <div className="card summary">
          <h2>نتیجهٔ آزمون آزمایشی</h2>
          {result.timedOut && <p className="muted">زمان تمام شد؛ سؤال‌های بی‌جواب، غلط حساب شدند.</p>}
          <p className="big"><span className="num">{fa(result.correct)}</span> از <span className="num">{fa(result.answered)}</span> درست · ٪<span className="num">{fa(pct)}</span></p>
          {result.skipped > 0 && <p className="muted"><span className="num">{fa(result.skipped)}</span> سؤال بی‌جواب ماند.</p>}
          <div className="exam-items">
            {result.items.map(it => (
              <div key={it.concept_id} className="exam-item">
                <span className={`dot3 ${it.wrong ? 'wrong' : ''}`} />
                <div className="exam-item-text"><b>{it.title}</b>
                  <span className="muted">{it.chapter_title}{it.book_name ? ` · ${it.book_name}` : ''}</span></div>
                <span className="num">{fa(it.correct)}/{fa(it.correct + it.wrong)}</span>
              </div>
            ))}
          </div>
          {result.wrong_concept_ids.length > 0 && (
            <button className="primary wide" onClick={() => onPracticeConcepts(result.wrong_concept_ids)}>
              مرور نکته‌هایی که اشتباه زدم
            </button>
          )}
          <button className="wide" onClick={onExit}>بازگشت</button>
        </div>
      </div>
    )
  }

  if (!exam) return (
    <div className="center-screen">
      <div className="card exam-setup">
        <h2>آزمون آزمایشی</h2>
        <p className="muted">شبیه آزمون آزمایشی: بدون نکته و راهنما، جواب‌ها آخر آزمون اعلام می‌شوند.</p>

        <div className="setup-row">
          <span className="setup-label">تعداد سؤال</span>
          <div className="segmented">
            {[10, 20].map(n => (
              <button key={n} type="button" className={cfgCount === n ? 'on' : ''}
                      onClick={() => setCfgCount(n)}>{fa(n)}</button>
            ))}
            <button type="button" className={typeof cfgCount === 'string' ? 'on' : ''}
                    onClick={() => setCfgCount('custom')}>خودم</button>
          </div>
          {cfgCount === 'custom' && (
            <input dir="ltr" inputMode="numeric" autoFocus placeholder="مثلاً ۱۵" value={customCount}
                   onChange={e => setCustomCount(e.target.value)} className="setup-input" />
          )}
        </div>

        <div className="setup-row">
          <span className="setup-label">زمان</span>
          <div className="segmented">
            {[15, 30].map(n => (
              <button key={n} type="button" className={cfgMinutes === n ? 'on' : ''}
                      onClick={() => setCfgMinutes(n)}>{fa(n)} دقیقه</button>
            ))}
            <button type="button" className={typeof cfgMinutes === 'string' ? 'on' : ''}
                    onClick={() => setCfgMinutes('custom')}>خودم</button>
          </div>
          {cfgMinutes === 'custom' && (
            <input dir="ltr" inputMode="numeric" placeholder="مثلاً ۴۵" value={customMinutes}
                   onChange={e => setCustomMinutes(e.target.value)} className="setup-input" />
          )}
        </div>

        <button className="primary wide" onClick={() => {
          const c = cfgCount === 'custom' ? parseInt(customCount, 10) : cfgCount
          const m = cfgMinutes === 'custom' ? parseInt(customMinutes, 10) : cfgMinutes
          if (!Number.isFinite(c) || c < 5 || c > 40) { setError('تعداد سؤال باید بین ۵ تا ۴۰ باشد'); return }
          if (!Number.isFinite(m) || m < 5 || m > 180) { setError('زمان باید بین ۵ تا ۱۸۰ دقیقه باشد'); return }
          setCfgCount(c); setCfgMinutes(m); start()
        }}>شروع آزمون</button>
        <button className="ghost wide" onClick={onExit}>انصراف</button>
      </div>
    </div>
  )

  const urgent = left !== null && left < 120
  return (
    <div className="session exam">
      <div className="session-header">
        <span className={`counter num ${urgent ? 'urgent' : ''}`}>⏱ {left !== null ? faTime(left) : ''}</span>
        <span className="counter muted num">{fa(answered)} از {fa(exam.total)}</span>
        <button className="ghost" aria-label="خروج از آزمون"
                onClick={() => window.confirm('از آزمون خارج می‌شوی؟ اگر زمان تمام نشده باشد، بی‌جواب‌ها غلط حساب می‌شوند.') && finish(false)}>
          <Icon name="close" /></button>
      </div>
      <div className="progress-bar" role="progressbar" aria-valuemin={0} aria-valuemax={exam.total} aria-valuenow={answered}>
        <div style={{ width: `${(answered / exam.total) * 100}%` }} />
      </div>
      <div className="exam-banner">آزمون آزمایشی: بدون نکته و راهنما — جواب‌ها آخر آزمون اعلام می‌شوند</div>

      {!question ? <div className="center-screen"><div className="spinner" /></div> : (
        <div className="question-box">
          <div className="stem"><Markdown text={question.stem_md} /></div>
          {question.figures?.map((f, i) => <Figure key={f.url} fig={f} alt={`شکل ${fa(i + 1)} سؤال`} />)}
          <div className={`options ${question.option_figures?.some(Boolean) ? 'options-figs' : ''}`} role="radiogroup" aria-label="گزینه‌ها">
            {question.options.map((opt, i) => (
              <div key={i} className="opt-cell">
                <button type="button" role="radio" aria-checked={selected === i + 1}
                        className={`option ${selected === i + 1 ? 'selected' : ''}`}
                        onClick={() => setSelected(i + 1)}>
                  <span className="opt-num">{fa(i + 1)}</span>
                  {question.option_figures?.[i]
                    ? <FigureImage fig={question.option_figures[i]} alt={`شکل گزینهٔ ${fa(i + 1)}`} eager />
                    : <Markdown text={opt} />}
                </button>
                {question.option_figures?.[i] && (
                  <button type="button" className="opt-zoom" aria-label={`بزرگ‌نمایی شکل گزینهٔ ${fa(i + 1)}`}
                          onClick={() => setZoomed(question.option_figures[i])}>
                    <Icon name="zoom" size={18} />
                  </button>
                )}
              </div>
            ))}
          </div>
          {zoomed && <Lightbox fig={zoomed} alt="شکل گزینه" onClose={() => setZoomed(null)} />}
          <div className="answer-actions">
            <button className="primary wide" disabled={selected === null} onClick={submit}>
              ثبت و سؤال بعدی <span className="kbd-hint">(Enter)</span>
            </button>
          </div>
          <div className="kbd-help muted">کلیدهای ۱–۴ برای انتخاب · Enter برای ثبت</div>
        </div>
      )}
    </div>
  )
}
