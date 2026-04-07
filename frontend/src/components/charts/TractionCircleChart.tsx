import { useEffect, useRef } from 'react'
import type { OverlayResponse } from '../../types/api'
import { useStore } from '../../store'

interface TractionCircleChartProps {
  overlay: OverlayResponse | null
  selectedLaps: number[]
  lapColorMap: Record<number, string>
}

const SIZE = 340
const PAD = 32
const PLOT = SIZE - PAD * 2
const CX = SIZE / 2
const CY = SIZE / 2
const R = PLOT / 2

function toCanvas(g: number, max: number): number {
  return (g / max) * R
}

function computeMaxG(overlay: OverlayResponse, selectedLaps: number[], latIdx: number, lonIdx: number): number {
  let maxG = 2.0
  for (const lapNum of selectedLaps) {
    for (const row of overlay.laps[String(lapNum)] ?? []) {
      if (row[latIdx] != null) maxG = Math.max(maxG, Math.abs(row[latIdx]))
      if (row[lonIdx] != null) maxG = Math.max(maxG, Math.abs(row[lonIdx]))
    }
  }
  return Math.ceil(maxG * 2) / 2
}

function drawBase(
  ctx: CanvasRenderingContext2D,
  overlay: OverlayResponse,
  selectedLaps: number[],
  lapColorMap: Record<number, string>,
  latIdx: number,
  lonIdx: number,
  maxG: number,
  dpr: number
) {
  ctx.save()
  ctx.scale(dpr, dpr)
  ctx.clearRect(0, 0, SIZE, SIZE)

  // Dark circle fill
  ctx.beginPath()
  ctx.arc(CX, CY, R, 0, Math.PI * 2)
  ctx.fillStyle = '#0a0a12'
  ctx.fill()

  // Concentric rings
  const ringCount = Math.round(maxG / 0.5)
  for (let i = 1; i <= ringCount; i++) {
    const rr = (i / ringCount) * R
    ctx.beginPath()
    ctx.arc(CX, CY, rr, 0, Math.PI * 2)
    ctx.strokeStyle = i === ringCount ? '#2e2e4e' : '#1a1a2e'
    ctx.lineWidth = i === ringCount ? 1.5 : 0.75
    ctx.stroke()
    if (i % 2 === 0 || i === ringCount) {
      ctx.fillStyle = '#374151'
      ctx.font = '9px monospace'
      ctx.textAlign = 'center'
      ctx.fillText(`${(i * 0.5).toFixed(1)}G`, CX + rr + 2, CY - 3)
    }
  }

  // Crosshair
  ctx.strokeStyle = '#1e1e2e'
  ctx.lineWidth = 0.75
  ctx.beginPath(); ctx.moveTo(CX - R, CY); ctx.lineTo(CX + R, CY); ctx.stroke()
  ctx.beginPath(); ctx.moveTo(CX, CY - R); ctx.lineTo(CX, CY + R); ctx.stroke()

  // Axis labels
  ctx.fillStyle = '#4b5563'
  ctx.font = '9px sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText('Brake', CX, CY - R - 6)
  ctx.fillText('Accel', CX, CY + R + 12)
  ctx.textAlign = 'right'; ctx.fillText('Left', CX - R - 4, CY + 3)
  ctx.textAlign = 'left'; ctx.fillText('Right', CX + R + 4, CY + 3)

  // Data points
  for (let lapIdx = 0; lapIdx < selectedLaps.length; lapIdx++) {
    const lapNum = selectedLaps[lapIdx]
    const isComparison = lapIdx === 1
    const color = lapColorMap[lapNum] ?? '#ffffff'
    const rows = overlay.laps[String(lapNum)] ?? []
    if (rows.length === 0) continue

    ctx.save()
    ctx.globalAlpha = isComparison ? 0.45 : 0.6
    const dotR = isComparison ? 1.2 : 1.5
    for (const row of rows) {
      const latG = row[latIdx]
      const lonG = row[lonIdx]
      if (latG == null || lonG == null) continue
      ctx.beginPath()
      ctx.arc(CX + toCanvas(latG, maxG), CY - toCanvas(lonG, maxG), dotR, 0, Math.PI * 2)
      ctx.fillStyle = color
      ctx.fill()
    }
    ctx.restore()

    // Dashed 95th-percentile envelope for CMP lap
    if (isComparison) {
      const radii = rows
        .map((row) => {
          const lat = row[latIdx]; const lon = row[lonIdx]
          return lat != null && lon != null ? Math.sqrt(lat * lat + lon * lon) : 0
        })
        .filter((r) => r > 0)
        .sort((a, b) => a - b)
      if (radii.length > 0) {
        const p95 = radii[Math.floor(radii.length * 0.95)]
        ctx.save()
        ctx.setLineDash([4, 3])
        ctx.strokeStyle = color
        ctx.globalAlpha = 0.3
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.arc(CX, CY, toCanvas(p95, maxG), 0, Math.PI * 2)
        ctx.stroke()
        ctx.restore()
      }
    }
  }

  // Legend
  selectedLaps.forEach((lapNum, i) => {
    const color = lapColorMap[lapNum] ?? '#ffffff'
    const lx = PAD
    const ly = SIZE - PAD + 6 + i * 13
    ctx.save()
    ctx.globalAlpha = 1
    if (i === 1) ctx.setLineDash([4, 3])
    ctx.strokeStyle = color
    ctx.lineWidth = 2
    ctx.beginPath(); ctx.moveTo(lx, ly); ctx.lineTo(lx + 14, ly); ctx.stroke()
    ctx.restore()
    ctx.fillStyle = color
    ctx.font = '9px monospace'
    ctx.textAlign = 'left'
    ctx.fillText(i === 0 ? `Lap ${lapNum} REF` : `Lap ${lapNum} CMP`, lx + 18, ly + 3)
  })

  ctx.restore()
}

