import React, { useEffect, useRef, useState } from 'react'
import { get, post, setToken } from './api'
import { fa, GRADE_FA } from './ui'
import Icon from './Icons'
import Mascot from './Mascot'
import Markdown from './Markdown'
import Login from './Login'

// The landing page IS the first question (design/DESIGN.md §3): give first, ask later.
// grade -> books (the student chooses) -> three questions from those books -> plan -> name -> username + password -> app.
const LOADS = [10, 20, 40]
const KEY = 'azmoon_trial'

// rotating hero headlines on the first page: same promise, different phrasing
const HEADLINES = ['سریع‌تر یاد بگیر، کمتر وقت بذار', 'هوشمندتر مطالعه کن', 'با صرف زمان کمتر نتیجه بهتری بگیر']
// social proof number shown under the grade cards — update as the real count grows
const STUDENTS_COUNT = 1200

function RotatingHeadline() {
  const [idx, setIdx] = useState(0)
  const [visible, setVisible] = useState(true)
  useEffect(() => {
    const t = setInterval(() => {
      setVisible(false)
      setTimeout(() => { setIdx(i => (i + 1) % HEADLINES.length); setVisible(true) }, 350)
    }, 3800)
    return () => clearInterval(t)
  }, [])
  return <h2 className={`st-headline ${visible ? 'in' : ''}`}>{HEADLINES[idx]}</h2>
}
const load = () => { try { return JSON.parse(sessionStorage.getItem(KEY) || 'null') } catch { return null } }

