// tiny WebAudio chimes — no asset files, works offline, unlocked by the click that plays them
let ctx = null
function ac() {
  if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)()
  if (ctx.state === 'suspended') ctx.resume()
  return ctx
}
function note(t, freq, dur, type = 'sine', gain = 0.18) {
  const a = ac()
  const o = a.createOscillator(), g = a.createGain()
  o.type = type; o.frequency.value = freq
  g.gain.setValueAtTime(0, a.currentTime + t)
  g.gain.linearRampToValueAtTime(gain, a.currentTime + t + 0.015)
  g.gain.exponentialRampToValueAtTime(0.0001, a.currentTime + t + dur)
  o.connect(g).connect(a.destination)
  o.start(a.currentTime + t); o.stop(a.currentTime + t + dur + 0.05)
}

// bright rising pair, Duolingo-ish «correct»
export function playCorrect() {
  try { note(0, 659.3, 0.18); note(0.09, 987.8, 0.32, 'sine', 0.2) } catch { /* audio unavailable */ }
}
// soft low pair, never harsh
export function playWrong() {
  try { note(0, 220, 0.2, 'triangle', 0.14); note(0.1, 164.8, 0.3, 'triangle', 0.12) } catch { /* audio unavailable */ }
}
// little fanfare for the session summary
export function playFinish() {
  try { note(0, 523.3, 0.15); note(0.1, 659.3, 0.15); note(0.2, 784, 0.4, 'sine', 0.2) } catch { /* audio unavailable */ }
}
