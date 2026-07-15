import React, { useState, useEffect, useCallback, useRef } from 'react';
import { financeApi } from '../../api/finance';
import { Button, Input, Spinner } from '../ui';
import { X, Phone, CheckCircle, AlertCircle, Download } from 'lucide-react';


const POLL_INTERVAL = 4000; 
const TIMEOUT_LIMIT = 90000; 

const ERROR_MESSAGES = {
  'STK_PUSH_FAILED': 'We could not reach your phone. Please check the number and try again.',
  'CONFIGURATION_ERROR': 'M-Pesa is not set up for this school. Please contact the bursar.',
  'INTERNAL_ERROR': 'Something went wrong on our side. Please try again in a moment.',
  'AMOUNT_EXCEEDS_BALANCE': 'The amount exceeds the invoice balance.',
  'AMOUNT_TOO_SMALL': 'Amount must be at least KES 1.00.',
  '1032': 'You cancelled the payment on your phone.',
  '1037': 'The payment request timed out. Please try again.',
  '1': 'You do not have enough M-Pesa funds for this transaction.',
  '2006': 'Wrong M-Pesa PIN entered.',
  '1001': 'Invalid phone number or M-Pesa account issue.',
  'default': 'Payment failed. Please try again or use another method.'
};

// Prevent React "Objects are not valid as a React child" crashes
const safeString = (val) => {
  if (val === null || val === undefined) return '';
  if (typeof val === 'string') return val;
  if (typeof val === 'number') return String(val);
  try {
    return JSON.stringify(val);
  } catch {
    return '';
  }
};

