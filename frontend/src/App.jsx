import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'  
import { ProtectedRoute, GuestRoute, ROLE_DASHBOARDS } from '@/components/auth/ProtectedRoute'
import { useAuthStore } from '@/store/authStore'  
import { AdminDashboard, TeacherDashboard, BursarPage, ParentDashboard } from '@/pages/dashboard'
import  LoginPage  from '@/pages/auth/LoginPage'  
import './App.css'

function RootRedirect() {
  const { isAuthenticated, user } = useAuthStore()
  if (!isAuthenticated()) return <Navigate to="/login" replace /> 
  return <Navigate to={ROLE_DASHBOARDS[user?.role] || '/dashboard'} replace />
}

export default function App() {
  console.log('App.jsx is rendering.....')
  return (
    <BrowserRouter>  
      <Routes>
        <Route path="/" element={<RootRedirect />} />
        <Route path="/login" element={<GuestRoute><LoginPage /></GuestRoute>} />
        <Route path="/dashboard" element={<ProtectedRoute allowedRoles={['admin','superadmin']}><AdminDashboard /></ProtectedRoute>} />
        <Route path="/teacher" element={<ProtectedRoute allowedRoles={['teacher']}><TeacherDashboard /></ProtectedRoute>} />
        <Route path="/finance" element={<ProtectedRoute allowedRoles={['bursar']}><BursarPage /></ProtectedRoute>} />
        <Route path="/parent" element={<ProtectedRoute allowedRoles={['parent']}><ParentDashboard /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}