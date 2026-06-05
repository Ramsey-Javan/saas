import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'  
import { ProtectedRoute, GuestRoute, ROLE_DASHBOARDS } from '@/components/auth/ProtectedRoute'
import { useAuthStore } from '@/store/authStore'  
import { AdminDashboard, TeacherDashboard, ParentDashboard } from '@/pages/dashboard'
import { StudentsPage, StudentDetailPage, AdmitStudentPage, BulkImportPage, StudentIdCardPage } from '@/pages/students'
import BursarDashboard from '@/pages/finance/BursarDashboard'
import InvoicesListPage from '@/pages/finance/InvoicesListPage'
import FeeStructuresPage from '@/pages/finance/FeeStructuresPage'
import InvoiceGenerationPage from '@/pages/finance/InvoiceGenerationPage'
import DefaultersListPage from '@/pages/finance/DefaultersListPage'
import PaymentsPage from '@/pages/finance/PaymentsPage'
import ReceiptsPage from '@/pages/finance/ReceiptsPage'
import StudentStatementPage from '@/pages/finance/StudentStatementPage'
import PendingChequesPage from '@/pages/finance/PendingChequesPage'
import WaiverPoliciesPage from '@/pages/finance/WaiverPoliciesPage'
import WaiversReportPage from '@/pages/finance/WaiversReportPage'
import WaiversDashboardPage from '@/pages/finance/WaiversDashboardPage'
import AcademicsDashboard from '@/pages/academics/AcademicsDashboard'
import CurriculumPage from '@/pages/academics/CurriculumPage'
import AssignmentsPage from '@/pages/academics/AssignmentsPage'
import GradesDashboard from '@/pages/academics/GradesDashboard'
import GradeSheetPage from '@/pages/academics/GradeSheetPage'
import AttendanceDashboard from '@/pages/academics/AttendanceDashboard'
import MarkAttendancePage from '@/pages/academics/MarkAttendancePage'
import ClassAttendancePage from '@/pages/academics/ClassAttendancePage'
import TimetablePage from '@/pages/academics/TimetablePage'
import ReportCardsDashboard from '@/pages/academics/ReportCardsDashboard'
import ReportCardDetailPage from '@/pages/academics/ReportCardDetailPage'
import ExamsDashboard from '@/pages/academics/ExamsDashboard'
import ExamMarksSheetPage from '@/pages/academics/ExamMarksSheetPage'
import ExamResultsPage from '@/pages/academics/ExamResultsPage'
import NationalExamsDashboard from '@/pages/academics/NationalExamsDashboard'
import NationalExamDetailPage from '@/pages/academics/NationalExamDetailPage'
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
        <Route path="/finance" element={<ProtectedShell allowedRoles={['admin','superadmin','bursar']}><BursarDashboard /></ProtectedShell>} />
        <Route path="/finance/payments" element={<ProtectedShell allowedRoles={['admin','superadmin','bursar']}><PaymentsPage /></ProtectedShell>} />
        <Route path="/finance/receipts" element={<ProtectedShell allowedRoles={['admin','superadmin','bursar']}><ReceiptsPage /></ProtectedShell>} />
        <Route path="/finance/cheques" element={<ProtectedShell allowedRoles={['admin','superadmin','bursar']}><PendingChequesPage /></ProtectedShell>} />
        <Route path="/finance/structures" element={<ProtectedShell allowedRoles={['admin','superadmin','bursar']}><FeeStructuresPage /></ProtectedShell>} />
        <Route path="/finance/invoices/generate" element={<ProtectedShell allowedRoles={['admin','superadmin','bursar']}><InvoiceGenerationPage /></ProtectedShell>} />
        <Route path="/finance/invoices" element={<ProtectedShell allowedRoles={['admin','superadmin','bursar']}><InvoicesListPage /></ProtectedShell>} />
        <Route path="/finance/defaulters" element={<ProtectedShell allowedRoles={['admin','superadmin','bursar']}><DefaultersListPage /></ProtectedShell>} />
        <Route path="/finance/waivers" element={<ProtectedShell allowedRoles={['admin','superadmin','bursar']}><WaiversReportPage /></ProtectedShell>} />
        <Route path="/finance/waivers-dashboard" element={<ProtectedShell allowedRoles={['admin','superadmin','bursar']}><WaiversDashboardPage /></ProtectedShell>} />
        <Route path="/finance/waiver-policies" element={<ProtectedShell allowedRoles={['admin','superadmin','bursar']}><WaiverPoliciesPage /></ProtectedShell>} />
        <Route path="/finance/students/:studentId/statement" element={<ProtectedShell allowedRoles={['admin','superadmin','bursar','parent']}><StudentStatementPage /></ProtectedShell>} />
        <Route path="/academics" element={<ProtectedShell allowedRoles={['admin','superadmin','teacher']}><AcademicsDashboard /></ProtectedShell>} />
        <Route path="/academics/curriculum" element={<ProtectedShell allowedRoles={['admin','superadmin']}><CurriculumPage /></ProtectedShell>} />
        <Route path="/academics/assignments" element={<ProtectedShell allowedRoles={['admin','superadmin']}><AssignmentsPage /></ProtectedShell>} />
        <Route path="/academics/grades" element={<ProtectedShell allowedRoles={['admin','superadmin','teacher']}><GradesDashboard /></ProtectedShell>} />
        <Route path="/academics/grades/:classroomId/:subjectId" element={<ProtectedShell allowedRoles={['admin','superadmin','teacher']}><GradeSheetPage /></ProtectedShell>} />
        <Route path="/academics/attendance" element={<ProtectedShell allowedRoles={['admin','superadmin','teacher']}><AttendanceDashboard /></ProtectedShell>} />
        <Route path="/academics/attendance/mark" element={<ProtectedShell allowedRoles={['admin','superadmin','teacher']}><MarkAttendancePage /></ProtectedShell>} />
        <Route path="/academics/attendance/:classroomId" element={<ProtectedShell allowedRoles={['admin','superadmin','teacher']}><ClassAttendancePage /></ProtectedShell>} />
        <Route path="/academics/timetable" element={<ProtectedShell allowedRoles={['admin','superadmin','teacher','parent']}><TimetablePage /></ProtectedShell>} />
        <Route path="/academics/report-cards" element={<ProtectedShell allowedRoles={['admin','superadmin','teacher']}><ReportCardsDashboard /></ProtectedShell>} />
        <Route path="/academics/report-cards/:id" element={<ProtectedShell allowedRoles={['admin','superadmin','teacher','parent']}><ReportCardDetailPage /></ProtectedShell>} />
        <Route path="/academics/exams" element={<ProtectedShell allowedRoles={['admin','superadmin','teacher']}><ExamsDashboard /></ProtectedShell>} />
        <Route path="/academics/exams/:examId" element={<ProtectedShell allowedRoles={['admin','superadmin','teacher']}><ExamMarksSheetPage /></ProtectedShell>} />
        <Route path="/academics/exams/:examId/results" element={<ProtectedShell allowedRoles={['admin','superadmin','teacher']}><ExamResultsPage /></ProtectedShell>} />
        <Route path="/academics/national-exams" element={<ProtectedShell allowedRoles={['admin','superadmin']}><NationalExamsDashboard /></ProtectedShell>} />
        <Route path="/academics/national-exams/:sessionId" element={<ProtectedShell allowedRoles={['admin','superadmin']}><NationalExamDetailPage /></ProtectedShell>} />
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
