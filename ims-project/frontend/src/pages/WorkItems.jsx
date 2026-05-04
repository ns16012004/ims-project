import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import { useStore } from '../store/useStore'

const STATUSES = ['OPEN', 'INVESTIGATING', 'RESOLVED', 'CLOSED']
const PRIORITIES = ['P0', 'P1', 'P2']

export default function WorkItems() {
  const { workItems, workItemsLoading, workItemsError, statusFilter, priorityFilter, setFilter, loadWorkItems } = useStore()
  const navigate = useNavigate()

  useEffect(() => { loadWorkItems() }, [])

  return (
    <>
      <div className="page-header">
        <div>
          <h2>WORK ITEMS</h2>
          <p>{workItems.length} incidents</p>
        </div>
        <button className="btn btn-ghost" onClick={loadWorkItems}>↻ Refresh</button>
      </div>
      <div className="page-content">
        {/* Filters */}
        <div className="card" style={{ marginBottom: 16, padding: '12px 16px' }}>
          <div className="filters">
            <span style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', marginRight: 4 }}>STATUS:</span>
            <button className={`filter-btn ${!statusFilter ? 'active' : ''}`} onClick={() => setFilter('status', null)}>All</button>
            {STATUSES.map(s => (
              <button key={s} className={`filter-btn ${statusFilter === s ? 'active' : ''}`} onClick={() => setFilter('status', s)}>{s}</button>
            ))}
            <div style={{ width: 1, height: 16, background: 'var(--border)', margin: '0 8px' }} />
            <span style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', marginRight: 4 }}>PRIORITY:</span>
            <button className={`filter-btn ${!priorityFilter ? 'active' : ''}`} onClick={() => setFilter('priority', null)}>All</button>
            {PRIORITIES.map(p => (
              <button key={p} className={`filter-btn ${priorityFilter === p ? 'active' : ''}`} onClick={() => setFilter('priority', p)}>{p}</button>
            ))}
          </div>
        </div>

        <div className="card">
          {workItemsLoading ? (
            <div className="loading">Loading incidents...</div>
          ) : workItemsError ? (
            <div className="alert-banner error">{workItemsError}</div>
          ) : workItems.length === 0 ? (
            <div className="empty">
              <div className="empty-icon">✓</div>
              <div>No work items found</div>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Priority</th>
                    <th>ID</th>
                    <th>Component</th>
                    <th>Title</th>
                    <th>Status</th>
                    <th>Signals</th>
                    <th>Created</th>
                    <th>MTTR</th>
                  </tr>
                </thead>
                <tbody>
                  {workItems.map(item => (
                    <tr key={item.id} onClick={() => navigate(`/workitems/${item.id}`)}>
                      <td><span className={`badge ${item.priority}`}>{item.priority}</span></td>
                      <td className="td-mono" style={{ fontSize: 10 }}>{item.id.slice(0, 8)}…</td>
                      <td className="td-mono">{item.component_id}</td>
                      <td style={{ maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.title}</td>
                      <td><span className={`status-badge ${item.status}`}>{item.status}</span></td>
                      <td className="td-mono">{item.signal_count}</td>
                      <td className="td-mono">{formatDistanceToNow(new Date(item.created_at), { addSuffix: true })}</td>
                      <td className="td-mono">{item.mttr_minutes != null ? `${item.mttr_minutes}m` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