function drawCursor(
  canvas: HTMLCanvasElement,
  off: HTMLCanvasElement,
  overlay: OverlayResponse,
  selectedLaps: number[],
  lapColorMap: Record<number, string>,
  latIdx: number,
  lonIdx: number,
  maxG: number,
  dpr: number,
  distanceM: number | null,
) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.drawImage(off, 0, 0)
  if (distanceM === null || latIdx === -1 || lonIdx === -1) return

  const distIdx = overlay.channels.indexOf('distance_m')
  if (distIdx === -1) return

  ctx.save()
  ctx.scale(dpr, dpr)

  for (let lapIdx = 0; lapIdx < selectedLaps.length; lapIdx++) {
    const lapNum = selectedLaps[lapIdx]
    const color = lapColorMap[lapNum] ?? '#ffffff'
    const rows = overlay.laps[String(lapNum)] ?? []
    if (rows.length === 0) continue

    // Normalize: distanceM is zero-based (from chart), but rows use
    // cumulative session distance. Offset by this lap's first distance sample.
    const lapOffset = rows[0][distIdx]
    const targetDist = distanceM + lapOffset

    let bestIdx = 0, bestDiff = Infinity
    for (let i = 0; i < rows.length; i++) {
      const d = Math.abs(rows[i][distIdx] - targetDist)
      if (d < bestDiff) { bestDiff = d; bestIdx = i }
    }

    const row = rows[bestIdx]
    const latG = row[latIdx]
    const lonG = row[lonIdx]
    if (latG == null || lonG == null) continue

    const px = CX + toCanvas(latG, maxG)
    const py = CY - toCanvas(lonG, maxG)

    ctx.beginPath()
    ctx.arc(px, py, 7, 0, Math.PI * 2)
    ctx.strokeStyle = color
    ctx.globalAlpha = 0.35
    ctx.lineWidth = 3
    ctx.stroke()

    ctx.beginPath()
    ctx.arc(px, py, 4, 0, Math.PI * 2)
    ctx.fillStyle = color
    ctx.globalAlpha = 1
    ctx.fill()

    ctx.beginPath()
    ctx.arc(px, py, 1.5, 0, Math.PI * 2)
    ctx.fillStyle = '#ffffff'
    ctx.globalAlpha = 0.9
    ctx.fill()
  }

  ctx.restore()
}

