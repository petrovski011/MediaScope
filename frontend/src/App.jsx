import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useAuth } from './store/auth'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Articles from './pages/Articles'
import ArticleDetail from './pages/ArticleDetail'
import Sources from './pages/Sources'
import SourceDetail from './pages/SourceDetail'
import Narratives from './pages/Narratives'
import Topics from './pages/Topics'
import Framing from './pages/Framing'
import Anomalies from './pages/Anomalies'
import Coordination from './pages/Coordination'
import Political from './pages/Political'
import Methodology from './pages/Methodology'
import Alerts from './pages/Alerts'
import Admin from './pages/Admin'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } }
})

function AuthGuard({ children }) {
  const { token, user, fetchMe } = useAuth()
  useEffect(() => { if (token && !user) fetchMe() }, [token])
  if (!token) return <Navigate to="/login" replace />
  return children
}

function AdminGuard({ children }) {
  const { token, user, fetchMe } = useAuth()
  useEffect(() => { if (token && !user) fetchMe() }, [token])
  if (!token) return <Navigate to="/login" replace />
  if (user && user.role !== 'admin') return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<AuthGuard><Layout /></AuthGuard>}>
            <Route index element={<Dashboard />} />
            <Route path="articles" element={<Articles />} />
            <Route path="articles/:id" element={<ArticleDetail />} />
            <Route path="sources" element={<Sources />} />
            <Route path="sources/:id" element={<SourceDetail />} />
            <Route path="narratives" element={<Narratives />} />
            <Route path="topics" element={<Topics />} />
            <Route path="framing" element={<Framing />} />
            <Route path="anomalies" element={<Anomalies />} />
            <Route path="coordination" element={<Coordination />} />
            <Route path="political" element={<Political />} />
            <Route path="metodologija" element={<Methodology />} />
            <Route path="alerts" element={<Alerts />} />
            <Route path="admin" element={<AdminGuard><Admin /></AdminGuard>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
