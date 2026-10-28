import { useEffect, useRef, useState } from 'react'
import cytoscape from 'cytoscape'

const api = async (path: string, opts: any = {}) => {
  const r = await fetch(path, opts)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}
const COLORS: Record<string, string> = { Paper: '#c9a86a', Method: '#7fb069', Dataset: '#6a9ec9', Metric: '#c96a6a', Finding: '#b48ec9', Limitation: '#d98e4a', ResearchProblem: '#e6e1d5', Domain: '#8a8f98', ResearchTopic: '#6ab8c9' }
type Tab = 'dashboard' | 'library' | 'graph' | 'assistant' | 'gaps' | 'topics'

export default function App() {
  const [tab, setTab] = useState<Tab>('dashboard')
  const [stats, setStats] = useState<any>(null)
  const [docs, setDocs] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const refresh = async () => {
    setLoading(true); setErr('')
    try { setStats(await api('/api/stats')); setDocs(await api('/api/documents')) } catch (e: any) { setErr(e.message) }
    setLoading(false)
  }
  useEffect(() => { refresh() }, [])
  const tabs: [Tab, string][] = [['dashboard', 'Dashboard'], ['library', 'Library'], ['graph', 'Knowledge Graph'], ['assistant', 'Research Assistant'], ['gaps', 'Gap Explorer'], ['topics', 'Topics & Recommendations']]
  return (<>
    <nav><b>ResearchMind</b>{tabs.map(([k, l]) => <button key={k} className={tab === k ? 'active' : ''} onClick={() => setTab(k)}>{l}</button>)}</nav>
    <main>
      {err && <div className="card" role="alert">Error: {err}</div>}
      {loading && !stats && <><div className="skeleton" /><div className="skeleton" /><div className="skeleton" /></>}
      {tab === 'dashboard' && <Dashboard stats={stats} refresh={refresh} />}
      {tab === 'library' && <Library docs={docs} refresh={refresh} />}
      {tab === 'graph' && <GraphView />}
      {tab === 'assistant' && <Assistant />}
      {tab === 'gaps' && <Gaps />}
      {tab === 'topics' && <Topics docs={docs} />}
    </main>
  </>)
}

function Dashboard({ stats, refresh }: any) {
  if (!stats) return <p className="muted">No data yet. Upload papers in the Library.</p>
  const items = [['Total papers', stats.total_papers], ['Processed', stats.processed_papers], ['Failed', stats.failed_papers], ['Entities', stats.entities], ['Relationships', stats.relationships], ['Limitations found', stats.limitations]]
  return (<><h1>Research overview</h1><p className="muted">Every number below comes from your uploaded collection. No demo statistics.</p>
    <div className="grid">{items.map(([l, v]) => <div className="card" key={l}><div className="stat">{v}</div><div className="muted">{l}</div></div>)}</div>
    <div className="card"><h2>Recent activity</h2>{stats.recent.length === 0 ? <p className="muted">No papers yet.</p> : stats.recent.map((r: any) => <p key={r.id}>{r.title || 'Untitled'} — {r.status}</p>)}
      <button className="ghost" onClick={refresh}>Refresh</button></div></>)
}

function Library({ docs, refresh }: any) {
  const [q, setQ] = useState(''); const [msg, setMsg] = useState('')
  const upload = async (files: FileList | null) => {
    if (!files?.length) return
    const fd = new FormData(); Array.from(files).forEach(f => fd.append('files', f))
    setMsg('Uploading and processing…')
    try { const r = await api('/api/documents/upload', { method: 'POST', body: fd }); setMsg(JSON.stringify(r.uploaded)); await refresh() } catch (e: any) { setMsg('Upload failed: ' + e.message) }
  }
  const filtered = docs.filter((d: any) => !q || (d.title || '').toLowerCase().includes(q.toLowerCase()) || d.filename.toLowerCase().includes(q.toLowerCase()))
  return (<><h1>Research library</h1>
    <div className="card"><label>Upload PDF papers (multiple allowed)</label><input type="file" accept=".pdf" multiple onChange={e => upload(e.target.files)} /><p className="muted">Duplicate files are detected by content hash. Scanned PDFs are reported as failed, not silently treated as success.</p>{msg && <p>{msg}</p>}</div>
    <input placeholder="Search papers…" value={q} onChange={e => setQ(e.target.value)} aria-label="Search papers" />
    {filtered.length === 0 ? <p className="muted">No papers match. Upload your first PDF above.</p> : filtered.map((d: any) => <div className="card" key={d.id}>
      <b>{d.title || d.filename}</b> <span className="muted">· {d.status}{d.year ? ` · ${d.year}` : ''} · {d.page_count} pages{d.scanned ? ' · scanned/unreadable' : ''}</span>
      {d.error && <p role="alert">{d.error}</p>}{d.abstract && <p className="muted">{d.abstract.slice(0, 300)}</p>}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <a href={`/api/documents/${d.id}/file`} target="_blank" rel="noreferrer"><button className="ghost">Open PDF</button></a>
        <button className="ghost" onClick={async () => { await api(`/api/documents/${d.id}/reprocess`, { method: 'POST' }); await refresh() }}>Reprocess</button>
        <button className="ghost" onClick={async () => { if (confirm('Delete this paper and all its entities, relationships and chunks?')) { await api(`/api/documents/${d.id}`, { method: 'DELETE' }); await refresh() } }}>Delete</button>
      </div></div>)}
  </>)
}

