import React, { useEffect, useRef, useState } from 'react'
import { get, post } from './api'
import Markdown from './Markdown'
import Icon from './Icons'
import Figure, { FigureImage, Lightbox } from './Figure'
import Mascot from './Mascot'

const BASE = { daily: '/sessions/daily', practice: '/sessions/practice', placement: '/sessions/placement' }
const TITLES = { daily: 'جلسهٔ امروز تمام شد', practice: 'تمرین تمام شد', placement: 'آزمون تعیین سطح تمام شد' }
const fa = (n) => Number(n).toLocaleString('fa-IR')

// «فردا» / «۴ روز دیگر» instead of a raw ISO date: the student should see the
// repetition engine keep its promise (DESIGN §9.3)
function relativeDue(iso) {
  if (!iso) return null
  const due = new Date(iso.slice(0, 10) + 'T00:00:00')
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const days = Math.round((due - today) / 86400000)
  if (days <= 0) return 'امروز'
  if (days === 1) return 'فردا'
  if (days < 30) return `${fa(days)} روز دیگر`
  return `${fa(Math.round(days / 30))} ماه دیگر`
}

export default function Session({ mode = 'daily', resume = false, dailyBookId = null, dailyChapterId = null, placementChapterId = null, onExit }) {
  const [session, setSession] = useState(null)
  const [index, setIndex] = useState(null)
  const [question, setQuestion] = useState(null)
  const [selected, setSelected] = useState(null)
  const [feedback, setFeedback] = useState(null)
  const [finished, setFinished] = useState(false)
  const [error, setError] = useState('')
  const [fontScale, setFontScale] = useState(Number(localStorage.getItem('font_scale') || 1))
  const [reportSent, setReportSent] = useState(false)
  const [lesson, setLesson] = useState(null)   // key-point card shown before a new concept
  const [writtenSolution, setWrittenSolution] = useState(null)
  const [zoomed, setZoomed] = useState(null)      // option figure opened large
  const [notice, setNotice] = useState(null)     // {msg, retry}: a failed answer/next keeps the question on screen
  const [tomorrow, setTomorrow] = useState(null)   // reviews due tomorrow, shown on the summary
  const startTime = useRef(Date.now())
  const busy = useRef(false)          // blocks double submit (Enter + click, double Enter)
  const base = BASE[mode]
  const bid = mode === 'daily' ? dailyBookId : null
  const chid = mode === 'daily' ? dailyChapterId : null
  const qs = (bid != null || chid != null) ? '?' + [bid != null ? `book_id=${encodeURIComponent(bid)}` : '', chid != null ? `chapter_id=${encodeURIComponent(chid)}` : ''].filter(Boolean).join('&') : ''

  useEffect(() => { (async () => {
    try {
      let s
      if (mode === 'daily') s = await post('/sessions/daily', { book_id: bid, chapter_id: chid })
      else if (mode === 'placement') s = await post('/sessions/placement', { chapter_id: placementChapterId })
      else if (resume) s = await get('/sessions/practice')
      else s = await startPractice()
      setSession(s)
      const nextIdx = s.slots.findIndex(sl => sl.status === 'pending')
      if (nextIdx === -1) { setFinished(true); return }
      setIndex(nextIdx); loadQuestion(nextIdx)
    } catch (e) { setError(e.message) }
  })() }, [])

  // keyboard shortcuts: 1-4 select, Enter submit/next
  useEffect(() => {
    const h = (e) => {
      const tag = e.target.tagName
      if (tag === 'TEXTAREA' || tag === 'INPUT') return
      if (lesson) {
        if (e.key === 'Enter') { e.preventDefault(); closeLesson() }
        return
      }
      const n = question?.options?.length || 0
      const k = Number(e.key)
      if (!feedback && k >= 1 && k <= n) setSelected(k)
      if (e.key === 'Enter') {
        // stop the focused button's own Enter-click: one Enter = one action
        e.preventDefault()
        if (feedback) next()
        else submit()
      }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [feedback, selected, question, index, lesson])

  function closeLesson() {
    setLesson(null)
    startTime.current = Date.now()   // reading the card is not answer time
  }

  function setFont(v) {
    const s = Math.min(1.5, Math.max(0.9, Math.round(v * 10) / 10))
    setFontScale(s); localStorage.setItem('font_scale', String(s))
  }

  async function startPractice() {
    const take = (k, dflt) => { const v = localStorage.getItem(k); localStorage.removeItem(k); return v ?? dflt }
    // read once and clear, so choices from one screen don't leak into the next practice
    const concepts = JSON.parse(take('practice_concepts', '[]'))
    const chapters = JSON.parse(take('practice_chapters', '[]'))
    const book = take('practice_book', null)
    const count = Number(take('practice_count', 10))
    const body = { count }
    if (concepts.length) body.concept_ids = concepts
    if (chapters.length) body.chapter_ids = chapters
    if (book) { body.book_ids = [book]; body.concept_ids = []; body.chapter_ids = [] }
    await post('/sessions/practice', body)
    return get('/sessions/practice')
  }

  async function loadQuestion(i) {
    setSelected(null); setFeedback(null); setReportSent(false); setQuestion(null); setWrittenSolution(null)
    try {
      const q = await get(`${base}/question/${i}${qs}`)
      setQuestion(q)
      setLesson(q.key_point || null)
      startTime.current = Date.now()   // time the question, not the network
    } catch (e) { setError(e.message) }
  }

  async function showWrittenSolution() {
    try {
      const r = await get(`/sessions/${mode}/solution/${index}${qs}`)
      setWrittenSolution(r.solution_md)
    } catch (e) { setError(e.message) }
  }

  async function submit(option = selected) {
    if (option === null || busy.current || feedback) return
    setNotice(null)
    busy.current = true
    const timeMs = Date.now() - startTime.current
    try {
      const fb = await post(`${base}/answer/${index}${qs}`, {
        selected_option: option,
        time_ms: timeMs,
      })
      setSelected(option)
      setFeedback({ ...fb, time_s: Math.round(timeMs / 1000), dontKnow: option === 0 })
    } catch (e) { setNotice({ msg: e.message, retry: () => submit(option) }) }
    finally { busy.current = false }
  }

  async function next() {
    if (busy.current) return
    setNotice(null)
    busy.current = true
    try {
      const s = await get(`${base}${qs}`)
      setSession(s)       // keep the last answer in the summary
      let nextIdx = s.slots.findIndex((sl, i) => i > index && sl.status === 'pending')
      if (nextIdx === -1) nextIdx = s.slots.findIndex(sl => sl.status === 'pending')
      if (nextIdx === -1) { setFinished(true); return }
      setIndex(nextIdx); loadQuestion(nextIdx)
    } catch (e) { setNotice({ msg: e.message, retry: next }) }
    finally { busy.current = false }
  }

  function exit() {
    if (finished || window.confirm('از جلسه خارج می‌شوی؟ پاسخ‌های ثبت‌شده حفظ می‌شوند.')) onExit()
  }

  async function reportQuestion() {
    const note = prompt('مشکل سؤال را بنویسید (مثلاً «گزینه ۲ باید ۳ باشد»):')
    if (!note) return
    try {
      await post(`/sessions/questions/${question.question_id}/report`, { note })
      setReportSent(true)
    } catch (e) { setError(e.message) }
  }

  useEffect(() => {
    if (finished && mode === 'daily') get('/auth/me/progress').then(pr => setTomorrow(pr.due_tomorrow)).catch(() => {})
  }, [finished])

  if (error) return (
    <div className="center-screen"><div className="card">
      <p className="error" role="alert">{error}</p>
      {index !== null && !question && <button className="primary" onClick={() => { setError(''); loadQuestion(index) }}>دوباره امتحان کن</button>}
      <button onClick={onExit}>بازگشت</button>
    </div></div>
  )
  if (finished) {
    const answered = (session?.slots || []).filter(s => s.status === 'answered')
    const correct = answered.filter(s => s.correct).length
    const pct = answered.length ? Math.round(100 * correct / answered.length) : 0
    const placedLearned = answered.filter(s => s.placed === 'learned').length
    const placedLearning = answered.filter(s => s.placed === 'learning').length
    return (
      <div className="center-screen">
        <div className="card summary">
          <Mascot mood={pct >= 60 ? 'happy' : 'cheer'} size={72} />
          <h2>{TITLES[mode]}</h2>
          {mode === 'placement' && answered.length > 0 && (
            <p>
              {placedLearned > 0 && <>{fa(placedLearned)} نکته را بلد بودی و یک هفتهٔ دیگر فقط مرورشان می‌کنی. </>}
              {placedLearning > 0 && <>{fa(placedLearning)} نکته را نسبتاً بلد بودی؛ سه روز دیگر یک بار دیگر می‌بینی‌شان. </>}
              {answered.length - placedLearned - placedLearning > 0 &&
                <>{fa(answered.length - placedLearned - placedLearning)} نکته را از اول با درس‌نامهٔ کوتاه یاد می‌گیری.</>}
            </p>
          )}
          {answered.length
            ? <p className="big">{fa(correct)} از {fa(answered.length)} درست · ٪{fa(pct)}</p>
            : <p className="muted">امروز سؤالی برای مرور نداری. فردا برمی‌گردیم.</p>}
          <div className="result-strip">
            {answered.map((s, i) => <span key={i} className={s.correct ? 'dot ok' : 'dot no'} />)}
          </div>
          {mode === 'daily' && tomorrow !== null && (
            <p className="muted">{tomorrow > 0 ? `فردا ${fa(tomorrow)} نکته برای مرور داری.` : 'فردا فقط نکته‌های تازه داری.'}</p>
          )}
          <button className="primary" onClick={onExit}>خب، تمام</button>
        </div>
      </div>
    )
  }
  if (!session || index === null || !question) return <div className="center-screen"><div className="spinner" /></div>

  const total = session.total ?? session.slots.length
  const done = feedback?.done ?? session.slots.filter(s => s.status === 'answered').length
  const correctText = feedback?.correct_option != null ? question.options?.[feedback.correct_option - 1] : null
  const written = question.type === 'tashrihi'
  const optFigs = question.option_figures?.some(Boolean) ? question.option_figures : null
  const due = relativeDue(feedback?.next_due)

  return (
    <div className="session">
      <div className="session-header">
        <span className="counter">{fa(done)} از {fa(total)} پاسخ داده شده</span>
        <span className="font-controls">
          <button className="ghost" aria-label="کوچک‌تر کردن متن" onClick={() => setFont(fontScale - 0.1)}>A−</button>
          <button className="ghost" aria-label="بزرگ‌تر کردن متن" onClick={() => setFont(fontScale + 0.1)}>A+</button>
        </span>
        <button className="ghost" aria-label="خروج از جلسه" onClick={exit}><Icon name="close" /></button>
      </div>
      {notice && (
        <div className="notice" role="alert">
          <span>{notice.msg}</span>
          <button onClick={notice.retry}>دوباره امتحان کن</button>
        </div>
      )}
      <div className="progress-bar" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done}>
        <div style={{ width: `${(done / Math.max(1, total)) * 100}%` }} />
      </div>

      {lesson && (
        <div className="question-box lesson-card" style={{ fontSize: `${fontScale}rem` }} aria-live="polite">
          <div className="lesson-head"><span className="lesson-tag"><Icon name="spark" size={16} /> نکتهٔ تازه</span><Mascot size={44} /></div>
          <h3>{lesson.title}</h3>
          <div className="stem"><Markdown text={lesson.text} /></div>
          <button className="primary wide" onClick={closeLesson}>
            فهمیدم، برو سراغ سؤال <span className="kbd-hint">(Enter)</span>
          </button>
        </div>
      )}

      {!lesson && <div className="question-box" style={{ fontSize: `${fontScale}rem` }}>
        {mode === 'placement' && !feedback && (
          <div className="repeat-banner">آزمون تعیین سطح: اگر بلدی جواب بده، اگر نه «نمی‌دانم» را بزن. اشتباه اینجا هیچ جریمه‌ای ندارد.</div>
        )}
        {question.repeat && <div className="repeat-banner">تکرار سؤال قبلی؛ فعلاً سؤال جدیدی برای این مبحث نداریم</div>}
        <div className="stem"><Markdown text={question.stem_md} /></div>
        {question.figures?.map((f, i) => <Figure key={f.url} fig={f} alt={`شکل ${fa(i + 1)} سؤال`} />)}
        {question.options && (
          <div className={`options ${optFigs ? 'options-figs' : ''}`} role="radiogroup" aria-label="گزینه‌ها">
            {question.options.map((opt, i) => (
              <div key={i} className="opt-cell">
              <button type="button" role="radio" aria-checked={selected === i + 1}
                   disabled={!!feedback}
                   className={`option ${selected === i + 1 ? 'selected' : ''} ${feedback && feedback.correct_option != null && i + 1 === feedback.correct_option ? 'correct' : ''} ${feedback && selected === i + 1 && feedback.correct_option !== i + 1 ? 'wrong' : ''}`}
                   onClick={() => !feedback && setSelected(i + 1)}>
                <span className="opt-num">{fa(i + 1)}</span>
                {optFigs?.[i] ? <FigureImage fig={optFigs[i]} alt={`شکل گزینهٔ ${fa(i + 1)}`} eager /> : <Markdown text={opt} />}
              </button>
              {optFigs?.[i] && (
                <button type="button" className="opt-zoom" aria-label={`بزرگ‌نمایی شکل گزینهٔ ${fa(i + 1)}`} onClick={() => setZoomed(optFigs[i])}>
                  <Icon name="zoom" size={18} />
                </button>
              )}
              </div>
            ))}
          </div>
        )}
        {zoomed && <Lightbox fig={zoomed} alt="شکل گزینه" onClose={() => setZoomed(null)} />}
        {!feedback && written && (
          // written question: solve on paper, compare with the solution, grade yourself
          <div className="answer-actions">
            {!writtenSolution ? (
              <>
                <p className="muted">روی کاغذ حل کن، بعد پاسخ را ببین و خودت بگو درست بود یا نه.</p>
                <button className="primary wide" onClick={showWrittenSolution}>دیدن پاسخ</button>
              </>
            ) : (
              <>
                <div className="solution open-solution"><Markdown text={writtenSolution} /></div>
                <p className="muted">با حل خودت مقایسه کن. صادق باش؛ برنامهٔ مرور بر همین اساس تنظیم می‌شود.</p>
                <div className="self-grade">
                  <button className="primary" onClick={() => submit(true)}>درست حل کرده بودم</button>
                  <button className="danger" onClick={() => submit(false)}>اشتباه یا ناقص بود</button>
                </div>
              </>
            )}
          </div>
        )}
        {!feedback && !written && (
          <div className="answer-actions">
            <button className="primary wide" disabled={selected === null} onClick={() => submit()}>
              ثبت پاسخ <span className="kbd-hint">(Enter)</span>
            </button>
            <button className="ghost wide" onClick={() => submit(0)}>نمی‌دانم، حل را نشانم بده</button>
          </div>
        )}

        {feedback && (
          <div className="feedback" aria-live="polite">
            <div className={`feedback-banner ${feedback.correct ? 'ok' : 'no'}`}>
              {feedback.correct ? 'درست بود' : feedback.dontKnow ? 'اشکالی ندارد، حل را ببین' : 'اشتباه بود'}
              <span className="muted"> · {fa(feedback.time_s)} ثانیه</span>
            </div>
            {feedback.correct_option != null && (
              <div className="correct-answer">
                پاسخ درست: گزینهٔ {fa(feedback.correct_option)}
                {correctText && <>: <Markdown text={correctText} /></>}
              </div>
            )}
            {due && <p className="due"><Icon name="clock" size={18} /> مرور بعدی این مبحث: {due}</p>}
            {feedback.correct && feedback.schedule_changed === false && (
              <p className="muted">این مرور زودتر از موعد بود؛ برای جلو رفتن در برنامه باید در روز موعدش هم درست جواب بدهی.</p>
            )}
            {feedback.remediation && <p className="due"><Icon name="retry" size={18} /> امروز در پایان جلسه یک سؤال دیگر از همین مبحث می‌بینی.</p>}
            {feedback.placed === 'learned' && <p className="due"><Icon name="check" size={18} /> این نکته را بلدی؛ از برنامه جلو افتاد و یک هفتهٔ دیگر مرور می‌شود.</p>}
            {feedback.placed === 'learning' && <p className="due"><Icon name="check" size={18} /> درست بود؛ سه روز دیگر یک بار دیگر می‌بینی‌اش.</p>}
            {feedback.key_point && (
              <div className="key-point-box">
                <b>نکتهٔ این سؤال: {feedback.key_point.title}</b>
                <Markdown text={feedback.key_point.text} />
              </div>
            )}
            {feedback.solution_md && (
              // after a miss the solution IS the lesson: open it by default
              <details className="solution" open={!feedback.correct}>
                <summary>{feedback.correct ? 'نمایش حل' : 'حل سؤال'}</summary>
                <Markdown text={feedback.solution_md} />
              </details>
            )}
            <p className="muted">
              <button type="button" className="link" onClick={reportQuestion} disabled={reportSent}>
                {reportSent ? 'گزارش ثبت شد' : 'گزارش خطا در سؤال'}
              </button>
            </p>
            <button className="primary wide" onClick={next}>بعدی <span className="kbd-hint">(Enter)</span></button>
          </div>
        )}
        <div className="kbd-help muted">کلیدهای ۱–۴ برای انتخاب گزینه · Enter برای تأیید/بعدی</div>
      </div>}
    </div>
  )
}
