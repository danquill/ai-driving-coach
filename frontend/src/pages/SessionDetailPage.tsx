import { useState, useMemo } from 'react'
import uPlot from 'uplot'
import { useParams, useNavigate } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getSession } from '../api/sessions'
import { listLaps, getIdealLap, getOverlay } from '../api/laps'
import { triggerAnalysis, getInsights, deleteInsight, deleteAllInsights, submitInsightFeedback } from '../api/analysis'
import { getCircuit } from '../api/circuits'
import { useJobPoller } from '../hooks/useJobPoller'
import { useTelemetryOverlay } from '../hooks/useTelemetryOverlay'
import { useStore } from '../store'
import { Tabs, TabList, Tab, TabPanel } from '../components/ui/Tabs'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardHeader, CardBody } from '../components/ui/Card'
import { SpinnerOverlay } from '../components/ui/Spinner'
import { EmptyState } from '../components/ui/EmptyState'
import { SpeedTraceChart } from '../components/charts/SpeedTraceChart'
import { ThrottleBrakeChart } from '../components/charts/ThrottleBrakeChart'
import { TractionCircleChart } from '../components/charts/TractionCircleChart'
import { SectorDeltaChart } from '../components/charts/SectorDeltaChart'
import { GearRpmChart } from '../components/charts/GearRpmChart'
import { SteeringChart } from '../components/charts/SteeringChart'
import { TrackMap } from '../components/map/TrackMap'
import { InsightMiniMap } from '../components/map/InsightMiniMap'
import { updateSession } from '../api/sessions'
import { formatLapTime, formatDelta } from '../utils/telemetry'
import { LAP_COLORS } from '../utils/colors'
import type { LapDetail, IdealLap, AnalysisJob, CoachingInsight, LapSector, Circuit } from '../types/api'
import { SESSION_TYPE_LABELS } from '../types/api'
import type { SessionType } from '../types/api'

// ─── Overview Tab ─────────────────────────────────────────────────────────────

