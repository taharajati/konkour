import React, { useEffect, useState } from 'react'
import { get } from './api'

// round book selector: cover thumbnail + current book name + chevron. Same look in
// «امروز» and «مسیر»; tapping it opens the book-switching side menu.
export default function BookPill({ bookId, onClick }) {
  const [book, setBook] = useState(null)

  useEffect(() => {
    get('/me/books').then(bs => {
      setBook(bs.find(b => b.book_id === bookId) || bs[0] || null)
    }).catch(() => {})
  }, [bookId])

  return (
    <button className="pk-book-pill" onClick={onClick} aria-haspopup="dialog" aria-label="تغییر کتاب">
      {book && <img src={book.cover} alt="" loading="lazy" onError={e => { e.currentTarget.style.visibility = 'hidden' }} />}
      <span>{book?.name || 'انتخاب کتاب'}</span>
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M6 9l6 6 6-6" /></svg>
    </button>
  )
}
