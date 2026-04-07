import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import type { Circuit } from '../../types/api'

interface InsightMiniMapProps {
  circuit: Circuit | null
  lapRows: Record<number, number[][]>
  channels: string[]
  lapColorMap: Record<number, string>
  distanceM: number
  distanceMStart?: number
  distanceMEnd?: number
  width?: number
  height?: number
}

/**
 * Renders a MapLibre map offscreen, captures it to a PNG data URL, then
 * destroys the GL context. Displays a static <img> — zero persistent GL
 * contexts after render, so safe to use in a list of cards.
 */
export function InsightMiniMap({
  circuit,
  lapRows,
  channels,
  lapColorMap,
  distanceM,
  distanceMStart,
  distanceMEnd,
  width = 240,
  height = 160,
}: InsightMiniMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [snapshot, setSnapshot] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  const latIdx = channels.indexOf('lat')
  const lonIdx = channels.indexOf('lon')
  const distIdx = channels.indexOf('distance_m')
  const hasData = latIdx !== -1 && lonIdx !== -1 && Object.keys(lapRows).length > 0

  useEffect(() => {
    // Wait until real data arrives before attempting render
    if (!hasData || !containerRef.current) return
    // Already captured or failed — don't re-run
    if (snapshot || failed) return

    const container = containerRef.current

    const map = new maplibregl.Map({
      container,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [0, 51.5],
      zoom: 14,
      attributionControl: false,
      interactive: false,
      preserveDrawingBuffer: true,
    })

    let removed = false

    const capture = () => {
      if (removed) return
      try {
        const dataUrl = map.getCanvas().toDataURL('image/png')
        setSnapshot(dataUrl)
      } catch {
        setFailed(true)
      } finally {
        removed = true
        try { map.remove() } catch { /* ignore */ }
      }
    }

    map.once('load', () => {
      const lapEntries = Object.entries(lapRows)
      const allCoords: [number, number][] = []

      for (let i = 0; i < lapEntries.length; i++) {
        const [lapNumStr, rows] = lapEntries[i]
        if (!rows || rows.length < 2) continue
        const lapNum = Number(lapNumStr)
        const color = lapColorMap[lapNum] ?? '#ffffff'
        const isCmp = i === 1
        try {
          map.addSource(`mini-s-${lapNum}`, {
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
            id: `mini-l-${lapNum}`,
            type: 'line',
            source: `mini-s-${lapNum}`,
            layout: { 'line-join': 'round', 'line-cap': 'round' },
            paint: {
              'line-color': color,
              'line-width': isCmp ? 2 : 3,
              'line-opacity': isCmp ? 0.6 : 1,
              ...(isCmp ? { 'line-dasharray': [4, 3] } : {}),
            },
          })
        } catch { /* ignore */ }
        for (const r of rows) allCoords.push([r[lonIdx], r[latIdx]])
      }

      // Fallback to circuit geometry
      if (lapEntries.length === 0 && circuit?.geometry) {
        try {
          map.addSource('mini-circuit', { type: 'geojson', data: { type: 'Feature', properties: {}, geometry: circuit.geometry } })
          map.addLayer({ id: 'mini-circuit-line', type: 'line', source: 'mini-circuit', paint: { 'line-width': 2, 'line-color': '#457b9d' } })
        } catch { /* ignore */ }
      }

      // Build highlighted segment coords and centre point from lap-relative distances
      const afterMove = () => map.once('idle', capture)

      let segmentCoords: [number, number][] = []
      let segmentCenter: [number, number] | null = null

      if (distIdx !== -1 && (distanceMStart != null || distanceMEnd != null)) {
        // Use first lap's rows; rows[0][distIdx] is the cumulative offset for lap start
        const rows = Object.values(lapRows)[0]
        if (rows?.length) {
          const lapOffset = rows[0][distIdx]
          const absStart = (distanceMStart ?? distanceM) + lapOffset
          const absEnd = (distanceMEnd ?? distanceM) + lapOffset

          for (const row of rows) {
            const d = row[distIdx]
            if (d >= absStart && d <= absEnd) {
              segmentCoords.push([row[lonIdx], row[latIdx]])
            }
          }

          // Centre of the segment
          if (segmentCoords.length > 0) {
            const mid = segmentCoords[Math.floor(segmentCoords.length / 2)]
            segmentCenter = mid
          }
        }
      }

      // Draw highlight segment
      if (segmentCoords.length >= 2) {
        try {
          map.addSource('mini-highlight', {
            type: 'geojson',
            data: {
              type: 'Feature',
              properties: {},
              geometry: { type: 'LineString', coordinates: segmentCoords },
            },
          })
          // Glow halo
          map.addLayer({
            id: 'mini-highlight-halo',
            type: 'line',
            source: 'mini-highlight',
            layout: { 'line-join': 'round', 'line-cap': 'round' },
            paint: { 'line-color': '#f59e0b', 'line-width': 8, 'line-opacity': 0.25 },
          })
          // Solid highlight
          map.addLayer({
            id: 'mini-highlight-line',
            type: 'line',
            source: 'mini-highlight',
            layout: { 'line-join': 'round', 'line-cap': 'round' },
            paint: { 'line-color': '#f59e0b', 'line-width': 3, 'line-opacity': 1 },
          })
        } catch { /* ignore */ }
      }

      if (segmentCenter) {
        // Fit bounds around the segment with padding
        const segBounds = segmentCoords.reduce(
          (b, c) => b.extend(c),
          new maplibregl.LngLatBounds(segmentCoords[0], segmentCoords[0])
        )
        map.once('moveend', afterMove)
        map.fitBounds(segBounds, { padding: 40, maxZoom: 16.5, duration: 0 })
      } else if (allCoords.length > 1) {
        const bounds = allCoords.reduce(
          (b, c) => b.extend(c),
          new maplibregl.LngLatBounds(allCoords[0], allCoords[0])
        )
        map.once('moveend', afterMove)
        map.fitBounds(bounds, { padding: 20, maxZoom: 16, duration: 0 })
      } else {
        capture()
      }
    })

    return () => {
      if (!removed) {
        removed = true
        try { map.remove() } catch { /* ignore */ }
      }
    }
  }, [hasData, snapshot, failed]) // re-run when data arrives; stop once captured

  if (snapshot) {
    return (
      <div className="rounded overflow-hidden border border-[#1e1e2e] flex-shrink-0" style={{ width, height }}>
        <img src={snapshot} alt="Track position" className="w-full h-full object-cover" />
      </div>
    )
  }

  if (failed) {
    return (
      <div
        className="rounded border border-[#1e1e2e] flex-shrink-0 flex items-center justify-center bg-[#0d0d14] text-[#4b5563] text-xs"
        style={{ width, height }}
      >
        No map data
      </div>
    )
  }

  // Skeleton shown while waiting for data or rendering
  // Container must be visible (not opacity-0) for MapLibre to size correctly
  return (
    <div className="relative flex-shrink-0 rounded overflow-hidden border border-[#1e1e2e]" style={{ width, height }}>
      <div
        ref={containerRef}
        className="absolute inset-0"
        style={{ width, height, visibility: 'hidden' }}
      />
      <div className="absolute inset-0 bg-[#0d0d14] animate-pulse" />
    </div>
  )
}
