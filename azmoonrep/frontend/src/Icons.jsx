import React from 'react'

// «قله» icon set. 24 grid, 2.2 stroke, round caps; the line takes the text colour and
// every icon has exactly ONE solid accent shape (the flag-on-the-peak motif).
// Directional icons (arrow, next) get class "ico-dir" and are mirrored in RTL by CSS.
const A = 'var(--primary)'
const P = {
  today: <><path d="M2.5 20.5 9.5 8.5l3.6 5.6 2.2-3.2 6.2 9.6z" /><path d="M9.5 8.5V3" /><path d="M9.5 3h5.2l-1.6 1.9 1.6 1.9H9.5z" fill={A} stroke={A} /></>,
  path: <><path d="M6 20.5c0-4.5 12-2.5 12-7.5S7.5 10.5 7.5 6" strokeDasharray="0.1 4.2" /><circle cx="6" cy="20.5" r="1.7" fill="currentColor" stroke="none" /><path d="M7.5 6V2.5" /><path d="M7.5 2.5h4.6l-1.4 1.6 1.4 1.6H7.5z" fill={A} stroke={A} /></>,
  check: <path d="M5 12.8l4.4 4.4L19 7.4" stroke={A} strokeWidth="3" />,
  cross: <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" strokeWidth="2.8" />,
  clock: <><circle cx="12" cy="12" r="8.8" /><path d="M12 7.2V12l3.2 2" /><circle cx="12" cy="12" r="1.5" fill={A} stroke="none" /></>,
  streak: <><path d="M3 20.5 7.5 13l2.5 3.5L13 11l2.5 4 2-3 3.5 8.5z" /><circle cx="18" cy="5.5" r="2.6" fill={A} stroke="none" /></>,
  arrow: <><path d="M19 12H6" /><path d="M11 6.5 5.5 12l5.5 5.5" /></>,
  next: <path d="M14.5 6 8.5 12l6 6" />,
  sliders: <><path d="M4 8h16M4 16h16" /><circle cx="9" cy="8" r="2.6" fill={A} stroke={A} /><circle cx="15" cy="16" r="2.6" fill="var(--card)" /></>,
  spark: <><path d="M12 3.2l2 6.2 6.2 2.6-6.2 2.6-2 6.2-2-6.2L3.8 12 10 9.4z" fill={A} stroke={A} /></>,
  retry: <><path d="M5 12.5a7 7 0 1 0 2.3-5.2" /><path d="M4.5 4v4.3h4.3" /><circle cx="12" cy="12.5" r="1.5" fill={A} stroke="none" /></>,
  flag: <><path d="M6 21V4" /><path d="M6 5h11l-2.6 3.4L17 11.8H6z" fill={A} stroke={A} /></>,
  book: <><path d="M5 5.6A2.6 2.6 0 0 1 7.6 3H19v15H7.6A2.6 2.6 0 0 0 5 20.6z" /><path d="M5 20.6A2.6 2.6 0 0 0 7.6 21H19" /><path d="M9 8h6" stroke={A} strokeWidth="2.6" /></>,
  user: <><circle cx="12" cy="8.5" r="3.6" /><path d="M4.8 20.5c1-4 3.9-5.6 7.2-5.6s6.2 1.6 7.2 5.6" /><circle cx="12" cy="8.5" r="1.3" fill={A} stroke="none" /></>,
  target: <><circle cx="12" cy="12" r="8.8" /><circle cx="12" cy="12" r="4.6" /><circle cx="12" cy="12" r="1.7" fill={A} stroke="none" /></>,
  pencil: <><path d="M4 20l1.2-4.6L16.4 4.2l3.4 3.4L8.6 18.8z" /><path d="M4 20l4.6-1.2-3.4-3.4z" fill={A} stroke={A} /></>,
  close: <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" />,
  zoom: <><circle cx="10.5" cy="10.5" r="6.3" /><path d="M15.2 15.2 20 20" /><path d="M10.5 8v5M8 10.5h5" stroke={A} strokeWidth="2.4" /></>,
  phone: <><rect x="7" y="2.8" width="10" height="18.4" rx="2.4" /><circle cx="12" cy="17.6" r="1.3" fill={A} stroke="none" /></>,
  notebook: <><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M9 3v18" /><path d="M12.5 8.5l1.6 1.6 3-3.2" stroke={A} strokeWidth="2.4" /></>,
}

export const ICON_NAMES = Object.keys(P)
const DIRECTIONAL = new Set(['arrow', 'next'])

export default function Icon({ name, size = 24, className = '', title }) {
  return (
    <svg className={`ico ${DIRECTIONAL.has(name) ? 'ico-dir' : ''} ${className}`} width={size} height={size}
         viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
         strokeLinecap="round" strokeLinejoin="round"
         role={title ? 'img' : undefined} aria-label={title} aria-hidden={title ? undefined : true}>
      {P[name]}
    </svg>
  )
}
