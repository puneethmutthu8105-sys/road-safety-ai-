import axios from 'axios'
import { useAuthStore } from '../store/authStore'

// In production (Render), VITE_API_URL points to the backend service URL.
// In local dev, it falls back to '/api/v1' (proxied by Vite to localhost:8000).
const BASE_URL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api/v1`
  : '/api/v1'

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api

// ── Auth ──────────────────────────────────────────────────────────────────────
export const authApi = {
  login: (email: string, password: string) =>
    api.post('/auth/login', new URLSearchParams({ username: email, password }), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    }),
  register: (name: string, email: string, password: string) =>
    api.post('/auth/register', { name, email, password }),
}

// ── Traffic ───────────────────────────────────────────────────────────────────
export const trafficApi = {
  getSnapshot: () => api.get('/traffic/snapshot'),
  analyze: () => api.post('/traffic/analyze'),
}

// ── Accidents ─────────────────────────────────────────────────────────────────
export const accidentApi = {
  getHistory: (limit = 100) => api.get(`/accidents/history?limit=${limit}`),
  reportAccident: (data: any) => api.post('/accidents/report', data),
  predictRisk: (lat: number, lng: number) => api.post('/accidents/predict-risk', { latitude: lat, longitude: lng }),
  getHotspots: () => api.get('/accidents/hotspots'),
  detectHotspots: () => api.post('/accidents/detect-hotspots'),
}

// ── Emergency ─────────────────────────────────────────────────────────────────
export const emergencyApi = {
  createReport: (data: any) => api.post('/emergency/report', data),
  listReports: (status?: string) => api.get('/emergency/reports' + (status ? `?status=${status}` : '')),
  getReport: (id: string) => api.get(`/emergency/reports/${id}`),
  updateStatus: (id: string, status: string) => api.patch(`/emergency/reports/${id}/status?status=${status}`),
  getAlerts: () => api.get('/emergency/alerts'),
  getHITLQueue: () => api.get('/emergency/hitl-queue'),
  submitHITLDecision: (id: string, decision: string, notes?: string) =>
    api.post(`/emergency/hitl-queue/${id}/decide`, { decision, notes }),
}

// ── Ambulance ─────────────────────────────────────────────────────────────────
export const ambulanceApi = {
  getFleet: () => api.get('/ambulance/fleet'),
  coordinate: (data: any) => api.post('/ambulance/coordinate', data),
}

// ── Reports ───────────────────────────────────────────────────────────────────
export const reportsApi = {
  getSummary: () => api.get('/reports/summary'),
  getSeverityDistribution: () => api.get('/reports/severity-distribution'),
  getAgentPerformance: () => api.get('/reports/agent-performance'),
}

// ── Admin ─────────────────────────────────────────────────────────────────────
export const adminApi = {
  getDashboard: () => api.get('/admin/dashboard'),
  listUsers: () => api.get('/admin/users'),
  listAgentRuns: () => api.get('/admin/agent-runs'),
}

// ── Road Conditions ───────────────────────────────────────────────────────────
export const roadConditionApi = {
  getConditions: () => api.get('/road-conditions'),
  analyze: () => api.post('/road-conditions/analyze'),
}
