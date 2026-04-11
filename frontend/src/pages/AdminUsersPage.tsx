import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { listUsers, adminUpdateUser } from '../api/users'
import type { UserResponse } from '../types/api'
import { useStore } from '../store'
import { AppHeader } from '../components/ui/AppHeader'

const ROLE_COLORS: Record<string, string> = {
  admin: 'bg-[#e63946]/20 text-[#e63946] border-[#e63946]/30',
  coach: 'bg-[#457b9d]/20 text-[#457b9d] border-[#457b9d]/30',
  driver: 'bg-[#6b7280]/20 text-[#9ca3af] border-[#6b7280]/30',
}

function UserRow({
  user,
  currentUserId,
  onRoleChange,
  onToggleActive,
}: {
  user: UserResponse
  currentUserId: string
  onRoleChange: (id: string, role: string) => void
  onToggleActive: (id: string, active: boolean) => void
}) {
  const isSelf = user.id === currentUserId
  const isActive = user.is_active !== false

  return (
    <tr className="border-t border-[#1e1e2e] hover:bg-[#16162a] transition-colors">
      <td className="px-4 py-3">
        <div className="text-sm text-[#e2e8f0]">{user.display_name}</div>
        <div className="text-xs text-[#6b7280] mt-0.5">{user.email}</div>
      </td>
      <td className="px-4 py-3">
        <span className={`text-xs font-medium px-2 py-0.5 rounded border ${ROLE_COLORS[user.role] ?? ROLE_COLORS.driver}`}>
          {user.role}
        </span>
      </td>
      <td className="px-4 py-3">
        <span className={`text-xs ${isActive ? 'text-[#00e676]' : 'text-[#6b7280]'}`}>
          {isActive ? 'Active' : 'Inactive'}
        </span>
      </td>
      <td className="px-4 py-3 text-xs text-[#6b7280] font-mono">
        {new Date(user.created_at).toLocaleDateString()}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          {/* Role selector */}
          <select
            value={user.role}
            disabled={isSelf}
            onChange={(e) => onRoleChange(user.id, e.target.value)}
            className="text-xs bg-[#0d0d14] border border-[#2e2e4e] rounded px-2 py-1 text-[#d1d5db] focus:outline-none focus:border-[#457b9d] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <option value="driver">driver</option>
            <option value="coach">coach</option>
            <option value="admin">admin</option>
          </select>
          {/* Active toggle */}
          <button
            disabled={isSelf}
            onClick={() => onToggleActive(user.id, !isActive)}
            title={isActive ? 'Deactivate user' : 'Activate user'}
            className={`text-xs px-2 py-1 rounded border transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
              isActive
                ? 'border-[#ff5252]/30 text-[#ff5252] hover:bg-[#ff5252]/10'
                : 'border-[#00e676]/30 text-[#00e676] hover:bg-[#00e676]/10'
            }`}
          >
            {isActive ? 'Deactivate' : 'Activate'}
          </button>
        </div>
      </td>
    </tr>
  )
}

export function AdminUsersPage() {
  const navigate = useNavigate()
  const user = useStore((s) => s.user)
  const qc = useQueryClient()
  const [search, setSearch] = useState('')

  useEffect(() => {
    if (!user) { navigate({ to: '/login' }); return }
    if (user.role !== 'admin') { navigate({ to: '/' }) }
  }, [user, navigate])

  const { data: users = [], isLoading } = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: listUsers,
    enabled: user?.role === 'admin',
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { role?: string; is_active?: boolean } }) =>
      adminUpdateUser(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'users'] }),
  })

  const filtered = users.filter(
    (u) =>
      u.display_name.toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase()),
  )

  const counts = {
    total: users.length,
    admin: users.filter((u) => u.role === 'admin').length,
    coach: users.filter((u) => u.role === 'coach').length,
    driver: users.filter((u) => u.role === 'driver').length,
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      <AppHeader
        subtitle="User Management"
        navItems={[{ label: 'Circuits', to: '/admin/circuits' }]}
        rightAction={{ label: 'Dashboard', onClick: () => navigate({ to: '/' }) }}
      />

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-white">Users</h2>
            <p className="text-sm text-[#6b7280] mt-1">Manage roles and access</p>
          </div>
          {/* Stats */}
          <div className="flex items-center gap-4 text-xs text-[#6b7280]">
            <span><span className="text-white font-medium">{counts.total}</span> total</span>
            <span className="text-[#e63946]"><span className="font-medium">{counts.admin}</span> admin</span>
            <span className="text-[#457b9d]"><span className="font-medium">{counts.coach}</span> coach</span>
            <span><span className="font-medium">{counts.driver}</span> driver</span>
          </div>
        </div>

        {/* Search */}
        <div className="mb-4">
          <input
            type="text"
            placeholder="Search by name or email…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-72 text-sm bg-[#12121a] border border-[#1e1e2e] rounded px-3 py-1.5 text-[#d1d5db] placeholder-[#4b5563] focus:outline-none focus:border-[#457b9d]"
          />
        </div>

        {/* Table */}
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg overflow-hidden">
          {isLoading ? (
            <div className="py-16 text-center text-[#6b7280] text-sm">Loading users…</div>
          ) : filtered.length === 0 ? (
            <div className="py-16 text-center text-[#6b7280] text-sm">
              {search ? 'No users match your search.' : 'No users found.'}
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="text-left text-xs text-[#6b7280] uppercase tracking-wider">
                  <th className="px-4 py-3 font-medium">User</th>
                  <th className="px-4 py-3 font-medium">Role</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Joined</th>
                  <th className="px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((u) => (
                  <UserRow
                    key={u.id}
                    user={u}
                    currentUserId={user?.id ?? ''}
                    onRoleChange={(id, role) => updateMutation.mutate({ id, data: { role } })}
                    onToggleActive={(id, active) =>
                      updateMutation.mutate({ id, data: { is_active: active } })
                    }
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>

        {updateMutation.isError && (
          <p className="mt-3 text-xs text-[#ff5252]">
            {(updateMutation.error as Error)?.message ?? 'Failed to update user.'}
          </p>
        )}
      </main>
    </div>
  )
}
