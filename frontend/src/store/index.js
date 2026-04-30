import { create } from 'zustand';

export const useAuthStore = create((set) => ({
  user: null,
  isAuthenticated: false,
  setUser: (user) => set({ user, isAuthenticated: !!user }),
  logout: () => set({ user: null, isAuthenticated: false }),
}));

export const useTenantStore = create((set) => ({
  currentTenant: null,
  setCurrentTenant: (tenant) => set({ currentTenant: tenant }),
}));

export const useStudentStore = create((set) => ({
  students: [],
  setStudents: (students) => set({ students }),
  addStudent: (student) => set((state) => ({ students: [...state.students, student] })),
  updateStudent: (id, updatedData) =>
    set((state) => ({
      students: state.students.map((s) => (s.id === id ? { ...s, ...updatedData } : s)),
    })),
  deleteStudent: (id) =>
    set((state) => ({
      students: state.students.filter((s) => s.id !== id),
    })),
}));

export const useFinanceStore = create((set) => ({
  payments: [],
  feeStructures: [],
  setPayments: (payments) => set({ payments }),
  setFeeStructures: (feeStructures) => set({ feeStructures }),
}));

export const useAcademicsStore = create((set) => ({
  classes: [],
  grades: [],
  attendance: [],
  setClasses: (classes) => set({ classes }),
  setGrades: (grades) => set({ grades }),
  setAttendance: (attendance) => set({ attendance }),
}));

export const useCommunicationStore = create((set) => ({
  notifications: [],
  smsLogs: [],
  setNotifications: (notifications) => set({ notifications }),
  setSMSLogs: (smsLogs) => set({ smsLogs }),
}));
