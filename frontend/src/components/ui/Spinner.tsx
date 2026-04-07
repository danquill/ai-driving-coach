import { clsx } from 'clsx'

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export function Spinner({ size = 'md', className }: SpinnerProps) {
  const sizes = {
    sm: 'h-4 w-4 border-2',
    md: 'h-8 w-8 border-2',
    lg: 'h-12 w-12 border-[3px]',
  }

  return (
    <div
      className={clsx(
        'rounded-full border-[#1e1e2e] border-t-[#e63946] animate-spin',
        sizes[size],
        className
      )}
    />
  )
}

export function SpinnerOverlay({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16">
      <Spinner size="lg" />
      {label && <p className="text-sm text-[#6b7280]">{label}</p>}
    </div>
  )
}
