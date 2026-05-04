import { useEffect } from 'react'
import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { useStore } from './store/useStore'
import { useWebSocket } from './hooks/useWebSocket'
import Dashboard from './pages/Dashboard'
import WorkItems from './pages/WorkItems'
import WorkItemDetail from './pages/WorkItemDetail'
import SignalTester from './pages/SignalTester'
import HealthPage from './pages/HealthPage'

const NAV = [
  { to: '/', label: 'Dashboard', icon: '◈' },
  { to: '/workitems', label: 'Work Items', icon: '⊞' },
  { to: '/signals', label: 'Signal Tester', icon: '⚡' },
  { to: '/health', label: 'Health', icon: '♦' },
]

export default function App() {
  const { loadHealth, health, loadStats, loadWorkItems } = useStore()
  useWebSocket()

  useEffect(() => {
    loadHealth()
    loadStats()
    loadWorkItems()

    // Poll every 15s
    const interval = setInterval(() => {
      loadHealth()
      loadStats()
      loadWorkItems()
    }, 15000)

    return () => clearInterval(interval)
  }, [])

  const isHealthy = health?.status === 'healthy'

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h1>IMS</h1>
          <p>Incident Management</p>
        </div>
        <nav className="sidebar-nav">
          {NAV.map(n => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === '/'}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <span className="icon">{n.icon}</span>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-status">
          <span className="status-dot" style={{ background: isHealthy ? 'var(--green)' : 'var(--p0)' }} />
          {health ? health.status.toUpperCase() : 'CONNECTING...'}
        </div>
      </aside>

      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/workitems" element={<WorkItems />} />
          <Route path="/workitems/:id" element={<WorkItemDetail />} />
          <Route path="/signals" element={<SignalTester />} />
          <Route path="/health" element={<HealthPage />} />
        </Routes>
      </main>

      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: 'var(--bg-3)',
            color: 'var(--text)',
            border: '1px solid var(--border)',
            fontFamily: 'var(--font-mono)',
            fontSize: '12px',
          },
        }}
      />
    </div>
  )
}
