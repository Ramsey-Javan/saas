import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'

/**
 * Role-to-dashboard mapping.
 * After login, each role lands on their own dashboard.
 */
export const ROLE_DASHBOARDS = {
  superadmin: '/platform',
  admin: '/dashboard',
  teacher: '/teacher',
  bursar: '/finance',
  parent: '/parent',
}

/**
 * Wraps a route and redirects to login if not authenticated.
 * Optionally restricts to specific roles.
 *
 * Usage:
 *   <ProtectedRoute allowedRoles={['admin', 'teacher']}>
 *     <StudentsPage />
 *   </ProtectedRoute>
 */
export function ProtectedRoute({ children, allowedRoles }) {
  const { user, isAuthenticated } = useAuthStore()
  const location = useLocation()

  if (!isAuthenticated()) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    // Redirect to their own dashboard instead of showing 403
    const fallback = ROLE_DASHBOARDS[user.role] || '/dashboard'
    return <Navigate to={fallback} replace />
  }

  return children
}

/**
 * Redirects already-authenticated users away from /login.
 */
export function GuestRoute({ children }) {
  const { isAuthenticated, user } = useAuthStore()

  if (isAuthenticated()) {
    const dashboard = ROLE_DASHBOARDS[user.role] || '/dashboard'
    return <Navigate to={dashboard} replace />
  }

  return children
}