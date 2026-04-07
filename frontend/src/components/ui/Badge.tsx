import { clsx } from 'clsx'
import type { SessionStatus, JobStatus } from '../../types/api'

type BadgeStatus = SessionStatus | JobStatus | string

interface BadgeProps {
  status: BadgeStatus
  className?: string
}

const STATUS_STYLES: Record<string, string> = {
  // Session statuses
  created: 'bg-[#6b7280]/20 text-[#9ca3af] border-[#6b7280]/30',
  uploading: 'bg-[#457b9d]/20 text-[#457b9d] border-[#457b9d]/30',
  processing: 'bg-amber-900/30 text-amber-400 border-amber-700/30',
  ready: 'bg-[#00e676]/10 text-[#00e676] border-[#00e676]/30',
  error: 'bg-[#ff5252]/10 text-[#ff5252] border-[#ff5252]/30',
  // Job statuses
  pending: 'bg-[#6b7280]/20 text-[#9ca3af] border-[#6b7280]/30',
  running: 'bg-[#457b9d]/20 text-[#457b9d] border-[#457b9d]/30',
  done: 'bg-[#00e676]/10 text-[#00e676] border-[#00e676]/30',
  failed: 'bg-[#ff5252]/10 text-[#ff5252] border-[#ff5252]/30',
}

const STATUS_DOTS: Record<string, string> = {
  running: 'bg-[#457b9d] animate-pulse',
  processing: 'bg-amber-400 animate-pulse',
  uploading: 'bg-[#457b9d] animate-pulse',
  ready: 'bg-[#00e676]',
  done: 'bg-[#00e676]',
  error: 'bg-[#ff5252]',
  failed: 'bg-[#ff5252]',
  created: 'bg-[#6b7280]',
  pending: 'bg-[#6b7280]',
}

export function Badge({ status, className }: BadgeProps) {
  const style = STATUS_STYLES[status] ?? 'bg-[#6b7280]/20 text-[#9ca3af] border-[#6b7280]/30'
  const dot = STATUS_DOTS[status] ?? 'bg-[#6b7280]'

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded border uppercase tracking-wide',
        style,
        className
      )}
    >
      <span className={clsx('w-1.5 h-1.5 rounded-full', dot)} />
      {status}
    </span>
  )
}
