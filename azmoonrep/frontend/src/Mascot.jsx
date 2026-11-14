import React from 'react'

// «قله»: a small black mountain with eyes and a green flag.
// mood: idle | happy (flag up, smile, one short hop) | cheer (after a miss: soft smile)
export default function Mascot({ mood = 'idle', size = 64 }) {
  const mouth = mood === 'happy' ? 'M26 44q6 6 12 0' : mood === 'cheer' ? 'M27 45q5 2.5 10 0' : 'M28 45h8'
  return (
    <svg className={`mascot ${mood === 'happy' ? 'hop' : ''}`} width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <path d="M32 14V4" stroke="var(--text)" strokeWidth="2.4" strokeLinecap="round" />
      <path className="mascot-flag" d="M32 4h11l-3 3.5 3 3.5H32z" fill="var(--primary)" />
      <path d="M5 59 27.5 16.5q4.5-7 9 0L59 59z" fill="var(--text)" />
      <path d="M22.5 26l5-9.5q4.5-7 9 0l5 9.5-4.5 4-5-4.5-5 4.5z" fill="var(--card)" />
      <circle cx="25" cy="38" r="3.4" fill="var(--card)" /><circle cx="39" cy="38" r="3.4" fill="var(--card)" />
      <circle cx="25.8" cy="38.6" r="1.5" fill="var(--text)" /><circle cx="39.8" cy="38.6" r="1.5" fill="var(--text)" />
      <path d={mouth} stroke="var(--card)" strokeWidth="2.2" strokeLinecap="round" fill="none" />
    </svg>
  )
}
