import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { useStore } from '../store/useStore'
import { formatDistanceToNow } from 'date-fns'

const PRIORITY_COLORS = { P0: '#ef4444', P1: '#f97316', P2: '#eab308' }

export default function Dashboard() {
  const { stats, workItems, loadStats, loadWorkItems, statsLoading } = useStore()
  const navigate = useNavigate()

  useEffect(() => {
    loadStats()
    loadWorkItems()
  }, [])

  const statusData = stats ? [
    { name: 'OPEN', value: stats.total_open, color: '#ef4444' },
    { name: 'INVESTIGATING', value: stats.total_investigating, color: '#f97316' },
    { name: 'RESOLVED', value: stats.total_resolved, color: '#eab308' },
    { name: 'CLOSED', value: stats.total_closed, color: '#22c55e' },
  ] : []

  const priorityData = stats ? [
    { name: 'P0', value: stats.p0_count },
    { name: 'P1', value: stats.p1_count },
    { name: 'P2', value: stats.p2_count },
  ] : []

  const activeIncidents = workItems
    .filter(w => w.status !== 'CLOSED')
    .sort((a, b) => {
      const po = { P0: 0, P1: 1, P2: 2, P3: 3 }
      return po[a.priority] - po[b.priority]
    })
    .slice(0, 8)

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload?.length) {
      return (
        <div style={{ background: 'var(--bg-3)', border: '1px solid var(--border)', padding: '8px 12px', borderRadius: '6px', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
          <div style={{ color: 'var(--text)' }}>{payload[0].name}</div>
          <div style={{ color: payload[0].fill || 'var(--accent)', fontWeight: 700 }}>{payload[0].value}</div>
        </div>
      )
    }
    return null
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h2>DASHBOARD</h2>
          <p>Real-time incident overview</p>
        </div>
        <button className="btn btn-ghost text-sm" onClick={() => { loadStats(); loadWorkItems() }}>
          ↻ Refresh
        </button>
      </div>
      <div className="page-content">

        {/* Stats Row */}
        <div className="stats-grid">
          <div className="stat-card p0">
            <div className="stat-label">P0 Critical</div>
            <div className="stat-value" style={{ color: 'var(--p0)' }}>{stats?.p0_count ?? '—'}</div>
            <div className="stat-sub">Active incidents</div>
          </div>
          <div className="stat-card p1">
            <div className="stat-label">P1 High</div>
            <div className="stat-value" style={{ color: 'var(--p1)' }}>{stats?.p1_count ?? '—'}</div>
            <div className="stat-sub">Active incidents</div>
          </div>
          <div className="stat-card p2">
            <div className="stat-label">P2 Medium</div>
            <div className="stat-value" style={{ color: 'var(--p2)' }}>{stats?.p2_count ?? '—'}</div>
            <div className="stat-sub">Active incidents</div>
          </div>
          <div className="stat-card blue">
            <div className="stat-label">Open</div>
            <div className="stat-value" style={{ color: 'var(--accent)' }}>{stats?.total_open ?? '—'}</div>
            <div className="stat-sub">Needs attention</div>
          </div>
          <div className="stat-card green">
            <div className="stat-label">Avg MTTR</div>
            <div className="stat-value" style={{ color: 'var(--green)', fontSize: 22 }}>
              {stats?.avg_mttr_minutes != null ? `${stats.avg_mttr_minutes}m` : '—'}
            </div>
            <div className="stat-sub">Mean time to repair</div>
          </div>
        </div>

        {/* Charts Row */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 24 }}>
          <div className="card">
            <div className="card-title">Incidents by Status</div>
            {statsLoading ? <div className="loading" style={{ height: 140 }}>Loading...</div> : (
              <ResponsiveContainer width="100%" height={140}>
                <BarChart data={statusData} barSize={28}>
                  <XAxis dataKey="name" tick={{ fill: 'var(--text-3)', fontSize: 10, fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: 'var(--text-3)', fontSize: 10 }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {statusData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
          <div className="card">
            <div className="card-title">Active by Priority</div>
            {statsLoading ? <div className="loading" style={{ height: 140 }}>Loading...</div> : (
              <ResponsiveContainer width="100%" height={140}>
                <BarChart data={priorityData} barSize={40}>
                  <XAxis dataKey="name" tick={{ fill: 'var(--text-3)', fontSize: 10, fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: 'var(--text-3)', fontSize: 10 }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {priorityData.map((entry, i) => <Cell key={i} fill={PRIORITY_COLORS[entry.name]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Live Incidents Feed */}
        <div className="card">
          <div className="section-header">
            <div className="card-title" style={{ marginBottom: 0 }}>Active Incidents</div>
            <button className="btn btn-ghost text-sm" onClick={() => navigate('/workitems')}>View all →</button>
          </div>
          <div className="table-wrap">
            {activeIncidents.length === 0 ? (
              <div className="empty">
                <div className="empty-icon">✓</div>
                <div>No active incidents</div>
              </div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Priority</th>
                    <th>Component</th>
                    <th>Title</th>
                    <th>Status</th>
                    <th>Signals</th>
                    <th>Age</th>
                  </tr>
                </thead>
                <tbody>
                  {activeIncidents.map(item => (
                    <tr key={item.id} onClick={() => navigate(`/workitems/${item.id}`)}>
                      <td><span className={`badge ${item.priority}`}>{item.priority}</span></td>
                      <td className="td-mono">{item.component_id}</td>
                      <td style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.title}</td>
                      <td><span className={`status-badge ${item.status}`}>{item.status}</span></td>
                      <td className="td-mono">{item.signal_count}</td>
                      <td className="td-mono">{formatDistanceToNow(new Date(item.created_at), { addSuffix: true })}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
