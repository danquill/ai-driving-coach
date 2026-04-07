import { ReactNode } from 'react'
import { clsx } from 'clsx'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={clsx(
        'flex flex-col items-center justify-center gap-4 py-16 px-8 text-center',
        className
      )}
    >
      {icon && (
        <div className="w-16 h-16 rounded-full bg-[#1e1e2e] flex items-center justify-center text-[#6b7280]">
          {icon}
        </div>
      )}
      <div className="space-y-1">
        <p className="text-base font-medium text-white">{title}</p>
        {description && <p className="text-sm text-[#6b7280] max-w-sm">{description}</p>}
      </div>
      {action && <div>{action}</div>}
    </div>
  )
}
