import React, { useEffect, useState } from 'react'
import 'katex/dist/katex.min.css'
import './styles.css'
import { get, getToken, clearToken } from './api'
import Start from './Start'
import Today from './Today'
import Path from './Path'
import Session from './Session'
import Settings from './Settings'
import Admin from './Admin'
import Onboarding from './Onboarding'
import Icon, { ICON_NAMES } from './Icons'
import Mascot from './Mascot'

// Tiny hash router: #/today  #/path  #/settings  #/plan  #/kit
function useHashRoute() {
  const read = () => (window.location.hash.replace(/^#\/?/, '') || 'today').split('/')
  const [route, setRoute] = useState(read)
  useEffect(() => {
    const on = () => setRoute(read())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return [route, (path) => { window.location.hash = '#/' + path }]
}

const NAV = [['today', 'امروز'], ['path', 'مسیر']]   // two destinations (design/DESIGN.md)

function Kit() {   // icon and mascot sheet, for design review
  return (
    <div className="pk">
      <h1 className="page-title">آیکون‌ها و ماسکوت</h1>
      <p className="pk-meta">هر آیکون یک جزء توپر سبز دارد. پیکان و «بعدی» در راست‌به‌چپ آینه می‌شوند.</p>
      <div className="kit" style={{ marginTop: 16 }}>{ICON_NAMES.map(n => <div key={n}><Icon name={n} size={30} /><br />{n}</div>)}</div>
      <div style={{ display: 'flex', gap: 24, marginTop: 24 }}><Mascot /><Mascot mood="happy" /><Mascot mood="cheer" /></div>
    </div>
  )
}

export default function App() {
  const [user, setUser] = useState(getToken() ? 'loading' : null)
  const [profile, setProfile] = useState(null)
  const [route, go] = useHashRoute()
  const [session, setSession] = useState(null)   // {mode, resume, placementChapterId}
  const view = route[0]

  const refreshProfile = () => get('/auth/me').then(p => { setProfile(p); return p })
  useEffect(() => {
    if (user === 'loading') refreshProfile().then(p => setUser(p)).catch(() => { clearToken(); setUser(null) })
  }, [user])

  // the browser Back button leaves a running session (answers are already saved)
  useEffect(() => {
    if (!session) return
    window.history.pushState({ session: true }, '')
    const onPop = () => setSession(null)
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [session])

  if (view === 'kit') return <Kit />
  if (user === 'loading') return <div className="center-screen"><div className="spinner" /></div>
  if (!user) return <Start onLoggedIn={async (res) => { await refreshProfile(); setUser(res); go('today') }} />

  const logout = () => {
    if (!window.confirm('از حساب خارج می‌شوی؟')) return
    clearToken(); setUser(null); setProfile(null); setSession(null); go('today')
  }
  if (profile.role === 'admin') return <div><Admin /><button className="logout" onClick={logout}>خروج</button></div>

  const endSession = () => {
    setSession(null)
    if (window.history.state?.session) window.history.back()
  }
  // accounts made without the start flow (username sign-up): pick books once
  if (!profile.onboarded && !session) {
    return <Onboarding onDone={async () => { await refreshProfile(); go('today') }} />
  }
  if (session) {
    return <Session key={JSON.stringify(session)} mode={session.mode} resume={!!session.resume}
      placementChapterId={session.placementChapterId || null} onExit={endSession} />
  }

  const navView = view === 'path' ? 'path' : view === 'today' ? 'today' : null
  return (
    <>
      <main>
        {view === 'path' ? <Path
            onPlacement={(chapterId) => setSession({ mode: 'placement', placementChapterId: chapterId })}
            onPractice={() => setSession({ mode: 'practice' })}
            onStartWrong={() => setSession({ mode: 'practice', resume: true })}
            onEditPlan={() => go('plan')} />
          : view === 'settings' ? <Settings user={profile} onSaved={refreshProfile} onEditPlan={() => go('plan')} onLogout={logout} />
          : view === 'plan' ? <Onboarding edit initialChapters={profile.scope_chapter_ids || []}
              initialBooks={profile.scope_book_ids || []}
              onDone={async () => { await refreshProfile(); go('path') }} />
          : <Today user={profile} onStartSession={() => setSession({ mode: 'daily' })} onOpenPath={() => go('path')} />}
      </main>
      <nav className="bottom-nav" aria-label="بخش‌های اصلی">
        {NAV.map(([id, label]) => (
          <a key={id} href={'#/' + id} className={navView === id ? 'nav-item active' : 'nav-item'}
             aria-current={navView === id ? 'page' : undefined}><Icon name={id} size={20} />{label}</a>
        ))}
      </nav>
    </>
  )
}
