import { useEffect, useRef } from 'react'
import { useStore } from '../store/useStore'

export function useWebSocket() {
  const wsRef = useRef(null)
  const { refreshAll } = useStore()

  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${proto}://${window.location.host}/ws/live`

    const connect = () => {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.type === 'stats') {
            useStore.setState({ queueStats: msg.data })
          }
          if (msg.type === 'refresh') {
            refreshAll()
          }
        } catch {}
      }

      ws.onclose = () => {
        // Reconnect after 3s
        setTimeout(connect, 3000)
      }
    }

    connect()
    return () => {
      if (wsRef.current) wsRef.current.close()
    }
  }, [])
}
