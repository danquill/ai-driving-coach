import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { listSessions, deleteSession } from '../api/sessions'
import type { Session } from '../types/api'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { SpinnerOverlay } from '../components/ui/Spinner'
import { AppHeader } from '../components/ui/AppHeader'
import { useStore } from '../store'
import { formatLapTime, formatSessionDate } from '../utils/telemetry'

function SessionCard({ session, onDelete }: { session: Session; onDelete: (id: string) => void }) {
  const navigate = useNavigate()
  const [confirming, setConfirming] = useState(false)

  function handleDeleteClick(e: React.MouseEvent) {
    e.stopPropagation()
    if (confirming) {
      onDelete(session.id)
    } else {
      setConfirming(true)
    }
  }

  function handleCancelDelete(e: React.MouseEvent) {
    e.stopPropagation()
    setConfirming(false)
  }

  return (
    <div
      onClick={() => navigate({ to: '/sessions/$sessionId', params: { sessionId: session.id } })}
      className="bg-gradient-to-b from-[#16162a] to-[#12121a] border border-[#1e1e2e] rounded-lg p-5 cursor-pointer hover:border-[#2e2e4e] hover:shadow-lg hover:shadow-black/30 transition-all duration-200 group"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-white truncate group-hover:text-white transition-colors">
            {session.name ?? 'Untitled Session'}
          </h3>
          <p className="text-xs text-[#6b7280] mt-0.5">
            {session.session_date ? formatSessionDate(session.session_date) : 'No date'}
          </p>
        </div>
        <Badge status={session.status} className="ml-3 flex-shrink-0" />
      </div>

      {/* Best lap time */}
      {session.best_lap_time_ms != null && (
        <div className="flex items-center gap-1.5">
          <svg className="w-3 h-3 text-[#457b9d] flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-xs font-mono text-[#e2e8f0] tracking-tight">
            {formatLapTime(session.best_lap_time_ms)}
          </span>
          <span className="text-xs text-[#4b5563]">best</span>
        </div>
      )}

      {/* Delete controls */}
      <div className="mt-3 pt-3 border-t border-[#1e1e2e] flex items-center justify-end gap-2">
        {confirming ? (
          <>
            <span className="text-xs text-[#ff5252] mr-auto">Delete session?</span>
            <button
              onClick={handleCancelDelete}
              className="text-xs text-[#6b7280] hover:text-white px-2 py-1 rounded transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleDeleteClick}
              className="text-xs text-[#ff5252] hover:text-white bg-[#ff5252]/10 hover:bg-[#ff5252]/20 px-2 py-1 rounded transition-colors"
            >
              Confirm
            </button>
          </>
        ) : (
          <button
            onClick={handleDeleteClick}
            className="text-xs text-[#6b7280] hover:text-[#ff5252] px-2 py-1 rounded transition-colors opacity-0 group-hover:opacity-100"
          >
            Delete
          </button>
        )}
      </div>
    </div>
  )
}

export function DashboardPage() {
  const navigate = useNavigate()
  const user = useStore((s) => s.user)
  const queryClient = useQueryClient()

  const { data: sessions, isLoading, error } = useQuery({
    queryKey: ['sessions'],
    queryFn: listSessions,
  })

  const deleteMutation = useMutation({
    mutationFn: deleteSession,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  })

  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      <AppHeader
        subtitle="Telemetry Platform"
        navItems={user?.role === 'admin' ? [
          { label: 'Circuits', to: '/admin/circuits' },
          { label: 'Users', to: '/admin/users' },
        ] : undefined}
      />

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Page Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold text-white">Sessions</h2>
            <p className="text-sm text-[#6b7280] mt-1">
              {sessions ? `${sessions.length} session${sessions.length !== 1 ? 's' : ''}` : ''}
            </p>
          </div>
          <Button
            variant="primary"
            onClick={() => navigate({ to: '/sessions/new' })}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New Session
          </Button>
        </div>

        {/* Content */}
        {isLoading && <SpinnerOverlay label="Loading sessions…" />}

        {error && (
          <div className="bg-[#ff5252]/10 border border-[#ff5252]/30 rounded-lg p-4 text-center">
            <p className="text-sm text-[#ff5252]">Failed to load sessions. Please refresh.</p>
          </div>
        )}

        {!isLoading && !error && sessions && sessions.length === 0 && (
          <EmptyState
            icon={
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M9 17v-6l-2-2m4 8v-8l2-2m-2 10h4m-4 0H7m-2-4h14M5 7h14" />
              </svg>
            }
            title="No sessions yet"
            description="Upload your first telemetry file to get started with lap time analysis."
            action={
              <Button variant="primary" onClick={() => navigate({ to: '/sessions/new' })}>
                Create First Session
              </Button>
            }
          />
        )}

        {!isLoading && sessions && sessions.length > 0 && (() => {
          // Group sessions by circuit name, preserving order of first appearance
          const groups: { name: string; sessions: Session[] }[] = []
          const seen = new Map<string, Session[]>()
          for (const s of sessions) {
            const key = s.circuit_name ?? 'No Track Assigned'
            if (!seen.has(key)) {
              const arr: Session[] = []
              seen.set(key, arr)
              groups.push({ name: key, sessions: arr })
            }
            seen.get(key)!.push(s)
          }
          return (
            <div className="space-y-8">
              {groups.map((group) => (
                <div key={group.name}>
                  <div className="flex items-center gap-3 mb-4">
                    <h3 className="text-sm font-semibold text-[#e2e8f0]">{group.name}</h3>
                    <div className="flex-1 h-px bg-[#1e1e2e]" />
                    <span className="text-xs text-[#4b5563]">{group.sessions.length}</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                    {group.sessions.map((session) => (
                      <SessionCard
                        key={session.id}
                        session={session}
                        onDelete={(id) => deleteMutation.mutate(id)}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )
        })()}
      </main>
    </div>
  )
}