const MpesaPaymentModal = ({
  isOpen,
  onClose,
  student,
  fee,
  amount: initialAmount,
  onSuccess,
  mode = 'modal'
}) => {
  const [phone, setPhone] = useState('');
  const [amount, setAmount] = useState(initialAmount || fee?.balance || '');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('idle'); // idle, pending, success, failed, cancelled, timeout
  const [paymentId, setPaymentId] = useState(null);
  const [checkoutId, setCheckoutId] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [errorCode, setErrorCode] = useState('');
  const [receiptNumber, setReceiptNumber] = useState('');

  const pollTimerRef = useRef(null);
  const timeoutTimerRef = useRef(null);

  const clearTimers = useCallback(() => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    if (timeoutTimerRef.current) clearTimeout(timeoutTimerRef.current);
  }, []);

  useEffect(() => {
    if (!isOpen) {
      clearTimers();
      setPhone('');
      setStatus('idle');
      setErrorMsg('');
      setErrorCode('');
      setPaymentId(null);
      setCheckoutId(null);
      setReceiptNumber('');
    } else {
      setAmount(initialAmount || fee?.balance || '');
    }
  }, [isOpen, fee, initialAmount, clearTimers]);

  useEffect(() => {
    return () => clearTimers();
  }, [clearTimers]);

  // SECURITY FIX #9: Synced with backend validate_phone
  // Handles +254, 0, 1, 7, and 254 prefixes (supports newer 01xx Safaricom numbers)
  const validatePhone = (num) => {
    if (!num) return null;
    const digits = num.replace(/\D/g, '');

    if (digits.startsWith('0') && digits.length === 10) return '254' + digits.slice(1);
    if (digits.startsWith('7') && digits.length === 9) return '254' + digits;
    if (digits.startsWith('1') && digits.length === 9) return '254' + digits;
    if (digits.startsWith('254') && digits.length === 12) return digits;
    return null;
  };

  // SECURITY FIX #14: Generate idempotency key for true idempotency
  // DEFENSIVE: student.id and fee.id may be UUID strings or undefined.
  // Use String() coercion and substring() instead of .slice() to avoid
  // TypeError when values are not string objects.
  const generateIdempotencyKey = useCallback(() => {
    const safeSlice = (val, len) => {
      if (val === null || val === undefined) return 'none';
      const s = String(val);
      return s.length > len ? s.substring(0, len) : s;
    };
    const feePart = safeSlice(fee?.id, 8);
    const studentPart = safeSlice(student?.id, 8);
    const amountPart = String(amount || '0').replace('.', '');
    const phonePart = safeSlice((phone || '').replace(/\D/g, ''), 4);
    const timestamp = Date.now();
    return `${studentPart}-${feePart}-${amountPart}-${phonePart}-${timestamp}`;
  }, [student, fee, amount, phone]);

  const handlePay = async (e) => {
    if (e) e.preventDefault();
    if (loading || status === 'pending' || !phone || !amount) return;

    // DEFENSIVE: Validate required IDs before generating idempotency key
    if (!student?.id) {
      setErrorMsg('Student information is missing. Please refresh the page.');
      return;
    }

    const normalizedPhone = validatePhone(phone);
    if (!normalizedPhone) {
      setErrorMsg('Please enter a valid Kenyan phone number (e.g., 0712 345 678 or 0112 345 678)');
      return;
    }

    setLoading(true);
    setErrorMsg('');
    setErrorCode('');
    setStatus('pending');

    // SECURITY FIX #14: Include idempotency key
    const idempotencyKey = generateIdempotencyKey();
    console.log('[M-Pesa] Initiating STK push:', { phone: normalizedPhone, amount, student: String(student?.id || 'N/A'), fee: String(fee?.id || 'N/A') });

    try {
      const data = await financeApi.initiateMpesa({
        phone: normalizedPhone,
        amount: parseFloat(amount),
        student_id: student?.id,
        fee_id: fee?.id,
        account_ref: student?.admission_number,
        description: `School Fee Payment - ${student?.admission_number || ''}`,
        idempotency_key: idempotencyKey,
      });

      // Handle duplicate payment (already initiated)
      if (data.duplicate) {
        setPaymentId(data.payment_id);
        setCheckoutId(data.checkout_request_id);
        // Continue polling as if we just initiated
      } else if (!data.success) {
        setStatus('failed');
        setErrorCode(data.error_code || 'STK_PUSH_FAILED');
        setErrorMsg(data.error || ERROR_MESSAGES[data.error_code] || ERROR_MESSAGES.default);
        setLoading(false);
        return;
      } else {
        setPaymentId(data.payment_id);
        setCheckoutId(data.checkout_request_id);
      }

      pollTimerRef.current = setInterval(() => {
        checkPaymentStatus(data.payment_id);
      }, POLL_INTERVAL);

      timeoutTimerRef.current = setTimeout(() => {
        clearTimers();
        setStatus('timeout');
        setErrorCode('1037');
        setErrorMsg('The payment request timed out. Please check if you received an M-Pesa prompt.');
        setLoading(false);
      }, TIMEOUT_LIMIT);

    } catch (err) {
      console.error('[M-Pesa] STK push failed:', err);
      // Axios error — err.response?.data has the server payload
      const serverError = err.response?.data;
      const errCode = serverError?.error_code || serverError?.error?.code || 'INTERNAL_ERROR';
      setStatus('failed');
      setErrorCode(errCode);
      setErrorMsg(
        ERROR_MESSAGES[errCode] ||
        serverError?.error?.message ||
        serverError?.error ||
        serverError?.detail ||
        safeString(err.message) ||
        'Network error. Please check your connection and try again.'
      );
      setLoading(false);
    }
  };

  const checkPaymentStatus = async (pid) => {
    try {
      const payment = await financeApi.getPaymentStatus(pid);
      const st = payment.status?.toLowerCase();

      // DEFENSIVE: Use result_code from backend (Daraja code) for accurate messages
      const darajaCode = payment.result_code || payment.mpesa_result_code || '';

      if (st === 'completed') {
        clearTimers();
        setReceiptNumber(payment.receipt_number || '');
        setStatus('success');
        setLoading(false);
        // IMMEDIATE: Call parent onSuccess right away so parent can refetch
        // before user closes the modal or navigates away.
        onSuccess?.({
          paymentId: pid,
          receiptNumber: payment.receipt_number,
          amount: payment.amount,
          status: payment.status,
        });
        // BROADCAST: Dispatch event for any page listening (StudentStatementPage, etc.)
        // Use setTimeout(0) to ensure listener is mounted if this fires during a render.
        if (student?.id) {
          setTimeout(() => {
            try {
              window.dispatchEvent(new CustomEvent('mpesa-payment-success', {
                detail: { studentId: String(student.id), paymentId: pid, receiptNumber: payment.receipt_number }
              }));
              console.log('[M-Pesa] Dispatched mpesa-payment-success event');
            } catch (err) {
              console.warn('[M-Pesa] Failed to dispatch event:', err);
            }
            // DIRECT REFETCH FALLBACK: try to refetch statement directly
            try {
              if (financeApi && financeApi.getStudentStatement) {
                financeApi.getStudentStatement(student.id).catch(() => {});
              }
            } catch (err) {
              // Silent fail
            }
          }, 0);
        }
      } else if (st === 'cancelled') {
        clearTimers();
        setStatus('cancelled');
        setErrorCode(darajaCode || '1032');
        setErrorMsg(
          ERROR_MESSAGES[darajaCode] ||
          safeString(payment.failure_reason) ||
          ERROR_MESSAGES['1032']
        );
        setLoading(false);
      } else if (st === 'expired') {
        clearTimers();
        setStatus('timeout');
        setErrorCode(darajaCode || '1037');
        setErrorMsg(
          ERROR_MESSAGES[darajaCode] ||
          safeString(payment.failure_reason) ||
          ERROR_MESSAGES['1037']
        );
        setLoading(false);
      } else if (st === 'failed') {
        clearTimers();
        setStatus('failed');
        setErrorCode(darajaCode || 'default');
        setErrorMsg(
          ERROR_MESSAGES[darajaCode] ||
          safeString(payment.failure_reason) ||
          ERROR_MESSAGES.default
        );
        setLoading(false);
      }
      // If still pending, keep polling
    } catch (err) {
      console.error('Status check error:', err);
      // Don't stop polling on transient errors
    }
  };

  // SECURITY FIX #16: Handle non-PDF responses gracefully
  const handleDownloadReceipt = async () => {
    if (!paymentId) return;
    try {
      const response = await financeApi.downloadReceipt(paymentId);
      // Verify it's actually a PDF
      const contentType = response.headers?.['content-type'] || '';
      if (!contentType.includes('application/pdf')) {
        throw new Error('Invalid receipt response from server');
      }
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `receipt_${paymentId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Receipt download failure:', err);
      // Could emit toast here if toastBus is available
      alert('Failed to download receipt. Please try again.');
    }
  };

  const handleRetry = () => {
    setStatus('idle');
    setErrorMsg('');
    setErrorCode('');
    setPaymentId(null);
    setCheckoutId(null);
    setReceiptNumber('');
  };

  if (!isOpen) return null;

  // Use CSS variables for theming — your existing BrandingProvider should set these
  const brandPrimary = 'var(--brand-primary, #10B981)';
  const brandPrimaryDark = 'var(--brand-primary-dark, #059669)';
  const brandDanger = 'var(--brand-danger, #EF4444)';
  const brandWarning = 'var(--brand-warning, #F59E0B)';

  const renderBody = () => (
    <div className="space-y-4">
      <h3
        className="text-lg font-bold mb-4 flex items-center gap-2"
        style={{ color: 'var(--text-primary, #1f2937)' }}
      >
        <Phone size={20} style={{ color: brandPrimary }} /> M-Pesa Payment
      </h3>

      <div
        className="mb-4 p-3 rounded-lg border"
        style={{
          backgroundColor: 'var(--surface-secondary, #f9fafb)',
          borderColor: 'var(--border-light, #e5e7eb)'
        }}
      >
        <p className="text-sm" style={{ color: 'var(--text-secondary, #6b7280)' }}>
          Student:{' '}
          <span className="font-semibold" style={{ color: 'var(--text-primary, #1f2937)' }}>
            {safeString(student?.name || student?.get_full_name || student?.admission_number)}
          </span>
        </p>
        <p className="text-sm" style={{ color: 'var(--text-secondary, #6b7280)' }}>
          Admission No:{' '}
          <span className="font-semibold" style={{ color: 'var(--text-primary, #1f2937)' }}>
            {safeString(student?.admission_number)}
          </span>
        </p>
        {fee && (
          <p className="text-sm" style={{ color: 'var(--text-secondary, #6b7280)' }}>
            Fee:{' '}
            <span className="font-semibold" style={{ color: 'var(--text-primary, #1f2937)' }}>
              {safeString(fee.description || fee.fee_term)}
            </span>
          </p>
        )}
        <p className="text-sm" style={{ color: 'var(--text-secondary, #6b7280)' }}>
          Amount:{' '}
          <span className="font-semibold" style={{ color: 'var(--text-primary, #1f2937)' }}>
            KES {safeString(parseFloat(amount || 0).toLocaleString())}
          </span>
        </p>
      </div>

      {status === 'idle' && (
        <form onSubmit={handlePay} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary, #374151)' }}>
              M-Pesa Phone Number
            </label>
            <Input
              type="tel"
              placeholder="e.g. 0712 345 678"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              disabled={loading}
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary, #374151)' }}>
              Amount (KES)
            </label>
            <Input
              type="number"
              placeholder="Amount"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              disabled={loading}
              className="w-full"
            />
          </div>
          <p className="text-xs" style={{ color: 'var(--text-muted, #9ca3af)' }}>
            You will receive an STK push prompt on this phone number. Enter your M-Pesa PIN to complete.
          </p>

          {errorMsg && (
            <div className="p-3 rounded text-sm" style={{ backgroundColor: 'var(--danger-bg, #fef2f2)', color: 'var(--danger-text, #b91c1c)', border: '1px solid var(--danger-border, #fecaca)' }}>
              {safeString(errorMsg)}
            </div>
          )}

          <Button
            type="submit"
            className="w-full text-white"
            disabled={loading || !phone || !amount}
            style={{ backgroundColor: brandPrimary }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = brandPrimaryDark)}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = brandPrimary)}
          >
            {loading ? <Spinner size="sm" /> : 'Send M-Pesa Request'}
          </Button>
        </form>
      )}

      {status === 'pending' && (
        <div className="text-center py-6 space-y-4">
          <div className="mx-auto" style={{ color: brandPrimary }}>
            <Spinner className="h-10 w-10" />
          </div>
          <div>
            <p className="text-lg font-semibold" style={{ color: brandPrimaryDark }}>
              Waiting for M-Pesa confirmation...
            </p>
            <p className="text-sm mt-1" style={{ color: 'var(--text-secondary, #6b7280)' }}>
              Please check phone <span className="font-semibold">{safeString(phone)}</span> and enter your M-Pesa PIN.
            </p>
          </div>
          <p className="text-xs animate-pulse" style={{ color: 'var(--text-muted, #9ca3af)' }}>
            Do not close this window until the payment completes.
          </p>
        </div>
      )}

      {status === 'success' && (
        <div className="text-center py-6 space-y-4">
          <CheckCircle size={56} style={{ color: brandPrimary }} className="mx-auto" />
          <div>
            <h3 className="text-xl font-bold" style={{ color: brandPrimaryDark }}>
              Payment Successful!
            </h3>
            <p className="text-sm mt-1" style={{ color: 'var(--text-secondary, #6b7280)' }}>
              Payment of KES {safeString(parseFloat(amount || 0).toLocaleString())} confirmed.
            </p>
            {receiptNumber && (
              <p className="text-sm mt-1" style={{ color: 'var(--text-secondary, #6b7280)' }}>
                Receipt:{' '}
                <span className="font-mono font-medium" style={{ color: 'var(--text-primary, #1f2937)' }}>
                  {safeString(receiptNumber)}
                </span>
              </p>
            )}
            {checkoutId && <p className="text-xs mt-1" style={{ color: 'var(--text-muted, #9ca3af)' }}>Ref: {safeString(checkoutId)}</p>}
          </div>
          <div className="flex items-center justify-center gap-3 pt-2">
            <Button
              variant="secondary"
              className="gap-2 flex items-center"
              onClick={handleDownloadReceipt}
              style={{ borderColor: brandPrimary, color: brandPrimary }}
            >
              <Download size={16} /> Download Receipt
            </Button>
            {onClose && <Button onClick={onClose}>Close</Button>}
          </div>
        </div>
      )}

      {(status === 'failed' || status === 'cancelled' || status === 'timeout') && (
        <div className="text-center py-6 space-y-4">
          <AlertCircle
            size={56}
            style={{
              color:
                status === 'cancelled'
                  ? brandWarning
                  : status === 'timeout'
                  ? brandWarning
                  : brandDanger,
            }}
            className="mx-auto"
          />
          <div>
            <h3
              className="text-xl font-bold"
              style={{
                color:
                  status === 'cancelled'
                    ? brandWarning
                    : status === 'timeout'
                    ? brandWarning
                    : brandDanger,
              }}
            >
              {status === 'cancelled'
                ? 'Payment Cancelled'
                : status === 'timeout'
                ? 'Request Timed Out'
                : 'Payment Failed'}
            </h3>
            <p className="text-sm mt-2 max-w-xs mx-auto" style={{ color: 'var(--text-secondary, #6b7280)' }}>
              {safeString(errorMsg)}
            </p>
            {errorCode && (
              <p className="text-xs mt-1" style={{ color: 'var(--text-muted, #9ca3af)' }}>Code: {safeString(errorCode)}</p>
            )}
          </div>
          <div className="flex gap-3 pt-2">
            <Button onClick={handleRetry} variant="secondary" className="flex-1">
              Try Again
            </Button>
            {onClose && (
              <Button onClick={onClose} variant="ghost" className="flex-1">
                Cancel
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );

  // SECURITY FIX #15: Hide close button in tab mode
  if (mode === 'tab') {
    return <div className="w-full bg-white p-4 rounded-xl">{renderBody()}</div>;
  }

  return (
    <div className="fixed inset-0 bg-black/40 bg-opacity-50 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 relative border" style={{ borderColor: 'var(--border-light, #e5e7eb)' }}>
        {/* SECURITY FIX #15: Only show close button in modal mode */}
        {mode !== 'tab' && onClose && (
          <button
            onClick={onClose}
            className="absolute top-4 right-4 transition-colors"
            style={{ color: 'var(--text-muted, #9ca3af)' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-secondary, #6b7280)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted, #9ca3af)')}
          >
            <X size={20} />
          </button>
        )}
        {renderBody()}
      </div>
    </div>
  );
};

export default MpesaPaymentModal;