export function TractionCircleChart({ overlay, selectedLaps, lapColorMap }: TractionCircleChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const offscreenRef = useRef<HTMLCanvasElement | null>(null)
  const maxGRef = useRef(2.0)
  const latIdxRef = useRef(-1)
  const lonIdxRef = useRef(-1)
  const dprRef = useRef(1)

  const cursorDistanceM = useStore((s) => s.cursorDistanceM)
  const cursorRef = useRef(cursorDistanceM)
  cursorRef.current = cursorDistanceM

  // Stable refs for cursor effect
  const overlayRef = useRef(overlay)
  const selectedLapsRef = useRef(selectedLaps)
  const lapColorMapRef = useRef(lapColorMap)
  overlayRef.current = overlay
  selectedLapsRef.current = selectedLaps
  lapColorMapRef.current = lapColorMap

  // ── Base render (scatter + grid) ────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !overlay || selectedLaps.length === 0) return

    const latIdx = overlay.channels.indexOf('lat_g')
    const lonIdx = overlay.channels.indexOf('lon_g')
    if (latIdx === -1 || lonIdx === -1) return

    const dpr = window.devicePixelRatio || 1
    dprRef.current = dpr
    latIdxRef.current = latIdx
    lonIdxRef.current = lonIdx

    const maxG = computeMaxG(overlay, selectedLaps, latIdx, lonIdx)
    maxGRef.current = maxG

    // Draw base to offscreen canvas
    const off = document.createElement('canvas')
    off.width = SIZE * dpr
    off.height = SIZE * dpr
    const offCtx = off.getContext('2d')!
    drawBase(offCtx, overlay, selectedLaps, lapColorMap, latIdx, lonIdx, maxG, dpr)
    offscreenRef.current = off

    // Blit to visible canvas
    canvas.width = SIZE * dpr
    canvas.height = SIZE * dpr
    canvas.style.width = `${SIZE}px`
    canvas.style.height = `${SIZE}px`
    const ctx = canvas.getContext('2d')!
    ctx.drawImage(off, 0, 0)

    // Apply current cursor on top after base render (use rAF so refs are settled)
    requestAnimationFrame(() => {
      const c = canvasRef.current
      const o = offscreenRef.current
      if (c && o && overlayRef.current) {
        drawCursor(c, o, overlayRef.current, selectedLapsRef.current, lapColorMapRef.current,
          latIdxRef.current, lonIdxRef.current, maxGRef.current, dprRef.current, cursorRef.current)
      }
    })
  }, [overlay, selectedLaps, lapColorMap])

  // ── Cursor overlay — only depends on cursorDistanceM, reads everything via refs ──
  useEffect(() => {
    const canvas = canvasRef.current
    const off = offscreenRef.current
    if (!canvas || !off || !overlayRef.current || selectedLapsRef.current.length === 0) return
    drawCursor(
      canvas, off,
      overlayRef.current,
      selectedLapsRef.current,
      lapColorMapRef.current,
      latIdxRef.current,
      lonIdxRef.current,
      maxGRef.current,
      dprRef.current,
      cursorDistanceM,
    )
  }, [cursorDistanceM])

  if (!overlay || selectedLaps.length === 0) return null

  const hasGData = overlay.channels.includes('lat_g') && overlay.channels.includes('lon_g')

  if (!hasGData) {
    return (
      <div
        className="flex items-center justify-center rounded-lg border border-[#1e1e2e] bg-[#0d0d14]"
        style={{ width: SIZE, height: SIZE }}
      >
        <p className="text-xs text-[#6b7280] text-center px-4">
          Enable Lat G &amp; Lon G channels
        </p>
      </div>
    )
  }

  return (
    <div className="bg-[#0d0d14] rounded-lg border border-[#1e1e2e] p-2">
      <div className="text-xs text-[#6b7280] uppercase tracking-widest px-2 pb-1 font-medium">
        Traction Circle
      </div>
      <div className="flex justify-center">
        <canvas ref={canvasRef} style={{ width: SIZE, height: SIZE }} />
      </div>
    </div>
  )
}
