import React, { useEffect, useState } from 'react'
import { get } from './api'
import { fa } from './ui'

// side menu for switching books, opened from the book pill in the «امروز» header:
// the student's own books on top (with covers), every other book greyed out below.
export default function BookMenu({ open, activeBookId, onSelect, onClose }) {
  const [mine, setMine] = useState(null)      // books in the student's plan (from /me/books)
  const [all, setAll] = useState(null)        // every book in the catalog
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    Promise.all([get('/me/books'), get('/curriculum/book-cards')])
      .then(([mine, all]) => { setMine(mine); setAll(all) })
      .catch(e => setError(e.message))
  }, [open])

  if (!open) return null
  const mineIds = new Set((mine || []).map(b => b.book_id))
  const others = (all || []).filter(b => !mineIds.has(b.book_id))
  const active = (mine || []).find(b => b.book_id === activeBookId) || (all || []).find(b => b.book_id === activeBookId)

  const pick = (id) => { onSelect(id); onClose() }

  return (
    <>
      <div className="bm-overlay" onClick={onClose} />
      <aside className="bm" role="dialog" aria-label="انتخاب کتاب">
        <header className="bm-head">
          <b>کتاب‌ها</b>
          {active && <span className="bm-current">{active.name}</span>}
          <button className="link-btn" onClick={onClose}>بستن</button>
        </header>

        {error && <p className="error" role="alert">{error}</p>}
        {!mine && !error && <div className="spinner" style={{ margin: '24px auto' }} />}

        {mine && (
          <>
            <div className="bm-sec">کتاب‌های برنامهٔ تو</div>
            <div className="bm-list">
              {mine.map(b => (
                <button key={b.book_id} type="button"
                        className={`bm-book ${b.book_id === activeBookId ? 'on' : ''}`}
                        onClick={() => pick(b.book_id)}>
                  <img onError={e => { e.currentTarget.style.visibility = 'hidden' }} src={b.cover} alt="" loading="lazy" />
                  <span className="bm-book-name">{b.name}</span>
                  <span className="bm-book-meta num">{fa(b.today_questions)} سؤال امروز</span>
                </button>
              ))}
              {!mine.length && <p className="bm-empty">هنوز کتابی در برنامه‌ات نیست.</p>}
            </div>
          </>
        )}

        {others.length > 0 && (
          <>
            <div className="bm-sec">کتاب‌های دیگر</div>
            <div className="bm-list bm-others">
              {others.map(b => (
                <div key={b.book_id} className="bm-book off" title="برای افزودن، برنامهٔ مطالعه را ویرایش کن">
                  <img onError={e => { e.currentTarget.style.visibility = 'hidden' }} src={b.cover} alt="" loading="lazy" />
                  <span className="bm-book-name">{b.name}</span>
                </div>
              ))}
            </div>
            <p className="bm-hint">برای افزودن این کتاب‌ها، «برنامهٔ مطالعه» را در تنظیمات ویرایش کن.</p>
          </>
        )}
      </aside>
    </>
  )
}
