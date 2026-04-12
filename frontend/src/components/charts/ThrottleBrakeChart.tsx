import { useEffect, useRef } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
import type { OverlayResponse } from '../../types/api'
import { overlayToUPlot } from '../../utils/telemetry'
import { useStore } from '../../store'
import { Spinner } from '../ui/Spinner'

interface ThrottleBrakeChartProps {
  overlay: OverlayResponse | null
  selectedLaps: number[]
  lapColorMap: Record<number, string>
}

function makeOpts(
  width: number,
  height: number,
  selectedLaps: number[],
  lapColorMap: Record<number, string>,
  channels: string[],
  setCursorDistance: (d: number | null) => void
): uPlot.Options {
  // Build series for throttle + brake per lap
  const series: uPlot.Series[] = [{ label: 'Distance (m)' }]

  for (let i = 0; i < selectedLaps.length; i++) {
    const lapNum = selectedLaps[i]
    const isComparison = i === 1
    const dash = isComparison ? [6, 4] : undefined
    const throttleFill = isComparison ? 'rgba(0,230,118,0.06)' : 'rgba(0,230,118,0.15)'
    const brakeFill = isComparison ? 'rgba(255,82,82,0.08)' : 'rgba(255,82,82,0.2)'
    void (lapColorMap[lapNum])
    if (channels.includes('throttle_pct')) {
      series.push({
        label: `Lap ${lapNum} Throttle`,
        stroke: '#00e676',
        fill: throttleFill,
        width: 1.5,
        dash,
        points: { show: false },
      })
    }
    if (channels.includes('brake_pct')) {
      series.push({
        label: `Lap ${lapNum} Brake`,
        stroke: '#ff5252',
        fill: brakeFill,
        width: 1.5,
        dash,
        points: { show: false },
      })
    }
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
        label: '%',
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
      y: { range: [0, 105] },
    },
    series,
    legend: { show: false },
  }
}

export function ThrottleBrakeChart({ overlay, selectedLaps, lapColorMap }: ThrottleBrakeChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<uPlot | null>(null)
  const setCursorDistanceM = useStore((s) => s.setCursorDistanceM)

  useEffect(() => {
    if (!containerRef.current || !overlay || selectedLaps.length === 0) return

    const throttleData = overlayToUPlot(overlay, selectedLaps, 'throttle_pct')
    const brakeData = overlayToUPlot(overlay, selectedLaps, 'brake_pct')
    const hasThrottle = throttleData.length > 1
    const hasBrake = brakeData.length > 1

    if (!hasThrottle && !hasBrake) return

    // Build combined data array: [distances, ...throttleSeries, ...brakeSeries]
    const distances = throttleData[0] ?? brakeData[0]
    const combined: (number | null)[][] = [distances as number[]]

    const channelsPresent: string[] = []
    for (let i = 0; i < selectedLaps.length; i++) {
      if (hasThrottle && throttleData[i + 1]) {
        combined.push(throttleData[i + 1] as number[])
        channelsPresent.push('throttle_pct')
      }
      if (hasBrake && brakeData[i + 1]) {
        combined.push(brakeData[i + 1] as number[])
        channelsPresent.push('brake_pct')
      }
    }

    const width = containerRef.current.clientWidth
    const height = containerRef.current.clientHeight || 260

    if (chartRef.current) {
      chartRef.current.destroy()
      chartRef.current = null
    }

    const opts = makeOpts(width, height, selectedLaps, lapColorMap, channelsPresent, setCursorDistanceM)
    chartRef.current = new uPlot(
      opts,
      combined as uPlot.AlignedData,
      containerRef.current
    )

    const ro = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry && chartRef.current) {
        chartRef.current.setSize({
          width: entry.contentRect.width,
          height: entry.contentRect.height || 260,
        })
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
      <div className="flex items-center justify-center h-40 bg-[#0d0d14] rounded-lg border border-[#1e1e2e]">
        <Spinner size="sm" />
      </div>
    )
  }

  if (selectedLaps.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 bg-[#0d0d14] rounded-lg border border-[#1e1e2e]">
        <p className="text-xs text-[#6b7280]">Select laps to display throttle/brake trace</p>
      </div>
    )
  }

  return (
    <div className="bg-[#0d0d14] rounded-lg border border-[#1e1e2e] p-2">
      <div className="flex items-center gap-4 px-2 pb-1">
        <span className="text-xs text-[#6b7280] uppercase tracking-widest font-medium">
          Throttle / Brake (%)
        </span>
        <div className="flex items-center gap-3 ml-auto">
          <span className="flex items-center gap-1 text-xs text-[#6b7280]">
            <span className="w-3 h-0.5 bg-[#00e676] inline-block" /> Throttle
          </span>
          <span className="flex items-center gap-1 text-xs text-[#6b7280]">
            <span className="w-3 h-0.5 bg-[#ff5252] inline-block" /> Brake
          </span>
        </div>
      </div>
      <div ref={containerRef} className="w-full" style={{ height: '260px' }} />
    </div>
  )
}
