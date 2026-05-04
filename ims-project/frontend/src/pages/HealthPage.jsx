import { useEffect, useState } from 'react'
import { fetchHealth } from '../services/api'
import { useStore } from '../store/useStore'

export default function HealthPage() {
  const { health, loadHealth, queueStats } = useStore()
  const [loading, setLoading] = useState(false)

  const refresh = async () => {
    setLoading(true)
    await loadHealth()
    setLoading(false)
  }

  useEffect(() => { refresh() }, [])

  const checks = health?.checks || {}
  const isHealthy = health?.status === 'healthy'

  const ServiceCard = ({ name, status }) => {
    const ok = status === 'ok'
    return (
      <div className="card" style={{ borderLeft: `3px solid ${ok ? 'var(--green)' : 'var(--p0)'}` }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{name}</div>
          <span className={`status-badge ${ok ? 'CLOSED' : 'OPEN'}`}>{ok ? 'OK' : 'ERROR'}</span>
        </div>
        {!ok && <div style={{ fontSize: 11, color: 'var(--p0)', marginTop: 6, fontFamily: 'var(--font-mono)' }}>{status}</div>}
      </div>
    )
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h2>SYSTEM HEALTH</h2>
          <p>Service connectivity and queue metrics</p>
        </div>
        <button className="btn btn-ghost" onClick={refresh} disabled={loading}>
          {loading ? 'Refreshing…' : '↻ Refresh'}
        </button>
      </div>
      <div className="page-content">
        <div className={`alert-banner ${isHealthy ? 'success' : 'error'}`} style={{ marginBottom: 16 }}>
          {isHealthy ? '✓ All systems operational' : '✗ One or more services degraded'}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12, marginBottom: 16 }}>
          <ServiceCard name="PostgreSQL" status={checks.postgres} />
          <ServiceCard name="MongoDB" status={checks.mongodb} />
          <ServiceCard name="Redis" status={checks.redis} />
        </div>

        {/* Queue Stats */}
        {(checks.queue || queueStats) && (
          <div className="card">
            <div className="card-title">Signal Queue</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
              {[
                ['Queue Size', (checks.queue || queueStats)?.queue_size],
                ['Max Size', (checks.queue || queueStats)?.queue_max],
                ['Utilization', `${(checks.queue || queueStats)?.utilization_pct}%`],
                ['Total Received', (checks.queue || queueStats)?.total_received],
                ['Total Processed', (checks.queue || queueStats)?.total_processed],
                ['Total Dropped', (checks.queue || queueStats)?.total_dropped],
                ['Drop Rate', `${(checks.queue || queueStats)?.drop_rate_pct}%`],
              ].map(([k, v]) => (
                <div key={k} style={{ background: 'var(--bg-3)', padding: '12px 14px', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', marginBottom: 4 }}>{k}</div>
                  <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, fontWeight: 700 }}>{v ?? '—'}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-title">Version</div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-2)' }}>
            IMS v{health?.version || '—'} · Backend: FastAPI + PostgreSQL + MongoDB + Redis
          </div>
        </div>
      </div>
    </>
  )
}
