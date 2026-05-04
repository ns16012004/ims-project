import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
})

api.interceptors.response.use(
  r => r,
  err => {
    const msg = err.response?.data?.detail || err.message || 'Request failed'
    return Promise.reject(new Error(msg))
  }
)

// Work Items
export const fetchWorkItems = (params = {}) =>
  api.get('/workitems', { params }).then(r => r.data)

export const fetchWorkItem = (id) =>
  api.get(`/workitems/${id}`).then(r => r.data)

export const fetchDashboardStats = () =>
  api.get('/workitems/stats').then(r => r.data)

export const updateWorkItemStatus = (id, status) =>
  api.patch(`/workitems/${id}/status`, { status }).then(r => r.data)

export const submitRCA = (id, rcaData) =>
  api.post(`/workitems/${id}/rca`, rcaData).then(r => r.data)

// Signals
export const ingestSignal = (payload) =>
  api.post('/signals', payload).then(r => r.data)

export const ingestSignalBatch = (payloads) =>
  api.post('/signals/batch', payloads).then(r => r.data)

export const fetchSignalsForWorkItem = (workItemId) =>
  api.get(`/signals/${workItemId}`).then(r => r.data)

export const fetchQueueStats = () =>
  api.get('/signals/queue/stats').then(r => r.data)

// Health
export const fetchHealth = () =>
  axios.get('/health').then(r => r.data)
