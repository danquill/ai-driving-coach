import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listSessions } from '../api/sessions'
import { getMe, updateMe } from '../api/users'
import type { Session } from '../types/api'
import { AppHeader } from '../components/ui/AppHeader'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { formatLapTime, formatSessionDate } from '../utils/telemetry'
import { useStore } from '../store'

// ─── Track record row ─────────────────────────────────────────────────────────

function TrackRecord({ trackName, bestSession }: {
  trackName: string
  bestSession: Session
}) {
  const navigate = useNavigate()
  return (
    <tr
      onClick={() => navigate({ to: '/sessions/$sessionId', params: { sessionId: bestSession.id } })}
      className="border-t border-[#1e1e2e] hover:bg-[#16162a] cursor-pointer transition-colors group"
    >
      <td className="px-4 py-3">
        <span className="text-sm text-white">{trackName}</span>
      </td>
      <td className="px-4 py-3">
        {bestSession.best_lap_time_ms != null ? (
          <span className="text-sm font-mono text-[#e2e8f0] tracking-tight">
            {formatLapTime(bestSession.best_lap_time_ms)}
          </span>
        ) : (
          <span className="text-sm text-[#4b5563]">—</span>
        )}
      </td>
      <td className="px-4 py-3">
        <span className="text-sm text-[#6b7280]">{bestSession.name ?? 'Untitled Session'}</span>
      </td>
      <td className="px-4 py-3">
        <span className="text-xs text-[#4b5563]">
          {bestSession.session_date ? formatSessionDate(bestSession.session_date) : '—'}
        </span>
      </td>
      <td className="px-4 py-3">
        <Badge status={bestSession.status} />
      </td>
      <td className="px-4 py-3 text-right">
        <span className="text-xs text-[#457b9d] opacity-0 group-hover:opacity-100 transition-opacity">
          View →
        </span>
      </td>
    </tr>
  )
}

// ─── Profile Page ─────────────────────────────────────────────────────────────

