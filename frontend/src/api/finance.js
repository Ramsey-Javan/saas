import api from './client'

export const WAIVER_UPDATED_EVENT = 'waiver:updated'
const WAIVER_UPDATED_STORAGE_KEY = 'finance:waiver-updated-at'
const WAIVER_UPDATED_CHANNEL = 'finance-waivers'

export const notifyWaiverUpdated = () => {
  if (typeof window === 'undefined') return

  window.dispatchEvent(new CustomEvent(WAIVER_UPDATED_EVENT))

  try {
    window.localStorage.setItem(WAIVER_UPDATED_STORAGE_KEY, String(Date.now()))
  } catch {
    // Ignore storage access errors; the in-window event above is enough for this tab.
  }

  if ('BroadcastChannel' in window) {
    const channel = new BroadcastChannel(WAIVER_UPDATED_CHANNEL)
    channel.postMessage({ type: WAIVER_UPDATED_EVENT })
    channel.close()
  }
}

export const subscribeToWaiverUpdates = (handler) => {
  if (typeof window === 'undefined') return () => {}

  const handleStorage = (event) => {
    if (event.key === WAIVER_UPDATED_STORAGE_KEY) handler()
  }

  let channel
  const handleBroadcast = (event) => {
    if (event.data?.type === WAIVER_UPDATED_EVENT) handler()
  }

  window.addEventListener(WAIVER_UPDATED_EVENT, handler)
  window.addEventListener('storage', handleStorage)

  if ('BroadcastChannel' in window) {
    channel = new BroadcastChannel(WAIVER_UPDATED_CHANNEL)
    channel.addEventListener('message', handleBroadcast)
  }

  return () => {
    window.removeEventListener(WAIVER_UPDATED_EVENT, handler)
    window.removeEventListener('storage', handleStorage)
    if (channel) {
      channel.removeEventListener('message', handleBroadcast)
      channel.close()
    }
  }
}

const withWaiverUpdate = (request) => request.then((response) => {
  notifyWaiverUpdated()
  return response
})

export const financeApi = {
  getStructures: (params) => api.get('/finance/structures/', { params }),
  createStructure: (data) => api.post('/finance/structures/', data),
  updateStructure: (id, data) => api.patch(`/finance/structures/${id}/`, data),
  deleteStructure: (id) => api.delete(`/finance/structures/${id}/`),
  generateBulkInvoices: (data) => api.post('/finance/invoices/generate_bulk/', data),
  
  getInvoices: (params) => api.get('/finance/invoices/', { params }),
  bulkInvoicesPdf: (data) => api.post('/finance/invoices/bulk-pdf/', data, { responseType: 'blob' }),
  bulkInvoicesSms: (data) => api.post('/finance/invoices/bulk-sms/', data),
  getDefaulters: (params) => api.get('/finance/invoices/defaulters/', { params }),
  getClassReport: (params) => api.get('/finance/invoices/class_report/', { params }),
  getTermSummary: (params) => api.get('/finance/invoices/term_summary/', { params }),
  getDashboardSummary: (params) => api.get('/finance/invoices/dashboard_summary/', { params }),
  
  getPayments: (params) => api.get('/finance/payments/', { params }),
  recordManualPayment: (data) => api.post('/finance/payments/manual/', data),
  clearCheque: (id) => api.patch(`/finance/payments/${id}/clear-cheque/`),
  bounceCheque: (id, data) => api.patch(`/finance/payments/${id}/bounce-cheque/`, data),
  downloadReceipt: (id) => api.get(`/finance/payments/${id}/receipt/pdf/`, { responseType: 'blob' }),
  getReceipts: (params) => api.get('/finance/receipts/', { params }),
  bulkReceiptsPdf: (data) => api.post('/finance/receipts/bulk-pdf/', data, { responseType: 'blob' }),
  getStudentStatement: (studentId) => api.get(`/finance/students/${studentId}/statement/`),
  getStudentStatementPdf: (studentId) => api.get(`/finance/students/${studentId}/statement/pdf/`, { responseType: 'blob' }),
  bulkStudentStatementsPdf: (data) => api.post('/finance/students/statements/bulk-pdf/', data, { responseType: 'blob' }),
  
  getWaiverPolicies: (params) => api.get('/finance/waiver-policies/', { params }),
  createWaiverPolicy: (data) => api.post('/finance/waiver-policies/', data),
  updateWaiverPolicy: (id, data) => api.patch(`/finance/waiver-policies/${id}/`, data),
  deleteWaiverPolicy: (id) => api.delete(`/finance/waiver-policies/${id}/`),
  getWaiverPoliciesDashboard: () => api.get('/finance/waiver-policies/dashboard/'),
  
  getWaivers: (params) => api.get('/finance/waivers/', { params }),
  createWaiver: (data) => withWaiverUpdate(api.post('/finance/waivers/', data, data instanceof FormData ? {
    headers: { 'Content-Type': 'multipart/form-data' },
  } : undefined)),
  updateWaiver: (id, data) => withWaiverUpdate(api.patch(`/finance/waivers/${id}/`, data, data instanceof FormData ? {
    headers: { 'Content-Type': 'multipart/form-data' },
  } : undefined)),
  deleteWaiver: (id) => withWaiverUpdate(api.delete(`/finance/waivers/${id}/`)),
  getWaiversByPolicy: (policyId) => api.get('/finance/waivers/by_policy/', { params: { policy_id: policyId } }),
  getWaiverReport: () => api.get('/finance/waivers/report/'),
  
  initiateMpesa: (data) => api.post('/finance/mpesa/stk_push/', data),
  getPaymentStatus: (id) => api.get(`/finance/mpesa/${id}/status/`),
}
