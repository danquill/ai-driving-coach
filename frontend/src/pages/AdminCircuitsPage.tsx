import { useEffect, useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import {
  listCircuits, createCircuit, deleteCircuit,
  createCorner, updateCorner, deleteCorner,
  createSector, deleteSector,
  listCornerKnowledge, createCornerKnowledge, deleteCornerKnowledge,
  listSessionsForCircuit, importGeometryFromLap,
} from '../api/circuits'
import type { Circuit, CircuitCorner, CircuitCornerKnowledge, CircuitSector } from '../types/api'
import { useStore } from '../store'
import { useNavigate } from '@tanstack/react-router'
import { AppHeader } from '../components/ui/AppHeader'

// ─── Corner editor row ────────────────────────────────────────────────────────

function CornerRow({
  corner,
  circuitId,
  onDelete,
  onUpdate,
}: {
  corner: CircuitCorner
  circuitId: string
  onDelete: (id: string) => void
  onUpdate: (id: string, data: Partial<CircuitCorner>) => void
}) {
  const [editing, setEditing] = useState(false)
  const [num, setNum] = useState(String(corner.corner_number))
  const [name, setName] = useState(corner.name ?? '')

  function save() {
    onUpdate(corner.id, { corner_number: Number(num), name: name || undefined })
    setEditing(false)
  }

  return (
    <tr className="border-t border-[#1e1e2e] hover:bg-[#16162a] transition-colors">
      <td className="px-3 py-2 text-center">
        {editing ? (
          <input
            className="w-12 text-center bg-[#0d0d14] border border-[#2e2e4e] rounded px-1 py-0.5 text-xs text-white"
            value={num}
            onChange={(e) => setNum(e.target.value)}
          />
        ) : (
          <span className="text-sm font-mono text-[#e2e8f0]">T{corner.corner_number}</span>
        )}
      </td>
      <td className="px-3 py-2">
        {editing ? (
          <input
            className="w-full bg-[#0d0d14] border border-[#2e2e4e] rounded px-2 py-0.5 text-xs text-white"
            value={name}
            placeholder="e.g. Corkscrew"
            onChange={(e) => setName(e.target.value)}
          />
        ) : (
          <span className="text-sm text-[#9ca3af]">{corner.name ?? <span className="italic text-[#4b5563]">—</span>}</span>
        )}
      </td>
      <td className="px-3 py-2 text-right">
        <span className="text-xs font-mono text-[#6b7280]">{Math.round(corner.distance_m)}m</span>
      </td>
      <td className="px-3 py-2 text-right">
        <div className="flex items-center justify-end gap-2">
          {editing ? (
            <>
              <button onClick={save} className="text-xs text-[#00e676] hover:text-white transition-colors px-2 py-0.5 rounded border border-[#00e676]/30 hover:border-[#00e676]">Save</button>
              <button onClick={() => setEditing(false)} className="text-xs text-[#6b7280] hover:text-white transition-colors">Cancel</button>
            </>
          ) : (
            <>
              <button onClick={() => setEditing(true)} className="text-xs text-[#457b9d] hover:text-white transition-colors">Edit</button>
              <button onClick={() => onDelete(corner.id)} className="text-xs text-[#6b7280] hover:text-[#ff5252] transition-colors">Delete</button>
            </>
          )}
        </div>
      </td>
    </tr>
  )
}

// ─── Geometry import panel ────────────────────────────────────────────────────

function GeometryImportPanel({ circuitId, onImported }: { circuitId: string; onImported: () => void }) {
  const [open, setOpen] = useState(false)
  const [selectedSession, setSelectedSession] = useState('')
  const [selectedLap, setSelectedLap] = useState<number | ''>('')
  const [result, setResult] = useState<{ point_count: number; track_length_m: number } | null>(null)

  const { data: sessions = [], isLoading } = useQuery({
    queryKey: ['circuit-sessions', circuitId],
    queryFn: () => listSessionsForCircuit(circuitId),
    enabled: open,
  })

  const importMutation = useMutation({
    mutationFn: () => importGeometryFromLap(circuitId, selectedSession, Number(selectedLap)),
    onSuccess: (data) => {
      setResult(data)
      onImported()
    },
  })

  const sessionObj = sessions.find((s) => s.session_id === selectedSession)

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 text-xs text-[#457b9d] hover:text-white transition-colors border border-[#1e1e2e] hover:border-[#2e2e4e] rounded-lg px-3 py-2"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
        </svg>
        Import track from session GPS
      </button>
    )
  }

  return (
    <div className="bg-[#0d0d14] border border-[#1e1e2e] rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-white">Import track geometry from GPS</span>
        <button onClick={() => { setOpen(false); setResult(null) }} className="text-[#4b5563] hover:text-white transition-colors text-xs">✕</button>
      </div>

      {result ? (
        <div className="flex items-center gap-3 py-2">
          <div className="w-5 h-5 rounded-full bg-[#00e676]/20 flex items-center justify-center flex-shrink-0">
            <svg className="w-3 h-3 text-[#00e676]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <span className="text-sm text-[#9ca3af]">
            Imported {result.point_count.toLocaleString()} GPS points · {(result.track_length_m / 1000).toFixed(3)} km track length
          </span>
          <button onClick={() => setResult(null)} className="ml-auto text-xs text-[#457b9d] hover:text-white transition-colors">Import again</button>
        </div>
      ) : (
        <>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="text-xs text-[#6b7280] block mb-1">Session</label>
              {isLoading ? (
                <div className="h-8 bg-[#16162a] rounded animate-pulse" />
              ) : sessions.length === 0 ? (
                <p className="text-xs text-[#4b5563] py-1.5">No sessions with GPS data for this circuit.</p>
              ) : (
                <select
                  value={selectedSession}
                  onChange={(e) => { setSelectedSession(e.target.value); setSelectedLap('') }}
                  className="w-full bg-[#0d0d14] border border-[#2e2e4e] rounded px-2 py-1.5 text-sm text-white focus:border-[#457b9d] outline-none"
                >
                  <option value="">— select session —</option>
                  {sessions.map((s) => (
                    <option key={s.session_id} value={s.session_id}>
                      {s.session_name ?? 'Untitled'}{s.session_date ? ` · ${s.session_date}` : ''}
                    </option>
                  ))}
                </select>
              )}
            </div>

            <div className="w-28">
              <label className="text-xs text-[#6b7280] block mb-1">Lap</label>
              <select
                value={selectedLap}
                onChange={(e) => setSelectedLap(e.target.value === '' ? '' : Number(e.target.value))}
                disabled={!sessionObj}
                className="w-full bg-[#0d0d14] border border-[#2e2e4e] rounded px-2 py-1.5 text-sm text-white focus:border-[#457b9d] outline-none disabled:opacity-40"
              >
                <option value="">— lap —</option>
                {sessionObj?.lap_numbers.map((n) => (
                  <option key={n} value={n}>Lap {n}</option>
                ))}
              </select>
            </div>
          </div>

          {importMutation.isError && (
            <p className="text-xs text-[#ff5252]">
              {(importMutation.error as Error).message ?? 'Import failed'}
            </p>
          )}

          <div className="flex justify-end gap-2">
            <button onClick={() => setOpen(false)} className="text-xs text-[#6b7280] hover:text-white transition-colors px-3 py-1.5 rounded">
              Cancel
            </button>
            <button
              onClick={() => importMutation.mutate()}
              disabled={!selectedSession || selectedLap === '' || importMutation.isPending}
              className="text-xs bg-[#457b9d] hover:bg-[#3a6a8a] disabled:opacity-40 text-white font-medium px-3 py-1.5 rounded transition-colors flex items-center gap-1.5"
            >
              {importMutation.isPending && (
                <span className="w-3 h-3 border border-white/40 border-t-white rounded-full animate-spin" />
              )}
              Import track
            </button>
          </div>
        </>
      )}
    </div>
  )
}


// ─── Shared circuit map ───────────────────────────────────────────────────────

function CircuitMap({
  circuit,
  corners,
  sectors,
  mode,
  onPlace,
}: {
  circuit: Circuit
  corners: CircuitCorner[]
  sectors: CircuitSector[]
  mode: 'corners' | 'sectors'
  onPlace: (lat: number, lon: number, distance_m: number) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef<maplibregl.Marker[]>([])
  const [mapLoaded, setMapLoaded] = useState(false)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    let removed = false

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [circuit.sectors[0]?.trigger_lon ?? -78.5, circuit.sectors[0]?.trigger_lat ?? 38.5],
      zoom: 14,
      attributionControl: false,
    })
    mapRef.current = map

    map.once('load', () => {
      if (circuit.geometry) {
        map.addSource('track', { type: 'geojson', data: { type: 'Feature', properties: {}, geometry: circuit.geometry } })
        map.addLayer({ id: 'track-line', type: 'line', source: 'track', paint: { 'line-color': '#457b9d', 'line-width': 3 } })

        const coords = (circuit.geometry as GeoJSON.LineString).coordinates as [number, number][]
        if (coords?.length > 1) {
          const bounds = coords.reduce(
            (b, c) => b.extend(c),
            new maplibregl.LngLatBounds(coords[0], coords[0])
          )
          map.fitBounds(bounds, { padding: 40, maxZoom: 16, duration: 0 })
        }
      }
      if (!removed) setMapLoaded(true)
    })

    map.on('click', (e) => {
      const { lng, lat } = e.lngLat
      let distanceM = 0
      if (circuit.geometry) {
        const coords = (circuit.geometry as GeoJSON.LineString).coordinates as [number, number][]
        let minDist = Infinity
        let cumDist = 0
        let bestCum = 0
        for (let i = 0; i < coords.length; i++) {
          if (i > 0) {
            const dx = (coords[i][0] - coords[i-1][0]) * 111320 * Math.cos(coords[i][1] * Math.PI / 180)
            const dy = (coords[i][1] - coords[i-1][1]) * 110540
            cumDist += Math.sqrt(dx*dx + dy*dy)
          }
          const dx = (coords[i][0] - lng) * 111320 * Math.cos(coords[i][1] * Math.PI / 180)
          const dy = (coords[i][1] - lat) * 110540
          const d = Math.sqrt(dx*dx + dy*dy)
          if (d < minDist) { minDist = d; bestCum = cumDist }
        }
        distanceM = bestCum
      }
      onPlace(lat, lng, Math.round(distanceM))
    })

    return () => {
      removed = true
      setMapLoaded(false)
      if (map._loaded) {
        try { map.remove() } catch { /* ignore */ }
      } else {
        map.once('load', () => { try { map.remove() } catch { /* ignore */ } })
      }
      mapRef.current = null
    }
  }, [circuit.id, circuit.geometry]) // eslint-disable-line react-hooks/exhaustive-deps

  // Sync markers whenever corners/sectors/mode changes
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapLoaded) return

    markersRef.current.forEach((m) => m.remove())
    markersRef.current = []

    if (mode === 'corners') {
      for (const corner of corners) {
        const el = document.createElement('div')
        el.style.cssText = `
          width:22px;height:22px;border-radius:50%;
          background:#1a1a2e;border:2px solid #f59e0b;
          display:flex;align-items:center;justify-content:center;
          font-size:9px;font-weight:700;color:#f59e0b;
          font-family:monospace;cursor:default;
          box-shadow:0 0 0 2px rgba(245,158,11,0.2);
        `
        el.textContent = String(corner.corner_number)
        markersRef.current.push(
          new maplibregl.Marker({ element: el, anchor: 'center' })
            .setLngLat([corner.lon, corner.lat])
            .addTo(map)
        )
      }
    } else {
      for (const sector of sectors) {
        const el = document.createElement('div')
        el.style.cssText = `
          width:26px;height:26px;border-radius:4px;
          background:#1a1a2e;border:2px solid #00e676;
          display:flex;align-items:center;justify-content:center;
          font-size:9px;font-weight:700;color:#00e676;
          font-family:monospace;cursor:default;
          box-shadow:0 0 0 2px rgba(0,230,118,0.2);
        `
        el.textContent = `S${sector.sector_number}`
        markersRef.current.push(
          new maplibregl.Marker({ element: el, anchor: 'center' })
            .setLngLat([sector.trigger_lon, sector.trigger_lat])
            .addTo(map)
        )
      }
    }
  }, [corners, sectors, mode, mapLoaded])

  return (
    <div className="relative rounded-lg overflow-hidden border border-[#1e1e2e]" style={{ height: 420 }}>
      <div ref={containerRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
      <div className="absolute bottom-2 left-2 bg-black/60 text-xs text-[#9ca3af] px-2 py-1 rounded pointer-events-none">
        Click on the track to place a {mode === 'corners' ? 'corner' : 'sector trigger'}
      </div>
    </div>
  )
}

