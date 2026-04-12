import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useStore } from '../store'
import { AppHeader } from '../components/ui/AppHeader'
import { Tabs, TabList, Tab, TabPanel } from '../components/ui/Tabs'
import { Button } from '../components/ui/Button'
import { listInvites, createInvite, deleteInvite } from '../api/invites'
import client from '../api/client'
import type { Invite } from '../api/invites'

// ─── Beta Status Panel ─────────────────────────────────────────────────────

function BetaPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ['beta-status'],
    queryFn: async () => {
      const r = await client.get<{ beta_mode: boolean }>('/auth/beta-status')
      return r.data
    },
  })

  return (
    <div className="max-w-lg space-y-6">
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-white">Beta Mode</h3>
          {isLoading ? (
            <span className="text-xs text-[#6b7280]">Loading…</span>
          ) : data?.beta_mode ? (
            <span className="text-xs font-bold uppercase tracking-widest px-2 py-0.5 rounded bg-[#e63946]/20 text-[#e63946] border border-[#e63946]/30">
              Enabled
            </span>
          ) : (
            <span className="text-xs font-bold uppercase tracking-widest px-2 py-0.5 rounded bg-[#6b7280]/20 text-[#9ca3af] border border-[#6b7280]/30">
              Disabled
            </span>
          )}
        </div>
        <p className="text-xs text-[#9ca3af] leading-relaxed mb-4">
          When beta mode is enabled, new accounts require a valid invite code to register.
          Existing users are not affected.
        </p>
        <div className="bg-[#0d0d14] border border-[#1e1e2e] rounded p-3 text-xs font-mono text-[#6b7280]">
          <p className="text-[#4b5563] mb-1"># .env</p>
          <p>
            <span className="text-[#457b9d]">BETA_MODE</span>
            <span className="text-[#9ca3af]">=</span>
            <span className={data?.beta_mode ? 'text-[#e63946]' : 'text-[#00e676]'}>
              {data?.beta_mode ? 'true' : 'false'}
            </span>
          </p>
        </div>
        <p className="mt-3 text-xs text-[#4b5563]">
          Toggle by editing <code className="text-[#9ca3af]">BETA_MODE</code> in your <code className="text-[#9ca3af]">.env</code> file and restarting the API container.
        </p>
      </div>
    </div>
  )
}

// ─── Invite Codes Panel ────────────────────────────────────────────────────

function InviteRow({ invite, onDelete }: { invite: Invite; onDelete: (id: string) => void }) {
  const [copied, setCopied] = useState(false)
  const isUsed = invite.used_at != null

  function copy() {
    navigator.clipboard.writeText(invite.code)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <tr className="border-t border-[#1e1e2e] hover:bg-[#16162a] transition-colors">
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <code className="text-sm font-mono text-[#d1d5db]">{invite.code}</code>
          {!isUsed && (
            <button
              onClick={copy}
              className="text-xs text-[#457b9d] hover:text-white transition-colors"
              title="Copy to clipboard"
            >
              {copied ? '✓' : 'copy'}
            </button>
          )}
        </div>
      </td>
      <td className="px-4 py-3 text-xs text-[#9ca3af]">
        {invite.email ?? <span className="text-[#4b5563]">any</span>}
      </td>
      <td className="px-4 py-3">
        {isUsed ? (
          <span className="text-xs text-[#6b7280]">
            Used {new Date(invite.used_at!).toLocaleDateString()}
          </span>
        ) : (
          <span className="text-xs text-[#00e676]">Available</span>
        )}
      </td>
      <td className="px-4 py-3 text-xs text-[#6b7280] font-mono">
        {new Date(invite.created_at).toLocaleDateString()}
      </td>
      <td className="px-4 py-3">
        {!isUsed && (
          <button
            onClick={() => onDelete(invite.id)}
            className="text-xs text-[#ff5252]/70 hover:text-[#ff5252] transition-colors"
          >
            Revoke
          </button>
        )}
      </td>
    </tr>
  )
}

