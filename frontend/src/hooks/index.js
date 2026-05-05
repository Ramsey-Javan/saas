import { useQuery, useMutation } from '@tanstack/react-query'
import {
  authAPI,
  studentAPI,
  financeAPI,
  academicsAPI,
  communicationAPI,
} from '../api/endpoints'

// Auth hooks
export const useLogin = () => {
  return useMutation({
    mutationFn: ({ email, password }) => authAPI.login(email, password),
  });
};

export const useGetCurrentUser = () => {
  return useQuery({
    queryKey: ['currentUser'],
    queryFn: () => authAPI.getCurrentUser(),
  });
};

// Student hooks
export const useStudents = () => {
  return useQuery({
    queryKey: ['students'],
    queryFn: () => studentAPI.list(),
  });
};

export const useStudent = (id) => {
  return useQuery({
    queryKey: ['student', id],
    queryFn: () => studentAPI.get(id),
    enabled: !!id,
  });
};

export const useCreateStudent = () => {
  return useMutation({
    mutationFn: (data) => studentAPI.create(data),
  });
};

// Finance hooks
export const useFeeStructures = () => {
  return useQuery({
    queryKey: ['feeStructures'],
    queryFn: () => financeAPI.getFeeStructures(),
  });
};

export const usePayments = () => {
  return useQuery({
    queryKey: ['payments'],
    queryFn: () => financeAPI.getPayments(),
  });
};

// Academics hooks
export const useClasses = () => {
  return useQuery({
    queryKey: ['classes'],
    queryFn: () => academicsAPI.getClasses(),
  });
};

export const useGrades = () => {
  return useQuery({
    queryKey: ['grades'],
    queryFn: () => academicsAPI.getGrades(),
  });
};

export const useAttendance = () => {
  return useQuery({
    queryKey: ['attendance'],
    queryFn: () => academicsAPI.getAttendance(),
  });
};

// Communication hooks
export const useNotifications = () => {
  return useQuery({
    queryKey: ['notifications'],
    queryFn: () => communicationAPI.getNotifications(),
  });
};
