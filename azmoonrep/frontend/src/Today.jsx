import React, { useEffect, useState } from 'react'
import { post } from './api'
import { fa, jalali, daysUntil } from './ui'
import Mascot from './Mascot'

const WEEKDAY_FA = ['د', 'س', 'چ', 'پ', 'ج', 'ش', 'ی']   // Python weekday(): Monday = 0

// design/DESIGN.md: one hero number, one green button. Everything else is quiet.
export default function Today({ user, onStartSession, onOpenPath }) {
  const [plan, setPlan] = useState(null)
  const [error, setError] = useState('')
  const load = () => { setError(''); post('/sessions/daily', {}).then(setPlan).catch(e => setError(e.message)) }
  useEffect(load, [])

  const toExam = daysUntil(user.exam_date)
  const top = (
    <header className="pk-top">
      <span>{new Date().toLocaleDateString('fa-IR', { weekday: 'long', day: 'numeric', month: 'long' })}</span>
      <span className="who">
        {plan?.streak_days >= 2 && <span className="pk-streak num" title="روزهای پیاپی با تمرین">{fa(plan.streak_days)} روز پیاپی</span>}
        {toExam !== null && toExam >= 0 && <span className="num">{fa(toExam)} روز تا آزمون</span>}
        {toExam === null && <a className="pk-examlink" href="#/settings">تاریخ آزمون را بگذار</a>}
        <a className="pk-avatar" href="#/settings" aria-label="تنظیمات">{(user.display_name || '؟').slice(0, 1)}</a>
      </span>
    </header>
  )
  if (error) return <div className="pk">{top}<p className="error" role="alert">{error}</p><button onClick={load}>دوباره امتحان کن</button></div>
  if (!plan) return <div className="pk">{top}<div className="card skeleton" style={{ height: 280, marginTop: 28 }} /></div>

  const pending = plan.slots.filter(s => s.status === 'pending').length
  const finished = plan.total > 0 && pending === 0
  const missed = new Set(plan.slots.filter(s => s.missed_yesterday).map(s => s.concept_id)).size
  const seen = new Set()
  const items = plan.slots.filter(s => !seen.has(s.concept_id) && seen.add(s.concept_id))
  const f = plan.focus

  return (
    <div className="pk">
      {top}
      <section className="pk-hero" aria-labelledby="today-title">
        {plan.total === 0 ? (
          <>
            <div className="pk-hero-row"><h1 id="today-title" className="pk-unit" style={{ fontSize: 28 }}>امروز مروری نداری</h1><Mascot /></div>
            <p className="pk-meta">نکتهٔ موعددار یا تازه‌ای نیست. از «مسیر» یک فصل را تعیین سطح کن یا آزاد تمرین کن.</p>
            <button className="primary pk-cta" onClick={onOpenPath}>رفتن به مسیر</button>
          </>
        ) : finished ? (
          <>
            <div className="pk-hero-row"><div><span className="pk-big num">{fa(plan.total)}</span></div><Mascot mood="happy" /></div>
            <h1 id="today-title" className="pk-unit">سؤال امروز را تمام کردی</h1>
            <p className="pk-meta">فردا نکته‌های موعددار برمی‌گردند.</p>
            <button className="primary pk-cta" onClick={onOpenPath}>دیدن مسیر</button>
          </>
        ) : (
          <>
            <div className="pk-hero-row"><span className="pk-big num">{fa(pending)}</span><Mascot /></div>
            <h1 id="today-title" className="pk-unit">سؤال امروز</h1>
            <p className="pk-meta">حدود {fa(plan.est_minutes)} دقیقه · {fa(plan.review_count + plan.remediation_count)} مرور، {fa(plan.new_count)} نکتهٔ تازه</p>
            {missed > 0 && <p className="pk-accent">{fa(missed)} نکته را دیروز اشتباه زدی؛ دوباره می‌آیند.</p>}
            <button className="primary pk-cta" onClick={onStartSession}>{plan.done > 0 ? 'ادامه' : 'شروع'}</button>
          </>
        )}
      </section>

      {items.length > 0 && (
        <details className="pk-more">
          <summary>نکته‌های امروز ({fa(items.length)})</summary>
          <ul>
            {items.map(s => (
              <li key={s.concept_id}>
                <span className={`dot3 ${s.missed_yesterday ? 'wrong' : s.kind === 'new' ? '' : 'learning'}`} />
                <span>{s.concept_title}</span>
                {s.kind === 'new' && <span className="muted">تازه</span>}
              </li>
            ))}
          </ul>
        </details>
      )}

      <footer className="pk-foot">
        {f && <>
          <div>{f.chapter_title}: <span className="num">{fa(f.learned)} از {fa(f.total)}</span> نکته یاد گرفته شده</div>
          <div className="pk-bar" role="progressbar" aria-valuemin={0} aria-valuemax={f.total} aria-valuenow={f.learned}>
            <i style={{ width: `${f.total ? (f.learned / f.total) * 100 : 0}%` }} /></div>
        </>}
        {plan.week && (
          <ol className="pk-week" aria-label="هفتهٔ اخیر">
            {plan.week.map(d => (
              <li key={d.date} className={`${d.answered ? 'on' : ''} ${d.today ? 'today' : ''}`}
                  title={`${jalali(d.date)}: ${fa(d.answered)} سؤال`}>{WEEKDAY_FA[d.weekday]}</li>
            ))}
          </ol>
        )}
      </footer>
    </div>
  )
}
