import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'  
import { ProtectedRoute, GuestRoute, RootRedirect } from '@/components/auth/ProtectedRoute'
import { AdminDashboard, TeacherDashboard, ParentDashboard } from '@/pages/dashboard'
import { StudentsPage, StudentDetailPage, AdmitStudentPage, BulkImportPage, StudentIdCardPage, ClassroomsPage, MyHomeClassPage } from '@/pages/students'
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
import TimetablePage from "@/pages/academics/timetable/TimetablePage";
import ReportCardDetailPage from '@/pages/academics/ReportCardDetailPage'
import ReportCardsDashboard from '@/pages/academics/ReportCardsDashboard'
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
import { SchoolProfileSettingsPage, ChangePasswordSettingsPage } from '@/pages/settings'
import { SuperadminDashboard, PlatformSchoolDetailPage } from '@/pages/platform'
import { ForgotPasswordPage, ResetPasswordPage } from '@/pages/auth'
import { PublicSignupPage } from '@/pages/public'
import AcceptInvitePage from '@/pages/auth/AcceptInvitePage'
import AppShell from '@/components/layout/AppShell'
import LoginPage from '@/pages/auth/LoginPage'  

import { 
  AnalyticsDashboard, 
  ClassPerformancePage, 
  StudentProfilePage, 
  SubjectAnalysisPage,
  SchoolPerformancePage,
  EarlyWarningPage, 
  ClassSubjectAnalysisPage,
  SubjectTeacherDetailPage
} from '@/pages/analytics'

import './App.css'

