import { useToastStore } from '@/store/toastStore';
import './Toast.css';

export default function ToastContainer() {
  const { toasts, removeToast } = useToastStore();

  if (toasts.length === 0) return null;

  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast-${t.type}`} onClick={() => removeToast(t.id)}>
          <span className="toast-icon">
            {t.type === 'error' ? '✕' : t.type === 'success' ? '✓' : '⚠'}
          </span>
          <span className="toast-message">{t.message}</span>
        </div>
      ))}
    </div>
  );
}
