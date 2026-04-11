import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { listSessions, deleteSession, getDemoSession } from '../api/sessions'
import { listEvents, createEvent, updateEvent, deleteEvent, assignSessions } from '../api/events'
import { listCircuits } from '../api/circuits'
import type { Session, Event } from '../types/api'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { SpinnerOverlay } from '../components/ui/Spinner'
import { AppHeader } from '../components/ui/AppHeader'
import { useStore } from '../store'
import { formatLapTime, formatSessionDate } from '../utils/telemetry'

// ─── Dashboard empty state ────────────────────────────────────────────────────

function DashboardEmptyState() {
  const navigate = useNavigate()
  const { data: demo } = useQuery({ queryKey: ['demo-session'], queryFn: getDemoSession })

  return (
    <div className="flex flex-col items-center py-16 px-4">
      {/* Icon */}
      <div className="w-14 h-14 rounded-full bg-[#16162a] border border-[#1e1e2e] flex items-center justify-center mb-5">
        <svg className="w-7 h-7 text-[#457b9d]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M9 17v-6l-2-2m4 8v-8l2-2m-2 10h4m-4 0H7m-2-4h14M5 7h14" />
        </svg>
      </div>

      <h3 className="text-lg font-semibold text-white mb-2">No sessions yet</h3>
      <p className="text-sm text-[#6b7280] text-center max-w-sm mb-6">
        Upload a telemetry file (.csv, .vbo, .ld) from your data logger to start analysing lap times, speed traces, and more.
      </p>

      <Button variant="primary" onClick={() => navigate({ to: '/sessions/new' })}>
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
        Upload Your First Session
      </Button>

      {/* Demo session callout */}
      {demo && (
        <div className="mt-10 w-full max-w-md bg-[#12121a] border border-[#1e1e2e] rounded-xl p-5">
          <div className="flex items-start gap-3 mb-4">
            <div className="w-8 h-8 rounded-full bg-[#457b9d]/15 flex items-center justify-center flex-shrink-0 mt-0.5">
              <svg className="w-4 h-4 text-[#457b9d]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-medium text-white mb-0.5">Browse an example session</p>
              <p className="text-xs text-[#6b7280]">
                See what the analysis looks like with real data — a full track day at Virginia International Raceway.
              </p>
            </div>
          </div>
          <div className="flex items-center justify-between bg-[#0a0a0f] rounded-lg px-4 py-3 mb-4">
            <div>
              <p className="text-sm font-medium text-white">{demo.name ?? 'VIR Full'}</p>
              <p className="text-xs text-[#6b7280] mt-0.5">{demo.circuit_name} · {demo.best_lap_time_ms != null ? `Best: ${Math.floor(demo.best_lap_time_ms / 60000)}:${((demo.best_lap_time_ms % 60000) / 1000).toFixed(3).padStart(6, '0')}` : ''}</p>
            </div>
            <span className="text-xs text-[#4b5563] bg-[#1e1e2e] px-2 py-0.5 rounded">Example</span>
          </div>
          <Button
            variant="secondary"
            className="w-full"
            onClick={() => navigate({ to: '/sessions/$sessionId', params: { sessionId: demo.id } })}
          >
            Open Example Session
          </Button>
        </div>
      )}
    </div>
  )
}

// ─── Session Card ─────────────────────────────────────────────────────────────

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

// ─── Session grid ─────────────────────────────────────────────────────────────

function SessionGrid({ sessions, onDelete }: { sessions: Session[]; onDelete: (id: string) => void }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {sessions.map((s) => (
        <SessionCard key={s.id} session={s} onDelete={onDelete} />
      ))}
    </div>
  )
}

// ─── Event form modal ─────────────────────────────────────────────────────────

interface EventFormModalProps {
  initial?: Event
  onClose: () => void
  onSave: (data: { name: string; event_date?: string; circuit_id?: string; notes?: string }) => void
  saving: boolean
}