export default function Start({ onLoggedIn }) {
  const saved = useRef(load()).current
  const [trial, setTrial] = useState(saved?.trial || null)     // {token, grade, questions}
  const [answers, setAnswers] = useState(saved?.answers || []) // display option per question
  const [results, setResults] = useState(saved?.results || []) // true/false per question
  const [step, setStep] = useState(saved?.step || 'grade')       // grade|books|loading|q|result|name|account|login
  const [catalog, setCatalog] = useState(null)                  // [{grade, books:[...]}]
  const [chosen, setChosen] = useState(saved?.chosen || [])     // book ids
  const [selected, setSelected] = useState(null)
  const [feedback, setFeedback] = useState(null)
  const [grade, setGrade] = useState(saved?.grade || null)
  const [daily, setDaily] = useState(saved?.daily || 20)
  const [name, setName] = useState(saved?.name || '')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const i = answers.length - (feedback ? 1 : 0)

  useEffect(() => { get('/curriculum/catalog').then(c => setCatalog(c.grades)).catch(() => setCatalog([])) }, [])
  useEffect(() => {
    if (step === 'loading' || step === 'login') return
    sessionStorage.setItem(KEY, JSON.stringify({ trial, answers, results, step: feedback ? 'q' : step, grade, chosen, daily, name }))
  }, [trial, answers, results, step, grade, chosen, daily, name, feedback])

  const gradeBooks = (catalog || []).find(g => g.grade === grade)?.books || []
  const chosenBooks = gradeBooks.filter(b => chosen.includes(b.book_id))
  const toggle = (id) => setChosen(c => c.includes(id) ? c.filter(x => x !== id) : [...c, id])
  function startTrial() {
    setStep('loading'); setTrial(null); setAnswers([]); setResults([])
    post('/trial/start', { grade, book_ids: chosen })
      .then(t => { setTrial(t); setStep('q') })
      .catch(() => setStep('result'))             // these books have no approved questions yet: straight to the plan
  }

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
  const signup = (e) => { e.preventDefault(); run(async () => {
    await post('/auth/register', { username: username.trim(), password, grade: Number(grade), display_name: name.trim() })
    const r = await post('/auth/login', { username: username.trim(), password })
    setToken(r.access_token)
    await post('/trial/claim', { token: trial?.token || null, answers, grade: Number(grade), book_ids: chosen,
                                 daily_load: daily, display_name: name })
    sessionStorage.removeItem(KEY)
    onLoggedIn(r)
  }) }

  if (step === 'login') return <Login onLoggedIn={onLoggedIn} onBack={() => setStep(trial ? (answers.length >= 3 ? 'result' : 'q') : 'result')} />

  const menu = (
    <nav className="st-menu" aria-label="منو">
      <a href="#" className={step === 'about' ? '' : 'on'} onClick={e => { e.preventDefault(); setStep('grade') }}>خانه</a>
      <a href="#" className={step === 'about' ? 'on' : ''} onClick={e => { e.preventDefault(); setStep('about') }}>درباره ریپ</a>
    </nav>
  )

  const top = (
    <header className="st-top">
      <span className="st-brand"><Icon name="today" /> آزمون‌ریپ</span>
      {menu}
      <button className="link-btn" onClick={() => setStep('login')}>حساب دارم</button>
    </header>
  )

  if (step === 'about') return (
    <div className="st st-about">
      {top}
      <h1>دربارهٔ آزمون‌ریپ</h1>
      <p className="st-sub">
        آزمون‌ریپ یک سیستم مرور هوشمند برای ریاضی کنکور است. به‌جای این‌که همه‌چیز را بارها مرور کنی،
        ریپ فقط همان نکته‌هایی را سراغت می‌آورد که یادت رفته — هر بار با یک سؤال تازه، نه همان سؤال قبلی.
        کمتر وقت می‌گذاری، بیشتر یاد می‌گیری.
      </p>

      <div className="about-media">
        <div className="about-video" role="img" aria-label="ویدیوی معرفی محصول">
          <span className="about-video-play">▶</span>
          <span>ویدیوی معرفی — به‌زودی</span>
        </div>
        <div className="about-video" role="img" aria-label="ویدیوی آموزش کار با برنامه">
          <span className="about-video-play">▶</span>
          <span>آموزش کار با برنامه — به‌زودی</span>
        </div>
      </div>

      <h3 className="about-h3">ریپ چطور کار می‌کند؟</h3>
      <div className="about-steps">
        <div className="about-step"><span>۱</span><div><b>پایه و کتاب‌ها را انتخاب می‌کنی</b><p>از کتاب‌های رسمی وزارت آموزش‌وپرورش، از ریاضی نهم تا ریاضیات گسستهٔ دوازدهم.</p></div></div>
        <div className="about-step"><span>۲</span><div><b>هر روز چند سؤال جواب می‌دهی</b><p>هر سؤال یک نکتهٔ مشخص را می‌سنجد. اشتباهاتت دوباره برمی‌گردند، چیزی که بلدی کنار می‌رود.</p></div></div>
        <div className="about-step"><span>۳</span><div><b>ریپ زمان مرور را خودش حساب می‌کند</b><p>هر نکته دقیقاً وقتی سراغت می‌آید که در آستانهٔ فراموشی‌اش هستی — همان جایی که مرور بیشترین اثر را دارد.</p></div></div>
      </div>

      <h3 className="about-h3">از زبان دانش‌آموزها</h3>
      <div className="about-quotes">
        <div className="about-quote">
          <p>«قبلاً فکر می‌کردم بلدم، تا وقتی همین سؤال‌ها با عدد جدید توی آزمون آمد و زدم امتحان. الان هر اشتباهم می‌شود یک مرور برای فردا.»</p>
          <span>— امیرحسین، یازدهم ریاضی‌فیزیک</span>
        </div>
        <div className="about-quote">
          <p>«دیگر لازم نیست کل فصل را برای مرور بخوانم؛ روزی چند دقیقه، همان‌هایی که یادم می‌رفت تمرین می‌شوند.»</p>
          <span>— مینا، دهم ریاضی</span>
        </div>
        <div className="about-quote">
          <p>«نکته‌هایی که بلد بودم کنار رفتند و وقت‌م آزاد شد برای درس‌هایی که واقعاً سخت بودند.»</p>
          <span>— محمدرضا، دوازدهم کنکوری</span>
        </div>
      </div>

      <h3 className="about-h3">تصاویر از داخل برنامه</h3>
      <div className="about-media">
        <div className="about-img" role="img" aria-label="تصویر صفحهٔ جلسهٔ روزانه">📸 صفحهٔ جلسهٔ روزانه — به‌زودی</div>
        <div className="about-img" role="img" aria-label="تصویر نمودار پیشرفت">📸 نمودار پیشرفت — به‌زودی</div>
      </div>

      <button className="primary pk-cta" onClick={() => setStep('grade')}>شروع کن — پایه‌ات را انتخاب کن</button>
      <button type="button" className="link-btn" onClick={() => setStep('grade')}><Icon name="arrow" size={16} className="back" /> برگشت</button>
    </div>
  )
  if (step === 'grade') return (
    <div className="st">
      {top}
      <RotatingHeadline />
      <h1>کدام پایه؟</h1>
      <p className="st-sub">پایهٔ درسی خود را انتخاب کنید.</p>
      <div className="st-choices" role="radiogroup" aria-label="پایه">
        {[9, 10, 11, 12].map(g => {
          const bs = (catalog || []).find(x => x.grade === g)?.books || []
          const ready = bs.reduce((n, b) => n + b.ready_key_points, 0)
          return (
            <button key={g} type="button" role="radio" aria-checked={grade === g} className={`st-choice ${grade === g ? 'on' : ''}`}
                    disabled={!bs.length} onClick={() => { setGrade(g); setChosen([]); setStep('books') }}>
              <b>{GRADE_FA[g]}</b>
              <span>{bs.length ? `${fa(bs.length)} کتاب${ready ? '' : ' · به‌زودی'}` : '—'}</span>
            </button>)
        })}
      </div>
      <p className="st-social-proof">
        تا امروز بیش از <b className="num">{fa(STUDENTS_COUNT)}</b> دانش‌آموز با استفاده از ریپ نتایج بهتری گرفته‌اند.
      </p>
    </div>
  )

  if (step === 'books') return (
    <div className="st">
      {top}
      <h1>کدام کتاب‌ها؟</h1>
      <p className="st-sub">پایهٔ {GRADE_FA[grade]}. هر چند کتاب که می‌خواهی را انتخاب کن؛ بعداً هم از تنظیمات عوضش می‌کنی.</p>
      <div className="st-choices st-books">
        {gradeBooks.map(b => (
          <button key={b.book_id} type="button" role="checkbox" aria-checked={chosen.includes(b.book_id)}
                  className={`st-choice ${chosen.includes(b.book_id) ? 'on' : ''}`} onClick={() => toggle(b.book_id)}>
            <b>{b.name}</b>
            <span>{b.field ? `${b.field} · ` : ''}{fa(b.chapters)} فصل</span>
            <span className={b.ready_key_points ? 'ok-text' : 'muted'}>
              {b.ready_key_points ? `${fa(b.ready_key_points)} از ${fa(b.key_points)} نکته سؤال دارد` : 'سؤال‌ها در حال آماده‌سازی'}
            </span>
          </button>
        ))}
      </div>
      <button className="primary pk-cta" disabled={!chosen.length} onClick={startTrial}>ادامه</button>
      <button type="button" className="link-btn" onClick={() => setStep('grade')}><Icon name="arrow" size={16} className="back" /> پایهٔ دیگر</button>
    </div>
  )

  if (step === 'loading') return <div className="st">{top}<div className="card skeleton" style={{ height: 300, marginTop: 30 }} /></div>

  if (step === 'q') {
    const q = trial.questions[i]
    const first = i === 0 && !feedback
    return (
      <div className="st">
        {top}
        {first
          ? <><h1>هر نکته را با کمترین تست یاد بگیر.</h1><p className="st-sub">سه سؤال از {chosenBooks.map(b => b.name).join(' و ')}. ثبت‌نام لازم نیست.</p></>
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
      ) : <><h1>برنامه‌ات آماده است</h1><p className="st-sub">سؤال‌های {chosenBooks.map(b => b.name).join(' و ')} هنوز در حال بازبینی است. ثبت‌نام کن؛ هر نکته‌ای که سؤالش تأیید شود، به برنامه‌ات اضافه می‌شود.</p></>}
      <div className="st-plan">
        <div className="row"><span>پایه</span><span>{GRADE_FA[grade]} <button type="button" className="link-btn" onClick={() => setStep('grade')}>تغییر</button></span></div>
        <div className="row"><span>هر روز</span>
          <div>
            <div className="segmented" role="radiogroup" aria-label="حجم روزانه">
              {LOADS.map(n => <button key={n} type="button" role="radio" aria-checked={daily === n} className={daily === n ? 'on' : ''} onClick={() => setDaily(n)}>{fa(n)} سؤال</button>)}
            </div>
            <p className="row-hint">بعداً می‌توانید با برنامهٔ درسی خود هماهنگ کنید.</p>
          </div></div>
        <div className="row"><span>کتاب‌ها</span><span>{chosenBooks.map(b => b.name).join('، ')} <button type="button" className="link-btn" onClick={() => setStep('books')}>تغییر</button></span></div>
      </div>
      <button className="primary pk-cta" onClick={() => setStep('name')}>همین خوب است</button>
    </div>
  )

  if (step === 'name') return (
    <form className="st" onSubmit={e => { e.preventDefault(); if (name.trim()) setStep('account') }}>
      {top}
      <h1>اسمت چیست؟</h1>
      <label htmlFor="st-name" className="st-sub">فقط برای اینکه بدانیم چه صدایت کنیم.</label>
      <input id="st-name" className="st-field" autoFocus autoComplete="given-name" maxLength={40} value={name} onChange={e => setName(e.target.value)} />
      <button className="primary pk-cta" disabled={!name.trim()}>ادامه</button>
    </form>
  )

  return (
    <form className="st" onSubmit={signup}>
      {top}
      <h1>{name.trim()}، برنامه‌ات را کجا نگه داریم؟</h1>
      <label htmlFor="st-user" className="st-sub">یک نام کاربری و رمز انتخاب کن تا برنامه و جواب‌هایت گم نشود.</label>
      <input id="st-user" className="st-field" dir="ltr" autoComplete="username" autoCapitalize="none" autoFocus
             placeholder="نام کاربری (انگلیسی)" value={username} onChange={e => setUsername(e.target.value)} />
      <input id="st-pass" className="st-field" dir="ltr" type="password" autoComplete="new-password"
             placeholder="رمز عبور (دست‌کم ۸ کاراکتر)" value={password} onChange={e => setPassword(e.target.value)} />
      {error && <p className="error" role="alert">{error}</p>}
      <button className="primary pk-cta" disabled={busy || !username.trim() || password.length < 8}>ذخیرهٔ برنامه</button>
      <button type="button" className="link-btn" onClick={() => { setStep('name'); setError('') }}><Icon name="arrow" size={16} className="back" /> برگشت</button>
    </form>
  )
}
