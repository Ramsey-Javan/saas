import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'  
import { ProtectedRoute, GuestRoute, ROLE_DASHBOARDS } from '@/components/auth/ProtectedRoute'
import { useAuthStore } from '@/store/authStore'  
import { AdminDashboard, TeacherDashboard, BursarPage, ParentDashboard } from '@/pages/dashboard'
import { StudentsPage, StudentDetailPage, AdmitStudentPage, BulkImportPage, StudentIdCardPage } from '@/pages/students'
import AppShell from '@/components/layout/AppShell'
import  LoginPage  from '@/pages/auth/LoginPage'  
import './App.css'

function RootRedirect() {
  const { isAuthenticated, user } = useAuthStore()
  if (!isAuthenticated()) return <Navigate to="/login" replace /> 
  return <Navigate to={ROLE_DASHBOARDS[user?.role] || '/dashboard'} replace />
}

function ProtectedShell({ allowedRoles, children }) {
  return (
    <ProtectedRoute allowedRoles={allowedRoles}>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  )
}

export default function App() {
  console.log('App.jsx is rendering.....')
  return (
    <BrowserRouter>  
      <Routes>
        <Route path="/" element={<RootRedirect />} />
        <Route path="/login" element={<GuestRoute><LoginPage /></GuestRoute>} />
        <Route path="/dashboard" element={<ProtectedShell allowedRoles={['admin','superadmin']}><AdminDashboard /></ProtectedShell>} />
        <Route path="/teacher" element={<ProtectedShell allowedRoles={['teacher']}><TeacherDashboard /></ProtectedShell>} />
        <Route path="/finance" element={<ProtectedShell allowedRoles={['bursar']}><BursarPage /></ProtectedShell>} />
        <Route path="/parent" element={<ProtectedShell allowedRoles={['parent']}><ParentDashboard /></ProtectedShell>} />
        <Route path="/students" element={<ProtectedShell allowedRoles={['admin','bursar','teacher']}><StudentsPage /></ProtectedShell>} />
        <Route path="/students/new" element={<ProtectedShell allowedRoles={['admin','bursar']}><AdmitStudentPage /></ProtectedShell>} />
        <Route path="/students/import" element={<ProtectedShell allowedRoles={['admin','bursar']}><BulkImportPage /></ProtectedShell>} />
        <Route path="/students/:id/id-card" element={<ProtectedShell allowedRoles={['admin','bursar']}><StudentIdCardPage /></ProtectedShell>} />
        <Route path="/students/:id" element={<ProtectedShell allowedRoles={['admin','bursar','teacher','parent']}><StudentDetailPage /></ProtectedShell>} />
        <Route path="/students/:id/edit" element={<ProtectedShell allowedRoles={['admin','bursar']}><AdmitStudentPage /></ProtectedShell>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