function EventFormModal({ initial, onClose, onSave, saving }: EventFormModalProps) {
  const [name, setName] = useState(initial?.name ?? '')
  const [eventDate, setEventDate] = useState(initial?.event_date ?? '')
  const [circuitId, setCircuitId] = useState(initial?.circuit_id ?? '')
  const [notes, setNotes] = useState(initial?.notes ?? '')

  const { data: circuits = [] } = useQuery({ queryKey: ['circuits'], queryFn: listCircuits })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    onSave({
      name: name.trim(),
      event_date: eventDate || undefined,
      circuit_id: circuitId || undefined,
      notes: notes.trim() || undefined,
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-xl w-full max-w-md p-6 shadow-2xl">
        <h3 className="text-sm font-semibold text-white mb-5">
          {initial ? 'Edit Event' : 'New Event'}
        </h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-xs text-[#6b7280] block mb-1">Name *</label>
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Summit Point Track Day"
              className="w-full text-sm bg-[#0d0d14] border border-[#2e2e4e] rounded px-3 py-2 text-white placeholder-[#4b5563] focus:outline-none focus:border-[#457b9d]"
            />
          </div>
          <div>
            <label className="text-xs text-[#6b7280] block mb-1">Date</label>
            <input
              type="date"
              value={eventDate}
              onChange={(e) => setEventDate(e.target.value)}
              className="w-full text-sm bg-[#0d0d14] border border-[#2e2e4e] rounded px-3 py-2 text-white focus:outline-none focus:border-[#457b9d]"
            />
          </div>
          <div>
            <label className="text-xs text-[#6b7280] block mb-1">Circuit</label>
            <select
              value={circuitId}
              onChange={(e) => setCircuitId(e.target.value)}
              className="w-full text-sm bg-[#0d0d14] border border-[#2e2e4e] rounded px-3 py-2 text-white focus:outline-none focus:border-[#457b9d]"
            >
              <option value="">— None —</option>
              {circuits.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-[#6b7280] block mb-1">Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="Conditions, goals, setup notes…"
              className="w-full text-sm bg-[#0d0d14] border border-[#2e2e4e] rounded px-3 py-2 text-white placeholder-[#4b5563] focus:outline-none focus:border-[#457b9d] resize-none"
            />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="ghost" size="sm" type="button" onClick={onClose}>Cancel</Button>
            <Button variant="primary" size="sm" type="submit" disabled={!name.trim() || saving}>
              {saving ? 'Saving…' : 'Save'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ─── Session picker modal ─────────────────────────────────────────────────────

interface SessionPickerModalProps {
  event: Event
  allSessions: Session[]
  onClose: () => void
  onSave: (sessionIds: string[]) => void
  saving: boolean
}

function SessionPickerModal({ event, allSessions, onClose, onSave, saving }: SessionPickerModalProps) {
  const eligible = allSessions.filter(
    (s) => s.event_id == null || s.event_id === event.id
  )
  const [selected, setSelected] = useState<Set<string>>(
    new Set(allSessions.filter((s) => s.event_id === event.id).map((s) => s.id))
  )

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) { next.delete(id) } else { next.add(id) }
      return next
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-xl w-full max-w-md p-6 shadow-2xl flex flex-col max-h-[80vh]">
        <h3 className="text-sm font-semibold text-white mb-1">Manage Sessions</h3>
        <p className="text-xs text-[#6b7280] mb-4">Select sessions to include in <span className="text-white">{event.name}</span></p>

        <div className="flex-1 overflow-y-auto space-y-1 min-h-0">
          {eligible.length === 0 && (
            <p className="text-xs text-[#4b5563] py-4 text-center">No sessions available to assign.</p>
          )}
          {eligible.map((s) => (
            <label
              key={s.id}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-[#16162a] cursor-pointer transition-colors"
            >
              <input
                type="checkbox"
                checked={selected.has(s.id)}
                onChange={() => toggle(s.id)}
                className="w-3.5 h-3.5 accent-[#457b9d] flex-shrink-0"
              />
              <div className="flex-1 min-w-0">
                <span className="text-sm text-white truncate block">{s.name ?? 'Untitled Session'}</span>
                <span className="text-xs text-[#6b7280]">
                  {s.circuit_name ?? 'No track'}{s.session_date ? ` · ${formatSessionDate(s.session_date)}` : ''}
                  {s.best_lap_time_ms != null ? ` · ${formatLapTime(s.best_lap_time_ms)}` : ''}
                </span>
              </div>
              <Badge status={s.status} />
            </label>
          ))}
        </div>

        <div className="flex justify-between items-center pt-4 border-t border-[#1e1e2e] mt-4">
          <span className="text-xs text-[#4b5563]">{selected.size} selected</span>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button>
            <Button variant="primary" size="sm" onClick={() => onSave([...selected])} disabled={saving}>
              {saving ? 'Saving…' : 'Save'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Event Block ──────────────────────────────────────────────────────────────

interface EventBlockProps {
  event: Event
  sessions: Session[]
  allSessions: Session[]
  onDelete: (id: string) => void
  onEdit: (event: Event) => void
  onDeleteEvent: (id: string) => void
  onManageSessions: (event: Event) => void
}

function EventBlock({ event, sessions, allSessions, onDelete, onEdit, onDeleteEvent, onManageSessions }: EventBlockProps) {
  const [expanded, setExpanded] = useState(true)
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  return (
    <div className="border border-[#1e1e2e] rounded-xl overflow-hidden">
      {/* Event header */}
      <div className="bg-[#16162a] px-5 py-3 flex items-center gap-3">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-2 flex-1 min-w-0 text-left group"
        >
          <svg
            className={`w-3.5 h-3.5 text-[#6b7280] flex-shrink-0 transition-transform ${expanded ? 'rotate-90' : ''}`}
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <span className="text-sm font-semibold text-white truncate group-hover:text-white">{event.name}</span>
          {event.event_date && (
            <span className="text-xs text-[#6b7280] flex-shrink-0">{formatSessionDate(event.event_date)}</span>
          )}
          {event.circuit_name && (
            <span className="text-xs text-[#4b5563] flex-shrink-0">· {event.circuit_name}</span>
          )}
        </button>
        <span className="text-xs text-[#4b5563] flex-shrink-0">{sessions.length} session{sessions.length !== 1 ? 's' : ''}</span>
        <div className="flex items-center gap-1 border-l border-[#1e1e2e] pl-3 ml-1">
          <button
            onClick={() => onManageSessions(event)}
            className="text-xs text-[#6b7280] hover:text-white px-2 py-1 rounded transition-colors"
          >
            Sessions
          </button>
          <button
            onClick={() => onEdit(event)}
            className="text-xs text-[#6b7280] hover:text-white px-2 py-1 rounded transition-colors"
          >
            Edit
          </button>
          {confirmingDelete ? (
            <>
              <span className="text-xs text-[#ff5252]">Delete event?</span>
              <button
                onClick={() => setConfirmingDelete(false)}
                className="text-xs text-[#6b7280] hover:text-white px-2 py-1 rounded transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => onDeleteEvent(event.id)}
                className="text-xs text-[#ff5252] hover:text-white px-2 py-1 rounded transition-colors"
              >
                Confirm
              </button>
            </>
          ) : (
            <button
              onClick={() => setConfirmingDelete(true)}
              className="text-xs text-[#6b7280] hover:text-[#ff5252] px-2 py-1 rounded transition-colors"
            >
              Delete
            </button>
          )}
        </div>
      </div>

      {/* Sessions grid */}
      {expanded && (
        <div className="p-4 bg-[#0a0a0f]">
          {sessions.length === 0 ? (
            <p className="text-xs text-[#4b5563] text-center py-6">No sessions in this event yet. Click "Sessions" to add some.</p>
          ) : (
            <SessionGrid sessions={sessions} onDelete={onDelete} />
          )}
        </div>
      )}
    </div>
  )
}

// ─── Dashboard Page ───────────────────────────────────────────────────────────

export function DashboardPage() {
  const navigate = useNavigate()
  const user = useStore((s) => s.user)
  const queryClient = useQueryClient()

  const { data: sessions, isLoading: sessionsLoading, error } = useQuery({
    queryKey: ['sessions'],
    queryFn: listSessions,
  })

  const { data: events = [], isLoading: eventsLoading } = useQuery({
    queryKey: ['events'],
    queryFn: listEvents,
  })

  const isLoading = sessionsLoading || eventsLoading

  const deleteMutation = useMutation({
    mutationFn: deleteSession,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  })

  const createEventMutation = useMutation({
    mutationFn: createEvent,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['events'] }),
  })

  const updateEventMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updateEvent>[1] }) =>
      updateEvent(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['events'] }),
  })

  const deleteEventMutation = useMutation({
    mutationFn: deleteEvent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['events'] })
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
    },
  })

  const assignMutation = useMutation({
    mutationFn: ({ eventId, sessionIds }: { eventId: string; sessionIds: string[] }) =>
      assignSessions(eventId, sessionIds),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  })

  // Modal state
  const [showCreateEvent, setShowCreateEvent] = useState(false)
  const [editingEvent, setEditingEvent] = useState<Event | null>(null)
  const [managingEvent, setManagingEvent] = useState<Event | null>(null)

  // Partition sessions
  const eventSessions = new Map<string, Session[]>()
  const ungrouped: Session[] = []
  for (const s of sessions ?? []) {
    if (s.event_id) {
      const arr = eventSessions.get(s.event_id) ?? []
      arr.push(s)
      eventSessions.set(s.event_id, arr)
    } else {
      ungrouped.push(s)
    }
  }

  // Group ungrouped sessions by circuit
  const circuitGroups: { name: string; sessions: Session[] }[] = []
  const seen = new Map<string, Session[]>()
  for (const s of ungrouped) {
    const key = s.circuit_name ?? 'No Track Assigned'
    if (!seen.has(key)) {
      const arr: Session[] = []
      seen.set(key, arr)
      circuitGroups.push({ name: key, sessions: arr })
    }
    seen.get(key)!.push(s)
  }

  const hasContent = (sessions?.length ?? 0) > 0 || events.length > 0

  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      {/* Modals */}
      {showCreateEvent && (
        <EventFormModal
          onClose={() => setShowCreateEvent(false)}
          onSave={(data) => createEventMutation.mutate(data, { onSuccess: () => setShowCreateEvent(false) })}
          saving={createEventMutation.isPending}
        />
      )}
      {editingEvent && (
        <EventFormModal
          initial={editingEvent}
          onClose={() => setEditingEvent(null)}
          onSave={(data) => updateEventMutation.mutate(
            { id: editingEvent.id, data },
            { onSuccess: () => setEditingEvent(null) }
          )}
          saving={updateEventMutation.isPending}
        />
      )}
      {managingEvent && (
        <SessionPickerModal
          event={managingEvent}
          allSessions={sessions ?? []}
          onClose={() => setManagingEvent(null)}
          onSave={(sessionIds) => assignMutation.mutate(
            { eventId: managingEvent.id, sessionIds },
            { onSuccess: () => setManagingEvent(null) }
          )}
          saving={assignMutation.isPending}
        />
      )}

      <AppHeader
        subtitle="Telemetry Platform"
        navItems={user?.role === 'admin' ? [
          { label: 'Circuits', to: '/admin/circuits' },
          { label: 'Users', to: '/admin/users' },
        ] : undefined}
      />

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Page header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold text-white">Sessions</h2>
            <p className="text-sm text-[#6b7280] mt-1">
              {sessions ? `${sessions.length} session${sessions.length !== 1 ? 's' : ''}` : ''}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="blue" onClick={() => setShowCreateEvent(true)}>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
              New Event
            </Button>
            <Button variant="primary" onClick={() => navigate({ to: '/sessions/new' })}>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              New Session
            </Button>
          </div>
        </div>

        {isLoading && <SpinnerOverlay label="Loading sessions…" />}

        {error && (
          <div className="bg-[#ff5252]/10 border border-[#ff5252]/30 rounded-lg p-4 text-center">
            <p className="text-sm text-[#ff5252]">Failed to load sessions. Please refresh.</p>
          </div>
        )}

        {!isLoading && !error && !hasContent && (
          <DashboardEmptyState />
        )}

        {!isLoading && !error && hasContent && (
          <div className="space-y-8">
            {/* Event blocks */}
            {events.length > 0 && (
              <div className="space-y-4">
                {events.map((event) => (
                  <EventBlock
                    key={event.id}
                    event={event}
                    sessions={eventSessions.get(event.id) ?? []}
                    allSessions={sessions ?? []}
                    onDelete={(id) => deleteMutation.mutate(id)}
                    onEdit={setEditingEvent}
                    onDeleteEvent={(id) => deleteEventMutation.mutate(id)}
                    onManageSessions={setManagingEvent}
                  />
                ))}
              </div>
            )}

            {/* Ungrouped sessions by circuit */}
            {circuitGroups.length > 0 && (
              <div className="space-y-8">
                {circuitGroups.map((group) => (
                  <div key={group.name}>
                    <div className="flex items-center gap-3 mb-4">
                      <h3 className="text-sm font-semibold text-[#e2e8f0]">{group.name}</h3>
                      <div className="flex-1 h-px bg-[#1e1e2e]" />
                      <span className="text-xs text-[#4b5563]">{group.sessions.length}</span>
                    </div>
                    <SessionGrid sessions={group.sessions} onDelete={(id) => deleteMutation.mutate(id)} />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
