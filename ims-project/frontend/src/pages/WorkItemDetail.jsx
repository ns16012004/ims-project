import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { format, formatDistanceToNow } from 'date-fns'
import toast from 'react-hot-toast'
import {
  fetchWorkItem, fetchSignalsForWorkItem,
  updateWorkItemStatus, submitRCA
} from '../services/api'
import { useStore } from '../store/useStore'

const STATUS_FLOW = ['OPEN', 'INVESTIGATING', 'RESOLVED', 'CLOSED']
const STATUS_TRANSITIONS = {
  OPEN: ['INVESTIGATING'],
  INVESTIGATING: ['RESOLVED', 'OPEN'],
  RESOLVED: ['CLOSED', 'INVESTIGATING'],
  CLOSED: [],
}
const ROOT_CAUSE_CATEGORIES = [
  'INFRASTRUCTURE', 'APPLICATION', 'NETWORK',
  'DATABASE', 'HUMAN_ERROR', 'THIRD_PARTY', 'UNKNOWN'
]

export default function WorkItemDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { refreshAll } = useStore()

  const [item, setItem] = useState(null)
  const [signals, setSignals] = useState([])
  const [loading, setLoading] = useState(true)
  const [showRCA, setShowRCA] = useState(false)
  const [statusLoading, setStatusLoading] = useState(false)

  const [rca, setRca] = useState({
    incident_start: '',
    incident_end: '',
    root_cause_category: 'INFRASTRUCTURE',
    root_cause_description: '',
    fix_applied: '',
    prevention_steps: '',
  })
  const [rcaLoading, setRcaLoading] = useState(false)

  const load = async () => {
    try {
      const [wi, sigs] = await Promise.all([
        fetchWorkItem(id),
        fetchSignalsForWorkItem(id),
      ])
      setItem(wi)
      setSignals(sigs.signals || [])
    } catch (e) {
      toast.error(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id])

  const handleStatusChange = async (newStatus) => {
    if (newStatus === 'CLOSED' && !item.rca) {
      toast.error('Submit RCA before closing the incident.')
      setShowRCA(true)
      return
    }
    setStatusLoading(true)
    try {
      const updated = await updateWorkItemStatus(id, newStatus)
      setItem(updated)
      toast.success(`Status updated → ${newStatus}`)
      refreshAll()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setStatusLoading(false)
    }
  }

  const handleRCASubmit = async () => {
    if (!rca.incident_start || !rca.incident_end) {
      toast.error('Please fill in incident start and end times.')
      return
    }
    if (rca.root_cause_description.length < 20) {
      toast.error('Root cause description must be at least 20 characters.')
      return
    }
    if (rca.fix_applied.length < 10) {
      toast.error('Fix applied must be at least 10 characters.')
      return
    }
    if (rca.prevention_steps.length < 10) {
      toast.error('Prevention steps must be at least 10 characters.')
      return
    }

    setRcaLoading(true)
    try {
      const updated = await submitRCA(id, rca)
      setItem(updated)
      setShowRCA(false)
      toast.success('RCA submitted successfully! MTTR calculated.')
      refreshAll()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setRcaLoading(false)
    }
  }

  if (loading) return <div className="loading" style={{ height: '100vh' }}>Loading incident...</div>
  if (!item) return <div className="empty">Incident not found</div>

  const currentStep = STATUS_FLOW.indexOf(item.status)
  const nextTransitions = STATUS_TRANSITIONS[item.status] || []

  return (
    <>
      <div className="page-header">
        <div>
          <button className="btn btn-ghost text-sm" onClick={() => navigate(-1)} style={{ marginBottom: 8 }}>← Back</button>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span className={`badge ${item.priority}`}>{item.priority}</span>
            {item.component_id}
          </h2>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{item.id}</p>
        </div>
        <span className={`status-badge ${item.status}`} style={{ fontSize: 13, padding: '6px 14px' }}>{item.status}</span>
      </div>

      <div className="page-content">
        {/* State Timeline */}
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-title">Incident Lifecycle</div>
          <div className="timeline">
            {STATUS_FLOW.map((s, i) => (
              <div className="timeline-step" key={s}>
                <div className={`step-dot ${i < currentStep ? 'done' : i === currentStep ? 'current' : ''}`}>
                  {i < currentStep ? '✓' : i + 1}
                </div>
                <div className="step-label">{s}</div>
              </div>
            ))}
          </div>

          {nextTransitions.length > 0 && (
            <div style={{ marginTop: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {nextTransitions.map(t => (
                <button
                  key={t}
                  className={`btn ${t === 'CLOSED' ? 'btn-primary' : 'btn-ghost'}`}
                  onClick={() => handleStatusChange(t)}
                  disabled={statusLoading}
                >
                  {statusLoading ? '…' : `→ ${t}`}
                </button>
              ))}
              {item.status === 'RESOLVED' && !item.rca && (
                <button className="btn btn-ghost" onClick={() => setShowRCA(true)}>
                  + Submit RCA first
                </button>
              )}
            </div>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
          {/* Details */}
          <div className="card">
            <div className="card-title">Details</div>
            <table style={{ width: '100%' }}>
              <tbody>
                {[
                  ['Title', item.title],
                  ['Component', item.component_id],
                  ['Type', item.component_type],
                  ['Priority', item.priority],
                  ['Signals', item.signal_count],
                  ['Created', format(new Date(item.created_at), 'PPpp')],
                  ['Updated', formatDistanceToNow(new Date(item.updated_at), { addSuffix: true })],
                  ['MTTR', item.mttr_minutes != null ? `${item.mttr_minutes} minutes` : '—'],
                ].map(([k, v]) => (
                  <tr key={k} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px 0', color: 'var(--text-3)', fontSize: 11, fontFamily: 'var(--font-mono)', width: 100 }}>{k}</td>
                    <td style={{ padding: '8px 0', fontSize: 13 }}>{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* RCA Summary or button */}
          <div className="card">
            <div className="section-header">
              <div className="card-title" style={{ marginBottom: 0 }}>Root Cause Analysis</div>
              {!item.rca && item.status !== 'CLOSED' && (
                <button className="btn btn-ghost text-sm" onClick={() => setShowRCA(true)}>+ Submit RCA</button>
              )}
            </div>
            {item.rca ? (
              <div>
                <div className="alert-banner success">RCA complete — MTTR: {item.rca.mttr_minutes} min</div>
                {[
                  ['Category', item.rca.root_cause_category],
                  ['Root Cause', item.rca.root_cause_description],
                  ['Fix Applied', item.rca.fix_applied],
                  ['Prevention', item.rca.prevention_steps],
                  ['Submitted', format(new Date(item.rca.submitted_at), 'PPp')],
                ].map(([k, v]) => (
                  <div key={k} style={{ marginBottom: 10 }}>
                    <div style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', marginBottom: 3 }}>{k}</div>
                    <div style={{ fontSize: 13 }}>{v}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty" style={{ padding: 20 }}>
                <div className="empty-icon" style={{ fontSize: 24 }}>📋</div>
                <div>No RCA submitted yet</div>
                <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 4 }}>Required before closing</div>
              </div>
            )}
          </div>
        </div>

        {/* Raw Signals */}
        <div className="card">
          <div className="card-title">Raw Signals ({signals.length})</div>
          {signals.length === 0 ? (
            <div className="empty">No signals linked yet</div>
          ) : (
            <div style={{ maxHeight: 320, overflowY: 'auto' }}>
              {signals.map((sig, i) => (
                <div className="signal-item" key={sig.id || i}>
                  <span className="signal-type">{sig.signal_type}</span>
                  <span className="signal-component">{sig.component_id}</span>
                  <span style={{ color: 'var(--text-2)' }}>{sig.message}</span>
                  <span className="signal-time">{sig.timestamp ? format(new Date(sig.timestamp), 'HH:mm:ss') : ''}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* RCA Modal */}
      {showRCA && (
        <div className="modal-overlay" onClick={() => setShowRCA(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">Submit Root Cause Analysis</div>
              <button className="btn btn-ghost" onClick={() => setShowRCA(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="alert-banner warning" style={{ marginBottom: 16 }}>
                ⚠ RCA is mandatory before closing this incident.
              </div>
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">Incident Start *</label>
                  <input
                    type="datetime-local"
                    className="form-input"
                    value={rca.incident_start}
                    onChange={e => setRca(r => ({ ...r, incident_start: e.target.value }))}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Incident End *</label>
                  <input
                    type="datetime-local"
                    className="form-input"
                    value={rca.incident_end}
                    onChange={e => setRca(r => ({ ...r, incident_end: e.target.value }))}
                  />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Root Cause Category *</label>
                <select
                  className="form-select"
                  value={rca.root_cause_category}
                  onChange={e => setRca(r => ({ ...r, root_cause_category: e.target.value }))}
                >
                  {ROOT_CAUSE_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Root Cause Description * (min 20 chars)</label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  placeholder="Describe the root cause in detail..."
                  value={rca.root_cause_description}
                  onChange={e => setRca(r => ({ ...r, root_cause_description: e.target.value }))}
                />
                <div style={{ fontSize: 10, color: rca.root_cause_description.length < 20 ? 'var(--p0)' : 'var(--green)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
                  {rca.root_cause_description.length}/20 min chars
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Fix Applied * (min 10 chars)</label>
                <textarea
                  className="form-textarea"
                  rows={2}
                  placeholder="What fix was applied to resolve the incident?"
                  value={rca.fix_applied}
                  onChange={e => setRca(r => ({ ...r, fix_applied: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Prevention Steps * (min 10 chars)</label>
                <textarea
                  className="form-textarea"
                  rows={2}
                  placeholder="Steps to prevent recurrence..."
                  value={rca.prevention_steps}
                  onChange={e => setRca(r => ({ ...r, prevention_steps: e.target.value }))}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setShowRCA(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleRCASubmit} disabled={rcaLoading}>
                {rcaLoading ? 'Submitting…' : '✓ Submit RCA'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