export function ProfilePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const setAuth = useStore((s) => s.setAuth)
  const accessToken = useStore((s) => s.accessToken)

  const { data: me } = useQuery({ queryKey: ['me'], queryFn: getMe })
  const { data: sessions = [] } = useQuery({ queryKey: ['sessions'], queryFn: listSessions })

  // Edit profile state
  const [displayName, setDisplayName] = useState('')
  const [editingProfile, setEditingProfile] = useState(false)

  // Password change state
  const [changingPassword, setChangingPassword] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordError, setPasswordError] = useState('')

  const updateMutation = useMutation({
    mutationFn: updateMe,
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ['me'] })
      // Sync updated display_name into the store so the header reflects it immediately
      if (accessToken) {
        setAuth(accessToken, {
          id: updated.id,
          email: updated.email,
          display_name: updated.display_name,
          role: updated.role,
        })
      }
      setEditingProfile(false)
      setChangingPassword(false)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setPasswordError('')
    },
    onError: () => {
      setPasswordError('Password update failed. Please check your current password and try again.')
    },
  })

  function handleProfileSave(e: React.FormEvent) {
    e.preventDefault()
    if (!displayName.trim()) return
    updateMutation.mutate({ display_name: displayName.trim() })
  }

  function handlePasswordSave(e: React.FormEvent) {
    e.preventDefault()
    setPasswordError('')
    if (newPassword.length < 8) { setPasswordError('New password must be at least 8 characters.'); return }
    if (newPassword !== confirmPassword) { setPasswordError('Passwords do not match.'); return }
    updateMutation.mutate({ current_password: currentPassword, new_password: newPassword })
  }

  // Derive per-track best sessions
  const trackBests = new Map<string, Session>()
  for (const s of sessions) {
    if (s.best_lap_time_ms == null) continue
    const key = s.circuit_name ?? 'No Track Assigned'
    const existing = trackBests.get(key)
    if (!existing || s.best_lap_time_ms < (existing.best_lap_time_ms ?? Infinity)) {
      trackBests.set(key, s)
    }
  }
  const trackRecords = [...trackBests.entries()].sort((a, b) => a[0].localeCompare(b[0]))

  const ROLE_LABELS: Record<string, string> = { admin: 'Admin', coach: 'Coach', driver: 'Driver' }
  const ROLE_COLORS: Record<string, string> = {
    admin: 'text-[#e63946]',
    coach: 'text-[#457b9d]',
    driver: 'text-[#6b7280]',
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      <AppHeader
        subtitle="Profile"
        rightAction={{ label: 'Dashboard', onClick: () => navigate({ to: '/' }) }}
      />

      <main className="max-w-3xl mx-auto px-6 py-8 space-y-8">

        {/* Account info */}
        <section className="bg-[#12121a] border border-[#1e1e2e] rounded-xl p-6">
          <div className="flex items-start justify-between mb-6">
            <div>
              <h2 className="text-lg font-bold text-white">{me?.display_name}</h2>
              <p className="text-sm text-[#6b7280] mt-0.5">{me?.email}</p>
              <span className={`text-xs font-medium mt-1 inline-block ${ROLE_COLORS[me?.role ?? ''] ?? 'text-[#6b7280]'}`}>
                {ROLE_LABELS[me?.role ?? ''] ?? me?.role}
              </span>
            </div>
            {!editingProfile && !changingPassword && (
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => { setDisplayName(me?.display_name ?? ''); setEditingProfile(true) }}
                >
                  Edit Profile
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setChangingPassword(true)}
                >
                  Change Password
                </Button>
              </div>
            )}
          </div>

          {/* Edit display name form */}
          {editingProfile && (
            <form onSubmit={handleProfileSave} className="border-t border-[#1e1e2e] pt-5 space-y-4">
              <div>
                <label className="text-xs text-[#6b7280] block mb-1">Display Name</label>
                <input
                  autoFocus
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="w-full max-w-sm text-sm bg-[#0d0d14] border border-[#2e2e4e] rounded px-3 py-2 text-white focus:outline-none focus:border-[#457b9d]"
                />
              </div>
              {updateMutation.isError && (
                <p className="text-xs text-[#ff5252]">Failed to update profile. Please try again.</p>
              )}
              <div className="flex gap-2">
                <Button variant="primary" size="sm" type="submit" disabled={!displayName.trim() || updateMutation.isPending}>
                  {updateMutation.isPending ? 'Saving…' : 'Save'}
                </Button>
                <Button variant="ghost" size="sm" type="button" onClick={() => setEditingProfile(false)}>Cancel</Button>
              </div>
            </form>
          )}

          {/* Change password form */}
          {changingPassword && (
            <form onSubmit={handlePasswordSave} className="border-t border-[#1e1e2e] pt-5 space-y-4">
              <div>
                <label className="text-xs text-[#6b7280] block mb-1">Current Password</label>
                <input
                  type="password"
                  autoFocus
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="w-full max-w-sm text-sm bg-[#0d0d14] border border-[#2e2e4e] rounded px-3 py-2 text-white focus:outline-none focus:border-[#457b9d]"
                />
              </div>
              <div>
                <label className="text-xs text-[#6b7280] block mb-1">New Password</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full max-w-sm text-sm bg-[#0d0d14] border border-[#2e2e4e] rounded px-3 py-2 text-white focus:outline-none focus:border-[#457b9d]"
                />
              </div>
              <div>
                <label className="text-xs text-[#6b7280] block mb-1">Confirm New Password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full max-w-sm text-sm bg-[#0d0d14] border border-[#2e2e4e] rounded px-3 py-2 text-white focus:outline-none focus:border-[#457b9d]"
                />
              </div>
              {passwordError && <p className="text-xs text-[#ff5252]">{passwordError}</p>}
              <div className="flex gap-2">
                <Button
                  variant="primary"
                  size="sm"
                  type="submit"
                  disabled={!currentPassword || !newPassword || !confirmPassword || updateMutation.isPending}
                >
                  {updateMutation.isPending ? 'Saving…' : 'Update Password'}
                </Button>
                <Button variant="ghost" size="sm" type="button" onClick={() => { setChangingPassword(false); setPasswordError('') }}>
                  Cancel
                </Button>
              </div>
            </form>
          )}
        </section>

        {/* Track records */}
        <section>
          <div className="flex items-center gap-3 mb-4">
            <h3 className="text-sm font-semibold text-[#e2e8f0]">Best Laps by Track</h3>
            <div className="flex-1 h-px bg-[#1e1e2e]" />
            <span className="text-xs text-[#4b5563]">{trackRecords.length} track{trackRecords.length !== 1 ? 's' : ''}</span>
          </div>

          {trackRecords.length === 0 ? (
            <div className="bg-[#12121a] border border-[#1e1e2e] rounded-xl p-8 text-center">
              <p className="text-sm text-[#4b5563]">No lap times recorded yet.</p>
            </div>
          ) : (
            <div className="bg-[#12121a] border border-[#1e1e2e] rounded-xl overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-xs text-[#6b7280] uppercase tracking-wider">
                    <th className="px-4 py-3 font-medium">Track</th>
                    <th className="px-4 py-3 font-medium">Best Lap</th>
                    <th className="px-4 py-3 font-medium">Session</th>
                    <th className="px-4 py-3 font-medium">Date</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {trackRecords.map(([trackName, session]) => (
                    <TrackRecord key={trackName} trackName={trackName} bestSession={session} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

      </main>
    </div>
  )
}
