import React, { useEffect, useRef, useState } from 'react'
import { jalali } from './ui'

// Jalali date picker. Value in/out is a Gregorian ISO string (YYYY-MM-DD), so the API is unchanged.
// All calendar maths goes through Intl (persian calendar); no conversion tables of our own.

const PARTS = new Intl.DateTimeFormat('en-u-ca-persian-nu-latn', { year: 'numeric', month: 'numeric', day: 'numeric' })
const MONTH_YEAR = new Intl.DateTimeFormat('fa-IR-u-ca-persian', { month: 'long', year: 'numeric' })
const WEEKDAYS = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج']   // Saturday first

const toJ = (d) => {
  const p = Object.fromEntries(PARTS.formatToParts(d).map(x => [x.type, x.value]))
  return { y: Number(p.relatedYear || p.year), m: Number(p.month), d: Number(p.day) }
}
const noon = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate(), 12)
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x }
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const fromIso = (s) => new Date(`${s.slice(0, 10)}T12:00:00`)
const firstOfMonth = (d) => addDays(d, 1 - toJ(d).d)
const nextMonth = (d) => firstOfMonth(addDays(firstOfMonth(d), 32))
const prevMonth = (d) => firstOfMonth(addDays(firstOfMonth(d), -1))
const faNum = (n) => n.toLocaleString('fa-IR')

export default function JalaliDate({ id, value, onChange, label }) {
  const [open, setOpen] = useState(false)
  const [view, setView] = useState(() => firstOfMonth(value ? fromIso(value) : noon(new Date())))
  const box = useRef(null)

  useEffect(() => {
    if (!open) return
    const away = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false) }
    const esc = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', away)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', away); document.removeEventListener('keydown', esc) }
  }, [open])

  const days = []
  for (let d = view, m = toJ(view).m; toJ(d).m === m; d = addDays(d, 1)) days.push(d)
  const lead = (view.getDay() + 1) % 7
  const today = iso(noon(new Date()))

  function pick(d) { onChange(iso(d)); setOpen(false) }

  return (
    <div className="jd" ref={box}>
      <button type="button" id={id} className="jd-field" aria-haspopup="dialog" aria-expanded={open}
              onClick={() => { setView(firstOfMonth(value ? fromIso(value) : noon(new Date()))); setOpen(o => !o) }}>
        {value ? jalali(value, { day: 'numeric', month: 'long', year: 'numeric' }) : <span className="muted">انتخاب تاریخ</span>}
      </button>
      {open && (
        <div className="jd-pop" role="dialog" aria-label={label || 'انتخاب تاریخ'}>
          <div className="jd-head">
            <button type="button" className="ghost" aria-label="ماه بعد" onClick={() => setView(nextMonth(view))}>‹</button>
            <b>{MONTH_YEAR.format(view)}</b>
            <button type="button" className="ghost" aria-label="ماه قبل" onClick={() => setView(prevMonth(view))}>›</button>
          </div>
          <div className="jd-grid">
            {WEEKDAYS.map(w => <span key={w} className="jd-wd">{w}</span>)}
            {Array.from({ length: lead }, (_, i) => <span key={`b${i}`} />)}
            {days.map(d => {
              const k = iso(d)
              return (
                <button key={k} type="button" className={`jd-day ${k === value ? 'on' : ''} ${k === today ? 'today' : ''}`}
                        aria-pressed={k === value} onClick={() => pick(d)}>{faNum(toJ(d).d)}</button>
              )
            })}
          </div>
          <div className="jd-foot">
            <button type="button" className="ghost" onClick={() => { onChange(''); setOpen(false) }}>پاک کردن</button>
            <button type="button" className="ghost" onClick={() => pick(noon(new Date()))}>امروز</button>
          </div>
        </div>
      )}
    </div>
  )
}