function GraphView() {
  const ref = useRef<HTMLDivElement>(null); const cyRef = useRef<any>(null)
  const [data, setData] = useState<any>(null); const [nodeType, setNodeType] = useState(''); const [relation, setRelation] = useState(''); const [q, setQ] = useState(''); const [selected, setSelected] = useState<any>(null)
  const load = async () => {
    const params = new URLSearchParams(); if (nodeType) params.set('node_type', nodeType); if (relation) params.set('relation', relation); if (q) params.set('q', q)
    const g = await api('/api/graph?' + params.toString()); setData(g)
    if (!ref.current) return
    cyRef.current?.destroy()
    const cy = cytoscape({ container: ref.current, elements: [...g.nodes.map((n: any) => ({ data: { id: n.id, label: n.label, type: n.type } })), ...g.edges.map((e: any) => ({ data: { id: e.id, source: e.source, target: e.target, label: e.label, ...e } }))],
      style: [{ selector: 'node', style: { 'background-color': (el: any) => COLORS[el.data('type')] || '#888', label: 'data(label)', color: '#eceae6', 'font-size': '11px', 'text-wrap': 'wrap', 'text-max-width': '90px' } }, { selector: 'edge', style: { label: 'data(label)', color: '#a8a49c', 'font-size': '9px', 'curve-style': 'bezier', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#555' } }],
      layout: { name: 'cose', animate: false } })
    cy.on('tap', 'node', (e: any) => { const n = e.target; const edges = g.edges.filter((x: any) => x.source === n.id() || x.target === n.id()); setSelected({ node: n.data(), edges }) })
    cyRef.current = cy
  }
  useEffect(() => { load() }, [])
  return (<><h1>Knowledge graph explorer</h1><p className="muted">Click a node to inspect its neighbourhood and evidence. CONTRADICTS_OR_QUALIFIES is created only with an explicit contrast marker plus a comparative claim.</p>
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      <select value={nodeType} onChange={e => setNodeType(e.target.value)} aria-label="Filter by node type"><option value="">All node types</option>{['Paper', 'ResearchProblem', 'Method', 'Dataset', 'Metric', 'Finding', 'Limitation', 'Domain'].map(t => <option key={t}>{t}</option>)}</select>
      <select value={relation} onChange={e => setRelation(e.target.value)} aria-label="Filter by relationship"><option value="">All relationships</option>{['ADDRESSES', 'USES_METHOD', 'EVALUATED_ON', 'MEASURED_BY', 'REPORTS_FINDING', 'IDENTIFIES_LIMITATION', 'RELATED_TO', 'CONTRADICTS_OR_QUALIFIES'].map(t => <option key={t}>{t}</option>)}</select>
      <input placeholder="Search nodes…" value={q} onChange={e => setQ(e.target.value)} style={{ maxWidth: 260 }} />
      <button className="primary" onClick={load}>Apply filters</button>
    </div>
    <div id="cy" ref={ref} style={{ marginTop: 12 }} />
    {data && <p className="muted">{data.nodes.length} nodes, {data.edges.length} edges{data.truncated ? ' (truncated for readability — filter or search)' : ''}</p>}
    {selected && <div className="card"><h2>{selected.node.label} <span className="muted">({selected.node.type})</span></h2>{selected.edges.map((e: any) => <p key={e.id}>{e.label}: {e.target} — p. {e.page} · confidence {e.confidence} · {e.method}<br /><span className="muted">{e.snippet}</span> <a href={`/api/documents/${e.doc_id}/file`} target="_blank" rel="noreferrer">Open paper</a></p>)}</div>}
  </>)
}

function Assistant() {
  const [question, setQuestion] = useState('Which methods are used to solve this research problem?')
  const [res, setRes] = useState<any>(null); const [busy, setBusy] = useState(false)
  const ask = async () => { setBusy(true); try { setRes(await api('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) })) } catch (e: any) { setRes({ answer: 'Error: ' + e.message, citations: [] }) } setBusy(false) }
  return (<><h1>Research assistant</h1><p className="muted">Answers are grounded in cited chunks. If evidence is insufficient, the assistant says so — it never invents a title, metric or page.</p>
    <textarea rows={3} value={question} onChange={e => setQuestion(e.target.value)} aria-label="Research question" />
    <button className="primary" onClick={ask} disabled={busy}>{busy ? 'Searching…' : 'Ask'}</button>
    {res && <div className="card"><p><b>Intent:</b> {res.intent} · <b>Mode:</b> {res.mode} · LLM used: {String(res.llm_used)}</p><p style={{ whiteSpace: 'pre-wrap' }}>{res.answer}</p>
      <h2>Citations</h2>{res.citations?.length === 0 ? <p className="muted">No supporting evidence found.</p> : res.citations.map((c: any, i: number) => <p key={i}><b>{c.title}</b> — p. {c.page} (score {c.score})<br /><span className="muted">{c.snippet}</span> <a href={`/api/documents/${c.paper_id}/file`} target="_blank" rel="noreferrer">Open PDF</a></p>)}
    </div>}
  </>)
}

function Gaps() {
  const [gaps, setGaps] = useState<any[]>([]); const [loaded, setLoaded] = useState(false)
  useEffect(() => { api('/api/gaps').then(g => { setGaps(g); setLoaded(true) }) }, [])
  const vote = async (key: string, verdict: string) => { await api(`/api/gaps/${key}/feedback`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ verdict }) }); setGaps(await api('/api/gaps')) }
  if (!loaded) return <><div className="skeleton" /><div className="skeleton" /></>
  return (<><h1>Gap explorer</h1><p className="muted">Potential opportunities <b>in this collection</b> only — not verified global gaps. Score = 100 × (0.30·Underrepresentation + 0.25·Limitation + 0.20·Relationship + 0.15·Trend + 0.10·Conflict), renormalised when a signal is missing. Weights are tunable heuristics, not probabilities.</p>
    {gaps.length === 0 ? <p className="muted">Upload papers first — gaps are derived from real limitations and topic coverage, not invented.</p> : gaps.map(g => <div className="card" key={g.key}>
      <h2>{g.title} — {g.score}/100</h2><p>{g.why}</p>
      {Object.entries(g.breakdown || {}).map(([k, w]: any) => <div key={k}><span className="muted">{k} (weight {w}) · signal {g.signals?.[k] ?? '—'}</span><div className="bar"><div style={{ width: `${(g.signals?.[k] ?? 0) * 100}%` }} /></div></div>)}
      <p><b>Proposed question:</b> {g.proposed_question}</p><p><b>Experiment:</b> {g.proposed_experiment}</p>
      <p><b>Methods:</b> {(g.methods || []).join(', ') || '—'} · <b>Datasets:</b> {(g.datasets || []).join(', ') || '—'} · <b>Metrics:</b> {(g.metrics || []).join(', ') || '—'}</p>
      <p><b>Evidence:</b> {(g.evidence || []).map((s: string, i: number) => <span key={i} className="muted">{s} </span>)}</p>
      <p className="muted">{g.caveat} Confidence: {g.confidence}. {g.feedback ? `Your feedback: ${g.feedback}` : ''}</p>
      <div style={{ display: 'flex', gap: 8 }}><button className="ghost" onClick={() => vote(g.key, 'useful')}>Useful</button><button className="ghost" onClick={() => vote(g.key, 'irrelevant')}>Irrelevant</button><button className="ghost" onClick={() => vote(g.key, 'already_investigated')}>Already investigated</button></div>
    </div>)}
  </>)
}

function Topics({ docs }: any) {
  const [data, setData] = useState<any>(null); const [paperId, setPaperId] = useState(''); const [recs, setRecs] = useState<any[]>([])
  useEffect(() => { api('/api/topics').then(setData) }, [])
  const loadRecs = async (id: string) => { setPaperId(id); if (id) setRecs(await api('/api/recommendations?paper_id=' + id)) }
  return (<><h1>Topics & recommendations</h1>
    {!data ? <div className="skeleton" /> : <><p className="muted">{data.note}</p>
      {data.topics.map((t: any) => <div className="card" key={t.id}><h2>Topic {t.id} ({t.size} papers)</h2><p>Keywords: {t.keywords.join(', ')}</p><p>{t.summary}</p><p className="muted">{(t.paper_titles || []).join(' · ')}</p></div>)}
    </>}
    <div className="card"><h2>Recommendations for a paper</h2><select value={paperId} onChange={e => loadRecs(e.target.value)} aria-label="Choose a paper"><option value="">Choose a paper…</option>{docs.map((d: any) => <option key={d.id} value={d.id}>{d.title || d.filename}</option>)}</select>
      {recs.map((r: any) => <p key={r.paper.id}><b>{r.paper.title}</b> — score {r.score}<br /><span className="muted">{r.explanation}</span></p>)}
    </div>
  </>)
}
