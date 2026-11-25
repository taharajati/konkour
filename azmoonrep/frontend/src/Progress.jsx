import React, { useEffect, useState } from 'react'
import { get } from './api'
import { fa, pct, jalali } from './ui'
import Icon from './Icons'
import Mascot from './Mascot'

const WEEKDAY_FA = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج']   // Jalali week starts on Saturday

function level(n) { return n === 0 ? 0 : n < 6 ? 1 : n < 16 ? 2 : 3 }

// 35 days as rows of 7, Saturday first, so a column is always the same weekday
function Heatmap({ days }) {
  const first = new Date(days[0].date + 'T12:00:00').getDay()       // Sat = 6
  const pad = (first + 1) % 7
  const cells = [...Array(pad).fill(null), ...days]
  return (
    <div className="hm" role="img" aria-label="فعالیت ۵ هفتهٔ اخیر">
      {WEEKDAY_FA.map(w => <span key={w} className="hm-wd">{w}</span>)}
      {cells.map((d, i) => d
        ? <span key={d.date} className={`hm-c l${level(d.answered)}`}
                title={`${jalali(d.date)}: ${fa(d.answered)} سؤال`} />
        : <span key={'p' + i} />)}
    </div>
  )
}

// «پیشرفت»: where the student stands, what to fix, what comes tomorrow
export default function Progress({ bookId, onStartWrong, onPracticeConcepts }) {
  const [p, setP] = useState(null)
  const [wrong, setWrong] = useState(0)
  const [error, setError] = useState('')
  const [dangerous, setDangerous] = useState(null)
  const load = () => {
    setError('')
    // پیشرفت is per book: the backend narrows the key-point scope when book_id is given
    const q = bookId ? `?book_id=${encodeURIComponent(bookId)}` : ''
    Promise.all([get('/auth/me/progress' + q), get('/auth/me/stats'), get('/auth/me/dangerous')])
      .then(([pr, st, dg]) => { setP(pr); setWrong(st.wrong_count || 0); setDangerous(dg) })
      .catch(e => setError(e.message))
  }
  useEffect(load, [bookId])

  if (error) return <div className="pk"><p className="error" role="alert">{error}</p><button onClick={load}>دوباره امتحان کن</button></div>
  if (!p) return <div className="pk"><div className="card skeleton" style={{ height: 300, marginTop: 20 }} /></div>

  if (p.total_answered === 0) return (
    <div className="pk">
      <header className="pk-top"><h1 className="page-title" style={{ color: 'var(--text)' }}>پیشرفت</h1></header>
      <div className="empty">
        <Mascot size={84} />
        <h2>هنوز چیزی برای نشان دادن نیست</h2>
        <p className="pk-meta">بعد از اولین جلسه، اینجا می‌بینی چند نکته را یاد گرفته‌ای و کدام‌ها مرور می‌خواهند.</p>
        <a className="primary link-primary" href="#/today">برو سراغ جلسهٔ امروز</a>
      </div>
    </div>
  )

  const share = p.total ? (p.learned / p.total) * 100 : 0
  return (
    <div className="pk">
      <header className="pk-top"><h1 className="page-title" style={{ color: 'var(--text)' }}>پیشرفت</h1></header>

      <section className="pg-hero">
        <div><span className="pk-big num">{fa(p.learned)}</span><span className="pk-unit">از {fa(p.total)} نکته را یاد گرفته‌ای</span></div>
        <div className="pk-bar" role="progressbar" aria-valuemin={0} aria-valuemax={p.total} aria-valuenow={p.learned}>
          <i style={{ width: `${share}%` }} /></div>
        <p className="pk-meta">{fa(p.learning)} نکته در حال یادگیری · {fa(p.new)} نکتهٔ شروع‌نشده</p>
      </section>

      <section className="pg-stats">
        <div><b className="num">{fa(p.streak_days)}</b><span>روز پیاپی</span></div>
        <div><b className="num">{fa(p.best_streak)}</b><span>بهترین رشته</span></div>
        <div><b className="num">{pct(p.week_accuracy)}</b><span>درست این هفته</span></div>
        <div><b className="num">{fa(p.total_answered)}</b><span>سؤال تا امروز</span></div>
      </section>

      <section className="pg-block">
        <h2 className="section-title">فردا</h2>
        {p.due_tomorrow > 0
          ? <p><Icon name="clock" size={18} /> <b className="num">{fa(p.due_tomorrow)}</b> نکته برای مرور فردا داری.</p>
          : <p className="muted">فردا مروری در صف نیست؛ فقط نکته‌های تازه.</p>}
        {p.due_today > 0 && <p className="muted"><span className="num">{fa(p.due_today)}</span> مرور هم برای امروز مانده است.</p>}
      </section>

      <section className="pg-block">
        <h2 className="section-title">پنج هفتهٔ اخیر</h2>
        <Heatmap days={p.activity} />
        <p className="pk-meta">{fa(p.days_active)} روز تمرین کرده‌ای. هر خانه یک روز است؛ تیره‌تر یعنی سؤال بیشتر.</p>
      </section>

      {p.weak.length > 0 && (
        <section className="pg-block">
          <h2 className="section-title">نکته‌هایی که بیشتر اشتباه کرده‌ای</h2>
          <ul className="pg-weak">
            {p.weak.map(w => (
              <li key={w.concept_id}>
                <div><b>{w.title}</b><span className="muted">{w.chapter_title}</span></div>
                <span className="pg-lapse num">{fa(w.lapses)} بار</span>
              </li>
            ))}
          </ul>
          <p className="pk-meta">این‌ها را سیستم زودتر و بیشتر برایت می‌آورد؛ لازم نیست کاری بکنی.</p>
        </section>
      )}

      {dangerous && dangerous.length > 0 && (
        <section className="pg-block dangerous">
          <h2 className="section-title">خطرناک‌ترین نکته‌هایت ⚠️</h2>
          <p className="pk-meta">اینجا <b>مطمئن بودی</b> و اشتباه زدی — دقیقاً همین‌ها سر جلسه خطرناک‌اند و بیشترین ارزش مطالعه را دارند.</p>
          <ul className="pg-weak">
            {dangerous.map(d => (
              <li key={d.concept_id}>
                <div><b>{d.title}</b><span className="muted">{d.book_name ? d.book_name + ' · ' : ''}{d.chapter_title}</span></div>
                <div className="dg-side">
                  <span className="pg-lapse num">{fa(d.confident_wrong)} بار</span>
                  <button onClick={() => onPracticeConcepts([d.concept_id])}>تمرین</button>
                </div>
              </li>
            ))}
          </ul>
          <div className="pt-actions" style={{ marginTop: 8 }}>
            <button onClick={() => onPracticeConcepts(dangerous.map(d => d.concept_id))}>تمرین همهٔ این نکته‌ها</button>
          </div>
        </section>
      )}

      <section className="pg-block">
        <div className="pt-head"><b><Icon name="notebook" size={20} /> دفترچهٔ اشتباه‌ها</b><span className="num">{fa(wrong)} سؤال</span></div>
        <div className="pt-actions" style={{ marginTop: 8 }}>
          <a className="btn-link" href="#/mistakes">دیدن فهرست</a>
          {wrong > 0 && <button onClick={onStartWrong}>مرور اشتباه‌ها</button>}
        </div>
      </section>
    </div>
  )
}
