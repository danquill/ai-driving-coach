import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import type { Circuit } from '../../types/api'

interface InsightMapPopoverProps {
  circuit: Circuit | null
  lapRows: Record<number, number[][]>
  channels: string[]
  lapColorMap: Record<number, string>
  /** distance_m_start from the insight (may be cumulative session distance) */
  distanceM: number
  onClose: () => void
}

export function InsightMapPopover({
  circuit,
  lapRows,
  channels,
  lapColorMap,
  distanceM,
  onClose,
}: InsightMapPopoverProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (!containerRef.current) return
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [0, 51.5],
      zoom: 14,
      attributionControl: false,
      interactive: true,
    })
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    mapRef.current = map
    map.once('load', () => setReady(true))
    return () => {
      map.remove()
      mapRef.current = null
      setReady(false)
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return

    const latIdx = channels.indexOf('lat')
    const lonIdx = channels.indexOf('lon')
    const distIdx = channels.indexOf('distance_m')

    const allCoords: [number, number][] = []

    // Draw lap traces
    const lapEntries = Object.entries(lapRows)
    for (let i = 0; i < lapEntries.length; i++) {
      const [lapNumStr, rows] = lapEntries[i]
      if (!rows || rows.length < 2 || latIdx === -1 || lonIdx === -1) continue
      const lapNum = Number(lapNumStr)
      const color = lapColorMap[lapNum] ?? '#ffffff'
      const isCmp = i === 1
      const sid = `pop-s-${lapNum}`
      const lid = `pop-l-${lapNum}`
      try {
        map.addSource(sid, {
          type: 'geojson',
          data: {
            type: 'Feature',
            properties: {},
            geometry: {
              type: 'LineString',
              coordinates: rows.map((r) => [r[lonIdx], r[latIdx]]),
            },
          },
        })
        map.addLayer({
          id: lid,
          type: 'line',
          source: sid,
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: {
            'line-color': color,
            'line-width': isCmp ? 2 : 3,
            'line-opacity': isCmp ? 0.6 : 1,
            ...(isCmp ? { 'line-dasharray': [4, 3] } : {}),
          },
        })
      } catch { /* already exists */ }
      for (const r of rows) allCoords.push([r[lonIdx], r[latIdx]])
    }

    // Fallback: circuit outline when no lap data
    if (lapEntries.length === 0 && circuit?.geometry && latIdx === -1) {
      try {
        map.addSource('pop-circuit', { type: 'geojson', data: { type: 'Feature', properties: {}, geometry: circuit.geometry } })
        map.addLayer({ id: 'pop-circuit-line', type: 'line', source: 'pop-circuit', paint: { 'line-width': 2, 'line-color': '#457b9d' } })
      } catch { /* ignore */ }
    }

    // Find pin position — search all laps for the best distance match.
    // Claude's distance_m_start may be cumulative session distance, so try both
    // the raw value and zero-based (offset by each lap's first sample).
    let pinLng: number | null = null
    let pinLat: number | null = null

    if (distIdx !== -1 && latIdx !== -1 && lonIdx !== -1) {
      let globalBestDiff = Infinity

      for (const [, rows] of lapEntries) {
        if (!rows?.length) continue
        const lapOffset = rows[0][distIdx]

        // Try raw cumulative match and zero-based match; take whichever is closer
        for (const targetDist of [distanceM, distanceM + lapOffset]) {
          let bestIdx = 0, bestDiff = Infinity
          for (let j = 0; j < rows.length; j++) {
            const d = Math.abs(rows[j][distIdx] - targetDist)
            if (d < bestDiff) { bestDiff = d; bestIdx = j }
          }
          if (bestDiff < globalBestDiff) {
            globalBestDiff = bestDiff
            pinLng = rows[bestIdx][lonIdx]
            pinLat = rows[bestIdx][latIdx]
          }
        }
      }
    }

    if (pinLng !== null && pinLat !== null) {
      const el = document.createElement('div')
      el.style.cssText = `
        width:14px;height:14px;border-radius:50%;
        background:#ffffff;border:3px solid #457b9d;
        box-shadow:0 0 0 4px rgba(69,123,157,0.35),0 0 12px rgba(69,123,157,0.6);
        pointer-events:none;
      `
      new maplibregl.Marker({ element: el, anchor: 'center' })
        .setLngLat([pinLng, pinLat])
        .addTo(map)
      map.flyTo({ center: [pinLng, pinLat], zoom: 15.5, duration: 800 })
    } else if (allCoords.length > 1) {
      const bounds = allCoords.reduce(
        (b, c) => b.extend(c),
        new maplibregl.LngLatBounds(allCoords[0], allCoords[0])
      )
      map.fitBounds(bounds, { padding: 40, maxZoom: 16, duration: 600 })
    }
  }, [ready, lapRows, channels, lapColorMap, distanceM, circuit])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="relative rounded-xl overflow-hidden border border-[#2e2e4e] shadow-2xl"
        style={{ width: 520, height: 420 }}>
        <div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between px-3 py-2 bg-[#0a0a0f]/80 backdrop-blur-sm border-b border-[#1e1e2e]">
          <span className="text-xs text-[#9ca3af] font-mono">
            Track position @{distanceM.toFixed(0)}m
          </span>
          <button onClick={onClose} className="text-[#6b7280] hover:text-white transition-colors">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div ref={containerRef} className="w-full h-full" />
      </div>
    </div>
  )
}
