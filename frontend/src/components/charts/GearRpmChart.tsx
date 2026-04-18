import { useEffect, useRef } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
import type { OverlayResponse } from '../../types/api'
import { overlayToUPlot, attachTouchCursor } from '../../utils/telemetry'
import { useStore } from '../../store'

interface GearRpmChartProps {
  overlay: OverlayResponse | null
  selectedLaps: number[]
  lapColorMap: Record<number, string>
}

function makeOpts(
  width: number,
  height: number,
  selectedLaps: number[],
  lapColorMap: Record<number, string>,
  hasGear: boolean,
  hasRpm: boolean,
  setCursorDistance: (d: number | null) => void,
): uPlot.Options {
  const series: uPlot.Series[] = [{ label: 'Distance (m)' }]

  for (let i = 0; i < selectedLaps.length; i++) {
    const lapNum = selectedLaps[i]
    const color = lapColorMap[lapNum] ?? '#ffffff'
    const dash = i === 1 ? [6, 4] : undefined
    if (hasGear) {
      series.push({ label: `L${lapNum} Gear`, scale: 'gear', stroke: color, width: 2, dash })
    }
    if (hasRpm) {
      series.push({
        label: `L${lapNum} RPM`,
        scale: 'rpm',
        stroke: color,
        width: 1.5,
        dash: dash ?? [2, 2],
        alpha: 0.6,
      })
    }
  }

  const axes: uPlot.Axis[] = [
    {
      label: 'Distance (m)',
      stroke: '#6b7280',
      grid: { stroke: '#1e1e2e', width: 1 },
      ticks: { stroke: '#1e1e2e' },
      font: '11px monospace',
      labelFont: '11px sans-serif',
      labelGap: 8,
    },
  ]

  if (hasGear) {
    axes.push({
      scale: 'gear',
      label: 'Gear',
      stroke: '#6b7280',
      grid: { stroke: '#1e1e2e', width: 1 },
      ticks: { stroke: '#1e1e2e' },
      font: '11px monospace',
      labelFont: '11px sans-serif',
      labelGap: 8,
      values: (_u, splits) => splits.map((v) => Math.round(v).toString()),
    })
  }

  if (hasRpm) {
    axes.push({
      scale: 'rpm',
      label: 'RPM',
      side: 1,
      stroke: '#6b7280',
      grid: { show: false },
      ticks: { stroke: '#1e1e2e' },
      font: '11px monospace',
      labelFont: '11px sans-serif',
      labelGap: 8,
    })
  }

  return {
    width,
    height,
    cursor: {
      sync: { key: 'telemetry-sync' },
      drag: { x: true, y: false },
    },
    hooks: {
      setCursor: [
        (u) => {
          const idx = u.cursor.idx
          if (idx != null && u.data[0]) {
            setCursorDistance((u.data[0][idx] as number) ?? null)
          } else {
            setCursorDistance(null)
          }
        },
      ],
    },
    axes,
    scales: {
      x: { time: false },
      gear: { range: [0, 8] },
      rpm: { range: [0, 16000] },
    },
    series,
    legend: { show: selectedLaps.length > 0 },
  }
}

export function GearRpmChart({ overlay, selectedLaps, lapColorMap }: GearRpmChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<uPlot | null>(null)
  const setCursorDistanceM = useStore((s) => s.setCursorDistanceM)

  useEffect(() => {
    if (!containerRef.current || !overlay || selectedLaps.length === 0) return

    const hasGear = overlay.channels.includes('gear')
    const hasRpm = overlay.channels.includes('rpm')
    if (!hasGear && !hasRpm) return

    const gearData = hasGear ? overlayToUPlot(overlay, selectedLaps, 'gear') : []
    const rpmData = hasRpm ? overlayToUPlot(overlay, selectedLaps, 'rpm') : []

    const distances = (gearData[0] ?? rpmData[0]) as number[]
    if (!distances || distances.length === 0) return

    // Build interleaved data: [distances, gear_lap1, rpm_lap1, gear_lap2, rpm_lap2, ...]
    const combined: (number | null)[][] = [distances]
    for (let i = 0; i < selectedLaps.length; i++) {
      if (hasGear && gearData[i + 1]) combined.push(gearData[i + 1] as number[])
      if (hasRpm && rpmData[i + 1]) combined.push(rpmData[i + 1] as number[])
    }

    const width = containerRef.current.clientWidth
    const height = containerRef.current.clientHeight || 200

    if (chartRef.current) {
      chartRef.current.destroy()
      chartRef.current = null
    }

    const opts = makeOpts(width, height, selectedLaps, lapColorMap, hasGear, hasRpm, setCursorDistanceM)
    chartRef.current = new uPlot(opts, combined as uPlot.AlignedData, containerRef.current)
    const detachTouch = attachTouchCursor(chartRef.current)

    const ro = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry && chartRef.current) {
        chartRef.current.setSize({ width: entry.contentRect.width, height: entry.contentRect.height || 200 })
      }
    })
    ro.observe(containerRef.current)

    return () => {
      detachTouch()
      ro.disconnect()
      chartRef.current?.destroy()
      chartRef.current = null
    }
  }, [overlay, selectedLaps, lapColorMap, setCursorDistanceM])

  if (!overlay || selectedLaps.length === 0) return null
  if (!overlay.channels.includes('gear') && !overlay.channels.includes('rpm')) return null

  return (
    <div className="bg-[#0d0d14] rounded-lg border border-[#1e1e2e] p-2">
      <div className="text-xs text-[#6b7280] uppercase tracking-widest px-2 pb-1 font-medium">Gear / RPM</div>
      <div ref={containerRef} className="w-full" style={{ height: '200px' }} />
    </div>
  )
}
