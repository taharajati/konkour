import React, { useEffect, useState } from 'react'
import { get, post } from './api'
import { fa } from './ui'
import Icon from './Icons'
import BookPill from './BookPill'

const DOT = { learned: 'learned', review: 'learning', wrong: 'wrong', new: '' }

// «مسیر»: every chapter of the plan on one line. One action per chapter:
// placement test if nothing is started, otherwise practise that chapter.
export default function Path({ bookId, onOpenBookMenu, onPlacement, onPractice, onStartWrong, onEditPlan }) {
  const [books, setBooks] = useState(null)
  const [wrong, setWrong] = useState(0)
  const [error, setError] = useState('')

  const load = () => {
    setError('')
    Promise.all([get('/me/books'), get('/auth/me/stats')]).then(async ([bs, st]) => {
      // مسیر is per book: show only the book selected in the side menu (fall back to all)
      const mine = bookId && bs.some(b => b.book_id === bookId) ? bs.filter(b => b.book_id === bookId) : bs
      setWrong(st.wrong_count || 0)
      const chapters = await Promise.all(mine.map(b => get(`/curriculum/books/${encodeURIComponent(b.book_id)}/chapters`)))
      setBooks(mine.map((b, i) => ({ ...b, chapters: chapters[i] })))
    }).catch(e => setError(e.message))
  }
  useEffect(load, [bookId])

  function practise(ch) {
    localStorage.setItem('practice_chapters', JSON.stringify([ch.chapter_id]))
    localStorage.removeItem('practice_concepts')
    localStorage.setItem('practice_count', '10')
    onPractice()
  }
  async function startWrong() {
    try { await post('/sessions/practice', { wrong_only: true, count: 10 }); onStartWrong() }
    catch (e) { setError(e.message) }
  }

  if (error) return <div className="pk"><p className="error" role="alert">{error}</p><button onClick={load}>دوباره امتحان کن</button></div>
  if (!books) return <div className="pk"><div className="card skeleton" style={{ height: 260, marginTop: 20 }} /></div>

  return (
    <div className="pk">
      <header className="pk-top"><BookPill bookId={bookId} onClick={onOpenBookMenu} />
        <button className="link-btn" onClick={onEditPlan}>تغییر کتاب‌ها</button></header>

      {!books.length && <p className="pk-meta">هنوز کتابی در برنامه‌ات نیست. «تغییر کتاب‌ها» را بزن.</p>}
      {books.map(b => (
        <section key={b.book_id}>
          {books.length > 1 && <h2 className="pt-book">{b.name}</h2>}
          <ol className="pt">
            {b.chapters.map(ch => {
              const learned = ch.counts.learned, started = ch.total - ch.counts.new
              const done = ch.total > 0 && learned === ch.total
              const canPlace = started === 0 && ch.placement_available > 1
              return (
                <li key={ch.chapter_id}>
                  <span className={`pt-node ${done ? 'done' : started ? 'started' : ''}`}>{done ? <Icon name="check" size={18} /> : fa(ch.number)}</span>
                  <div className="pt-head"><b>{ch.title}</b>{ch.total > 0 && <span className="num">{fa(learned)} از {fa(ch.total)}</span>}</div>
                  {ch.total === 0 || (ch.placement_available === 0 && started === 0)
                    ? <p className="pt-soon">سؤال‌های این فصل هنوز آماده نیست.</p>
                    : <>
                      <div className="pk-bar"><i style={{ width: `${(learned / ch.total) * 100}%` }} /></div>
                      <div className="pt-actions">
                        {canPlace
                          ? <button className="primary" onClick={() => onPlacement(ch.chapter_id)}>تعیین سطح، {fa(ch.placement_available)} سؤال</button>
                          : <button onClick={() => practise(ch)}>تمرین این فصل</button>}
                      </div>
                      <details>
                        <summary>{fa(ch.total)} نکته</summary>
                        <ul>{ch.concepts.map(c => <li key={c.concept_id}><span className={`dot3 ${DOT[c.status]}`} />{c.title}</li>)}</ul>
                      </details>
                    </>}
                </li>
              )
            })}
          </ol>
        </section>
      ))}

      {wrong > 0 && (
        <section className="pk-more" style={{ paddingTop: 14 }}>
          <div className="pt-head"><b><Icon name="notebook" size={20} /> دفترچهٔ اشتباهات</b><span className="num">{fa(wrong)} سؤال</span></div>
          <div className="pt-actions" style={{ marginTop: 8 }}><button onClick={startWrong}>مرور اشتباه‌ها</button></div>
        </section>
      )}
    </div>
  )
}
