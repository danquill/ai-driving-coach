import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { listSessions, deleteSession } from '../api/sessions'
import type { Session } from '../types/api'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { SpinnerOverlay } from '../components/ui/Spinner'
import { useStore } from '../store'

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
            {session.session_date
              ? new Date(session.session_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' })
              : 'No date'}
          </p>
        </div>
        <Badge status={session.status} className="ml-3 flex-shrink-0" />
      </div>

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
  const clearAuth = useStore((s) => s.clearAuth)
  const queryClient = useQueryClient()

  const { data: sessions, isLoading, error } = useQuery({
    queryKey: ['sessions'],
    queryFn: listSessions,
  })

  const deleteMutation = useMutation({
    mutationFn: deleteSession,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  })

  function handleLogout() {
    clearAuth()
    navigate({ to: '/login' })
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      {/* Top Nav */}
      <header className="border-b border-[#1e1e2e] bg-[#12121a]">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-black tracking-[0.2em] text-white">
              TR<span className="text-[#e63946]">A</span>CK
            </h1>
            <span className="text-[#1e1e2e]">|</span>
            <span className="text-sm text-[#6b7280]">Telemetry Platform</span>
          </div>
          <div className="flex items-center gap-4">
            {user && (
              <span className="text-xs text-[#6b7280]">{user.display_name}</span>
            )}
            {user?.role === 'admin' && (
              <Button variant="ghost" size="sm" onClick={() => navigate({ to: '/admin/circuits' })}>
                Circuits
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              Sign Out
            </Button>
          </div>
        </div>
      </header>

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

        {!isLoading && sessions && sessions.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {sessions.map((session) => (
              <SessionCard
                key={session.id}
                session={session}
                onDelete={(id) => deleteMutation.mutate(id)}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
