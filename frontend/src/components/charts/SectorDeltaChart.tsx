import ReactECharts from 'echarts-for-react'
import type { LapDetail, IdealLap } from '../../types/api'
import { LAP_COLORS } from '../../utils/colors'

interface SectorDeltaChartProps {
  laps: LapDetail[]
  idealLap: IdealLap | null
  selectedLapNumbers: number[]
  lapColorMap: Record<number, string>
}

export function SectorDeltaChart({
  laps,
  idealLap: _idealLap,
  selectedLapNumbers,
  lapColorMap,
}: SectorDeltaChartProps) {
  const validLaps = laps.filter((l) => l.is_valid && !l.is_outlap && !l.is_inlap)
  const bestLap = validLaps.reduce<LapDetail | null>(
    (best, l) => !best || (l.lap_time_ms ?? Infinity) < (best.lap_time_ms ?? Infinity) ? l : best,
    null
  )

  if (!bestLap || selectedLapNumbers.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 bg-[#0d0d14] rounded-lg border border-[#1e1e2e]">
        <p className="text-xs text-[#6b7280]">Select laps to see sector deltas</p>
      </div>
    )
  }

  const sectorCount = bestLap.sectors?.length ?? 3
  const sectorLabels = Array.from({ length: sectorCount }, (_, i) => `S${i + 1}`)

  // Build series — one per selected lap
  const displayedLaps = selectedLapNumbers
    .map((n) => laps.find((l) => l.lap_number === n))
    .filter((l): l is LapDetail => !!l)

  const series = displayedLaps.map((lap) => {
    const color = lapColorMap[lap.lap_number] ?? LAP_COLORS[0]
    const data = sectorLabels.map((_, idx) => {
      const lapSector = lap.sectors?.[idx]
      const bestSector = bestLap.sectors?.[idx]
      if (!lapSector || !bestSector) return 0
      return lapSector.sector_time_ms - bestSector.sector_time_ms
    })

    return {
      name: `Lap ${lap.lap_number}`,
      type: 'bar',
      data: data.map((val) => ({
        value: val,
        itemStyle: {
          // Use lap color at full opacity when faster, dimmed when slower
          color: val <= 0 ? color : color + '55',
          borderRadius: val <= 0 ? [0, 4, 4, 0] : [4, 0, 0, 4],
        },
      })),
      label: {
        show: true,
        position: (params: { value: number }) => (params.value <= 0 ? 'right' : 'left'),
        formatter: (params: { value: number }) => {
          const val = params.value / 1000
          const sign = val <= 0 ? '' : '+'
          return `${sign}${val.toFixed(3)}s`
        },
        color: '#9ca3af',
        fontSize: 11,
        fontFamily: 'monospace',
      },
      barGap: '10%',
      barMaxWidth: 24,
      itemStyle: { color },
    }
  })

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#12121a',
      borderColor: '#1e1e2e',
      textStyle: { color: '#e5e7eb', fontFamily: 'monospace', fontSize: 12 },
      formatter: (params: { seriesName: string; name: string; value: number; color: string }[]) => {
        return params
          .map((p) => {
            const val = p.value / 1000
            const sign = val <= 0 ? '' : '+'
            const deltaColor = val <= 0 ? '#00e676' : '#ff5252'
            return `<span style="color:${p.color}">${p.seriesName}</span> ${p.name}: <strong style="color:${deltaColor}">${sign}${val.toFixed(3)}s</strong>`
          })
          .join('<br/>')
      },
    },
    legend: {
      data: displayedLaps.map((l) => `Lap ${l.lap_number}`),
      textStyle: { color: '#9ca3af', fontSize: 11 },
      top: 0,
    },
    grid: {
      left: '8%',
      right: '12%',
      top: 32,
      bottom: 0,
      containLabel: true,
    },
    xAxis: {
      type: 'value',
      name: 'Delta (s)',
      nameTextStyle: { color: '#6b7280', fontSize: 11 },
      axisLine: { lineStyle: { color: '#1e1e2e' } },
      axisLabel: {
        color: '#6b7280',
        fontSize: 10,
        fontFamily: 'monospace',
        formatter: (val: number) => {
          const s = val / 1000
          return (s > 0 ? '+' : '') + s.toFixed(2) + 's'
        },
      },
      splitLine: { lineStyle: { color: '#1e1e2e', type: 'dashed' } },
      axisPointer: { lineStyle: { color: '#2e2e4e' } },
    },
    yAxis: {
      type: 'category',
      data: sectorLabels,
      axisLine: { lineStyle: { color: '#1e1e2e' } },
      axisLabel: { color: '#9ca3af', fontSize: 12, fontFamily: 'monospace', fontWeight: 600 },
      axisTick: { show: false },
    },
    series,
  }

  return (
    <div className="bg-[#0d0d14] rounded-lg border border-[#1e1e2e] p-3">
      <div className="text-xs text-[#6b7280] uppercase tracking-widest font-medium px-2 pb-2">
        Sector Deltas vs Best Lap
      </div>
      <ReactECharts
        option={option}
        style={{ height: '180px', width: '100%' }}
        theme="dark"
        opts={{ renderer: 'canvas' }}
      />
    </div>
  )
}