// ─── Pending corner form ──────────────────────────────────────────────────────

function PendingCornerForm({
  lat,
  lon,
  distanceM,
  existingNumbers,
  onConfirm,
  onCancel,
}: {
  lat: number
  lon: number
  distanceM: number
  existingNumbers: Set<number>
  onConfirm: (num: number, name: string) => void
  onCancel: () => void
}) {
  // Default to next available corner number
  const nextNum = (() => {
    let n = 1
    while (existingNumbers.has(n)) n++
    return n
  })()
  const [num, setNum] = useState(String(nextNum))
  const [name, setName] = useState('')

  return (
    <div className="bg-[#16162a] border border-[#f59e0b]/40 rounded-lg p-4 space-y-3">
      <p className="text-xs text-[#f59e0b] font-medium">New corner at ~{Math.round(distanceM)}m</p>
      <div className="flex gap-3">
        <div className="w-20">
          <label className="text-xs text-[#6b7280] block mb-1">Turn #</label>
          <input
            type="number"
            min={1}
            className="w-full bg-[#0d0d14] border border-[#2e2e4e] rounded px-2 py-1.5 text-sm text-white focus:border-[#457b9d] outline-none"
            value={num}
            onChange={(e) => setNum(e.target.value)}
          />
        </div>
        <div className="flex-1">
          <label className="text-xs text-[#6b7280] block mb-1">Name <span className="text-[#4b5563]">(optional)</span></label>
          <input
            type="text"
            placeholder="e.g. Corkscrew"
            className="w-full bg-[#0d0d14] border border-[#2e2e4e] rounded px-2 py-1.5 text-sm text-white placeholder-[#4b5563] focus:border-[#457b9d] outline-none"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
      </div>
      <div className="flex gap-2 justify-end">
        <button onClick={onCancel} className="text-xs text-[#6b7280] hover:text-white px-3 py-1.5 rounded transition-colors">
          Cancel
        </button>
        <button
          onClick={() => onConfirm(Number(num), name)}
          disabled={!num || isNaN(Number(num))}
          className="text-xs bg-[#f59e0b] hover:bg-[#d97706] disabled:opacity-40 text-black font-medium px-3 py-1.5 rounded transition-colors"
        >
          Add Corner
        </button>
      </div>
    </div>
  )
}

