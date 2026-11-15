import React, { useEffect, useRef, useState } from 'react'
import Icon from './Icons'

// Figures are rendered from the PDF at 3x, so half their pixel width is a sharp
// on-screen size. The box is reserved from w/h before the image loads (no jumping).
const cssWidth = (fig) => fig?.w ? Math.max(120, Math.round(fig.w / 2)) : undefined

export function FigureImage({ fig, alt, eager = false }) {
  const [failed, setFailed] = useState(false)
  if (failed) return <span className="fig-failed">شکل بارگذاری نشد</span>
  return (
    <img src={fig.url} alt={alt} width={fig.w || undefined} height={fig.h || undefined}
         loading={eager ? 'eager' : 'lazy'} decoding="async" draggable={false}
         style={{ aspectRatio: fig.w && fig.h ? `${fig.w} / ${fig.h}` : undefined, width: cssWidth(fig) }}
         onError={() => setFailed(true)} />
  )
}

// A figure under the question text: white card (figures are black on white, also in
// dark mode), tap to open it large.
export default function Figure({ fig, alt = 'شکل سؤال', caption }) {
  const [open, setOpen] = useState(false)
  if (!fig) return null
  return (
    <figure className="fig">
      <button type="button" className="fig-btn" onClick={() => setOpen(true)} aria-label={`${alt}، بزرگ‌نمایی`}>
        <FigureImage fig={fig} alt={alt} eager />
        <span className="fig-zoom" aria-hidden="true"><Icon name="zoom" size={18} /></span>
      </button>
      {caption && <figcaption>{caption}</figcaption>}
      {open && <Lightbox fig={fig} alt={alt} onClose={() => setOpen(false)} />}
    </figure>
  )
}

export function Lightbox({ fig, alt, onClose }) {
  const [big, setBig] = useState(false)
  const closeRef = useRef(null)
  useEffect(() => {
    const prev = document.activeElement
    closeRef.current?.focus()
    const onKey = (e) => { if (e.key === 'Escape') { e.stopPropagation(); onClose() } }
    window.addEventListener('keydown', onKey, true)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey, true)
      document.body.style.overflow = ''
      prev?.focus?.()
    }
  }, [])
  return (
    <div className="lightbox" role="dialog" aria-modal="true" aria-label={alt} onClick={onClose}>
      <button ref={closeRef} type="button" className="lightbox-close" onClick={onClose} aria-label="بستن"><Icon name="close" /></button>
      <div className={`lightbox-scroll ${big ? 'big' : ''}`} onClick={e => e.stopPropagation()}>
        <img src={fig.url} alt={alt} draggable={false} onClick={() => setBig(b => !b)}
             style={big && fig.w ? { width: fig.w, maxWidth: 'none' } : undefined} />
      </div>
      <p className="lightbox-hint">{big ? 'برای کوچک شدن روی شکل بزن' : 'برای بزرگ‌تر شدن روی شکل بزن'}</p>
    </div>
  )
}
