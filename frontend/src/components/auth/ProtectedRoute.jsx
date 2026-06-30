import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'

export const ROLE_DASHBOARDS = {
  superadmin: '/platform',
  admin: '/dashboard',
  teacher: '/teacher',
  bursar: '/finance',
  finance: '/finance',
  parent: '/parent',
}

function useHydratedAuth() {
  // zustand's persist middleware hydrates synchronously from sessionStorage
  // on store creation (unlike async storages), but we still gate on
  // isHydrated to be explicit and to give a single, shared "are we ready
  // to make routing decisions yet" signal across all the route guards below.
  const { user, accessToken, isHydrated } = useAuthStore()
  return { user, accessToken, isHydrated }
}

function FullScreenSpinner() {
  return (
    <div className="flex h-screen items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
    </div>
  )
}

export function RootRedirect() {
  const { user, accessToken, isHydrated } = useHydratedAuth()

  if (!isHydrated) {
    return <FullScreenSpinner />
  }

  const isAuthenticated = !!user && !!accessToken

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <Navigate to={ROLE_DASHBOARDS[user.role] || '/dashboard'} replace />
}

export function ProtectedRoute({ children, allowedRoles }) {
  const { user, accessToken, isHydrated } = useHydratedAuth()
  const location = useLocation()

  if (!isHydrated) {
    return <FullScreenSpinner />
  }

  const isAuthenticated = !!user && !!accessToken

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    const fallback = ROLE_DASHBOARDS[user.role] || '/dashboard'
    return <Navigate to={fallback} replace />
  }

  return children
}

export function GuestRoute({ children }) {
  const { user, accessToken, isHydrated } = useHydratedAuth()

  if (!isHydrated) {
    return <FullScreenSpinner />
  }

  const isAuthenticated = !!user && !!accessToken

  if (isAuthenticated) {
    const dashboard = ROLE_DASHBOARDS[user.role] || '/dashboard'
    return <Navigate to={dashboard} replace />
  }

  return children
}