function InvitesPanel() {
  const qc = useQueryClient()
  const [email, setEmail] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [filter, setFilter] = useState<'all' | 'available' | 'used'>('all')

  const { data: invites = [], isLoading } = useQuery({
    queryKey: ['admin', 'invites'],
    queryFn: listInvites,
  })

  const createMutation = useMutation({
    mutationFn: () => createInvite(email.trim() || undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'invites'] })
      setEmail('')
      setShowForm(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteInvite,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'invites'] }),
  })

  const filtered = invites.filter((inv) => {
    if (filter === 'available') return inv.used_at == null
    if (filter === 'used') return inv.used_at != null
    return true
  })

  const counts = {
    total: invites.length,
    available: invites.filter((i) => i.used_at == null).length,
    used: invites.filter((i) => i.used_at != null).length,
  }

  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4 text-xs text-[#6b7280]">
          <span><span className="text-white font-medium">{counts.total}</span> total</span>
          <span className="text-[#00e676]"><span className="font-medium">{counts.available}</span> available</span>
          <span><span className="font-medium">{counts.used}</span> used</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded overflow-hidden border border-[#1e1e2e] text-xs">
            {(['all', 'available', 'used'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 capitalize transition-colors ${
                  filter === f
                    ? 'bg-[#1e1e2e] text-white'
                    : 'text-[#6b7280] hover:text-[#9ca3af]'
                }`}
              >
                {f}
              </button>
            ))}
          </div>
          <Button variant="primary" size="sm" onClick={() => setShowForm((v) => !v)}>
            + New Invite
          </Button>
        </div>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="bg-[#12121a] border border-[#457b9d]/30 rounded-lg p-4 flex items-end gap-3">
          <div className="flex-1">
            <label className="block text-xs font-medium text-[#9ca3af] mb-1.5 uppercase tracking-wide">
              Lock to email <span className="normal-case text-[#4b5563]">(optional)</span>
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="driver@team.com"
              className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded px-3 py-2 text-sm text-white placeholder-[#374151] focus:outline-none focus:border-[#457b9d]"
            />
          </div>
          <Button
            variant="primary"
            size="sm"
            loading={createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            Generate
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setShowForm(false)}>
            Cancel
          </Button>
        </div>
      )}

      {/* Table */}
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-lg overflow-hidden">
        {isLoading ? (
          <div className="py-12 text-center text-[#6b7280] text-sm">Loading…</div>
        ) : filtered.length === 0 ? (
          <div className="py-12 text-center text-[#6b7280] text-sm">
            {filter !== 'all' ? `No ${filter} invite codes.` : 'No invite codes yet. Generate one above.'}
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="text-left text-xs text-[#6b7280] uppercase tracking-wider">
                <th className="px-4 py-3 font-medium">Code</th>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Created</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((inv) => (
                <InviteRow
                  key={inv.id}
                  invite={inv}
                  onDelete={(id) => deleteMutation.mutate(id)}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {createMutation.isError && (
        <p className="text-xs text-[#ff5252]">Failed to generate invite code. Please try again.</p>
      )}
      {deleteMutation.isError && (
        <p className="text-xs text-[#ff5252]">Failed to delete invite code. Please try again.</p>
      )}
    </div>
  )
}

// ─── Page ──────────────────────────────────────────────────────────────────

export function AdminPlatformPage() {
  const navigate = useNavigate()
  const user = useStore((s) => s.user)

  useEffect(() => {
    if (!user) { navigate({ to: '/login' }); return }
    if (user.role !== 'admin') { navigate({ to: '/' }) }
  }, [user, navigate])

  if (!user || user.role !== 'admin') return null

  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      <AppHeader
        subtitle="Platform"
        navItems={[
          { label: 'Users', to: '/admin/users' },
          { label: 'Circuits', to: '/admin/circuits' },
        ]}
        rightAction={{ label: 'Dashboard', onClick: () => navigate({ to: '/' }) }}
      />

      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-white">Platform Settings</h2>
          <p className="text-sm text-[#6b7280] mt-1">Beta access, invite codes, and platform configuration</p>
        </div>

        <Tabs defaultTab="invites">
          <TabList className="mb-6">
            <Tab value="invites">Invite Codes</Tab>
            <Tab value="beta">Beta Mode</Tab>
          </TabList>

          <TabPanel value="invites">
            <InvitesPanel />
          </TabPanel>

          <TabPanel value="beta">
            <BetaPanel />
          </TabPanel>
        </Tabs>
      </main>
    </div>
  )
}