// Fallback wrapper to prevent white-screens on missing imports or render errors
function SafeRoute({ children, fallback }) {
  try {
    return children;
  } catch (e) {
    console.error('Route render error:', e);
    return fallback || <div className="p-8 text-center text-red-600">Failed to load page.</div>;
  }
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
        <Route path="/" element={<SafeRoute><RootRedirect /></SafeRoute>} />
        <Route path="/login" element={<GuestRoute><SafeRoute><LoginPage /></SafeRoute></GuestRoute>} />
        <Route path="/signup" element={<GuestRoute><SafeRoute><PublicSignupPage /></SafeRoute></GuestRoute>} />
        <Route path="/accept-invite" element={<GuestRoute><SafeRoute><AcceptInvitePage /></SafeRoute></GuestRoute>} />
        
        <Route path="/dashboard" element={
          <ProtectedShell allowedRoles={['admin']}>
            <SafeRoute><AdminDashboard /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/teacher" element={
          <ProtectedShell allowedRoles={['teacher']}>
            <SafeRoute><TeacherDashboard /></SafeRoute>
          </ProtectedShell>
        } />
        
        {/* FINANCE ROUTES */}
        <Route path="/finance" element={
          <ProtectedShell allowedRoles={['admin','bursar']}>
            <SafeRoute><BursarDashboard /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/finance/payments" element={
          <ProtectedShell allowedRoles={['admin','bursar']}>
            <SafeRoute><PaymentsPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/finance/receipts" element={
          <ProtectedShell allowedRoles={['admin','bursar']}>
            <SafeRoute><ReceiptsPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/finance/cheques" element={
          <ProtectedShell allowedRoles={['admin','bursar']}>
            <SafeRoute><PendingChequesPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/finance/structures" element={
          <ProtectedShell allowedRoles={['admin','bursar']}>
            <SafeRoute><FeeStructuresPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/finance/invoices/generate" element={
          <ProtectedShell allowedRoles={['admin','bursar']}>
            <SafeRoute><InvoiceGenerationPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/finance/invoices" element={
          <ProtectedShell allowedRoles={['admin','bursar']}>
            <SafeRoute><InvoicesListPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/finance/defaulters" element={
          <ProtectedShell allowedRoles={['admin','bursar']}>
            <SafeRoute><DefaultersListPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/finance/waivers" element={
          <ProtectedShell allowedRoles={['admin','bursar']}>
            <SafeRoute><WaiversReportPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/finance/waivers-dashboard" element={
          <ProtectedShell allowedRoles={['admin','bursar']}>
            <SafeRoute><WaiversDashboardPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/finance/waiver-policies" element={
          <ProtectedShell allowedRoles={['admin','bursar']}>
            <SafeRoute><WaiverPoliciesPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/finance/students/:studentId/statement" element={
          <ProtectedShell allowedRoles={['admin','bursar','parent']}>
            <SafeRoute><StudentStatementPage /></SafeRoute>
          </ProtectedShell>
        } />
        
        {/* ACADEMICS ROUTES */}
        <Route path="/academics" element={
          <ProtectedShell allowedRoles={['admin','teacher']}>
            <SafeRoute><AcademicsDashboard /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/academics/curriculum" element={
          <ProtectedShell allowedRoles={['admin']}>
            <SafeRoute><CurriculumPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/academics/assignments" element={
          <ProtectedShell allowedRoles={['admin']}>
            <SafeRoute><AssignmentsPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/academics/grades" element={
          <ProtectedShell allowedRoles={['admin','teacher']}>
            <SafeRoute><GradesDashboard /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/academics/grades/:classroomId/:subjectId" element={
          <ProtectedShell allowedRoles={['admin','teacher']}>
            <SafeRoute><GradeSheetPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/academics/attendance" element={
          <ProtectedShell allowedRoles={['admin','teacher']}>
            <SafeRoute><AttendanceDashboard /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/academics/attendance/mark" element={
          <ProtectedShell allowedRoles={['admin','teacher']}>
            <SafeRoute><MarkAttendancePage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/academics/attendance/:classroomId" element={
          <ProtectedShell allowedRoles={['admin','teacher']}>
            <SafeRoute><ClassAttendancePage /></SafeRoute>
          </ProtectedShell>
        } />
        
        {/* ✅ TIMETABLE ROUTE IS ALREADY CORRECTLY CONFIGURED HERE */}
        <Route path="/academics/timetable" element={
          <ProtectedShell allowedRoles={['admin','teacher','parent']}>
            <SafeRoute><TimetablePage /></SafeRoute>
          </ProtectedShell>
        } />
        
        <Route path="/academics/report-cards" element={
          <ProtectedShell allowedRoles={['admin','teacher']}>
            <SafeRoute><ReportCardsDashboard /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/academics/report-cards/:id" element={
          <ProtectedShell allowedRoles={['admin','teacher','parent']}>
            <SafeRoute><ReportCardDetailPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/teacher/home-class" element={
          <ProtectedShell allowedRoles={['teacher']}>
            <SafeRoute><MyHomeClassPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/academics/exams" element={
          <ProtectedShell allowedRoles={['admin','teacher']}>
            <SafeRoute><ExamsDashboard /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/academics/exams/:examId" element={
          <ProtectedShell allowedRoles={['admin','teacher']}>
            <SafeRoute><ExamMarksSheetPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/academics/exams/:examId/results" element={
          <ProtectedShell allowedRoles={['admin','teacher']}>
            <SafeRoute><ExamResultsPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/academics/national-exams" element={
          <ProtectedShell allowedRoles={['admin']}>
            <SafeRoute><NationalExamsDashboard /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/academics/national-exams/:sessionId" element={
          <ProtectedShell allowedRoles={['admin']}>
            <SafeRoute><NationalExamDetailPage /></SafeRoute>
          </ProtectedShell>
        } />
        
        {/* PARENT ROUTE */}
        <Route path="/parent" element={
          <ProtectedShell allowedRoles={['parent']}>
            <SafeRoute><ParentDashboard /></SafeRoute>
          </ProtectedShell>
        } />
        
        {/* STUDENTS ROUTES */}
        <Route path="/students" element={
          <ProtectedShell allowedRoles={['admin','teacher','bursar']}>
            <SafeRoute><StudentsPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/students/new" element={
          <ProtectedShell allowedRoles={['admin']}>
            <SafeRoute><AdmitStudentPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/students/import" element={
          <ProtectedShell allowedRoles={['admin']}>
            <SafeRoute><BulkImportPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/students/classrooms" element={
          <ProtectedShell allowedRoles={['admin']}>
            <SafeRoute><ClassroomsPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/students/:id/id-card" element={
          <ProtectedShell allowedRoles={['admin']}>
            <SafeRoute><StudentIdCardPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/students/:id" element={
          <ProtectedShell allowedRoles={['admin','teacher','parent','bursar']}>
            <SafeRoute><StudentDetailPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/students/:id/edit" element={
          <ProtectedShell allowedRoles={['admin']}>
            <SafeRoute><AdmitStudentPage /></SafeRoute>
          </ProtectedShell>
        } />
        
        {/* ✅ ANALYTICS ROUTES (CLEANED UP & DEDUPLICATED) */}
        <Route path="/analytics" element={
          <ProtectedShell allowedRoles={['admin', 'teacher']}>
            <SafeRoute><AnalyticsDashboard /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/analytics/class/:classroomId" element={
          <ProtectedShell allowedRoles={['admin', 'teacher']}>
            <SafeRoute><ClassPerformancePage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/analytics/class/:classroomId/subject/:subjectId" element={
          <ProtectedShell allowedRoles={['admin', 'teacher']}>
            <SafeRoute><ClassSubjectAnalysisPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/analytics/student/:studentId" element={
          <ProtectedShell allowedRoles={['admin', 'teacher', 'parent']}>
            <SafeRoute><StudentProfilePage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/analytics/subject/:subjectId" element={
          <ProtectedShell allowedRoles={['admin', 'teacher']}>
            <SafeRoute><SubjectAnalysisPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/analytics/subject-teacher/:subjectId" element={
          <ProtectedShell allowedRoles={['admin', 'teacher']}>
            <SafeRoute><SubjectTeacherDetailPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/analytics/school-performance" element={
          <ProtectedShell allowedRoles={['admin', 'teacher']}>
            <SafeRoute><SchoolPerformancePage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/analytics/early-warning" element={
          <ProtectedShell allowedRoles={['admin', 'teacher']}>
            <SafeRoute><EarlyWarningPage /></SafeRoute>
          </ProtectedShell>
        } />
        
        {/* COMMUNICATION ROUTES */}
        <Route path="/communication" element={
          <ProtectedShell allowedRoles={['admin','teacher']}>
            <SafeRoute><CommunicationDashboard /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/communication/compose" element={
          <ProtectedShell allowedRoles={['admin','teacher']}>
            <SafeRoute><ComposeMessagePage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/communication/templates" element={
          <ProtectedShell allowedRoles={['admin']}>
            <SafeRoute><TemplatesPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/communication/scheduled" element={
          <ProtectedShell allowedRoles={['admin','teacher']}>
            <SafeRoute><ScheduledMessagesPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/communication/logs" element={
          <ProtectedShell allowedRoles={['admin','teacher']}>
            <SafeRoute><MessageLogsPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/communication/notifications" element={
          <ProtectedShell allowedRoles={['admin','teacher','bursar','parent']}>
            <SafeRoute><NotificationsPage /></SafeRoute>
          </ProtectedShell>
        } />
        
        {/* STAFF ROUTES */}
        <Route path="/staff" element={
          <ProtectedShell allowedRoles={['admin']}>
            <SafeRoute><StaffListPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/staff/new" element={
          <ProtectedShell allowedRoles={['admin']}>
            <SafeRoute><AddStaffPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/staff/:id" element={
          <ProtectedShell allowedRoles={['admin']}>
            <SafeRoute><StaffDetailPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/staff/:id/edit" element={
          <ProtectedShell allowedRoles={['admin']}>
            <SafeRoute><EditStaffPage /></SafeRoute>
          </ProtectedShell>
        } />   
        
        {/* SCHOOL MANAGEMENT / SETTINGS ROUTES */}
        <Route path="/settings/school-profile" element={
          <ProtectedShell allowedRoles={['admin']}>
            <SafeRoute><SchoolProfileSettingsPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/settings/change-password" element={
          <ProtectedShell allowedRoles={['admin', 'teacher', 'parent', 'bursar']}>
            <SafeRoute><ChangePasswordSettingsPage /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/platform" element={
          <ProtectedShell allowedRoles={['superadmin']}>
            <SafeRoute><SuperadminDashboard /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/platform/schools" element={
          <ProtectedShell allowedRoles={['superadmin']}>
            <SafeRoute><SuperadminDashboard /></SafeRoute>
          </ProtectedShell>
        } />
        <Route path="/platform/schools/:id" element={
          <ProtectedShell allowedRoles={['superadmin']}>
            <SafeRoute><PlatformSchoolDetailPage /></SafeRoute>
          </ProtectedShell>
        } />
        
        
        {/* PUBLIC/AUTH GUEST ROUTES */}
        <Route path="/forgot-password" element={<GuestRoute><SafeRoute><ForgotPasswordPage /></SafeRoute></GuestRoute>} />
        <Route path="/reset-password" element={<GuestRoute><SafeRoute><ResetPasswordPage /></SafeRoute></GuestRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}