function OverviewTab({ sessionId }: { sessionId: string }) {
  const { data: session } = useQuery({ queryKey: ['session', sessionId], queryFn: () => getSession(sessionId) })
  const { data: circuit } = useQuery({
    queryKey: ['circuit', session?.circuit_id],
    queryFn: () => getCircuit(session!.circuit_id!),
    enabled: !!session?.circuit_id,
  })
  const { data: jobs } = useJobPoller(sessionId)
  const qc = useQueryClient()

  const triggerMutation = useMutation({
    mutationFn: (jobType: string) => triggerAnalysis(sessionId, jobType),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sessions', sessionId, 'jobs'] }),
  })

  const sessionTypeMutation = useMutation({
    mutationFn: (session_type: SessionType) => updateSession(sessionId, { session_type }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['session', sessionId] }),
  })

  const jobTypes = ['parse', 'detect_laps', 'sector_analysis', 'ideal_lap', 'ai_coaching']

  return (
    <div className="p-6 space-y-6">
      {/* Session metadata */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold text-white uppercase tracking-wide">Session Info</h3>
        </CardHeader>
        <CardBody>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div>
              <p className="text-xs text-[#6b7280] uppercase tracking-wide mb-1">Name</p>
              <p className="text-sm text-white font-medium">{session?.name ?? '—'}</p>
            </div>
            <div>
              <p className="text-xs text-[#6b7280] uppercase tracking-wide mb-1">Circuit</p>
              <p className="text-sm text-white">{circuit?.name ?? '—'}</p>
            </div>
            <div>
              <p className="text-xs text-[#6b7280] uppercase tracking-wide mb-1">Date</p>
              <p className="text-sm text-white">
                {session?.session_date ? new Date(session.session_date).toLocaleDateString() : '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-[#6b7280] uppercase tracking-wide mb-1">Session Type</p>
              <select
                value={session?.session_type ?? ''}
                onChange={(e) => sessionTypeMutation.mutate(e.target.value as SessionType)}
                className="text-sm bg-[#1e1e2e] border border-[#2e2e4e] text-white rounded px-2 py-0.5 focus:outline-none focus:border-[#457b9d] cursor-pointer"
              >
                <option value="">— select —</option>
                {(Object.entries(SESSION_TYPE_LABELS) as [SessionType, string][]).map(([val, label]) => (
                  <option key={val} value={val}>{label}</option>
                ))}
              </select>
            </div>
            <div>
              <p className="text-xs text-[#6b7280] uppercase tracking-wide mb-1">Status</p>
              {session?.status && <Badge status={session.status} />}
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Jobs */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold text-white uppercase tracking-wide">Analysis Jobs</h3>
          <div className="hidden md:flex gap-2">
            {jobTypes.map((jt) => (
              <Button
                key={jt}
                variant="secondary"
                size="sm"
                loading={triggerMutation.isPending && triggerMutation.variables === jt}
                onClick={() => triggerMutation.mutate(jt)}
              >
                {jt.replace('_', ' ')}
              </Button>
            ))}
          </div>
        </CardHeader>
        <CardBody className="p-0">
          <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[#1e1e2e]">
                <th className="text-left text-[#6b7280] uppercase tracking-wide px-5 py-2.5 font-medium">Job</th>
                <th className="text-left text-[#6b7280] uppercase tracking-wide px-5 py-2.5 font-medium">Status</th>
                <th className="text-left text-[#6b7280] uppercase tracking-wide px-5 py-2.5 font-medium hidden md:table-cell">Started</th>
                <th className="text-left text-[#6b7280] uppercase tracking-wide px-5 py-2.5 font-medium hidden md:table-cell">Completed</th>
                <th className="text-left text-[#6b7280] uppercase tracking-wide px-5 py-2.5 font-medium hidden md:table-cell">Summary</th>
              </tr>
            </thead>
            <tbody>
              {(jobs ?? []).map((job: AnalysisJob) => (
                <tr key={job.id} className="border-b border-[#1e1e2e] hover:bg-[#0d0d14] transition-colors">
                  <td className="px-5 py-3 font-mono text-white">{job.job_type}</td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <Badge status={job.status} />
                      {(job.status === 'failed' || job.status === 'done') && (
                        <button
                          onClick={() => triggerMutation.mutate(job.job_type)}
                          disabled={triggerMutation.isPending}
                          className="text-[10px] text-[#457b9d] hover:text-white border border-[#1e1e2e] hover:border-[#457b9d] px-2 py-1 md:px-1.5 md:py-0.5 rounded transition-colors disabled:opacity-40"
                        >
                          {triggerMutation.isPending && triggerMutation.variables === job.job_type ? '…' : 'Rerun'}
                        </button>
                      )}
                    </div>
                  </td>
                  <td className="px-5 py-3 text-[#6b7280] hidden md:table-cell">
                    {job.started_at ? new Date(job.started_at).toLocaleTimeString() : '—'}
                  </td>
                  <td className="px-5 py-3 text-[#6b7280] hidden md:table-cell">
                    {job.completed_at ? new Date(job.completed_at).toLocaleTimeString() : '—'}
                  </td>
                  <td className="px-5 py-3 text-[#9ca3af] max-w-xs truncate hidden md:table-cell" title={job.error_message ?? undefined}>
                    {job.status === 'failed' ? job.error_message : job.result_summary ?? '—'}
                  </td>
                </tr>
              ))}
              {(!jobs || jobs.length === 0) && (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-[#6b7280]">No jobs yet</td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}

// ─── Laps Tab ─────────────────────────────────────────────────────────────────

function LapsTab({ sessionId }: { sessionId: string }) {
  const { data: laps, isLoading } = useQuery<LapDetail[]>({
    queryKey: ['laps', sessionId],
    queryFn: () => listLaps(sessionId),
  })
  const { data: idealLap } = useQuery<IdealLap>({
    queryKey: ['idealLap', sessionId],
    queryFn: () => getIdealLap(sessionId),
    retry: false,
  })
  const selectedLapNumbers = useStore((s) => s.selectedLapNumbers)
  const lapColorMap = useStore((s) => s.lapColorMap)
  const toggleLap = useStore((s) => s.toggleLap)

  if (isLoading) return <SpinnerOverlay label="Loading laps…" />

  const validLaps = (laps ?? []).filter((l) => l.is_valid && !l.is_outlap && !l.is_inlap)
  const bestLap = validLaps.reduce<LapDetail | null>((best, l) =>
    !best || (l.lap_time_ms ?? Infinity) < (best.lap_time_ms ?? Infinity) ? l : best, null)

  return (
    <div className="p-6 space-y-6">
      {/* Lap table */}
      <Card>
        <CardBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[#1e1e2e]">
                  <th className="text-left text-[#6b7280] uppercase tracking-wide px-4 py-2.5 font-medium w-10">#</th>
                  <th className="text-left text-[#6b7280] uppercase tracking-wide px-4 py-2.5 font-medium">Time</th>
                  <th className="text-left text-[#6b7280] uppercase tracking-wide px-4 py-2.5 font-medium">Delta</th>
                  {bestLap?.sectors?.map((_, i) => (
                    <th key={i} className="text-left text-[#6b7280] uppercase tracking-wide px-4 py-2.5 font-medium">S{i + 1}</th>
                  ))}
                  <th className="text-left text-[#6b7280] uppercase tracking-wide px-4 py-2.5 font-medium">Max Spd</th>
                  <th className="text-left text-[#6b7280] uppercase tracking-wide px-4 py-2.5 font-medium">Valid</th>
                  <th className="text-right text-[#6b7280] uppercase tracking-wide px-4 py-2.5 font-medium">
                    Compare
                    {selectedLapNumbers.length > 0 && (
                      <span className="ml-1.5 normal-case font-normal text-[10px] text-[#457b9d]">
                        {selectedLapNumbers.length}/2
                      </span>
                    )}
                  </th>
                </tr>
              </thead>
              <tbody>
                {(laps ?? []).map((lap) => {
                  const isBest = bestLap?.lap_number === lap.lap_number
                  const delta = (bestLap && lap.lap_time_ms != null && bestLap.lap_time_ms != null && !isBest)
                    ? lap.lap_time_ms - bestLap.lap_time_ms
                    : null
                  const isSelected = selectedLapNumbers.includes(lap.lap_number)
                  const canSelect = isSelected || selectedLapNumbers.length < 2
                  const color = lapColorMap[lap.lap_number]
                  const role = isSelected
                    ? (selectedLapNumbers.indexOf(lap.lap_number) === 0 ? 'REF' : 'CMP')
                    : null

                  return (
                    <tr
                      key={lap.lap_number}
                      className={`border-b border-[#1e1e2e] transition-colors ${
                        isBest ? 'bg-[#00e676]/5' : isSelected ? 'bg-[#12121a]' : 'hover:bg-[#0d0d14]'
                      }`}
                    >
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-1.5">
                          {color && (
                            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                          )}
                          <span className="font-mono text-[#9ca3af]">{lap.lap_number}</span>
                        </div>
                      </td>
                      <td className="px-4 py-2.5 font-mono text-white font-medium">
                        {lap.lap_time_ms != null ? formatLapTime(lap.lap_time_ms) : '—'}
                        {isBest && <span className="ml-2 text-[#00e676] text-xs">BEST</span>}
                        {lap.is_outlap && <span className="ml-2 text-[#6b7280] text-xs">OUT</span>}
                        {lap.is_inlap && <span className="ml-2 text-[#6b7280] text-xs">IN</span>}
                      </td>
                      <td className="px-4 py-2.5 font-mono">
                        {delta !== null ? (
                          <span className={delta < 0 ? 'text-[#00e676]' : 'text-[#ff5252]'}>
                            {formatDelta(delta)}
                          </span>
                        ) : (
                          <span className="text-[#6b7280]">—</span>
                        )}
                      </td>
                      {lap.sectors?.map((s, i) => (
                        <td key={i} className="px-4 py-2.5 font-mono text-[#9ca3af]">
                          {formatLapTime(s.sector_time_ms)}
                        </td>
                      ))}
                      <td className="px-4 py-2.5 font-mono text-[#9ca3af]">
                        {lap.max_speed_kph?.toFixed(0) ?? '—'} kph
                      </td>
                      <td className="px-4 py-2.5">
                        {lap.is_valid
                          ? <span className="text-[#00e676]">✓</span>
                          : <span className="text-[#ff5252]">✗</span>}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <button
                          onClick={() => toggleLap(lap.lap_number)}
                          disabled={!canSelect}
                          className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded border transition-all ${
                            isSelected
                              ? 'border-transparent text-white font-semibold'
                              : canSelect
                              ? 'border-[#2e2e4e] text-[#6b7280] hover:border-[#457b9d] hover:text-[#457b9d]'
                              : 'border-[#1e1e2e] text-[#374151] cursor-not-allowed'
                          }`}
                          style={isSelected && color ? { backgroundColor: color + '33', borderColor: color, color } : {}}
                        >
                          {role ?? 'Select'}
                        </button>
                      </td>
                    </tr>
                  )
                })}

                {/* Ideal lap row */}
                {idealLap && (
                  <tr className="border-b border-[#1e1e2e] bg-amber-900/10">
                    <td className="px-4 py-2.5 text-amber-400 font-mono text-xs">∞</td>
                    <td className="px-4 py-2.5 font-mono text-amber-400 font-medium">
                      {formatLapTime(idealLap.theoretical_time_ms)}
                      <span className="ml-2 text-xs">IDEAL</span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-amber-400">
                      {bestLap?.lap_time_ms != null
                        ? formatDelta(idealLap.theoretical_time_ms - bestLap.lap_time_ms)
                        : '—'}
                    </td>
                    {Object.entries(idealLap.sector_sources).map(([sectorNum, lapNum]) => (
                      <td key={sectorNum} className="px-4 py-2.5 font-mono text-amber-400/70 text-xs">
                        <span className="text-[#6b7280]">L{lapNum}</span>
                      </td>
                    ))}
                    <td colSpan={3} className="px-4 py-2.5 text-xs text-[#6b7280]">theoretical</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>

      {/* Sector delta chart */}
      {laps && laps.length > 0 && (
        <SectorDeltaChart
          laps={laps}
          idealLap={idealLap ?? null}
          selectedLapNumbers={selectedLapNumbers}
          lapColorMap={lapColorMap}
        />
      )}
    </div>
  )
}

// ─── Analysis Tab ─────────────────────────────────────────────────────────────

const CHART_PANELS = [
  { key: 'speed', label: 'Speed' },
  { key: 'throttle', label: 'Throttle / Brake' },
  { key: 'gear', label: 'Gear / RPM' },
  { key: 'steering', label: 'Steering' },
  { key: 'traction', label: 'Traction' },
  { key: 'map', label: 'Map' },
] as const

type ChartPanelKey = typeof CHART_PANELS[number]['key']

function AnalysisTab({ sessionId }: { sessionId: string }) {
  const { data: session } = useQuery({ queryKey: ['session', sessionId], queryFn: () => getSession(sessionId) })
  const { data: laps } = useQuery<LapDetail[]>({
    queryKey: ['laps', sessionId],
    queryFn: () => listLaps(sessionId),
  })
  const { data: circuit } = useQuery({
    queryKey: ['circuit', session?.circuit_id],
    queryFn: () => getCircuit(session!.circuit_id!),
    enabled: !!session?.circuit_id,
  })

  const selectedLapNumbers = useStore((s) => s.selectedLapNumbers)
  const lapColorMap = useStore((s) => s.lapColorMap)
  const toggleLap = useStore((s) => s.toggleLap)

  const { data: overlay } = useTelemetryOverlay(sessionId)

  // Build per-lap telemetry rows for map — memoized to prevent draw effect churn
  const mapChannels = overlay?.channels ?? []
  const mapLaps = useMemo(() => {
    const result: Record<number, number[][]> = {}
    if (overlay) {
      for (const lapNum of selectedLapNumbers) {
        const rows = overlay.laps[String(lapNum)]
        if (rows) result[lapNum] = rows
      }
    }
    return result
  }, [overlay, selectedLapNumbers])

  const [chartsExpanded, setChartsExpanded] = useState(false)
  const [lapDrawerOpen, setLapDrawerOpen] = useState(false)
  const [visibleCharts, setVisibleCharts] = useState<Set<ChartPanelKey>>(
    new Set(CHART_PANELS.map((p) => p.key))
  )
  const validLaps = (laps ?? []).filter((l) => l.is_valid)

  function toggleChart(key: ChartPanelKey) {
    setVisibleCharts((prev) => {
      const next = new Set(prev)
      if (next.has(key)) { next.delete(key) } else { next.add(key) }
      return next
    })
  }

  // Lap list sidebar content (shared between desktop sidebar and mobile drawer)
  const lapListContent = (
    <div className="p-3 border-b border-[#1e1e2e]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-semibold text-[#6b7280] uppercase tracking-widest">Laps</span>
        <span className="text-[10px] text-[#4b5563]">{selectedLapNumbers.length}/2</span>
      </div>
      {validLaps.length === 0 && (
        <p className="text-xs text-[#4b5563]">No valid laps</p>
      )}
      <div className="space-y-0.5">
        {validLaps.map((lap) => {
          const isSelected = selectedLapNumbers.includes(lap.lap_number)
          const color = isSelected ? lapColorMap[lap.lap_number] : null
          const canSelect = isSelected || selectedLapNumbers.length < 2
          return (
            <button
              key={lap.lap_number}
              onClick={() => { canSelect && toggleLap(lap.lap_number); setLapDrawerOpen(false) }}
              disabled={!canSelect}
              className={`w-full flex items-center gap-2 px-2 py-2 md:py-1.5 rounded text-left transition-colors ${
                isSelected ? 'bg-[#1e1e2e]' : canSelect ? 'hover:bg-[#0d0d14]' : 'opacity-30 cursor-not-allowed'
              }`}
            >
              <span
                className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: color ?? '#374151' }}
              />
              <span className="text-xs font-mono text-white flex-1">L{lap.lap_number}</span>
              {isSelected && (
                <span className="text-[9px] text-[#6b7280] uppercase">
                  {selectedLapNumbers.indexOf(lap.lap_number) === 0 ? 'REF' : 'CMP'}
                </span>
              )}
              <span className="text-[10px] font-mono text-[#6b7280]">
                {lap.lap_time_ms != null ? formatLapTime(lap.lap_time_ms) : '—'}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )

  return (
    <div className="flex h-full min-h-0 relative">
      {/* Mobile lap drawer overlay */}
      {lapDrawerOpen && (
        <div
          className="md:hidden fixed inset-0 z-40 bg-black/60"
          onClick={() => setLapDrawerOpen(false)}
        />
      )}
      <div className={`md:hidden fixed left-0 top-0 bottom-0 z-50 bg-[#12121a] border-r border-[#1e1e2e] overflow-y-auto transition-transform duration-300 w-56 ${lapDrawerOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex items-center justify-between px-3 pt-3 pb-2 border-b border-[#1e1e2e]">
          <span className="text-xs font-semibold text-white">Select Laps</span>
          <button onClick={() => setLapDrawerOpen(false)} className="text-[#6b7280] hover:text-white p-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        {lapListContent}
      </div>

      {/* Desktop left sidebar: lap selector */}
      <div className={`hidden md:block flex-shrink-0 border-r border-[#1e1e2e] transition-all duration-300 overflow-y-auto ${chartsExpanded ? 'w-0 overflow-hidden opacity-0 pointer-events-none' : 'w-44'}`}>
        {lapListContent}
      </div>

      {/* Right: toolbar + charts */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Toolbar */}
        <div className="flex flex-col border-b border-[#1e1e2e] flex-shrink-0">
          {/* Row 1: controls */}
          <div className="flex items-center gap-2 px-3 py-2">
            {/* Mobile: lap selector toggle */}
            <button
              onClick={() => setLapDrawerOpen(true)}
              className="md:hidden flex items-center gap-1.5 text-xs text-[#9ca3af] hover:text-white border border-[#1e1e2e] hover:border-[#374151] bg-[#12121a] hover:bg-[#1e1e2e] px-2.5 py-1.5 rounded transition-colors flex-shrink-0"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
              Laps {selectedLapNumbers.length > 0 && `(${selectedLapNumbers.length})`}
            </button>
            <div className="flex-1" />
            <button
              onClick={() => {
                const s = uPlot.sync('telemetry-sync')
                for (const u of s.plots) {
                  const xs = u.data[0] as number[]
                  if (xs?.length) u.setScale('x', { min: xs[0], max: xs[xs.length - 1] })
                }
              }}
              className="flex items-center gap-1.5 text-xs text-[#9ca3af] hover:text-white border border-[#1e1e2e] hover:border-[#374151] bg-[#12121a] hover:bg-[#1e1e2e] px-2.5 py-1.5 md:py-1 rounded transition-colors flex-shrink-0"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5v-4m0 4h-4m4 0l-5-5" />
              </svg>
              Reset zoom
            </button>
            <button
              onClick={() => setChartsExpanded((v) => !v)}
              title={chartsExpanded ? 'Collapse' : 'Expand'}
              className="flex items-center gap-1.5 text-xs text-[#9ca3af] hover:text-white border border-[#1e1e2e] hover:border-[#374151] bg-[#12121a] hover:bg-[#1e1e2e] px-2.5 py-1.5 md:py-1 rounded transition-colors flex-shrink-0"
            >
              {chartsExpanded ? (
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 9L4 4m0 0h5m-5 0v5M15 9l5-5m0 0h-5m5 0v5M9 15l-5 5m0 0h5m-5 0v-5M15 15l5 5m0 0h-5m5 0v-5" />
                </svg>
              ) : (
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5v-4m0 4h-4m4 0l-5-5" />
                </svg>
              )}
            </button>
          </div>
          {/* Row 2: chart visibility toggles */}
          <div className="flex items-center gap-1.5 flex-wrap px-3 pb-2 border-t border-[#1e1e2e]">
            {CHART_PANELS.map((panel) => {
              const active = visibleCharts.has(panel.key)
              return (
                <button
                  key={panel.key}
                  onClick={() => toggleChart(panel.key)}
                  className={`mt-2 px-2.5 py-1.5 md:py-1 text-[11px] rounded border transition-all ${
                    active
                      ? 'bg-[#457b9d]/20 border-[#457b9d] text-[#457b9d]'
                      : 'bg-transparent border-[#1e1e2e] text-[#6b7280] hover:border-[#2e2e4e] hover:text-[#9ca3af]'
                  }`}
                >
                  {panel.label}
                </button>
              )
            })}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-1 md:p-4 space-y-3">

          {selectedLapNumbers.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full min-h-[400px]">
              <div className="text-center">
                <div className="flex gap-2 justify-center mb-3">
                  {LAP_COLORS.map((c) => (
                    <div
                      key={c}
                      className="w-6 h-6 rounded-full border-2 border-[#1e1e2e]"
                      style={{ backgroundColor: c }}
                    />
                  ))}
                </div>
                <p className="text-sm text-white font-medium">Select laps to compare</p>
                <p className="text-xs text-[#6b7280] mt-1">Up to 2 laps can be overlaid</p>
              </div>
            </div>
          ) : (
            <>
              {visibleCharts.has('speed') && (
                <SpeedTraceChart
                  overlay={overlay}
                  selectedLaps={selectedLapNumbers}
                  lapColorMap={lapColorMap}
                />
              )}
              {visibleCharts.has('throttle') && (
                <ThrottleBrakeChart
                  overlay={overlay}
                  selectedLaps={selectedLapNumbers}
                  lapColorMap={lapColorMap}
                />
              )}
              {visibleCharts.has('gear') && (
                <GearRpmChart
                  overlay={overlay}
                  selectedLaps={selectedLapNumbers}
                  lapColorMap={lapColorMap}
                />
              )}
              {visibleCharts.has('steering') && (
                <SteeringChart
                  overlay={overlay}
                  selectedLaps={selectedLapNumbers}
                  lapColorMap={lapColorMap}
                />
              )}
              {(visibleCharts.has('traction') || visibleCharts.has('map')) && (
                <div className="flex flex-col md:flex-row gap-3 md:items-stretch">
                  {visibleCharts.has('traction') && (
                    <div className={visibleCharts.has('map') ? 'md:flex-1 md:min-w-0' : 'md:w-1/2'}>
                      <TractionCircleChart
                        overlay={overlay}
                        selectedLaps={selectedLapNumbers}
                        lapColorMap={lapColorMap}
                      />
                    </div>
                  )}
                  {visibleCharts.has('map') && (
                    <div className={visibleCharts.has('traction') ? 'h-48 md:h-auto md:flex-1 md:min-w-0' : 'w-full h-48 md:h-[340px]'}>
                      <TrackMap
                        circuit={circuit ?? null}
                        lapRows={mapLaps}
                        selectedLaps={selectedLapNumbers}
                        channels={mapChannels}
                        lapColorMap={lapColorMap}
                        colorMode="speed"
                      />
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>{/* end overflow-y-auto charts scroll */}
      </div>{/* end right flex-col */}
    </div>
  )
}

// ─── Insights Tab ─────────────────────────────────────────────────────────────

const INSIGHT_CATEGORY_COLORS: Record<string, string> = {
  braking: 'bg-[#ff5252]/10 text-[#ff5252] border-[#ff5252]/30',
  acceleration: 'bg-[#00e676]/10 text-[#00e676] border-[#00e676]/30',
  cornering: 'bg-[#457b9d]/20 text-[#457b9d] border-[#457b9d]/30',
  line: 'bg-amber-900/20 text-amber-400 border-amber-700/30',
  general: 'bg-[#6b7280]/20 text-[#9ca3af] border-[#6b7280]/30',
}

function InsightCard({
  insight,
  sessionId,
  onJumpTo,
  onDelete,
  circuit,
  lapRows,
  channels,
  lapColorMap,
  mapReady,
}: {
  insight: CoachingInsight
  sessionId: string
  onJumpTo?: (distanceM: number) => void
  onDelete?: (id: string) => void
  circuit: Circuit | null
  lapRows: Record<number, number[][]>
  channels: string[]
  lapColorMap: Record<number, string>
  mapReady: boolean
}) {
  const catStyle = INSIGHT_CATEGORY_COLORS[insight.category.toLowerCase()] ?? INSIGHT_CATEGORY_COLORS.general
  const confidencePct = insight.confidence != null ? Math.round(insight.confidence * 100) : null
  const hasMap = insight.distance_m_start != null
  const user = useStore((s) => s.user)
  const isCoach = user?.role === 'coach' || user?.role === 'admin'

  const [feedbackState, setFeedbackState] = useState<'none' | 'good' | 'bad'>(
    insight.feedback ?? 'none'
  )
  const [showCorrectionForm, setShowCorrectionForm] = useState(false)
  const [correctionNote, setCorrectionNote] = useState('')
  const [submittedNote, setSubmittedNote] = useState(insight.feedback_note ?? '')

  const feedbackMutation = useMutation({
    mutationFn: (data: { feedback: 'good' | 'bad'; feedback_note?: string }) =>
      submitInsightFeedback(sessionId, insight.id, data),
    onSuccess: (_, vars) => {
      setFeedbackState(vars.feedback)
      if (vars.feedback === 'bad' && vars.feedback_note) {
        setSubmittedNote(vars.feedback_note)
      }
      setShowCorrectionForm(false)
      setCorrectionNote('')
    },
  })

  const borderClass =
    feedbackState === 'good'
      ? 'border border-[#00e676]/30'
      : feedbackState === 'bad'
        ? 'border border-[#ff5252]/30'
        : ''

  return (
    <Card variant="inset" className={`p-4 ${borderClass}`}>
      {/* Header row: category + distance + delete */}
      <div className="flex items-center gap-2 flex-wrap mb-2">
        <span className={`text-xs px-2 py-0.5 rounded border uppercase tracking-wide font-medium ${catStyle}`}>
          {insight.category.replace(/_/g, ' ')}
        </span>
        {insight.distance_m_start != null && (
          <button
            onClick={() => onJumpTo?.(insight.distance_m_start!)}
            title="Jump to this position on the charts"
            className="text-xs font-mono text-[#457b9d] hover:text-white border border-[#457b9d]/30 hover:border-[#457b9d] px-1.5 py-0.5 rounded transition-colors"
          >
            @{insight.distance_m_start.toFixed(0)}m ↗
          </button>
        )}
        {/* Feedback buttons — coach/admin only */}
        <div className="ml-auto flex items-center gap-1">
          {isCoach && (
            <>
              <button
                onClick={() => feedbackMutation.mutate({ feedback: 'good' })}
                title="Good recommendation"
                disabled={feedbackMutation.isPending}
                className={`p-1 rounded transition-colors ${
                  feedbackState === 'good'
                    ? 'text-[#00e676]'
                    : 'text-[#6b7280] hover:text-[#00e676]'
                }`}
              >
                <svg className="w-3.5 h-3.5" fill={feedbackState === 'good' ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
                </svg>
              </button>
              <button
                onClick={() => setShowCorrectionForm(true)}
                title="Flag bad recommendation"
                disabled={feedbackMutation.isPending}
                className={`p-1 rounded transition-colors ${
                  feedbackState === 'bad'
                    ? 'text-[#ff5252]'
                    : 'text-[#6b7280] hover:text-[#ff5252]'
                }`}
              >
                <svg className="w-3.5 h-3.5" fill={feedbackState === 'bad' ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018c.163 0 .326.02.485.06L17 4m-7 10v2a2 2 0 002 2h.095c.5 0 .905-.405.905-.905 0-.714.211-1.412.608-2.006L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5" />
                </svg>
              </button>
            </>
          )}
          <button
            onClick={() => onDelete?.(insight.id)}
            title="Delete insight"
            className="text-[#6b7280] hover:text-[#ff5252] transition-colors p-1 rounded"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>

      {/* Text above map on mobile, side-by-side on desktop */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="flex-1 space-y-2 min-w-0">
          <p className="text-sm text-[#d1d5db] leading-relaxed">{insight.insight_text}</p>
          {confidencePct != null && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-[#6b7280]">Confidence</span>
              <div className="flex-1 h-1 bg-[#1e1e2e] rounded-full max-w-24">
                <div
                  className="h-1 rounded-full bg-gradient-to-r from-[#457b9d] to-[#00e676]"
                  style={{ width: `${confidencePct}%` }}
                />
              </div>
              <span className="text-xs font-mono text-[#6b7280]">{confidencePct}%</span>
            </div>
          )}
          {/* Submitted correction note */}
          {isCoach && feedbackState === 'bad' && submittedNote && !showCorrectionForm && (
            <p className="text-xs text-[#ff5252]/80 italic border-t border-[#1e1e2e] pt-2">
              Coach note: "{submittedNote}"
            </p>
          )}
          {/* Correction form */}
          {isCoach && showCorrectionForm && (
            <div className="space-y-2 border-t border-[#1e1e2e] pt-3">
              <p className="text-xs text-[#6b7280]">What should the coach have said instead?</p>
              <input
                type="text"
                value={correctionNote}
                onChange={(e) => setCorrectionNote(e.target.value)}
                placeholder="e.g. The corner needs a later turn-in, not brush braking"
                className="w-full text-xs bg-[#0d0d14] border border-[#1e1e2e] rounded px-2 py-1.5 text-[#d1d5db] placeholder-[#4b5563] focus:outline-none focus:border-[#457b9d]"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && correctionNote.trim()) {
                    feedbackMutation.mutate({ feedback: 'bad', feedback_note: correctionNote.trim() })
                  }
                }}
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="primary"
                  disabled={!correctionNote.trim() || feedbackMutation.isPending}
                  onClick={() => feedbackMutation.mutate({ feedback: 'bad', feedback_note: correctionNote.trim() })}
                >
                  Submit
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => { setShowCorrectionForm(false); setCorrectionNote('') }}
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
        {hasMap && (
          <div className="w-full md:w-[280px] md:flex-shrink-0">
            {mapReady
              ? <InsightMiniMap
                  circuit={circuit}
                  lapRows={lapRows}
                  channels={channels}
                  lapColorMap={lapColorMap}
                  distanceM={insight.distance_m_start ?? 0}
                  distanceMStart={insight.distance_m_start ?? undefined}
                  distanceMEnd={insight.distance_m_end ?? undefined}
                  width={280}
                  height={200}
                  fullWidth
                />
              : <div
                  className="rounded border border-[#1e1e2e] bg-[#0d0d14] animate-pulse w-full"
                  style={{ height: 200 }}
                />
            }
          </div>
        )}
      </div>
    </Card>
  )
}

function InsightsTab({ sessionId }: { sessionId: string }) {
  const qc = useQueryClient()
  const setCursorDistanceM = useStore((s) => s.setCursorDistanceM)
  const selectedLapNumbers = useStore((s) => s.selectedLapNumbers)
  const lapColorMap = useStore((s) => s.lapColorMap)

  // Fetch jobs to detect in-progress coaching and check prerequisites
  const { data: jobs } = useJobPoller(sessionId)
  const { data: idealLap } = useQuery({
    queryKey: ['idealLap', sessionId],
    queryFn: () => getIdealLap(sessionId),
    retry: false,
  })
  const { data: laps } = useQuery<LapDetail[]>({
    queryKey: ['laps', sessionId],
    queryFn: () => listLaps(sessionId),
  })
  const [compareLapNumber, setCompareLapNumber] = useState<number | null>(null)

  const { data: session } = useQuery({ queryKey: ['session', sessionId], queryFn: () => getSession(sessionId) })
  const { data: circuit } = useQuery({
    queryKey: ['circuit', session?.circuit_id],
    queryFn: () => getCircuit(session!.circuit_id!),
    enabled: !!session?.circuit_id,
  })


  const MAP_CHANNELS = ['distance_m', 'lat', 'lon']
  const { data: mapOverlay } = useQuery({
    queryKey: ['overlay-map', sessionId],
    queryFn: async () => {
      const laps = await listLaps(sessionId)
      const valid = laps.filter((l) => l.is_valid && !l.is_outlap && !l.is_inlap && l.lap_time_ms != null)
      if (!valid.length) throw new Error('No valid laps')
      const best = valid.reduce((b, l) => l.lap_time_ms! < b.lap_time_ms! ? l : b)
      return getOverlay(sessionId, [best.lap_number], MAP_CHANNELS)
    },
    retry: false,
  })

  const mapChannels = mapOverlay?.channels ?? []
  const mapLaps = useMemo(() => {
    if (!mapOverlay) return {}
    const result: Record<number, number[][]> = {}
    for (const [lapNum, rows] of Object.entries(mapOverlay.laps)) {
      if (rows) result[Number(lapNum)] = rows
    }
    return result
  }, [mapOverlay])

  const miniLapColorMap = useMemo(() => {
    const result: Record<number, string> = {}
    for (const lapNum of Object.keys(mapLaps)) result[Number(lapNum)] = '#ffffff'
    return result
  }, [mapLaps])

  const coachingJob = jobs
    ?.filter((j) => j.job_type === 'ai_coaching')
    .sort((a, b) => (b.queued_at ?? '').localeCompare(a.queued_at ?? ''))[0]

  const isRunning = coachingJob?.status === 'pending' || coachingJob?.status === 'running'
  const hasPrerequisite = !!idealLap
  const lastError = coachingJob?.status === 'failed' ? coachingJob.error_message : null

  const { data: insights, isLoading } = useQuery<CoachingInsight[]>({
    queryKey: ['insights', sessionId],
    queryFn: () => getInsights(sessionId),
    // Re-poll while a job is running so insights appear automatically when done
    refetchInterval: isRunning ? 3000 : false,
  })

  const triggerMutation = useMutation({
    mutationFn: () => triggerAnalysis(
      sessionId,
      'ai_coaching',
      compareLapNumber !== null ? { compare_lap_number: compareLapNumber } : undefined,
    ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sessions', sessionId, 'jobs'] })
    },
  })

  const deleteOneMutation = useMutation({
    mutationFn: (insightId: string) => deleteInsight(sessionId, insightId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['insights', sessionId] }),
  })

  const deleteAllMutation = useMutation({
    mutationFn: () => deleteAllInsights(sessionId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['insights', sessionId] }),
  })

  const errorMessage = triggerMutation.error
    ? (() => {
        const err = triggerMutation.error as { response?: { data?: { detail?: string } } }
        return err.response?.data?.detail ?? 'Failed to start analysis'
      })()
    : null

  if (isLoading) return <SpinnerOverlay label="Loading insights…" />

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-white">AI Coaching Insights</h3>
          <p className="text-xs text-[#6b7280] mt-0.5">
            {insights?.length ?? 0} insight{insights?.length !== 1 ? 's' : ''} generated
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          {!hasPrerequisite && (
            <p className="text-xs text-amber-400">
              Run sector analysis &amp; ideal lap jobs first
            </p>
          )}
          {errorMessage && (
            <p className="text-xs text-[#ff5252]">{errorMessage}</p>
          )}
          {lastError && !errorMessage && (
            <p className="text-xs text-[#ff5252]">Last run failed: {lastError}</p>
          )}
          <div className="flex items-center gap-2">
            {insights && insights.length > 0 && (
              <Button
                variant="secondary"
                size="sm"
                loading={deleteAllMutation.isPending}
                onClick={() => deleteAllMutation.mutate()}
              >
                Clear all
              </Button>
            )}
            {(() => {
              const bestLap = laps?.reduce((a, b) =>
                (a.lap_time_ms ?? Infinity) < (b.lap_time_ms ?? Infinity) ? a : b
              )
              const otherLaps = laps?.filter(l => l.lap_number !== bestLap?.lap_number) ?? []
              const noLapSelected = compareLapNumber === null
              return (
                <>
                  <select
                    className="text-xs bg-[#1e2028] border border-[#2d3748] text-white rounded px-2 py-1.5 disabled:opacity-50"
                    value={compareLapNumber ?? ''}
                    disabled={isRunning || !laps || otherLaps.length === 0}
                    onChange={e => setCompareLapNumber(e.target.value ? Number(e.target.value) : null)}
                  >
                    <option value="">Select lap to analyse</option>
                    {otherLaps.map(l => (
                      <option key={l.lap_number} value={l.lap_number}>
                        Lap {l.lap_number} — {l.lap_time_ms ? (l.lap_time_ms / 1000).toFixed(3) + 's' : '?'}
                      </option>
                    ))}
                  </select>
                  <Button
                    variant="primary"
                    size="sm"
                    disabled={!hasPrerequisite || isRunning || triggerMutation.isPending || noLapSelected}
                    loading={triggerMutation.isPending || isRunning}
                    onClick={() => triggerMutation.mutate()}
                  >
                    {isRunning ? 'Generating…' : 'Generate Insights'}
                  </Button>
                </>
              )
            })()}
          </div>
        </div>
      </div>

      {/* In-progress banner */}
      {isRunning && (
        <div className="flex items-center gap-3 px-4 py-3 bg-[#457b9d]/10 border border-[#457b9d]/30 rounded-lg">
          <div className="w-2 h-2 rounded-full bg-[#457b9d] animate-pulse flex-shrink-0" />
          <p className="text-xs text-[#457b9d]">
            Claude is analyzing your telemetry data — this takes around 20–30 seconds…
          </p>
        </div>
      )}

      {(!insights || insights.length === 0) && !isRunning && (
        <EmptyState
          icon={
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          }
          title="No insights yet"
          description={hasPrerequisite
            ? "Click 'Generate Insights' to run the AI coaching analysis on this session's telemetry data."
            : "Complete the parse → detect laps → sector analysis → ideal lap jobs first, then generate insights."}
        />
      )}

      <div className="space-y-3">
        {insights?.map((insight) => (
          <InsightCard
            key={insight.id}
            insight={insight}
            sessionId={sessionId}
            onJumpTo={setCursorDistanceM}
            onDelete={(id) => deleteOneMutation.mutate(id)}
            circuit={circuit ?? null}
            lapRows={mapLaps}
            channels={mapChannels}
            lapColorMap={miniLapColorMap}
            mapReady={mapChannels.length > 0}
          />
        ))}
      </div>
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export function SessionDetailPage() {
  const { sessionId } = useParams({ from: '/sessions/$sessionId' })
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('overview')

  const { data: session, isLoading } = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => getSession(sessionId),
  })

  if (isLoading) return <SpinnerOverlay label="Loading session…" />

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex flex-col">
      {/* Header */}
      <header className="border-b border-[#1e1e2e] bg-[#12121a] flex-shrink-0">
        <div className="max-w-screen-xl mx-auto px-4 md:px-6 h-14 flex items-center gap-4">
          <button
            onClick={() => navigate({ to: '/' })}
            className="text-[#6b7280] hover:text-white transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="text-[#1e1e2e]">|</span>
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <h1 className="text-sm font-semibold text-white truncate">
              {session?.name ?? 'Loading…'}
            </h1>
            {session?.status && <Badge status={session.status} />}
          </div>
          <div className="flex items-center gap-4 text-xs text-[#6b7280]">
            {session?.session_date && (
              <span>{new Date(session.session_date).toLocaleDateString()}</span>
            )}
          </div>
        </div>
      </header>

      {/* Tab nav + content */}
      <div className="flex-1 flex flex-col min-h-0">
        <Tabs activeTab={activeTab} onTabChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
          <TabList className="bg-[#12121a] flex-shrink-0">
            <Tab value="overview">Overview</Tab>
            <Tab value="laps">Laps</Tab>
            <Tab value="analysis">Analysis</Tab>
            <Tab value="insights">Insights</Tab>
          </TabList>

          <TabPanel value="overview" className="overflow-y-auto">
            <OverviewTab sessionId={sessionId} />
          </TabPanel>
          <TabPanel value="laps" className="overflow-y-auto">
            <LapsTab sessionId={sessionId} />
          </TabPanel>
          <TabPanel value="analysis" className="flex flex-col min-h-0 overflow-hidden">
            <AnalysisTab sessionId={sessionId} />
          </TabPanel>
          <TabPanel value="insights" className="overflow-y-auto">
            <InsightsTab sessionId={sessionId} />
          </TabPanel>
        </Tabs>
      </div>
    </div>
  )
}
