import { InputHTMLAttributes, forwardRef } from 'react'
import clsx from 'clsx'
import { Check } from 'lucide-react'

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string
  helperText?: string
}

const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ label, helperText, className, checked, ...props }, ref) => {
    return (
      <div className={clsx('flex items-start', className)}>
        <div className="flex items-center h-5">
          <input
            ref={ref}
            type="checkbox"
            checked={checked}
            className="sr-only"
            {...props}
          />
          <button
            type="button"
            role="checkbox"
            aria-checked={checked}
            onClick={() => {
              const event = new Event('click', { bubbles: true })
              if (props.onChange) {
                props.onChange(event as any)
              }
            }}
            className={clsx(
              'w-5 h-5 rounded border-2 flex items-center justify-center transition-colors',
              'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
              checked
                ? 'bg-primary-600 border-primary-600'
                : 'bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600',
              props.disabled && 'opacity-50 cursor-not-allowed'
            )}
            disabled={props.disabled}
          >
            {checked && <Check className="w-4 h-4 text-white" />}
          </button>
        </div>
        {label && (
          <div className="ml-3">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {label}
            </label>
            {helperText && (
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {helperText}
              </p>
            )}
          </div>
        )}
      </div>
    )
  }
)

Checkbox.displayName = 'Checkbox'

export default Checkbox
