import { useQuery, useMutation } from '@tanstack/react-query';
import * as api from '../api/endpoints';

// Auth hooks
export const useLogin = () => {
  return useMutation({
    mutationFn: ({ email, password }) => api.authAPI.login(email, password),
  });
};

export const useGetCurrentUser = () => {
  return useQuery({
    queryKey: ['currentUser'],
    queryFn: () => api.authAPI.getCurrentUser(),
  });
};

// Student hooks
export const useStudents = () => {
  return useQuery({
    queryKey: ['students'],
    queryFn: () => api.studentAPI.list(),
  });
};

export const useStudent = (id) => {
  return useQuery({
    queryKey: ['student', id],
    queryFn: () => api.studentAPI.get(id),
    enabled: !!id,
  });
};

export const useCreateStudent = () => {
  return useMutation({
    mutationFn: (data) => api.studentAPI.create(data),
  });
};

// Finance hooks
export const useFeeStructures = () => {
  return useQuery({
    queryKey: ['feeStructures'],
    queryFn: () => api.financeAPI.getFeeStructures(),
  });
};

export const usePayments = () => {
  return useQuery({
    queryKey: ['payments'],
    queryFn: () => api.financeAPI.getPayments(),
  });
};

// Academics hooks
export const useClasses = () => {
  return useQuery({
    queryKey: ['classes'],
    queryFn: () => api.academicsAPI.getClasses(),
  });
};

export const useGrades = () => {
  return useQuery({
    queryKey: ['grades'],
    queryFn: () => api.academicsAPI.getGrades(),
  });
};

export const useAttendance = () => {
  return useQuery({
    queryKey: ['attendance'],
    queryFn: () => api.academicsAPI.getAttendance(),
  });
};

// Communication hooks
export const useNotifications = () => {
  return useQuery({
    queryKey: ['notifications'],
    queryFn: () => api.communicationAPI.getNotifications(),
  });
};
