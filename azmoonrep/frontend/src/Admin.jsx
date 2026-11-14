import React, { useEffect, useState } from 'react'
import { get, post, patch, getBlobUrl } from './api'
import Markdown from './Markdown'

const TABS = [["questions", "مرور سؤالات"], ["coverage", "پوشش نکته‌ها"], ["reports", "گزارش خطاها"], ["import", "وارد کردن"], ["stats", "آمار"]]
const VERIFY_LABEL = {
  verified: ['کلید و حل مستقل یکی‌اند', 'ok'],
  conflict: ['کلید با حل مستقل فرق دارد', 'bad'],
  solver_only: ['کلید چاپی نبود؛ پاسخ از حل مستقل', 'warn'],
  needs_fix: ['متن یا گزینه‌ها مشکل دارد', 'bad'],
  written: ['سؤال تشریحی', ''],
}
const MIN_APPROVED = 5   // a key point needs this many approved questions for real variety
const FILTERS = [["all", "همه"], ["pending", "در انتظار"], ["approved", "تأیید شده"], ["rejected", "رد شده"], ["flagged", "مشکوک"]]

export default function Admin() {
  const [tab, setTab] = useState('questions')
  return (
    <div className="page admin-page">
      <header className="topbar"><b>پنل مدیر</b></header>
      <div className="tabs">
        {TABS.map(([id, label]) => (
          <button key={id} className={`pill ${tab === id ? 'active' : ''}`} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>
      {tab === 'import' && <ImportTab />}
      {tab === 'questions' && <QuestionsTab />}
      {tab === 'coverage' && <CoverageTab />}
      {tab === 'reports' && <ReportsTab />}
      {tab === 'stats' && <StatsTab />}
    </div>
  )
}

function ImportTab() {
  const [booksPath, setBooksPath] = useState('D:/beh/main books/books_catalog.json')
  const [taxonomyPath, setTaxonomyPath] = useState('D:/beh/taxonomy')
  const [questionsPath, setQuestionsPath] = useState('D:/beh/question_bank')
  const [log, setLog] = useState('')
  async function runImport() {
    setLog('در حال وارد کردن…')
    try {
      const res = await post('/admin/import', { books_json: booksPath, taxonomy_dir: taxonomyPath, questions_root: questionsPath })
      setLog(JSON.stringify(res, null, 2))
    } catch (e) { setLog(e.message) }
  }
  return (
    <div className="card">
      <h3>وارد کردن محتوا</h3>
      <label>مسیر books_catalog.json</label>
      <input dir="ltr" value={booksPath} onChange={e => setBooksPath(e.target.value)} />
      <label>پوشهٔ فهرست نکته‌ها (taxonomy)</label>
      <input dir="ltr" value={taxonomyPath} onChange={e => setTaxonomyPath(e.target.value)} />
      <label>مسیر ریشهٔ سوالات آماده</label>
      <input dir="ltr" value={questionsPath} onChange={e => setQuestionsPath(e.target.value)} />
      <button className="primary" onClick={runImport}>اجرا</button>
      {log && <pre className="log">{log}</pre>}
    </div>
  )
}

function QuestionsTab() {
  const [status, setStatus] = useState('pending')
  const [search, setSearch] = useState('')
  const [searchQ, setSearchQ] = useState('')
  const [chapter, setChapter] = useState('')
  const [sort, setSort] = useState('created')
  const [skip, setSkip] = useState(0)
  const [data, setData] = useState(null)
  const [openId, setOpenId] = useState(null)
  const [sel, setSel] = useState({})
  const [bulkNote, setBulkNote] = useState('')
  const [bulkRejecting, setBulkRejecting] = useState(false)
  const [dupes, setDupes] = useState(null)

  useEffect(() => {
    setData(null); setSel({})
    const p = new URLSearchParams({ status, sort, skip, limit: 50 })
    if (searchQ) p.set('search', searchQ)
    if (chapter) p.set('chapter_id', chapter)
    get(`/admin/questions?${p}`).then(setData).catch(e => setData({ error: e.message }))
  }, [status, searchQ, chapter, sort, skip])

  const selIds = Object.keys(sel).filter(k => sel[k])

  async function bulkReview(approved) {
    try {
      await post('/admin/questions/bulk-review', { public_ids: selIds, approved, note: bulkNote })
      setSel({}); setBulkNote(''); setBulkRejecting(false)
      const p = new URLSearchParams({ status, sort, skip, limit: 50 })
      if (searchQ) p.set('search', searchQ)
      if (chapter) p.set('chapter_id', chapter)
      get(`/admin/questions?${p}`).then(setData)
    } catch (e) { alert(e.message) }
  }

  return (
    <>
      {status === 'pending' && data && !data.error && (
        <div className="card review-hero">
          <div><span className="pk-big num" style={{ fontSize: 64 }}>{Number(data.total).toLocaleString('fa-IR')}</span>
            <span className="pk-unit">سؤال در انتظار بازبینی</span></div>
          <button className="primary" disabled={!data.items.length}
                  onClick={() => setOpenId(data.items[0].public_id)}>شروع بازبینی</button>
        </div>
      )}
      <div className="card search-bar">
        <input dir="ltr" placeholder="جستجو در متن سؤال، مبحث یا شناسه…" value={search}
               onChange={e => setSearch(e.target.value)}
               onKeyDown={e => e.key === 'Enter' && (setSkip(0), setSearchQ(search))} />
        <button onClick={() => { setSkip(0); setSearchQ(search) }}>جستجو</button>
        <select value={sort} onChange={e => { setSkip(0); setSort(e.target.value) }}>
          <option value="created">جدیدترین</option>
          <option value="difficulty">دشواری</option>
        </select>
        <button onClick={async () => {
          setDupes(await get('/admin/questions/duplicates'))
        }}>یافتن سؤالات تکراری</button>
      </div>
      <div className="chip-row">
        {FILTERS.map(([id, label]) => (
          <button key={id} className={`chip ${status === id ? 'chip-on' : ''}`} onClick={() => { setSkip(0); setStatus(id) }}>
            {label}
          </button>
        ))}
        <select className="chapter-filter" value={chapter} onChange={e => { setSkip(0); setChapter(e.target.value) }}>
          <option value="">همهٔ فصل‌ها</option>
          <option value="__none">بدون فصل</option>
          {[...new Set((data?.items || []).map(i => i.chapter_id).filter(Boolean))].map(cid => (
            <option key={cid} value={cid}>{cid}</option>
          ))}
        </select>
      </div>

      {selIds.length > 0 && (
        <div className="card bulk-bar">
          <b>{selIds.length}</b> انتخاب شده
          <button className="primary" onClick={() => bulkReview(true)}>تأیید گروهی ✓</button>
          <button className="danger" onClick={() => setBulkRejecting(true)}>رد گروهی ✕</button>
          {bulkRejecting && (
            <>
              <textarea className="note-input" dir="rtl" rows={2} placeholder="یادداشت رد شدن (برای هوش مصنوعی)"
                        value={bulkNote} onChange={e => setBulkNote(e.target.value)} />
              <button className="danger" disabled={!bulkNote.trim()} onClick={() => bulkReview(false)}>ثبت رد گروهی</button>
            </>
          )}
        </div>
      )}

      {!data ? <div className="center-screen"><div className="spinner" /></div> : data.error
        ? <div className="card"><p className="error">{data.error}</p></div>
        : <div className="card">
            <p className="muted">{data.total} سؤال {data.total > 50 ? `(نمایش ${skip + 1}–${skip + data.items.length})` : ''}</p>
            <div className="qlist">
              {data.items.map(q => (
                <div key={q.public_id} className="qrow">
                  <input type="checkbox" checked={!!sel[q.public_id]}
                         onChange={() => setSel(s => ({ ...s, [q.public_id]: !s[q.public_id] }))}
                         onClick={e => e.stopPropagation()} aria-label={`انتخاب ${q.public_id}`} />
                  <span className={`rstatus ${q.review_status}`} title={{ approved: 'تأییدشده', rejected: 'ردشده', pending: 'در انتظار' }[q.review_status]}>
                    {{ approved: '✓', rejected: '✕', pending: '…' }[q.review_status]}
                  </span>
                  <span className="qrow-title" onClick={() => setOpenId(q.public_id)}>{q.topic} — {q.subtopic}</span>
                  {q.needs_answer_verification && <span className="badge warn">مشک‌دار</span>}
                  {q.outlier && <span className="badge warn">پرت</span>}
                  {q.served > 0 && <span className="badge">{q.served} پاسخ · {Math.round((q.correct_rate || 0) * 100)}٪</span>}
                  {q.figures?.length > 0 && <span className="badge">شکل</span>}
                  <span className="badge">{q.public_id}</span>
                </div>
              ))}
              {!data.items.length && <p className="muted">موردی نیست.</p>}
            </div>
            {data.total > 50 && (
              <div className="pager">
                <button disabled={skip === 0} onClick={() => setSkip(Math.max(0, skip - 50))}>قبلی</button>
                <span className="muted">صفحهٔ {Math.floor(skip / 50) + 1} از {Math.ceil(data.total / 50)}</span>
                <button disabled={skip + 50 >= data.total} onClick={() => setSkip(skip + 50)}>بعدی</button>
              </div>
            )}
          </div>}

      {dupes && (
        <div className="modal-back" onClick={() => setDupes(null)}>
          <div className="card modal" onClick={e => e.stopPropagation()}>
            <div className="modal-head"><b>سؤالات احتمالاً تکراری ({dupes.groups.length} گروه)</b>
              <button className="ghost" onClick={() => setDupes(null)}>✕</button></div>
            {!dupes.groups.length && <p className="muted">تکراری پیدا نشد ✓</p>}
            {dupes.groups.map((g, i) => (
              <div key={i} className="report-row">
                <p className="muted">{g.concept_id}</p>
                <div className="review-actions">
                  {g.public_ids.map(pid => <a key={pid} className="link badge" href="#" onClick={e => { e.preventDefault(); setOpenId(pid); setDupes(null) }}>{pid}</a>)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {openId && <QuestionDetail key={openId} publicId={openId} onClose={() => setOpenId(null)} onReviewed={() => {
        // review is a session: after each decision the next pending question opens
        const reviewed = openId
        const p = new URLSearchParams({ status, sort, skip, limit: 50 })
        if (searchQ) p.set('search', searchQ)
        if (chapter) p.set('chapter_id', chapter)
        get(`/admin/questions?${p}`).then(d => {
          setData(d)
          const next = d.items.find(it => it.review_status === 'pending' && it.public_id !== reviewed)
          setOpenId(next ? next.public_id : null)
        }).catch(() => setOpenId(null))
      }} />}
    </>
  )
}

function ScanImage({ path }) {
  const [url, setUrl] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => {
    let u = null
    getBlobUrl(path).then(x => { u = x; setUrl(x) }).catch(e => setErr(e.message))
    return () => { if (u) URL.revokeObjectURL(u) }
  }, [path])
  if (err) return <p className="muted">{err}</p>
  if (!url) return <div className="spinner" />
  return <img className="figure source-img" src={url} alt="اسکن سؤال" />
}

function QuestionDetail({ publicId, onClose, onReviewed }) {
  const [q, setQ] = useState(null)
  const [note, setNote] = useState('')
  const [rejecting, setRejecting] = useState(false)
  const [error, setError] = useState('')
  // the scan is open by default: review = compare the transcription with the source
  const [showSource, setShowSource] = useState(true)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(null)
  const [saved, setSaved] = useState('')
  const [concepts, setConcepts] = useState(null)

  useEffect(() => { get(`/admin/questions/${publicId}`).then(setQ).catch(e => setError(e.message)) }, [publicId])

  async function review(approved) {
    try {
      await post(`/admin/questions/${publicId}/review`, { approved, note })
      onReviewed()
    } catch (e) { setError(e.message) }
  }

  async function saveEdit() {
    try {
      const body = {
        stem_md: draft.stem_md,
        options: draft.options,
        answer_option: draft.answer_option,
        solution_md: draft.solution_md,
        difficulty: Number(draft.difficulty),
      }
      if (draft.concept_id && draft.concept_id !== q.concept_id) body.concept_id = draft.concept_id
      await patch(`/admin/questions/${publicId}`, body)
      setQ(await get(`/admin/questions/${publicId}`))
      setEditing(false); setSaved('ذخیره شد ✓')
    } catch (e) { setError(e.message) }
  }

  function startEdit() {
    setDraft({ stem_md: q.stem_md, options: q.options || [], answer_option: q.answer?.option,
               solution_md: q.solution_md, difficulty: q.difficulty, concept_id: q.concept_id || '' })
    setEditing(true); setSaved('')
    if (!concepts) get('/admin/concepts').then(d => setConcepts(d.concepts)).catch(() => setConcepts([]))
  }

  if (error) return <div className="modal-back"><div className="card modal"><p className="error">{error}</p><button onClick={onClose}>بستن</button></div></div>
  if (!q) return <div className="modal-back"><div className="spinner" /></div>

  return (
    <div className="modal-back" onClick={onClose}>
      <div className="card modal" onClick={e => e.stopPropagation()}>
        <div className="modal-head">
          <b>{q.public_id}</b>
          <span className="muted">{q.topic} — {q.subtopic} · پایهٔ {q.grade} · دشواری {q.difficulty}</span>
          <button className="ghost" onClick={onClose}>✕</button>
        </div>

        <div className="review-status-line">
          وضعیت: {{ approved: 'تأیید شده ✓', rejected: 'رد شده ✕', pending: 'در انتظار بررسی' }[q.review_status]}
          {q.rejection_note && <div className="reject-note">یادداشت رد شدن: {q.rejection_note}</div>}
          {q.served > 0 && (
            <div className="qstats">
              <span className="badge">{q.served} بار سرو شده</span>
              <span className="badge">{q.correct} درست</span>
              <span className={`badge ${q.correct_rate != null && (q.correct_rate < 0.15 || q.correct_rate > 0.95) ? 'warn' : ''}`}>
                نرخ درست: {Math.round((q.correct_rate || 0) * 100)}٪
              </span>
            </div>
          )}
        </div>

        <div className="review-status-line">
          نکته: {q.concept_title || <span className="error">به هیچ نکته‌ای وصل نیست</span>}
          {q.verification && (
            <div className="qstats">
              <span className={`badge ${(VERIFY_LABEL[q.verification.status] || ['', ''])[1]}`}>
                {(VERIFY_LABEL[q.verification.status] || [q.verification.status])[0]}
              </span>
              {q.verification.key_option && <span className="badge">کلید چاپی: {q.verification.key_option}</span>}
              {q.verification.solver_option && <span className="badge">حل مستقل: {q.verification.solver_option}</span>}
            </div>
          )}
          {q.verification?.notes?.length > 0 && (
            <ul className="verify-notes">{q.verification.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
          )}
        </div>

        <h4>متن سؤال</h4>
        {editing ? (
          <textarea className="note-input" dir="rtl" rows={5} value={draft.stem_md}
                    onChange={e => setDraft(d => ({ ...d, stem_md: e.target.value }))} />
        ) : (
          <div className="stem"><Markdown text={q.stem_md} /></div>
        )}
        {q.figures?.map(f => <img key={f} className="figure" src={f} alt="شکل" />)}

        {q.options && !editing && (
          <>
            <h4>گزینه‌ها</h4>
            <div className="options">
              {q.options.map((o, i) => (
                <div key={i} className={`option ${q.answer?.option === i + 1 ? 'correct' : ''}`}>
                  <span className="opt-num">{i + 1}</span>
                  <Markdown text={o} />
                  {q.answer?.option === i + 1 && <span className="badge">پاسخ</span>}
                </div>
              ))}
            </div>
          </>
        )}
        {editing && (
          <>
            <h4>گزینه‌ها (هر سطر یک گزینه)</h4>
            {draft.options.map((o, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
                <input type="radio" name="ans" checked={draft.answer_option === i + 1}
                       onChange={() => setDraft(d => ({ ...d, answer_option: i + 1 }))} />
                <textarea className="note-input" dir="rtl" rows={1} style={{ borderColor: 'var(--border)', margin: 0 }}
                          value={o}
                          onChange={e => setDraft(d => ({ ...d, options: d.options.map((x, j) => j === i ? e.target.value : x) }))} />
              </div>
            ))}
            <label>نکته</label>
            <select value={draft.concept_id} onChange={e => setDraft(d => ({ ...d, concept_id: e.target.value }))}>
              <option value="">— انتخاب کنید —</option>
              {(concepts || []).map(c => (
                <option key={c.concept_id} value={c.concept_id}>{c.lesson_title} · {c.title}</option>
              ))}
            </select>
            <label>دشواری (۱–۵)</label>
            <input type="number" min="1" max="5" value={draft.difficulty}
                   onChange={e => setDraft(d => ({ ...d, difficulty: e.target.value }))} />
            <h4>حل</h4>
            <textarea className="note-input" dir="rtl" rows={4} value={draft.solution_md}
                      onChange={e => setDraft(d => ({ ...d, solution_md: e.target.value }))} />
            <div className="review-actions">
              <button className="primary" onClick={saveEdit}>ذخیرهٔ تغییرات</button>
              <button onClick={() => setEditing(false)}>انصراف</button>
              {saved && <span className="badge">{saved}</span>}
            </div>
          </>
        )}
        {!editing && (
          <h4>حل</h4>
        )}
        {!editing && <Markdown text={q.solution_md} />}

        <div className="source-toggle">
          <button className="ghost" onClick={() => setShowSource(s => !s)}>
            {showSource ? 'پنهان کردن تصویر مرجع' : 'نمایش تصویر مرجع (اسکن PDF)'}
          </button>
          {showSource && <ScanImage path={q.screenshot} />}
        </div>

        {(q.review_status !== 'approved' || rejecting) && !editing && (
          <>
            {rejecting && <textarea className="note-input" dir="rtl" rows={3}
              placeholder="مشکل چیست؟ (این متن بعداً به هوش مصنوعی داده می‌شود تا سؤال را درست کند) مثلاً: «گزینه ۳ باید ۲۴ باشد» یا «متن سؤال ناقص است، جملهٔ آخر جا افتاده»"
              value={note} onChange={e => setNote(e.target.value)} />}
            <div className="review-actions">
              <button className="primary" onClick={() => review(true)}>تأیید ✓</button>
              {!rejecting
                ? <button className="danger" onClick={() => setRejecting(true)}>رد ✕</button>
                : <button className="danger" disabled={!note.trim()} onClick={() => review(false)}>ثبت رد شدن با یادداشت</button>}
            </div>
          </>
        )}
        {q.review_status === 'approved' && !editing && !rejecting && (
          <button className="danger wide" onClick={() => { setNote(''); setRejecting(true) }}>
            تغییر نظر: رد کردن
          </button>
        )}
        {!editing && (
          <div className="review-actions">
            <button onClick={startEdit}>✎ ویرایش سؤال</button>
          </div>
        )}
        {q.history?.length > 0 && (
          <>
            <h4>تاریخچه</h4>
            {q.history.slice().reverse().map((h, i) => (
              <div key={i} className="history-row">
                <span className="badge">{{ edited: 'ویرایش', approved: 'تأیید', rejected: 'رد', bulk_approved: 'تأیید گروهی', bulk_rejected: 'رد گروهی', imported: 'ورود' }[h.action] || h.action}</span>
                <span className="muted">{h.by} · {String(h.at).slice(0, 16)}</span>
                {h.note && <div className="muted">{h.note}</div>}
              </div>
            ))}
          </>
        )}
        {error && <p className="error">{error}</p>}
      </div>
    </div>
  )
}

function CoverageTab() {
  const [data, setData] = useState(null)
  useEffect(() => { get('/admin/concepts').then(setData).catch(e => setData({ error: e.message })) }, [])
  if (!data) return <div className="card"><div className="spinner" /></div>
  if (data.error) return <div className="card"><p className="error">{data.error}</p></div>
  const short = data.concepts.filter(c => c.approved < MIN_APPROVED).length
  let lastLesson = null
  return (
    <div className="card">
      <h3>پوشش نکته‌ها</h3>
      <p className="muted">
        هر نکته دست‌کم {MIN_APPROVED} سؤال تأییدشده لازم دارد تا موتور تکرار بتواند هر بار سؤال تازه بدهد.
        {' '}{short} نکته از {data.concepts.length} هنوز کم دارد.
        {data.unmapped_questions > 0 && <> · {data.unmapped_questions} سؤال هنوز به هیچ نکته‌ای وصل نیست.</>}
      </p>
      <table className="coverage">
        <thead><tr><th>نکته</th><th>تأییدشده</th><th>همه</th></tr></thead>
        <tbody>
          {data.concepts.map(c => {
            const head = c.lesson_title !== lastLesson
            lastLesson = c.lesson_title
            return (
              <React.Fragment key={c.concept_id}>
                {head && <tr className="lesson-row"><td colSpan={3}>{c.chapter_title} · {c.lesson_title}</td></tr>}
                <tr className={c.approved < MIN_APPROVED ? 'short' : ''}>
                  <td title={c.concept_id}>{c.title}</td>
                  <td>{c.approved}</td>
                  <td>{c.questions}</td>
                </tr>
              </React.Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function StatsTab() {
  const [stats, setStats] = useState(null)
  useEffect(() => { get('/admin/stats').then(setStats).catch(e => setStats({ error: e.message })) }, [])
  if (!stats) return <div className="card"><div className="spinner" /></div>
  if (stats.error) return <div className="card"><p className="error">{stats.error}</p></div>
  const L = stats.learning || {}
  const show = v => v === null || v === undefined ? '—' : v
  const rows = [
    ['میانهٔ تعداد سؤال تا یادگرفتن یک نکته', show(L.median_questions_to_learn),
     'سنجهٔ اصلی محصول: هرچه کمتر، بهتر (نکته‌هایی که با تعیین سطح جلو افتاده‌اند حساب نمی‌شوند)'],
    ['نکته‌های یادگرفته در برنامه', show(L.key_points_learned), ''],
    ['حفظ پس از ۲۱ روز یا بیشتر', L.retention_after_21_days == null ? '—' : `٪${Math.round(L.retention_after_21_days * 100)}`,
     `درصد درست در مرورهای بعد از فاصلهٔ طولانی (${show(L.long_gap_reviews)} مرور)`],
    ['نکته‌های جلو افتاده با تعیین سطح', show(L.placed_by_placement_test), `${show(L.placement_questions_answered)} سؤال تعیین سطح پاسخ داده شده`],
    ['دانش‌آموزها', show(stats.students), ''],
    ['سؤال‌ها / تأییدنشده', `${show(stats.questions)} / ${show(stats.unreviewed_questions)}`, ''],
    ['پاسخ‌ها', show(stats.responses), ''],
  ]
  async function download(path, name) {
    try {
      const url = await getBlobUrl(path)
      const a = document.createElement('a')
      a.href = url; a.download = name; a.click()
      setTimeout(() => URL.revokeObjectURL(url), 2000)
    } catch (e) { alert(e.message) }
  }
  return (
    <div className="card">
      <h3>آمار</h3>
      <div className="review-actions">
        <button onClick={() => download('/admin/pilot-report.csv', 'pilot-report.csv')}>⬇ گزارش پایلوت (CSV)</button>
        <button onClick={() => download('/admin/generation/export', 'generation-export.json')}
                title="نکته‌هایی که کمتر از ۵ سؤال دارند، با نمونه؛ ورودی python -m pipeline generate">
          ⬇ فهرست نکته‌های نیازمند سؤال</button>
      </div>
      <table className="coverage">
        <tbody>
          {rows.map(([k, v, note]) => (
            <tr key={k}><td>{k}{note && <div className="muted">{note}</div>}</td><td><b>{v}</b></td></tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ReportsTab() {
  const [reports, setReports] = useState(null)
  const load = () => get('/admin/reports').then(setReports).catch(e => setReports({ error: e.message }))
  useEffect(() => { load() }, [])
  async function resolve(id, status) {
    await post(`/admin/reports/${id}/resolve`, { status })
    load()
  }
  if (!reports) return <div className="card">…</div>
  if (reports.error) return <div className="card"><p className="error">{reports.error}</p></div>
  return (
    <div className="card">
      <h3>گزارش خطاهای دانش‌آموزان</h3>
      {!reports.length && <p className="muted">گزارش بازی نیست.</p>}
      {reports.map(r => (
        <div key={r.id} className="report-row">
          <div className="report-head">
            <b>{r.question_public_id}</b>
            <span className="muted">{r.topic} · {r.student} · {r.created_at}</span>
          </div>
          <p className="report-note">{r.note}</p>
          <div className="review-actions">
            <a className="link" href={`/static/questions/${r.question_public_id}/question_shot.png`} target="_blank">اسکن سؤال</a>
            <button className="primary" onClick={() => resolve(r.id, 'resolved')}>برطرف شد</button>
            <button onClick={() => resolve(r.id, 'dismissed')}>نادیده بگیر</button>
          </div>
        </div>
      ))}
    </div>
  )
}
