import { useState, FormEvent } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { register } from '../api/auth'
import { Button } from '../components/ui/Button'

export function RegisterPage() {
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await register(email, password, displayName)
      navigate({ to: '/' })
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      const msg = Array.isArray(detail)
        ? (detail as { msg?: string }[]).map(e => e.msg ?? String(e)).join(', ')
        : typeof detail === 'string'
          ? detail
          : 'Registration failed. Please try again.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center px-4">
      <div
        className="absolute inset-0 opacity-5"
        style={{
          backgroundImage: `linear-gradient(#1e1e2e 1px, transparent 1px), linear-gradient(90deg, #1e1e2e 1px, transparent 1px)`,
          backgroundSize: '40px 40px',
        }}
      />

      <div className="relative w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-5xl font-black tracking-[0.25em] text-white mb-1">
            TR<span className="text-[#e63946]">A</span>CK
          </h1>
          <p className="text-xs text-[#6b7280] tracking-widest uppercase">
            Motorsport Telemetry Analysis
          </p>
        </div>

        <div className="bg-gradient-to-b from-[#16162a] to-[#12121a] border border-[#1e1e2e] rounded-xl p-8 shadow-2xl shadow-black/50">
          <h2 className="text-lg font-semibold text-white mb-6">Create Account</h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-[#9ca3af] mb-1.5 uppercase tracking-wide">
                Display Name
              </label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                required
                autoComplete="name"
                placeholder="Your name or callsign"
                className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-md px-3 py-2.5 text-sm text-white placeholder-[#374151] focus:outline-none focus:border-[#457b9d] focus:ring-1 focus:ring-[#457b9d] transition-colors"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-[#9ca3af] mb-1.5 uppercase tracking-wide">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                placeholder="driver@team.com"
                className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-md px-3 py-2.5 text-sm text-white placeholder-[#374151] focus:outline-none focus:border-[#457b9d] focus:ring-1 focus:ring-[#457b9d] transition-colors"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-[#9ca3af] mb-1.5 uppercase tracking-wide">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="new-password"
                minLength={8}
                placeholder="Min. 8 characters"
                className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-md px-3 py-2.5 text-sm text-white placeholder-[#374151] focus:outline-none focus:border-[#457b9d] focus:ring-1 focus:ring-[#457b9d] transition-colors"
              />
            </div>

            {error && (
              <div className="bg-[#ff5252]/10 border border-[#ff5252]/30 rounded-md px-3 py-2">
                <p className="text-xs text-[#ff5252]">{error}</p>
              </div>
            )}

            <Button type="submit" variant="primary" className="w-full mt-2" loading={loading}>
              Create Account
            </Button>
          </form>

          <div className="mt-6 pt-6 border-t border-[#1e1e2e] text-center">
            <p className="text-xs text-[#6b7280]">
              Already have an account?{' '}
              <a
                href="/login"
                className="text-[#457b9d] hover:text-white transition-colors font-medium"
              >
                Sign in
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
