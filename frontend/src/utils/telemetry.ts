import chroma from 'chroma-js'
import type { OverlayResponse } from '../types/api'
import type uPlot from 'uplot'

// ─── Touch cursor support ──────────────────────────────────────────────────────

/**
 * Attaches touch event listeners to a uPlot instance so that sliding a finger
 * across the chart moves the cursor (and fires setCursor hooks / sync) exactly
 * as a mouse hover would. Returns a cleanup function.
 */
export function attachTouchCursor(u: uPlot): () => void {
  const canvas = u.ctx.canvas

  function toMouseEvent(touch: Touch, type: string): MouseEvent {
    return new MouseEvent(type, {
      bubbles: true,
      cancelable: true,
      clientX: touch.clientX,
      clientY: touch.clientY,
    })
  }

  function onTouchStart(e: TouchEvent) {
    if (e.touches.length !== 1) return
    canvas.dispatchEvent(toMouseEvent(e.touches[0], 'mouseenter'))
    canvas.dispatchEvent(toMouseEvent(e.touches[0], 'mousemove'))
  }

  function onTouchMove(e: TouchEvent) {
    if (e.touches.length !== 1) return
    e.preventDefault()
    canvas.dispatchEvent(toMouseEvent(e.touches[0], 'mousemove'))
  }

  function onTouchEnd() {
    canvas.dispatchEvent(new MouseEvent('mouseleave', { bubbles: true }))
  }

  canvas.addEventListener('touchstart', onTouchStart, { passive: false })
  canvas.addEventListener('touchmove', onTouchMove, { passive: false })
  canvas.addEventListener('touchend', onTouchEnd)

  return () => {
    canvas.removeEventListener('touchstart', onTouchStart)
    canvas.removeEventListener('touchmove', onTouchMove)
    canvas.removeEventListener('touchend', onTouchEnd)
  }
}

// ─── uPlot data transformation ────────────────────────────────────────────────

/**
 * Transforms OverlayResponse into uPlot's AlignedData (parallel arrays).
 * X-axis = distance_m (first channel). Each subsequent array = one lap's channel values.
 *
 * The overlay response format:
 *   channels: ["distance_m", "speed_kph"]
 *   laps: { "1": [[0.0, 112.4], [1.0, 113.1], ...], "2": [...] }
 *
 * Each inner array is ONE ROW: [distance_m, channel_value].
 * We transpose to: [allDistances[], lapN_channel[], ...]
 */
export function overlayToUPlot(
  overlay: OverlayResponse,
  lapNumbers: number[],
  channel: string
): uPlot.AlignedData {
  const distIdx = overlay.channels.indexOf('distance_m')
  const chanIdx = overlay.channels.indexOf(channel)

  if (distIdx === -1 || chanIdx === -1) return []

  // Use first selected lap's distances as X axis, normalized to start at 0.
  // Each lap's distance_m is cumulative session distance — we subtract the
  // first sample so every lap starts at 0 and they overlay correctly.
  const firstLapKey = String(lapNumbers[0])
  const firstLapData = overlay.laps[firstLapKey] ?? []
  const firstOffset = firstLapData.length > 0 ? firstLapData[0][distIdx] : 0
  const distances = firstLapData.map((row) => row[distIdx] - firstOffset)

  const result: uPlot.AlignedData = [distances]

  for (const lapNum of lapNumbers) {
    const lapData = overlay.laps[String(lapNum)] ?? []
    const values = lapData.map((row) => row[chanIdx])
    result.push(values)
  }

  return result
}

// ─── Lap time formatting ──────────────────────────────────────────────────────

/**
 * Formats milliseconds as M:SS.mmm
 */
export function formatLapTime(ms: number): string {
  if (!ms || ms <= 0) return '--:--.---'
  const totalSec = ms / 1000
  const minutes = Math.floor(totalSec / 60)
  const seconds = totalSec % 60
  const secStr = seconds.toFixed(3).padStart(6, '0')
  return `${minutes}:${secStr}`
}

/**
 * Formats a delta in ms as ±X.XXX
 */
export function formatDelta(ms: number): string {
  const sign = ms < 0 ? '-' : '+'
  const abs = Math.abs(ms)
  const totalSec = abs / 1000
  const minutes = Math.floor(totalSec / 60)
  const seconds = totalSec % 60
  if (minutes > 0) {
    return `${sign}${minutes}:${seconds.toFixed(3).padStart(6, '0')}`
  }
  return `${sign}${seconds.toFixed(3)}`
}

/**
 * Formats a session date string as "Jan 5, '25"
 */
export function formatSessionDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' })
}

// ─── Color scales ─────────────────────────────────────────────────────────────

const SPEED_SCALE = chroma.scale(['#0080ff', '#00ff80', '#ffff00', '#ff4000'])

/**
 * Returns RGBA tuple [r, g, b, a] for a speed value.
 */
export function speedToColor(
  speed: number,
  min: number,
  max: number
): [number, number, number, number] {
  const t = max === min ? 0 : Math.max(0, Math.min(1, (speed - min) / (max - min)))
  const c = SPEED_SCALE(t).rgba()
  return [Math.round(c[0]), Math.round(c[1]), Math.round(c[2]), 255]
}

const THROTTLE_SCALE = chroma.scale(['#1a1a2e', '#00e676'])
const BRAKE_SCALE = chroma.scale(['#1a1a2e', '#ff5252'])
const STEERING_SCALE = chroma.scale(['#ff5252', '#ffffff', '#457b9d'])
const LATERAL_G_SCALE = chroma.scale(['#00e676', '#ff5252'])

/**
 * Dispatches to appropriate color scale per channel.
 */
export function channelToColor(
  value: number,
  channel: string
): [number, number, number, number] {
  let t: number
  let c: chroma.Color

  switch (channel) {
    case 'speed_kph':
      return speedToColor(value, 0, 280)
    case 'throttle_pct':
      t = Math.max(0, Math.min(1, value / 100))
      c = THROTTLE_SCALE(t)
      break
    case 'brake_pct':
      t = Math.max(0, Math.min(1, value / 100))
      c = BRAKE_SCALE(t)
      break
    case 'steering_deg':
      t = Math.max(0, Math.min(1, (value + 180) / 360))
      c = STEERING_SCALE(t)
      break
    case 'lat_g':
      t = Math.max(0, Math.min(1, (value + 3) / 6))
      c = LATERAL_G_SCALE(t)
      break
    default:
      return [100, 100, 100, 255]
  }

  const rgba = c.rgba()
  return [Math.round(rgba[0]), Math.round(rgba[1]), Math.round(rgba[2]), 255]
}
