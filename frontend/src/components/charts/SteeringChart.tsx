import { useEffect, useRef } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
import type { OverlayResponse } from '../../types/api'
import { overlayToUPlot } from '../../utils/telemetry'
import { useStore } from '../../store'

interface SteeringChartProps {
  overlay: OverlayResponse | null
  selectedLaps: number[]
  lapColorMap: Record<number, string>
}

function makeOpts(
  width: number,
  height: number,
  selectedLaps: number[],
  lapColorMap: Record<number, string>,
  setCursorDistance: (d: number | null) => void,
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
            setCursorDistance((u.data[0][idx] as number) ?? null)
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
        label: 'Steering (deg)',
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
      y: { range: [-200, 200] },
    },
    series,
    legend: { show: selectedLaps.length > 0 },
  }
}

export function SteeringChart({ overlay, selectedLaps, lapColorMap }: SteeringChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<uPlot | null>(null)
  const setCursorDistanceM = useStore((s) => s.setCursorDistanceM)

  useEffect(() => {
    if (!containerRef.current || !overlay || selectedLaps.length === 0) return

    const data = overlayToUPlot(overlay, selectedLaps, 'steering_deg')
    if (data.length === 0 || !data[0] || data[0].length === 0) return

    const width = containerRef.current.clientWidth
    const height = containerRef.current.clientHeight || 200

    if (chartRef.current) {
      chartRef.current.destroy()
      chartRef.current = null
    }

    const opts = makeOpts(width, height, selectedLaps, lapColorMap, setCursorDistanceM)
    chartRef.current = new uPlot(opts, data as uPlot.AlignedData, containerRef.current)

    const ro = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry && chartRef.current) {
        chartRef.current.setSize({ width: entry.contentRect.width, height: entry.contentRect.height || 200 })
      }
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chartRef.current?.destroy()
      chartRef.current = null
    }
  }, [overlay, selectedLaps, lapColorMap, setCursorDistanceM])

  if (!overlay || selectedLaps.length === 0) return null
  if (!overlay.channels.includes('steering_deg')) return null

  return (
    <div className="bg-[#0d0d14] rounded-lg border border-[#1e1e2e] p-2">
      <div className="text-xs text-[#6b7280] uppercase tracking-widest px-2 pb-1 font-medium">Steering (deg)</div>
      <div ref={containerRef} className="w-full" style={{ height: '200px' }} />
    </div>
  )
}
