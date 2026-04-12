import { useState, FormEvent, useEffect, useRef } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { login } from '../api/auth'
import { useStore } from '../store'
import { Button } from '../components/ui/Button'

// ─── Animated track canvas ────────────────────────────────────────────────────

// Virginia International Raceway (VIR Full) — real GPS trace, normalised to [0,1].
// 120 points sampled from actual lap telemetry, centered at (0.5, 0.5), aspect-ratio preserved.
const TRACK_POINTS = [
  [0.5267, 0.0627],
  [0.5531, 0.0612],
  [0.5807, 0.0601],
  [0.6073, 0.0600],
  [0.6352, 0.0604],
  [0.6631, 0.0619],
  [0.6881, 0.0637],
  [0.7065, 0.0656],
  [0.7292, 0.0707],
  [0.7250, 0.0846],
  [0.7153, 0.0968],
  [0.7006, 0.1038],
  [0.6873, 0.1102],
  [0.6712, 0.1112],
  [0.6534, 0.1079],
  [0.6355, 0.1020],
  [0.6182, 0.0948],
  [0.5984, 0.0899],
  [0.5779, 0.0914],
  [0.5592, 0.0990],
  [0.5446, 0.1082],
  [0.5362, 0.1207],
  [0.5372, 0.1354],
  [0.5414, 0.1516],
  [0.5466, 0.1693],
  [0.5522, 0.1872],
  [0.5612, 0.2028],
  [0.5694, 0.2075],
  [0.5801, 0.2028],
  [0.5932, 0.1993],
  [0.6059, 0.2038],
  [0.6155, 0.2157],
  [0.6251, 0.2315],
  [0.6294, 0.2486],
  [0.6220, 0.2643],
  [0.6169, 0.2822],
  [0.6158, 0.3018],
  [0.6112, 0.3223],
  [0.6092, 0.3437],
  [0.6107, 0.3654],
  [0.6112, 0.3896],
  [0.6106, 0.4135],
  [0.6083, 0.4382],
  [0.6060, 0.4639],
  [0.6021, 0.4906],
  [0.6002, 0.5161],
  [0.6008, 0.5430],
  [0.6057, 0.5696],
  [0.6113, 0.5953],
  [0.6095, 0.6222],
  [0.6055, 0.6492],
  [0.6093, 0.6772],
  [0.6091, 0.7021],
  [0.5992, 0.7269],
  [0.5864, 0.7489],
  [0.5787, 0.7710],
  [0.5784, 0.7909],
  [0.5844, 0.8100],
  [0.5967, 0.8278],
  [0.6064, 0.8471],
  [0.6130, 0.8696],
  [0.6180, 0.8915],
  [0.6218, 0.9120],
  [0.6194, 0.9239],
  [0.6126, 0.9296],
  [0.6024, 0.9363],
  [0.5929, 0.9400],
  [0.5870, 0.9339],
  [0.5809, 0.9223],
  [0.5737, 0.9092],
  [0.5656, 0.8953],
  [0.5559, 0.8791],
  [0.5468, 0.8643],
  [0.5367, 0.8460],
  [0.5255, 0.8269],
  [0.5141, 0.8076],
  [0.5018, 0.7874],
  [0.4894, 0.7666],
  [0.4772, 0.7447],
  [0.4656, 0.7215],
  [0.4549, 0.6996],
  [0.4441, 0.6767],
  [0.4334, 0.6535],
  [0.4228, 0.6295],
  [0.4125, 0.6057],
  [0.4023, 0.5820],
  [0.3920, 0.5582],
  [0.3813, 0.5330],
  [0.3705, 0.5074],
  [0.3597, 0.4821],
  [0.3479, 0.4561],
  [0.3365, 0.4335],
  [0.3254, 0.4171],
  [0.3128, 0.4063],
  [0.3037, 0.3976],
  [0.3014, 0.3892],
  [0.3033, 0.3777],
  [0.3166, 0.3689],
  [0.3282, 0.3591],
  [0.3296, 0.3430],
  [0.3256, 0.3214],
  [0.3197, 0.3027],
  [0.3117, 0.2836],
  [0.2993, 0.2662],
  [0.2845, 0.2548],
  [0.2725, 0.2423],
  [0.2708, 0.2296],
  [0.2724, 0.2111],
  [0.2779, 0.1932],
  [0.2905, 0.1775],
  [0.3071, 0.1649],
  [0.3243, 0.1519],
  [0.3431, 0.1394],
  [0.3639, 0.1287],
  [0.3850, 0.1181],
  [0.4061, 0.1076],
  [0.4287, 0.0959],
  [0.4517, 0.0832],
  [0.4753, 0.0726],
  [0.4994, 0.0648],
]

