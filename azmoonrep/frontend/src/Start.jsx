import React, { useEffect, useRef, useState } from 'react'
import { post, setToken } from './api'
import { fa, GRADE_FA } from './ui'
import Icon from './Icons'
import Mascot from './Mascot'
import Markdown from './Markdown'
import Login from './Login'

// The landing page IS the first question (design/DESIGN.md §3): give first, ask later.
// q (three questions) -> result + prefilled plan -> name -> phone -> code -> app.
const LOADS = [10, 20, 40]
const KEY = 'azmoon_trial'
const load = () => { try { return JSON.parse(sessionStorage.getItem(KEY) || 'null') } catch { return null } }

export default function Start({ onLoggedIn }) {
  const saved = useRef(load()).current
  const [trial, setTrial] = useState(saved?.trial || null)     // {token, grade, questions}
  const [answers, setAnswers] = useState(saved?.answers || []) // display option per question
  const [results, setResults] = useState(saved?.results || []) // true/false per question
  const [step, setStep] = useState(saved?.step || 'loading')   // loading|q|result|name|phone|code|login
  const [selected, setSelected] = useState(null)
  const [feedback, setFeedback] = useState(null)
  const [grade, setGrade] = useState(saved?.grade || 9)
  const [daily, setDaily] = useState(saved?.daily || 20)
  const [name, setName] = useState(saved?.name || '')
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [wait, setWait] = useState(0)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const i = answers.length - (feedback ? 1 : 0)

  useEffect(() => {
    if (saved?.trial) return
    post('/trial/start', {}).then(t => { setTrial(t); setGrade(t.grade || 9); setStep('q') })
      .catch(() => setStep('result'))          // no approved questions yet: go straight to the plan
  }, [])
  useEffect(() => {
    if (step === 'loading' || step === 'login') return
    sessionStorage.setItem(KEY, JSON.stringify({ trial, answers, results, step: feedback ? 'q' : step, grade, daily, name }))
  }, [trial, answers, results, step, grade, daily, name, feedback])
  useEffect(() => {
    if (wait <= 0) return
    const t = setTimeout(() => setWait(w => w - 1), 1000)
    return () => clearTimeout(t)
  }, [wait])

  async function run(fn) {
    if (busy) return
    setBusy(true); setError('')
    try { await fn() } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const answer = (opt) => run(async () => {
    const fb = await post('/trial/answer', { token: trial.token, index: answers.length, selected_option: opt })
    setSelected(opt); setFeedback(fb)
    setAnswers(a => [...a, opt]); setResults(r => [...r, fb.correct])
  })
  function next() {
    setFeedback(null); setSelected(null)
    if (answers.length >= trial.questions.length) setStep('result')
  }
  const sendCode = (e) => { e?.preventDefault(); run(async () => {
    const r = await post('/auth/otp/request', { phone })
    setPhone(r.phone); setCode(''); setWait(60); setStep('code')
  }) }
  const verify = (e) => { e.preventDefault(); run(async () => {
    const r = await post('/auth/otp/verify', { phone, code })
    setToken(r.access_token)
    await post('/trial/claim', { token: trial?.token || null, answers, grade: Number(grade),
                                 daily_load: daily, display_name: name })
    sessionStorage.removeItem(KEY)
    onLoggedIn(r)
  }) }

  if (step === 'login') return <Login onLoggedIn={onLoggedIn} onBack={() => setStep(trial ? (answers.length >= 3 ? 'result' : 'q') : 'result')} />

  const top = (
    <header className="st-top">
      <span className="st-brand"><Icon name="today" /> آزمون‌ریپ</span>
      <button className="link-btn" onClick={() => setStep('login')}>حساب دارم</button>
    </header>
  )
  if (step === 'loading') return <div className="st">{top}<div className="card skeleton" style={{ height: 300, marginTop: 30 }} /></div>

  if (step === 'q') {
    const q = trial.questions[i]
    const first = i === 0 && !feedback
    return (
      <div className="st">
        {top}
        {first
          ? <><h1>هر نکته را با کمترین تست یاد بگیر.</h1><p className="st-sub">با همین سؤال شروع کن؛ ثبت‌نام لازم نیست.</p></>
          : <p className="st-sub" style={{ marginTop: 22 }}>سؤال {fa(i + 1)} از {fa(trial.questions.length)}</p>}
        <div className="st-steps" aria-hidden="true">{trial.questions.map((_, k) => <i key={k} className={k < answers.length ? 'on' : ''} />)}</div>
        <div className="question-box">
          <div className="stem"><Markdown text={q.stem_md} /></div>
          <div className="options" role="radiogroup" aria-label="گزینه‌ها">
            {q.options.map((o, k) => (
              <button key={k} type="button" role="radio" aria-checked={selected === k + 1} disabled={!!feedback || busy}
                      className={`option ${feedback && k + 1 === feedback.correct_option ? 'correct' : ''} ${feedback && selected === k + 1 && !feedback.correct ? 'wrong' : ''}`}
                      onClick={() => answer(k + 1)}>
                <span className="opt-num">{fa(k + 1)}</span><Markdown text={o} />
              </button>
            ))}
          </div>
          {!feedback && <button className="link-btn" disabled={busy} onClick={() => answer(0)}>نمی‌دانم</button>}
          {feedback && (
            <div className="feedback" aria-live="polite">
              <div className={`feedback-banner ${feedback.correct ? 'ok' : 'no'}`}>{feedback.correct ? 'درست بود' : 'این یکی را با هم یاد می‌گیریم'}</div>
              {feedback.key_point && <div className="key-point-box"><b>نکته: {feedback.key_point.title}</b><Markdown text={feedback.key_point.text} /></div>}
              <button className="primary pk-cta" onClick={next}>{answers.length >= trial.questions.length ? 'نتیجه را ببین' : 'بعدی'}</button>
            </div>
          )}
          {error && <p className="error" role="alert">{error}</p>}
        </div>
        {first && (
          <div className="st-how">
            <span><Icon name="spark" size={18} /> هر اشتباه، همان نکته را با سؤال دیگری برمی‌گرداند.</span>
            <span><Icon name="target" size={18} /> نکته‌هایی که بلدی کنار می‌روند.</span>
          </div>
        )}
      </div>
    )
  }

  const known = results.filter(Boolean).length
  if (step === 'result') return (
    <div className="st">
      {top}
      {trial && results.length > 0 ? (
        <>
          <div className="st-score"><Mascot mood={known ? 'happy' : 'cheer'} size={72} />
            <div><span className="pk-big num">{fa(known)}</span><span className="pk-unit">از {fa(results.length)} نکته را بلدی</span></div></div>
          <p className="st-sub" style={{ marginTop: 10 }}>{known === results.length ? 'این‌ها را فقط مرور می‌کنی.' : 'بقیه را با درس‌نامهٔ کوتاه و سؤال‌های تازه یاد می‌گیری.'}</p>
        </>
      ) : <><h1>هر نکته را با کمترین تست یاد بگیر.</h1><p className="st-sub">برنامه‌ات آماده است؛ اگر خواستی عوضش کن.</p></>}
      <div className="st-plan">
        <div className="row"><span>پایه</span>
          <select aria-label="پایه" value={grade} onChange={e => setGrade(e.target.value)}>
            {[9, 10, 11, 12].map(g => <option key={g} value={g}>{GRADE_FA[g]}</option>)}
          </select></div>
        <div className="row"><span>هر روز</span>
          <div className="segmented" role="radiogroup" aria-label="حجم روزانه">
            {LOADS.map(n => <button key={n} type="button" role="radio" aria-checked={daily === n} className={daily === n ? 'on' : ''} onClick={() => setDaily(n)}>{fa(n)} سؤال</button>)}
          </div></div>
        <div className="row"><span>کتاب‌ها</span><span className="muted">ریاضی پایهٔ {GRADE_FA[grade]}، فصل‌هایی که سؤال دارند</span></div>
      </div>
      <button className="primary pk-cta" onClick={() => setStep('name')}>همین خوب است</button>
    </div>
  )

  if (step === 'name') return (
    <form className="st" onSubmit={e => { e.preventDefault(); if (name.trim()) setStep('phone') }}>
      {top}
      <h1>اسمت چیست؟</h1>
      <label htmlFor="st-name" className="st-sub">فقط برای اینکه بدانیم چه صدایت کنیم.</label>
      <input id="st-name" className="st-field" autoFocus autoComplete="given-name" maxLength={40} value={name} onChange={e => setName(e.target.value)} />
      <button className="primary pk-cta" disabled={!name.trim()}>ادامه</button>
    </form>
  )

  if (step === 'phone') return (
    <form className="st" onSubmit={sendCode}>
      {top}
      <h1>{name.trim()}، برنامه‌ات را کجا نگه داریم؟</h1>
      <label htmlFor="st-phone" className="st-sub">شمارهٔ موبایلت را بده تا برنامه و جواب‌هایت گم نشود. یک کد برایت می‌فرستیم.</label>
      <input id="st-phone" className="st-field" dir="ltr" inputMode="tel" autoComplete="tel" autoFocus placeholder="09121234567" value={phone} onChange={e => setPhone(e.target.value)} />
      {error && <p className="error" role="alert">{error}</p>}
      <button className="primary pk-cta" disabled={busy || !phone.trim()}>ارسال کد</button>
      <button type="button" className="link-btn" onClick={() => setStep('name')}><Icon name="arrow" size={16} className="back" /> برگشت</button>
    </form>
  )

  return (
    <form className="st" onSubmit={verify}>
      {top}
      <h1>کد را وارد کن</h1>
      <label htmlFor="st-code" className="st-sub">کد ۵ رقمی به <span dir="ltr">{phone}</span> پیامک شد.</label>
      <input id="st-code" className="st-field otp-input" dir="ltr" inputMode="numeric" autoComplete="one-time-code" autoFocus maxLength={8} value={code} onChange={e => setCode(e.target.value)} />
      {error && <p className="error" role="alert">{error}</p>}
      <button className="primary pk-cta" disabled={busy || code.trim().length < 5}>ذخیرهٔ برنامه</button>
      <div className="login-links">
        <button type="button" className="link-btn" disabled={wait > 0 || busy} onClick={sendCode}>{wait > 0 ? `ارسال دوباره تا ${fa(wait)} ثانیهٔ دیگر` : 'ارسال دوبارهٔ کد'}</button>
        <button type="button" className="link-btn" onClick={() => { setStep('phone'); setError('') }}>تغییر شماره</button>
      </div>
    </form>
  )
}
