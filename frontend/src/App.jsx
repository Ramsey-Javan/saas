import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'  
import { ProtectedRoute, GuestRoute, ROLE_DASHBOARDS, RootRedirect } from '@/components/auth/ProtectedRoute'
import { useAuthStore } from '@/store/authStore'  
import { AdminDashboard, TeacherDashboard, ParentDashboard } from '@/pages/dashboard'
import { StudentsPage, StudentDetailPage, AdmitStudentPage, BulkImportPage, StudentIdCardPage, ClassroomsPage,MyHomeClassPage } from '@/pages/students'
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
import {
  CommunicationDashboard,
  ComposeMessagePage,
  TemplatesPage,
  ScheduledMessagesPage,
  MessageLogsPage,
  NotificationsPage,
} from '@/pages/communication'
import { StaffListPage, AddStaffPage, StaffDetailPage, EditStaffPage } from '@/pages/staff'
import { SchoolProfileSettingsPage } from '@/pages/settings'
import { SuperadminDashboard, PlatformSchoolDetailPage } from '@/pages/platform'
import { PublicSignupPage } from '@/pages/public'
import AcceptInvitePage from '@/pages/auth/AcceptInvitePage'
import AppShell from '@/components/layout/AppShell'
import LoginPage from '@/pages/auth/LoginPage'  
import './App.css'

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
        <Route path="/signup" element={<GuestRoute><PublicSignupPage /></GuestRoute>} />
        <Route path="/accept-invite" element={<GuestRoute><AcceptInvitePage /></GuestRoute>} />
        <Route path="/dashboard" element={<ProtectedShell allowedRoles={['admin']}><AdminDashboard /></ProtectedShell>} />
        <Route path="/teacher" element={<ProtectedShell allowedRoles={['teacher']}><TeacherDashboard /></ProtectedShell>} />
        <Route path="/finance" element={<ProtectedShell allowedRoles={['admin','bursar']}><BursarDashboard /></ProtectedShell>} />
        <Route path="/finance/payments" element={<ProtectedShell allowedRoles={['admin','bursar']}><PaymentsPage /></ProtectedShell>} />
        <Route path="/finance/receipts" element={<ProtectedShell allowedRoles={['admin','bursar']}><ReceiptsPage /></ProtectedShell>} />
        <Route path="/finance/cheques" element={<ProtectedShell allowedRoles={['admin','bursar']}><PendingChequesPage /></ProtectedShell>} />
        <Route path="/finance/structures" element={<ProtectedShell allowedRoles={['admin','bursar']}><FeeStructuresPage /></ProtectedShell>} />
        <Route path="/finance/invoices/generate" element={<ProtectedShell allowedRoles={['admin','bursar']}><InvoiceGenerationPage /></ProtectedShell>} />
        <Route path="/finance/invoices" element={<ProtectedShell allowedRoles={['admin','bursar']}><InvoicesListPage /></ProtectedShell>} />
        <Route path="/finance/defaulters" element={<ProtectedShell allowedRoles={['admin','bursar']}><DefaultersListPage /></ProtectedShell>} />
        <Route path="/finance/waivers" element={<ProtectedShell allowedRoles={['admin','bursar']}><WaiversReportPage /></ProtectedShell>} />
        <Route path="/finance/waivers-dashboard" element={<ProtectedShell allowedRoles={['admin','bursar']}><WaiversDashboardPage /></ProtectedShell>} />
        <Route path="/finance/waiver-policies" element={<ProtectedShell allowedRoles={['admin','bursar']}><WaiverPoliciesPage /></ProtectedShell>} />
        <Route path="/finance/students/:studentId/statement" element={<ProtectedShell allowedRoles={['admin','bursar','parent']}><StudentStatementPage /></ProtectedShell>} />
        <Route path="/academics" element={<ProtectedShell allowedRoles={['admin','teacher']}><AcademicsDashboard /></ProtectedShell>} />
        <Route path="/academics/curriculum" element={<ProtectedShell allowedRoles={['admin']}><CurriculumPage /></ProtectedShell>} />
        <Route path="/academics/assignments" element={<ProtectedShell allowedRoles={['admin']}><AssignmentsPage /></ProtectedShell>} />
        <Route path="/academics/grades" element={<ProtectedShell allowedRoles={['admin','teacher']}><GradesDashboard /></ProtectedShell>} />
        <Route path="/academics/grades/:classroomId/:subjectId" element={<ProtectedShell allowedRoles={['admin','teacher']}><GradeSheetPage /></ProtectedShell>} />
        <Route path="/academics/attendance" element={<ProtectedShell allowedRoles={['admin','teacher']}><AttendanceDashboard /></ProtectedShell>} />
        <Route path="/academics/attendance/mark" element={<ProtectedShell allowedRoles={['admin','teacher']}><MarkAttendancePage /></ProtectedShell>} />
        <Route path="/academics/attendance/:classroomId" element={<ProtectedShell allowedRoles={['admin','teacher']}><ClassAttendancePage /></ProtectedShell>} />
        <Route path="/academics/timetable" element={<ProtectedShell allowedRoles={['admin','teacher','parent']}><TimetablePage /></ProtectedShell>} />
        <Route path="/academics/report-cards" element={<ProtectedShell allowedRoles={['admin','teacher']}><ReportCardsDashboard /></ProtectedShell>} />
        <Route path="/academics/report-cards/:id" element={<ProtectedShell allowedRoles={['admin','teacher','parent']}><ReportCardDetailPage /></ProtectedShell>} />
        <Route path="/teacher/home-class" element={<ProtectedShell allowedRoles={['teacher']}><MyHomeClassPage /></ProtectedShell>} />
        <Route path="/academics/exams" element={<ProtectedShell allowedRoles={['admin','teacher']}><ExamsDashboard /></ProtectedShell>} />
        <Route path="/academics/exams/:examId" element={<ProtectedShell allowedRoles={['admin','teacher']}><ExamMarksSheetPage /></ProtectedShell>} />
        <Route path="/academics/exams/:examId/results" element={<ProtectedShell allowedRoles={['admin','teacher']}><ExamResultsPage /></ProtectedShell>} />
        <Route path="/academics/national-exams" element={<ProtectedShell allowedRoles={['admin']}><NationalExamsDashboard /></ProtectedShell>} />
        <Route path="/academics/national-exams/:sessionId" element={<ProtectedShell allowedRoles={['admin']}><NationalExamDetailPage /></ProtectedShell>} />
        <Route path="/parent" element={<ProtectedShell allowedRoles={['parent']}><ParentDashboard /></ProtectedShell>} />
        <Route path="/students" element={<ProtectedShell allowedRoles={['admin','teacher','bursar']}><StudentsPage /></ProtectedShell>} />
        <Route path="/students/new" element={<ProtectedShell allowedRoles={['admin']}><AdmitStudentPage /></ProtectedShell>} />
        <Route path="/students/import" element={<ProtectedShell allowedRoles={['admin']}><BulkImportPage /></ProtectedShell>} />
        <Route path="/students/classrooms" element={<ProtectedShell allowedRoles={['admin']}><ClassroomsPage /></ProtectedShell>} />
        <Route path="/students/:id/id-card" element={<ProtectedShell allowedRoles={['admin']}><StudentIdCardPage /></ProtectedShell>} />
        <Route path="/students/:id" element={<ProtectedShell allowedRoles={['admin','teacher','parent','bursar']}><StudentDetailPage /></ProtectedShell>} />
        <Route path="/students/:id/edit" element={<ProtectedShell allowedRoles={['admin']}><AdmitStudentPage /></ProtectedShell>} />
        <Route path="/communication" element={<ProtectedShell allowedRoles={['admin','teacher']}><CommunicationDashboard /></ProtectedShell>} />
        <Route path="/communication/compose" element={<ProtectedShell allowedRoles={['admin','teacher']}><ComposeMessagePage /></ProtectedShell>} />
        <Route path="/communication/templates" element={<ProtectedShell allowedRoles={['admin']}><TemplatesPage /></ProtectedShell>} />
        <Route path="/communication/scheduled" element={<ProtectedShell allowedRoles={['admin','teacher']}><ScheduledMessagesPage /></ProtectedShell>} />
        <Route path="/communication/logs" element={<ProtectedShell allowedRoles={['admin','teacher']}><MessageLogsPage /></ProtectedShell>} />
        <Route path="/communication/notifications" element={<ProtectedShell allowedRoles={['admin','teacher','bursar','parent']}><NotificationsPage /></ProtectedShell>} />
        <Route path="/staff" element={<ProtectedShell allowedRoles={['admin']}><StaffListPage /></ProtectedShell>} />
        <Route path="/staff/new" element={<ProtectedShell allowedRoles={['admin']}><AddStaffPage /></ProtectedShell>} />
        <Route path="/staff/:id" element={<ProtectedShell allowedRoles={['admin']}><StaffDetailPage /></ProtectedShell>} />
        <Route path="/staff/:id/edit" element={<ProtectedShell allowedRoles={['admin']}><EditStaffPage /></ProtectedShell>} />   
        <Route path="/settings/school-profile" element={<ProtectedShell allowedRoles={['admin']}><SchoolProfileSettingsPage /></ProtectedShell>} />
        <Route path="/platform" element={<ProtectedShell allowedRoles={['superadmin']}><SuperadminDashboard /></ProtectedShell>} />
        <Route path="/platform/schools" element={<ProtectedShell allowedRoles={['superadmin']}><SuperadminDashboard /></ProtectedShell>} />
        <Route path="/platform/schools/:id" element={<ProtectedShell allowedRoles={['superadmin']}><PlatformSchoolDetailPage /></ProtectedShell>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}