// ─── Pending sector form ──────────────────────────────────────────────────────

function PendingSectorForm({
  lat,
  lon,
  existingNumbers,
  onConfirm,
  onCancel,
}: {
  lat: number
  lon: number
  existingNumbers: Set<number>
  onConfirm: (num: number) => void
  onCancel: () => void
}) {
  const nextNum = (() => {
    let n = 1
    while (existingNumbers.has(n)) n++
    return n
  })()
  const [num, setNum] = useState(String(nextNum))

  return (
    <div className="bg-[#16162a] border border-[#00e676]/40 rounded-lg p-4 space-y-3">
      <p className="text-xs text-[#00e676] font-medium">New sector trigger at {lat.toFixed(5)}, {lon.toFixed(5)}</p>
      <div className="w-28">
        <label className="text-xs text-[#6b7280] block mb-1">Sector #</label>
        <input
          type="number"
          min={1}
          className="w-full bg-[#0d0d14] border border-[#2e2e4e] rounded px-2 py-1.5 text-sm text-white focus:border-[#00e676] outline-none"
          value={num}
          onChange={(e) => setNum(e.target.value)}
        />
      </div>
      <div className="flex gap-2 justify-end">
        <button onClick={onCancel} className="text-xs text-[#6b7280] hover:text-white px-3 py-1.5 rounded transition-colors">
          Cancel
        </button>
        <button
          onClick={() => onConfirm(Number(num))}
          disabled={!num || isNaN(Number(num))}
          className="text-xs bg-[#00e676] hover:bg-[#00c85a] disabled:opacity-40 text-black font-medium px-3 py-1.5 rounded transition-colors"
        >
          Add Sector
        </button>
      </div>
    </div>
  )
}


