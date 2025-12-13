import { X, CheckCircle, XCircle, AlertTriangle, Info } from 'lucide-react'
import { useToast, Toast, ToastType } from '@/contexts/ToastContext'

const toastStyles: Record<
  ToastType,
  {
    bg: string
    border: string
    text: string
    icon: React.ComponentType<{ size: number; className?: string }>
    iconColor: string
  }
> = {
  success: {
    bg: 'bg-green-50 dark:bg-green-900/20',
    border: 'border-green-200 dark:border-green-800',
    text: 'text-green-800 dark:text-green-200',
    icon: CheckCircle,
    iconColor: 'text-green-500 dark:text-green-400',
  },
  error: {
    bg: 'bg-red-50 dark:bg-red-900/20',
    border: 'border-red-200 dark:border-red-800',
    text: 'text-red-800 dark:text-red-200',
    icon: XCircle,
    iconColor: 'text-red-500 dark:text-red-400',
  },
  warning: {
    bg: 'bg-yellow-50 dark:bg-yellow-900/20',
    border: 'border-yellow-200 dark:border-yellow-800',
    text: 'text-yellow-800 dark:text-yellow-200',
    icon: AlertTriangle,
    iconColor: 'text-yellow-500 dark:text-yellow-400',
  },
  info: {
    bg: 'bg-blue-50 dark:bg-blue-900/20',
    border: 'border-blue-200 dark:border-blue-800',
    text: 'text-blue-800 dark:text-blue-200',
    icon: Info,
    iconColor: 'text-blue-500 dark:text-blue-400',
  },
}

interface ToastItemProps {
  toast: Toast
  onClose: (id: string) => void
}

function ToastItem({ toast, onClose }: ToastItemProps) {
  const style = toastStyles[toast.type]
  const Icon = style.icon

  return (
    <div
      className={`
        flex items-start gap-3 p-4 rounded-lg border shadow-lg
        ${style.bg} ${style.border} ${style.text}
        animate-in slide-in-from-right duration-300
        max-w-md w-full
      `}
    >
      <Icon size={20} className={`flex-shrink-0 mt-0.5 ${style.iconColor}`} />
      <p className="flex-1 text-sm font-medium">{toast.message}</p>
      <button
        onClick={() => onClose(toast.id)}
        className={`flex-shrink-0 hover:opacity-70 transition-opacity ${style.iconColor}`}
        aria-label="Close notification"
      >
        <X size={18} />
      </button>
    </div>
  )
}

export default function ToastContainer() {
  const { toasts, hideToast } = useToast()

  if (toasts.length === 0) return null

  return (
    <div
      className="fixed top-4 right-4 z-50 flex flex-col gap-3"
      aria-live="polite"
      aria-atomic="true"
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onClose={hideToast} />
      ))}
    </div>
  )
}
