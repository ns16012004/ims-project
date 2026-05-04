import { useState } from 'react'
import toast from 'react-hot-toast'
import { ingestSignal, ingestSignalBatch } from '../services/api'
import { useStore } from '../store/useStore'

const COMPONENT_TYPES = ['RDBMS', 'API', 'MCP_HOST', 'CACHE', 'ASYNC_QUEUE', 'NOSQL']
const SIGNAL_TYPES = ['ERROR', 'LATENCY_SPIKE', 'TIMEOUT', 'HEALTH_FAIL', 'CONNECTION_REFUSED']

const PRESET_SCENARIOS = [
  {
    name: '🔴 RDBMS Outage (P0)',
    description: 'Simulate a primary database failure — will trigger P0 alert',
    signals: Array.from({ length: 100 }, (_, i) => ({
      component_id: 'RDBMS_PRIMARY',
      component_type: 'RDBMS',
      signal_type: 'CONNECTION_REFUSED',
      message: `Connection refused to primary DB replica ${i + 1}`,
      metadata: { retry: i, host: 'db-primary-01' },
    })),
  },
  {
    name: '🟠 MCP Host Degraded (P1)',
    description: 'Simulate MCP Host latency spikes — P1 alert',
    signals: Array.from({ length: 100 }, (_, i) => ({
      component_id: 'MCP_HOST_01',
      component_type: 'MCP_HOST',
      signal_type: 'LATENCY_SPIKE',
      message: `Request latency ${500 + i * 10}ms exceeds SLA`,
      metadata: { latency_ms: 500 + i * 10 },
    })),
  },
  {
    name: '🟡 Cache Failure (P2)',
    description: 'Simulate cache cluster failure — P2 alert',
    signals: Array.from({ length: 100 }, (_, i) => ({
      component_id: 'CACHE_CLUSTER_01',
      component_type: 'CACHE',
      signal_type: 'HEALTH_FAIL',
      message: `Cache node ${i % 3} health check failed`,
      metadata: { node: i % 3 },
    })),
  },
  {
    name: '⚡ Multi-component Cascade',
    description: 'RDBMS outage triggers cascade to API and Queue',
    signals: [
      ...Array.from({ length: 60 }, (_, i) => ({
        component_id: 'RDBMS_PRIMARY',
        component_type: 'RDBMS',
        signal_type: 'CONNECTION_REFUSED',
        message: `DB connection refused [${i}]`,
      })),
      ...Array.from({ length: 30 }, (_, i) => ({
        component_id: 'API_GATEWAY_01',
        component_type: 'API',
        signal_type: 'TIMEOUT',
        message: `API gateway timeout due to DB unavailability [${i}]`,
      })),
      ...Array.from({ length: 20 }, (_, i) => ({
        component_id: 'ASYNC_QUEUE_01',
        component_type: 'ASYNC_QUEUE',
        signal_type: 'ERROR',
        message: `Queue consumer failing due to downstream DB [${i}]`,
      })),
    ],
  },
]