// ─── Circuit detail panel ─────────────────────────────────────────────────────

// ─── Knowledge tab ────────────────────────────────────────────────────────────

const PHASE_OPTIONS = ['', 'entry', 'turn-in', 'mid-corner', 'exit'] as const

function KnowledgeTab({ circuit }: { circuit: Circuit }) {
  const qc = useQueryClient()

  const { data: entries = [], isLoading } = useQuery({
    queryKey: ['cornerKnowledge', circuit.id],
    queryFn: () => listCornerKnowledge(circuit.id),
  })

  const createMutation = useMutation({
    mutationFn: (data: Parameters<typeof createCornerKnowledge>[1]) =>
      createCornerKnowledge(circuit.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cornerKnowledge', circuit.id] })
      setForm(emptyForm)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteCornerKnowledge(circuit.id, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cornerKnowledge', circuit.id] }),
  })

  const emptyForm = {
    corner_number: '',
    typical_phase_of_interest: '',
    known_handling_tendency: '',
    correct_technique: '',
    incorrect_recommendations: '',
    coaching_notes: '',
  }
  const [form, setForm] = useState(emptyForm)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const payload: Parameters<typeof createCornerKnowledge>[1] = {
      coaching_notes: form.coaching_notes || undefined,
      known_handling_tendency: form.known_handling_tendency || undefined,
      correct_technique: form.correct_technique || undefined,
      typical_phase_of_interest: form.typical_phase_of_interest || undefined,
      incorrect_recommendations: form.incorrect_recommendations
        ? form.incorrect_recommendations.split(',').map((s) => s.trim()).filter(Boolean)
        : undefined,
    }
    if (form.corner_number) payload.corner_number = parseInt(form.corner_number, 10)
    createMutation.mutate(payload)
  }

  const corners = circuit.corners ?? []
  const cornerLabel = (cn: number | undefined) => {
    if (cn == null) return 'Circuit-wide'
    const c = corners.find((c) => c.corner_number === cn)
    return c ? `T${cn}${c.name ? ` — ${c.name}` : ''}` : `T${cn}`
  }

  return (
    <div className="space-y-4">
      {isLoading ? (
        <p className="text-sm text-[#4b5563] text-center py-4">Loading…</p>
      ) : entries.length > 0 ? (
        <div className="bg-[#0d0d14] rounded-lg border border-[#1e1e2e] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-[#6b7280] uppercase tracking-wide">
                <th className="px-3 py-2 w-32">Corner</th>
                <th className="px-3 py-2 w-24">Phase</th>
                <th className="px-3 py-2">Tendency / Notes</th>
                <th className="px-3 py-2 w-20 text-center">Source</th>
                <th className="px-3 py-2 w-16"></th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id} className="border-t border-[#1e1e2e] hover:bg-[#16162a] transition-colors align-top">
                  <td className="px-3 py-2">
                    <span className="text-xs font-mono text-[#e2e8f0]">{cornerLabel(entry.corner_number)}</span>
                  </td>
                  <td className="px-3 py-2">
                    <span className="text-xs text-[#9ca3af]">{entry.typical_phase_of_interest ?? '—'}</span>
                  </td>
                  <td className="px-3 py-2 max-w-xs">
                    {entry.known_handling_tendency && (
                      <p className="text-xs text-[#9ca3af]">{entry.known_handling_tendency}</p>
                    )}
                    {entry.coaching_notes && (
                      <p className="text-xs text-[#d1d5db] mt-0.5 italic">
                        "{entry.coaching_notes.length > 80
                          ? entry.coaching_notes.slice(0, 80) + '…'
                          : entry.coaching_notes}"
                      </p>
                    )}
                    {entry.incorrect_recommendations && entry.incorrect_recommendations.length > 0 && (
                      <p className="text-xs text-[#ff5252]/70 mt-0.5">
                        Never: {entry.incorrect_recommendations.join(', ')}
                      </p>
                    )}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <span className={`text-xs px-1.5 py-0.5 rounded border ${
                      entry.source === 'correction'
                        ? 'text-[#ff5252] border-[#ff5252]/30 bg-[#ff5252]/10'
                        : 'text-[#6b7280] border-[#6b7280]/30'
                    }`}>
                      {entry.source}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      onClick={() => deleteMutation.mutate(entry.id)}
                      className="text-xs text-[#6b7280] hover:text-[#ff5252] transition-colors"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-[#4b5563] text-center py-4">
          No knowledge entries yet. Add constraints below to guide the AI coach.
        </p>
      )}

      {/* Add knowledge form */}
      <div className="bg-[#0d0d14] rounded-lg border border-[#1e1e2e] p-4">
        <p className="text-xs font-medium text-[#9ca3af] uppercase tracking-wide mb-3">Add Knowledge Entry</p>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-[#6b7280] block mb-1">
                Corner # <span className="text-[#4b5563]">(leave blank for circuit-wide)</span>
              </label>
              <input
                type="number"
                value={form.corner_number}
                onChange={(e) => setForm((f) => ({ ...f, corner_number: e.target.value }))}
                placeholder="e.g. 4"
                className="w-full text-xs bg-[#16162a] border border-[#1e1e2e] rounded px-2 py-1.5 text-[#d1d5db] placeholder-[#4b5563] focus:outline-none focus:border-[#457b9d]"
              />
            </div>
            <div>
              <label className="text-xs text-[#6b7280] block mb-1">Phase of interest</label>
              <select
                value={form.typical_phase_of_interest}
                onChange={(e) => setForm((f) => ({ ...f, typical_phase_of_interest: e.target.value }))}
                className="w-full text-xs bg-[#16162a] border border-[#1e1e2e] rounded px-2 py-1.5 text-[#d1d5db] focus:outline-none focus:border-[#457b9d]"
              >
                {PHASE_OPTIONS.map((p) => (
                  <option key={p} value={p}>{p || '—'}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs text-[#6b7280] block mb-1">Known handling tendency</label>
            <input
              type="text"
              value={form.known_handling_tendency}
              onChange={(e) => setForm((f) => ({ ...f, known_handling_tendency: e.target.value }))}
              placeholder="e.g. entry understeer, exit oversteer"
              className="w-full text-xs bg-[#16162a] border border-[#1e1e2e] rounded px-2 py-1.5 text-[#d1d5db] placeholder-[#4b5563] focus:outline-none focus:border-[#457b9d]"
            />
          </div>
          <div>
            <label className="text-xs text-[#6b7280] block mb-1">Correct technique</label>
            <input
              type="text"
              value={form.correct_technique}
              onChange={(e) => setForm((f) => ({ ...f, correct_technique: e.target.value }))}
              placeholder="e.g. trail brake through apex, late turn-in"
              className="w-full text-xs bg-[#16162a] border border-[#1e1e2e] rounded px-2 py-1.5 text-[#d1d5db] placeholder-[#4b5563] focus:outline-none focus:border-[#457b9d]"
            />
          </div>
          <div>
            <label className="text-xs text-[#6b7280] block mb-1">
              Never recommend <span className="text-[#4b5563]">(comma-separated)</span>
            </label>
            <input
              type="text"
              value={form.incorrect_recommendations}
              onChange={(e) => setForm((f) => ({ ...f, incorrect_recommendations: e.target.value }))}
              placeholder="e.g. brush braking, earlier turn-in"
              className="w-full text-xs bg-[#16162a] border border-[#1e1e2e] rounded px-2 py-1.5 text-[#d1d5db] placeholder-[#4b5563] focus:outline-none focus:border-[#457b9d]"
            />
          </div>
          <div>
            <label className="text-xs text-[#6b7280] block mb-1">Coaching notes</label>
            <textarea
              value={form.coaching_notes}
              onChange={(e) => setForm((f) => ({ ...f, coaching_notes: e.target.value }))}
              rows={3}
              placeholder="Free-text guidance injected directly into the coaching prompt…"
              className="w-full text-xs bg-[#16162a] border border-[#1e1e2e] rounded px-2 py-1.5 text-[#d1d5db] placeholder-[#4b5563] focus:outline-none focus:border-[#457b9d] resize-none"
            />
          </div>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="px-4 py-1.5 text-xs font-medium bg-[#457b9d]/20 text-[#457b9d] border border-[#457b9d]/30 rounded hover:bg-[#457b9d]/30 transition-colors disabled:opacity-50"
          >
            {createMutation.isPending ? 'Adding…' : 'Add Knowledge Entry'}
          </button>
        </form>
      </div>
    </div>
  )
}

// ─── Circuit detail ────────────────────────────────────────────────────────────

function CircuitDetail({ circuit }: { circuit: Circuit }) {
  const qc = useQueryClient()
  const [tab, setTab] = useState<'corners' | 'sectors' | 'knowledge'>('corners')
  const [pending, setPending] = useState<{ lat: number; lon: number; distance_m: number } | null>(null)

  const corners = circuit.corners ?? []
  const sectors = circuit.sectors ?? []
  const existingCornerNums = new Set(corners.map((c) => c.corner_number))
  const existingSectorNums = new Set(sectors.map((s) => s.sector_number))

  const createCornerMutation = useMutation({
    mutationFn: (data: Parameters<typeof createCorner>[1]) => createCorner(circuit.id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['circuits'] }); setPending(null) },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<CircuitCorner> }) =>
      updateCorner(circuit.id, id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['circuits'] }),
  })

  const deleteCornerMutation = useMutation({
    mutationFn: (id: string) => deleteCorner(circuit.id, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['circuits'] }),
  })

  const createSectorMutation = useMutation({
    mutationFn: (data: Parameters<typeof createSector>[1]) => createSector(circuit.id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['circuits'] }); setPending(null) },
  })

  const deleteSectorMutation = useMutation({
    mutationFn: (id: string) => deleteSector(circuit.id, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['circuits'] }),
  })

  function handlePlace(lat: number, lon: number, distance_m: number) {
    setPending({ lat, lon, distance_m })
  }

  function handleConfirmCorner(corner_number: number, name: string) {
    if (!pending) return
    createCornerMutation.mutate({
      corner_number,
      name: name || undefined,
      distance_m: pending.distance_m,
      lat: pending.lat,
      lon: pending.lon,
    })
  }

  function handleConfirmSector(sector_number: number) {
    if (!pending) return
    createSectorMutation.mutate({
      sector_number,
      trigger_lat: pending.lat,
      trigger_lon: pending.lon,
    })
  }

  // Clear pending when switching tabs
  function switchTab(t: 'corners' | 'sectors' | 'knowledge') {
    setTab(t)
    setPending(null)
  }

  return (
    <div className="space-y-4">
      <GeometryImportPanel
        circuitId={circuit.id}
        onImported={() => qc.invalidateQueries({ queryKey: ['circuits'] })}
      />

      {/* Tab switcher */}
      <div className="flex gap-1 border-b border-[#1e1e2e]">
        {(['corners', 'sectors', 'knowledge'] as const).map((t) => (
          <button
            key={t}
            onClick={() => switchTab(t)}
            className={`px-4 py-2 text-xs font-medium capitalize transition-colors border-b-2 -mb-px ${
              tab === t
                ? 'text-white border-[#457b9d]'
                : 'text-[#6b7280] border-transparent hover:text-[#9ca3af]'
            }`}
          >
            {t === 'corners' ? `Corners (${corners.length})` : t === 'sectors' ? `Sectors (${sectors.length})` : 'Knowledge'}
          </button>
        ))}
      </div>

      {tab !== 'knowledge' && (
        <CircuitMap
          circuit={circuit}
          corners={corners}
          sectors={sectors}
          mode={tab as 'corners' | 'sectors'}
          onPlace={handlePlace}
        />
      )}

      {pending && tab === 'corners' && (
        <PendingCornerForm
          lat={pending.lat}
          lon={pending.lon}
          distanceM={pending.distance_m}
          existingNumbers={existingCornerNums}
          onConfirm={handleConfirmCorner}
          onCancel={() => setPending(null)}
        />
      )}

      {pending && tab === 'sectors' && (
        <PendingSectorForm
          lat={pending.lat}
          lon={pending.lon}
          existingNumbers={existingSectorNums}
          onConfirm={handleConfirmSector}
          onCancel={() => setPending(null)}
        />
      )}

      {tab === 'corners' && (
        corners.length > 0 ? (
          <div className="bg-[#0d0d14] rounded-lg border border-[#1e1e2e] overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-[#6b7280] uppercase tracking-wide">
                  <th className="px-3 py-2 text-center w-16">Turn</th>
                  <th className="px-3 py-2">Name</th>
                  <th className="px-3 py-2 text-right">Distance</th>
                  <th className="px-3 py-2 text-right w-32"></th>
                </tr>
              </thead>
              <tbody>
                {corners.map((corner) => (
                  <CornerRow
                    key={corner.id}
                    corner={corner}
                    circuitId={circuit.id}
                    onDelete={(id) => deleteCornerMutation.mutate(id)}
                    onUpdate={(id, data) => updateMutation.mutate({ id, data })}
                  />
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-[#4b5563] text-center py-4">
            No corners yet — click on the track to add them.
          </p>
        )
      )}

      {tab === 'sectors' && (
        sectors.length > 0 ? (
          <div className="bg-[#0d0d14] rounded-lg border border-[#1e1e2e] overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-[#6b7280] uppercase tracking-wide">
                  <th className="px-3 py-2 text-center w-20">Sector</th>
                  <th className="px-3 py-2">Trigger (lat, lon)</th>
                  <th className="px-3 py-2 text-right w-24"></th>
                </tr>
              </thead>
              <tbody>
                {[...sectors].sort((a, b) => a.sector_number - b.sector_number).map((sector) => (
                  <tr key={sector.id} className="border-t border-[#1e1e2e] hover:bg-[#16162a] transition-colors">
                    <td className="px-3 py-2 text-center">
                      <span className="text-sm font-mono text-[#00e676]">S{sector.sector_number}</span>
                    </td>
                    <td className="px-3 py-2">
                      <span className="text-xs font-mono text-[#9ca3af]">
                        {sector.trigger_lat.toFixed(5)}, {sector.trigger_lon.toFixed(5)}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right">
                      <button
                        onClick={() => deleteSectorMutation.mutate(sector.id)}
                        className="text-xs text-[#6b7280] hover:text-[#ff5252] transition-colors"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-[#4b5563] text-center py-4">
            No sectors yet — click on the track to place sector trigger points.
          </p>
        )
      )}

      {tab === 'knowledge' && (
        <KnowledgeTab circuit={circuit} />
      )}
    </div>
  )
}

// ─── New circuit modal ────────────────────────────────────────────────────────

function NewCircuitModal({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [country, setCountry] = useState('')
  const [timezone, setTimezone] = useState('America/New_York')

  const createMutation = useMutation({
    mutationFn: () => createCircuit({ name: name.trim(), country: country.trim() || undefined, timezone }),
    onSuccess: (circuit) => {
      qc.invalidateQueries({ queryKey: ['circuits'] })
      onCreated(circuit.id)
    },
  })

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-[#12121a] border border-[#2e2e4e] rounded-xl p-6 w-full max-w-sm space-y-4 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white">New Circuit</h3>
          <button onClick={onClose} className="text-[#4b5563] hover:text-white transition-colors">✕</button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-xs text-[#6b7280] block mb-1">Name <span className="text-[#e63946]">*</span></label>
            <input
              autoFocus
              type="text"
              placeholder="e.g. Road Atlanta"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-[#0d0d14] border border-[#2e2e4e] rounded px-3 py-2 text-sm text-white placeholder-[#4b5563] focus:border-[#457b9d] outline-none"
            />
          </div>
          <div>
            <label className="text-xs text-[#6b7280] block mb-1">Country</label>
            <input
              type="text"
              placeholder="e.g. USA"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              className="w-full bg-[#0d0d14] border border-[#2e2e4e] rounded px-3 py-2 text-sm text-white placeholder-[#4b5563] focus:border-[#457b9d] outline-none"
            />
          </div>
          <div>
            <label className="text-xs text-[#6b7280] block mb-1">Timezone</label>
            <input
              type="text"
              placeholder="e.g. America/New_York"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="w-full bg-[#0d0d14] border border-[#2e2e4e] rounded px-3 py-2 text-sm text-white placeholder-[#4b5563] focus:border-[#457b9d] outline-none"
            />
          </div>
        </div>

        {createMutation.isError && (
          <p className="text-xs text-[#ff5252]">Failed to create circuit.</p>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <button onClick={onClose} className="text-xs text-[#6b7280] hover:text-white px-3 py-1.5 rounded transition-colors">
            Cancel
          </button>
          <button
            onClick={() => createMutation.mutate()}
            disabled={!name.trim() || createMutation.isPending}
            className="text-xs bg-[#457b9d] hover:bg-[#3a6a8a] disabled:opacity-40 text-white font-medium px-4 py-1.5 rounded transition-colors flex items-center gap-1.5"
          >
            {createMutation.isPending && (
              <span className="w-3 h-3 border border-white/40 border-t-white rounded-full animate-spin" />
            )}
            Create
          </button>
        </div>
      </div>
    </div>
  )
}


// ─── Main page ────────────────────────────────────────────────────────────────

export function AdminCircuitsPage() {
  const user = useStore((s) => s.user)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [showNewModal, setShowNewModal] = useState(false)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)

  const { data: circuits = [], isLoading } = useQuery({
    queryKey: ['circuits'],
    queryFn: listCircuits,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteCircuit(id),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ['circuits'] })
      if (selectedId === id) setSelectedId(null)
      setConfirmDeleteId(null)
    },
  })

  // Redirect non-admins
  useEffect(() => {
    if (user && user.role !== 'admin') navigate({ to: '/' })
  }, [user, navigate])

  const selected = circuits.find((c) => c.id === selectedId) ?? null

  // Auto-select first circuit
  useEffect(() => {
    if (!selectedId && circuits.length > 0) setSelectedId(circuits[0].id)
  }, [circuits, selectedId])

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-[#457b9d] border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      {showNewModal && (
        <NewCircuitModal
          onClose={() => setShowNewModal(false)}
          onCreated={(id) => { setSelectedId(id); setShowNewModal(false) }}
        />
      )}
      <AppHeader
        subtitle="Circuit Editor"
        navItems={[
          { label: 'Users', to: '/admin/users' },
          { label: 'Platform', to: '/admin/platform' },
        ]}
        rightAction={{ label: 'Dashboard', onClick: () => navigate({ to: '/' }) }}
      />

      <div className="flex h-[calc(100vh-57px)]">
        {/* Circuit list sidebar */}
        <div className="w-56 border-r border-[#1e1e2e] overflow-y-auto flex-shrink-0 flex flex-col">
          <div className="p-3 flex-1 space-y-1">
            {circuits.map((c) => (
              <div key={c.id} className="group relative">
                <button
                  onClick={() => setSelectedId(c.id)}
                  className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors ${
                    selectedId === c.id
                      ? 'bg-[#16162a] text-white border border-[#2e2e4e]'
                      : 'text-[#9ca3af] hover:bg-[#16162a] hover:text-white'
                  }`}
                >
                  <div className="font-medium truncate pr-5">{c.name}</div>
                  <div className="text-xs text-[#4b5563] mt-0.5">
                    {c.corners?.length ?? 0} corners · {c.sectors?.length ?? 0} sectors
                  </div>
                </button>
                {/* Delete button — confirm inline */}
                {confirmDeleteId === c.id ? (
                  <div className="absolute right-1 top-1/2 -translate-y-1/2 flex gap-1">
                    <button
                      onClick={() => deleteMutation.mutate(c.id)}
                      className="text-[10px] bg-[#e63946] hover:bg-[#c1121f] text-white px-1.5 py-0.5 rounded transition-colors"
                    >
                      {deleteMutation.isPending ? '…' : 'Del'}
                    </button>
                    <button
                      onClick={() => setConfirmDeleteId(null)}
                      className="text-[10px] text-[#6b7280] hover:text-white px-1 py-0.5 rounded transition-colors"
                    >
                      ✕
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(c.id) }}
                    className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 text-[#4b5563] hover:text-[#e63946] transition-all"
                    title="Delete circuit"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                )}
              </div>
            ))}
          </div>
          <div className="p-3 border-t border-[#1e1e2e]">
            <button
              onClick={() => setShowNewModal(true)}
              className="w-full flex items-center justify-center gap-1.5 text-xs text-[#457b9d] hover:text-white border border-[#1e1e2e] hover:border-[#2e2e4e] rounded-lg px-3 py-2 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              New Circuit
            </button>
          </div>
        </div>

        {/* Detail panel */}
        <div className="flex-1 overflow-y-auto p-6">
          {selected ? (
            <>
              <div className="mb-4">
                <h2 className="text-lg font-semibold text-white">{selected.name}</h2>
                <p className="text-xs text-[#6b7280] mt-0.5">
                  {selected.country} · {selected.track_length_m != null ? `${(selected.track_length_m / 1000).toFixed(2)} km` : ''}
                </p>
              </div>
              <CircuitDetail circuit={selected} />
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-[#4b5563] text-sm">
              Select a circuit
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
