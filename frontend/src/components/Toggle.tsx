import { InputHTMLAttributes, forwardRef } from 'react'
import clsx from 'clsx'

interface ToggleProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string
  helperText?: string
}

const Toggle = forwardRef<HTMLInputElement, ToggleProps>(
  ({ label, helperText, className, checked, ...props }, ref) => {
    return (
      <div className={clsx('flex items-center', className)}>
        <button
          type="button"
          role="switch"
          aria-checked={checked}
          onClick={() => {
            const event = new Event('click', { bubbles: true })
            if (props.onChange) {
              props.onChange(event as any)
            }
          }}
          className={clsx(
            'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
            checked
              ? 'bg-primary-600'
              : 'bg-gray-200 dark:bg-gray-700',
            props.disabled && 'opacity-50 cursor-not-allowed'
          )}
          disabled={props.disabled}
        >
          <span
            className={clsx(
              'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
              checked ? 'translate-x-6' : 'translate-x-1'
            )}
          />
        </button>
        <input
          ref={ref}
          type="checkbox"
          className="sr-only"
          checked={checked}
          {...props}
        />
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

Toggle.displayName = 'Toggle'

export default Toggle