export default function SignalTester() {
  const { refreshAll } = useStore()
  const [form, setForm] = useState({
    component_id: 'RDBMS_PRIMARY',
    component_type: 'RDBMS',
    signal_type: 'ERROR',
    message: 'Database connection timed out',
    count: 1,
  })
  const [sending, setSending] = useState(false)
  const [scenarioLoading, setScenarioLoading] = useState(null)
  const [results, setResults] = useState([])

  const addResult = (msg, type = 'success') => {
    setResults(r => [{ msg, type, ts: new Date().toLocaleTimeString() }, ...r].slice(0, 20))
  }

  const handleSend = async () => {
    setSending(true)
    try {
      const count = parseInt(form.count) || 1
      const signals = Array.from({ length: count }, () => ({
        component_id: form.component_id,
        component_type: form.component_type,
        signal_type: form.signal_type,
        message: form.message,
      }))

      if (count === 1) {
        const res = await ingestSignal(signals[0])
        addResult(`Signal accepted: ${res.signal_id}`)
        toast.success('Signal sent!')
      } else {
        const res = await ingestSignalBatch(signals)
        addResult(`Batch: ${res.accepted} accepted, ${res.dropped} dropped`)
        toast.success(`${res.accepted} signals sent!`)
      }
      setTimeout(refreshAll, 2000)
    } catch (e) {
      addResult(e.message, 'error')
      toast.error(e.message)
    } finally {
      setSending(false)
    }
  }

  const runScenario = async (scenario, idx) => {
    setScenarioLoading(idx)
    try {
      const CHUNK = 500
      let totalAccepted = 0
      for (let i = 0; i < scenario.signals.length; i += CHUNK) {
        const chunk = scenario.signals.slice(i, i + CHUNK)
        const res = await ingestSignalBatch(chunk)
        totalAccepted += res.accepted
      }
      addResult(`Scenario "${scenario.name}": ${totalAccepted}/${scenario.signals.length} signals sent`)
      toast.success(`Scenario running — ${totalAccepted} signals ingested`)
      setTimeout(refreshAll, 3000)
    } catch (e) {
      addResult(e.message, 'error')
      toast.error(e.message)
    } finally {
      setScenarioLoading(null)
    }
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h2>SIGNAL TESTER</h2>
          <p>Inject test signals into the IMS pipeline</p>
        </div>
      </div>
      <div className="page-content">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>

          {/* Manual form */}
          <div className="card">
            <div className="card-title">Manual Signal Injection</div>
            <div className="form-group">
              <label className="form-label">Component ID</label>
              <input className="form-input" value={form.component_id}
                onChange={e => setForm(f => ({ ...f, component_id: e.target.value }))}
                placeholder="e.g., RDBMS_PRIMARY" />
            </div>
            <div className="grid-2">
              <div className="form-group">
                <label className="form-label">Component Type</label>
                <select className="form-select" value={form.component_type}
                  onChange={e => setForm(f => ({ ...f, component_type: e.target.value }))}>
                  {COMPONENT_TYPES.map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Signal Type</label>
                <select className="form-select" value={form.signal_type}
                  onChange={e => setForm(f => ({ ...f, signal_type: e.target.value }))}>
                  {SIGNAL_TYPES.map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Message</label>
              <input className="form-input" value={form.message}
                onChange={e => setForm(f => ({ ...f, message: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Count (for debounce testing, send 100+)</label>
              <input type="number" className="form-input" value={form.count} min={1} max={500}
                onChange={e => setForm(f => ({ ...f, count: e.target.value }))} />
            </div>
            <button className="btn btn-primary" onClick={handleSend} disabled={sending} style={{ width: '100%' }}>
              {sending ? 'Sending…' : `⚡ Send ${form.count > 1 ? form.count + ' signals' : 'Signal'}`}
            </button>
          </div>

          {/* Result log */}
          <div className="card">
            <div className="card-title">Activity Log</div>
            <div style={{ maxHeight: 320, overflowY: 'auto' }}>
              {results.length === 0 ? (
                <div className="empty" style={{ padding: 20 }}>
                  <div>No activity yet</div>
                </div>
              ) : results.map((r, i) => (
                <div key={i} className="signal-item" style={{ borderColor: r.type === 'error' ? 'var(--p0-border)' : 'var(--border)' }}>
                  <span style={{ color: 'var(--text-3)' }}>{r.ts}</span>
                  {' '}
                  <span style={{ color: r.type === 'error' ? 'var(--p0)' : 'var(--green)' }}>{r.msg}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Preset Scenarios */}
        <div className="card">
          <div className="card-title">Preset Failure Scenarios</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12 }}>
            {PRESET_SCENARIOS.map((s, idx) => (
              <div key={idx} style={{
                background: 'var(--bg-3)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)', padding: '14px 16px'
              }}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>{s.name}</div>
                <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 12 }}>{s.description}</div>
                <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', marginBottom: 10 }}>
                  {s.signals.length} signals → debounce → work item
                </div>
                <button
                  className="btn btn-ghost"
                  style={{ width: '100%' }}
                  onClick={() => runScenario(s, idx)}
                  disabled={scenarioLoading !== null}
                >
                  {scenarioLoading === idx ? 'Running…' : '▶ Run Scenario'}
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}
