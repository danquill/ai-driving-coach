import { useEffect, useRef } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
import type { OverlayResponse } from '../../types/api'
import { overlayToUPlot } from '../../utils/telemetry'
import { useStore } from '../../store'
import { Spinner } from '../ui/Spinner'

interface SpeedTraceChartProps {
  overlay: OverlayResponse | null
  selectedLaps: number[]
  lapColorMap: Record<number, string>
}

function makeOpts(
  width: number,
  height: number,
  selectedLaps: number[],
  lapColorMap: Record<number, string>,
  setCursorDistance: (d: number | null) => void
): uPlot.Options {
  const series: uPlot.Series[] = [
    { label: 'Distance (m)' },
    ...selectedLaps.map((lapNum, i) => ({
      label: `Lap ${lapNum}`,
      stroke: lapColorMap[lapNum] ?? '#ffffff',
      width: 2,
      dash: i === 1 ? [6, 4] : undefined,
    })),
  ]

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
            const dist = u.data[0][idx]
            setCursorDistance(dist ?? null)
          } else {
            setCursorDistance(null)
          }
        },
      ],
    },
    axes: [
      {
        label: 'Distance (m)',
        stroke: '#6b7280',
        grid: { stroke: '#1e1e2e', width: 1 },
        ticks: { stroke: '#1e1e2e' },
        font: '11px monospace',
        labelFont: '11px sans-serif',
        labelGap: 8,
      },
      {
        label: 'Speed (kph)',
        stroke: '#6b7280',
        grid: { stroke: '#1e1e2e', width: 1 },
        ticks: { stroke: '#1e1e2e' },
        font: '11px monospace',
        labelFont: '11px sans-serif',
        labelGap: 8,
      },
    ],
    scales: {
      x: { time: false },
    },
    series,
    legend: {
      show: selectedLaps.length > 0,
    },
  }
}

export function SpeedTraceChart({ overlay, selectedLaps, lapColorMap }: SpeedTraceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<uPlot | null>(null)
  const setCursorDistanceM = useStore((s) => s.setCursorDistanceM)


  useEffect(() => {
    if (!containerRef.current || !overlay || selectedLaps.length === 0) return

    const data = overlayToUPlot(overlay, selectedLaps, 'speed_kph')
    if (data.length === 0 || !data[0] || data[0].length === 0) return

    const width = containerRef.current.clientWidth
    const height = containerRef.current.clientHeight || 200

    // Destroy previous instance
    if (chartRef.current) {
      chartRef.current.destroy()
      chartRef.current = null
    }

    const opts = makeOpts(width, height, selectedLaps, lapColorMap, setCursorDistanceM)
    chartRef.current = new uPlot(opts, data as uPlot.AlignedData, containerRef.current)

    // ResizeObserver
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry && chartRef.current) {
        const w = entry.contentRect.width
        const h = entry.contentRect.height || 200
        chartRef.current.setSize({ width: w, height: h })
      }
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chartRef.current?.destroy()
      chartRef.current = null
    }
  }, [overlay, selectedLaps, lapColorMap, setCursorDistanceM])

  if (!overlay) {
    return (
      <div className="flex items-center justify-center h-48 bg-[#0d0d14] rounded-lg border border-[#1e1e2e]">
        <div className="flex flex-col items-center gap-3 text-[#6b7280]">
          <Spinner size="sm" />
          <span className="text-xs">Loading speed trace…</span>
        </div>
      </div>
    )
  }

  if (selectedLaps.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 bg-[#0d0d14] rounded-lg border border-[#1e1e2e]">
        <p className="text-xs text-[#6b7280]">Select laps to display speed trace</p>
      </div>
    )
  }

  return (
    <div className="bg-[#0d0d14] rounded-lg border border-[#1e1e2e] p-2">
      <div className="text-xs text-[#6b7280] uppercase tracking-widest px-2 pb-1 font-medium">Speed (kph)</div>
      <div ref={containerRef} className="w-full" style={{ height: '200px' }} />
    </div>
  )
}