// Interpolate a closed catmull-rom spline at parameter t (0–1 over all segments)
function catmullRom(points: number[][], t: number): [number, number] {
  const n = points.length
  const segment = t * n
  const i = Math.floor(segment) % n
  const u = segment - Math.floor(segment)

  const p0 = points[(i - 1 + n) % n]
  const p1 = points[i]
  const p2 = points[(i + 1) % n]
  const p3 = points[(i + 2) % n]

  const x = 0.5 * (
    (2 * p1[0]) +
    (-p0[0] + p2[0]) * u +
    (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * u * u +
    (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * u * u * u
  )
  const y = 0.5 * (
    (2 * p1[1]) +
    (-p0[1] + p2[1]) * u +
    (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * u * u +
    (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * u * u * u
  )
  return [x, y]
}

// Pre-sample the spline at high resolution for drawing and arc-length parameterisation
const SAMPLES = 1200
const splineSamples: [number, number][] = Array.from({ length: SAMPLES }, (_, i) =>
  catmullRom(TRACK_POINTS, i / SAMPLES)
)

// Speed profile: simulate braking into corners and acceleration out.
// Corner = where curvature is high. We derive a fake speed value per sample.
function deriveSpeed(samples: [number, number][]): number[] {
  const n = samples.length
  const speeds: number[] = new Array(n)
  // Curvature proxy: angle change between consecutive segments
  for (let i = 0; i < n; i++) {
    const a = samples[(i - 1 + n) % n]
    const b = samples[i]
    const c = samples[(i + 1) % n]
    const dx1 = b[0] - a[0], dy1 = b[1] - a[1]
    const dx2 = c[0] - b[0], dy2 = c[1] - b[1]
    const cross = Math.abs(dx1 * dy2 - dy1 * dx2)
    const dot = dx1 * dx2 + dy1 * dy2
    const angle = Math.atan2(cross, Math.max(dot, 1e-9))
    speeds[i] = angle  // high angle = corner = slow
  }
  // Smooth and invert: high curvature → low speed
  const smoothed: number[] = new Array(n)
  const W = 20
  for (let i = 0; i < n; i++) {
    let s = 0
    for (let j = -W; j <= W; j++) s += speeds[(i + j + n) % n]
    smoothed[i] = s / (2 * W + 1)
  }
  const max = Math.max(...smoothed)
  return smoothed.map((v) => 1 - v / max)  // 0=slow, 1=fast
}

const speedProfile = deriveSpeed(splineSamples)

// Speed → colour (blue slow → green mid → red fast), matching speedToColor palette
function speedColor(t: number, alpha = 1): string {
  // blue #0080ff → green #00ff80 → yellow #ffff00 → red #ff4000
  let r, g, b
  if (t < 0.33) {
    const u = t / 0.33
    r = Math.round(0 + u * 0)
    g = Math.round(128 + u * (255 - 128))
    b = Math.round(255 + u * (128 - 255))
  } else if (t < 0.66) {
    const u = (t - 0.33) / 0.33
    r = Math.round(0 + u * 255)
    g = 255
    b = Math.round(128 - u * 128)
  } else {
    const u = (t - 0.66) / 0.34
    r = 255
    g = Math.round(255 - u * 255)
    b = Math.round(0 + u * 0)
  }
  return `rgba(${r},${g},${b},${alpha})`
}

function TrackCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rafRef = useRef<number>(0)
  const tRef = useRef(0)  // car position 0–1

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    function resize() {
      if (!canvas) return
      canvas.width = canvas.offsetWidth * window.devicePixelRatio
      canvas.height = canvas.offsetHeight * window.devicePixelRatio
      ctx!.scale(window.devicePixelRatio, window.devicePixelRatio)
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(canvas)

    function toCanvas(nx: number, ny: number): [number, number] {
      if (!canvas) return [0, 0]
      const w = canvas.offsetWidth
      const h = canvas.offsetHeight
      // Center and scale the normalised track into the canvas with padding
      const pad = 30
      return [pad + nx * (w - pad * 2), pad + ny * (h - pad * 2)]
    }

    function draw(ts: number) {
      if (!canvas || !ctx) return
      const w = canvas.offsetWidth
      const h = canvas.offsetHeight

      ctx.clearRect(0, 0, w, h)

      // ── Draw track base (dark grey, wide) ──────────────────────────────────
      ctx.beginPath()
      const [sx, sy] = toCanvas(...splineSamples[0])
      ctx.moveTo(sx, sy)
      for (let i = 1; i < SAMPLES; i++) {
        const [x, y] = toCanvas(...splineSamples[i])
        ctx.lineTo(x, y)
      }
      ctx.closePath()
      ctx.strokeStyle = 'rgba(30,30,46,0.9)'
      ctx.lineWidth = 22
      ctx.lineJoin = 'round'
      ctx.lineCap = 'round'
      ctx.stroke()

      // ── Draw speed-coloured racing line (thin, on top) ─────────────────────
      for (let i = 0; i < SAMPLES; i++) {
        const a = splineSamples[i]
        const b = splineSamples[(i + 1) % SAMPLES]
        const [x1, y1] = toCanvas(...a)
        const [x2, y2] = toCanvas(...b)
        ctx.beginPath()
        ctx.moveTo(x1, y1)
        ctx.lineTo(x2, y2)
        ctx.strokeStyle = speedColor(speedProfile[i], 0.55)
        ctx.lineWidth = 3
        ctx.stroke()
      }

      // ── Advance car ────────────────────────────────────────────────────────
      // Speed varies 0.6–1.4× base based on speed profile
      const carIdx = Math.floor(tRef.current * SAMPLES) % SAMPLES
      const speed = 0.6 + speedProfile[carIdx] * 0.8
      tRef.current = (tRef.current + speed * 0.00018) % 1

      // ── Draw car trail ─────────────────────────────────────────────────────
      const TRAIL = 40
      for (let j = TRAIL; j >= 0; j--) {
        const trailT = (tRef.current - j / SAMPLES * 2 + 1) % 1
        const [tx, ty] = toCanvas(...catmullRom(TRACK_POINTS, trailT))
        const alpha = (1 - j / TRAIL) * 0.6
        const size = (1 - j / TRAIL) * 3.5
        ctx.beginPath()
        ctx.arc(tx, ty, size, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(230,57,70,${alpha})`
        ctx.fill()
      }

      // ── Draw car dot ───────────────────────────────────────────────────────
      const [cx, cy] = toCanvas(...catmullRom(TRACK_POINTS, tRef.current))
      // Glow
      const grd = ctx.createRadialGradient(cx, cy, 0, cx, cy, 14)
      grd.addColorStop(0, 'rgba(230,57,70,0.5)')
      grd.addColorStop(1, 'rgba(230,57,70,0)')
      ctx.beginPath()
      ctx.arc(cx, cy, 14, 0, Math.PI * 2)
      ctx.fillStyle = grd
      ctx.fill()
      // Dot
      ctx.beginPath()
      ctx.arc(cx, cy, 4.5, 0, Math.PI * 2)
      ctx.fillStyle = '#e63946'
      ctx.fill()
      ctx.beginPath()
      ctx.arc(cx, cy, 4.5, 0, Math.PI * 2)
      ctx.strokeStyle = 'rgba(255,255,255,0.8)'
      ctx.lineWidth = 1.5
      ctx.stroke()

      rafRef.current = requestAnimationFrame(draw)
    }

    rafRef.current = requestAnimationFrame(draw)
    return () => {
      cancelAnimationFrame(rafRef.current)
      ro.disconnect()
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full"
      style={{ opacity: 0.6 }}
    />
  )
}

// ─── Login Page ───────────────────────────────────────────────────────────────

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const setAuth = useStore((s) => s.setAuth)
  const navigate = useNavigate()

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const result = await login(email, password)
      setAuth(result.access_token, result.user)
      navigate({ to: '/' })
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      const msg = Array.isArray(detail)
        ? (detail as { msg?: string }[]).map(e => e.msg ?? String(e)).join(', ')
        : typeof detail === 'string'
          ? detail
          : 'Login failed. Check your credentials.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center px-4 relative overflow-hidden">
      {/* Animated track background */}
      <TrackCanvas />

      {/* Subtle radial vignette so the form sits cleanly over the animation */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse 55% 70% at 50% 50%, transparent 30%, #0a0a0f 100%)',
        }}
      />

      <div className="relative w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <h1 className="text-5xl font-black tracking-[0.25em] text-white mb-1">
            TR<span className="text-[#e63946]">A</span>CK
          </h1>
          <p className="text-xs text-[#6b7280] tracking-widest uppercase">
            Motorsport Telemetry Analysis
          </p>
        </div>

        {/* Card */}
        <div className="bg-gradient-to-b from-[#16162a]/95 to-[#12121a]/95 backdrop-blur-sm border border-[#1e1e2e] rounded-xl p-6 md:p-8 shadow-2xl shadow-black/50">
          <h2 className="text-lg font-semibold text-white mb-6">Sign In</h2>

          <form onSubmit={handleSubmit} className="space-y-4">
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
                autoComplete="current-password"
                placeholder="••••••••"
                className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-md px-3 py-2.5 text-sm text-white placeholder-[#374151] focus:outline-none focus:border-[#457b9d] focus:ring-1 focus:ring-[#457b9d] transition-colors"
              />
            </div>

            {error && (
              <div className="bg-[#ff5252]/10 border border-[#ff5252]/30 rounded-md px-3 py-2">
                <p className="text-xs text-[#ff5252]">{error}</p>
              </div>
            )}

            <Button type="submit" variant="primary" className="w-full mt-2" loading={loading}>
              Sign In
            </Button>
          </form>

          <div className="mt-6 pt-6 border-t border-[#1e1e2e] text-center">
            <p className="text-xs text-[#6b7280]">
              Don't have an account?{' '}
              <a
                href="/register"
                className="text-[#457b9d] hover:text-white transition-colors font-medium"
              >
                Create account
              </a>
            </p>
          </div>
        </div>


      </div>
    </div>
  )
}
