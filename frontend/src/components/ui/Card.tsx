import { HTMLAttributes, forwardRef } from 'react'
import { clsx } from 'clsx'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'elevated' | 'inset'
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ variant = 'default', className, children, ...props }, ref) => {
    const variants = {
      default: 'bg-[#12121a] border border-[#1e1e2e]',
      elevated:
        'bg-gradient-to-b from-[#16162a] to-[#12121a] border border-[#1e1e2e] shadow-xl shadow-black/30',
      inset: 'bg-[#0d0d14] border border-[#1e1e2e]',
    }

    return (
      <div
        ref={ref}
        className={clsx('rounded-lg', variants[variant], className)}
        {...props}
      >
        {children}
      </div>
    )
  }
)

Card.displayName = 'Card'

export function CardHeader({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={clsx(
        'px-5 py-4 border-b border-[#1e1e2e] flex items-center justify-between',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardBody({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={clsx('px-5 py-4', className)} {...props}>
      {children}
    </div>
  )
}
