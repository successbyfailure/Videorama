import { ReactNode } from 'react'
import clsx from 'clsx'

interface CardProps {
  children: ReactNode
  className?: string
  padding?: 'none' | 'small' | 'medium' | 'large'
  onClick?: () => void
}

export default function Card({
  children,
  className,
  padding = 'medium',
  onClick,
}: CardProps) {
  const paddingClasses = {
    none: '',
    small: 'p-4',
    medium: 'p-6',
    large: 'p-8',
  }

  return (
    <div
      className={clsx(
        'bg-white dark:bg-gray-800 rounded-lg shadow-md',
        paddingClasses[padding],
        className
      )}
      onClick={onClick}
    >
      {children}
    </div>
  )
}
