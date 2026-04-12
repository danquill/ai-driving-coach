import { useState, useRef, DragEvent, ChangeEvent } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { listCircuits } from '../api/circuits'
import { createSession } from '../api/sessions'
import { uploadFile } from '../api/sessions'
import { useJobPoller } from '../hooks/useJobPoller'
import { Button } from '../components/ui/Button'
import { Card, CardHeader, CardBody } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { useStore } from '../store'
import type { AnalysisJob } from '../types/api'

// ─── Step indicators ──────────────────────────────────────────────────────────

type WizardStep = 'metadata' | 'upload' | 'processing'

const STEPS: { key: WizardStep; label: string }[] = [
  { key: 'metadata', label: 'Metadata' },
  { key: 'upload', label: 'Upload' },
  { key: 'processing', label: 'Processing' },
]

// ─── Job pipeline display ─────────────────────────────────────────────────────

const JOB_PIPELINE = [
  { type: 'parse', label: 'Parse File' },
  { type: 'detect_laps', label: 'Detect Laps' },
  { type: 'sector_analysis', label: 'Sector Analysis' },
  { type: 'ideal_lap', label: 'Ideal Lap' },
]

function JobStep({ job }: { job: AnalysisJob | undefined }) {
  const status = job?.status ?? 'pending'
  return (
    <div className="flex items-center gap-3">
      <div className="flex-shrink-0">
        {status === 'done' && (
          <div className="w-6 h-6 rounded-full bg-[#00e676]/20 border border-[#00e676]/50 flex items-center justify-center">
            <svg className="w-3 h-3 text-[#00e676]" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
          </div>
        )}
        {status === 'running' && (
          <div className="w-6 h-6 rounded-full bg-[#457b9d]/20 border border-[#457b9d]/50 flex items-center justify-center">
            <div className="w-3 h-3 rounded-full bg-[#457b9d] animate-pulse" />
          </div>
        )}
        {status === 'failed' && (
          <div className="w-6 h-6 rounded-full bg-[#ff5252]/20 border border-[#ff5252]/50 flex items-center justify-center">
            <svg className="w-3 h-3 text-[#ff5252]" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </div>
        )}
        {status === 'pending' && (
          <div className="w-6 h-6 rounded-full bg-[#1e1e2e] border border-[#2e2e4e] flex items-center justify-center">
            <div className="w-2 h-2 rounded-full bg-[#374151]" />
          </div>
        )}
      </div>
      <span className={`text-sm ${status === 'done' ? 'text-[#00e676]' : status === 'running' ? 'text-white' : status === 'failed' ? 'text-[#ff5252]' : 'text-[#6b7280]'}`}>
        {JOB_PIPELINE.find((j) => j.type === job?.job_type)?.label ?? 'Unknown'}
      </span>
      <span className="ml-auto">
        <Badge status={status} />
      </span>
    </div>
  )
}

// ─── Processing step ──────────────────────────────────────────────────────────

function ProcessingStep({ sessionId }: { sessionId: string }) {
  const navigate = useNavigate()
  const { data: jobs } = useJobPoller(sessionId)

  const allDone = jobs?.every((j) => j.status === 'done' || j.status === 'failed') ?? false
  const anyFailed = jobs?.some((j) => j.status === 'failed') ?? false

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <p className="text-sm text-[#9ca3af] mb-4">
          Analysis pipeline running. This usually takes 30–60 seconds.
        </p>
        {JOB_PIPELINE.map((step) => {
          const job = jobs?.find((j) => j.job_type === step.type)
          return (
            <div key={step.type} className="bg-[#0d0d14] border border-[#1e1e2e] rounded-lg px-4 py-3">
              <JobStep job={job ?? { id: '', session_id: sessionId, job_type: step.type, status: 'pending' }} />
            </div>
          )
        })}
      </div>

      {allDone && !anyFailed && (
        <div className="bg-[#00e676]/5 border border-[#00e676]/20 rounded-lg p-4 text-center">
          <p className="text-sm text-[#00e676] font-medium mb-3">Analysis complete!</p>
          <Button
            variant="primary"
            onClick={() => navigate({ to: '/sessions/$sessionId', params: { sessionId } })}
          >
            View Session
          </Button>
        </div>
      )}

      {anyFailed && (
        <div className="bg-[#ff5252]/5 border border-[#ff5252]/20 rounded-lg p-4">
          <p className="text-sm text-[#ff5252]">Some analysis jobs failed. You can still view the session.</p>
          <Button
            variant="secondary"
            size="sm"
            className="mt-3"
            onClick={() => navigate({ to: '/sessions/$sessionId', params: { sessionId } })}
          >
            View Session
          </Button>
        </div>
      )}
    </div>
  )
}

// ─── Main wizard ──────────────────────────────────────────────────────────────

export function NewSessionPage() {
  const navigate = useNavigate()
  const setUploadProgress = useStore((s) => s.setUploadProgress)
  const setUploadStatus = useStore((s) => s.setUploadStatus)

  const [step, setStep] = useState<WizardStep>('metadata')
  const [sessionId, setSessionId] = useState<string | null>(null)

  // Metadata
  const [name, setName] = useState('')
  const [date, setDate] = useState(new Date().toISOString().split('T')[0])
  const [circuitId, setCircuitId] = useState('')

  // Upload
  const [dragOver, setDragOver] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const [uploadProgress, setUploadProgressLocal] = useState<Record<string, number>>({})
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [metaLoading, setMetaLoading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data: circuits } = useQuery({
    queryKey: ['circuits'],
    queryFn: listCircuits,
  })

  // ── Step 1: Metadata ────────────────────────────────────────────────────────

  async function handleMetadataSubmit() {
    if (!circuitId) return
    setMetaLoading(true)
    try {
      const session = await createSession({
        name: name || `Session ${new Date().toLocaleDateString()}`,
        circuit_id: circuitId,
        session_date: date,
      })
      setSessionId(session.id)
      setStep('upload')
    } catch (err) {
      console.error(err)
    } finally {
      setMetaLoading(false)
    }
  }

  // ── Step 2: Upload ──────────────────────────────────────────────────────────

  function handleDragOver(e: DragEvent) {
    e.preventDefault()
    setDragOver(true)
  }

  function handleDragLeave() {
    setDragOver(false)
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault()
    setDragOver(false)
    const dropped = Array.from(e.dataTransfer.files).filter((f) =>
      /\.(vbo|csv|apexsession|ld|drk|xdrk)$/i.test(f.name)
    )
    setFiles((prev) => [...prev, ...dropped])
  }

  function handleFileInput(e: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files ?? []).filter((f) =>
      /\.(vbo|csv|apexsession|ld|drk|xdrk)$/i.test(f.name)
    )
    setFiles((prev) => [...prev, ...selected])
  }

  async function handleUpload() {
    if (!sessionId || files.length === 0) return
    setUploading(true)
    setUploadError(null)
    try {
      for (const file of files) {
        setUploadProgress(file.name, 0, file.name)
        await uploadFile(sessionId, file, (pct) => {
          setUploadProgressLocal((prev) => ({ ...prev, [file.name]: pct }))
          setUploadProgress(file.name, pct, file.name)
        })
        setUploadStatus(file.name, 'done')
        setUploadProgressLocal((prev) => ({ ...prev, [file.name]: 100 }))
      }
      setStep('processing')
    } catch (err) {
      setUploadError('Upload failed. Please check your file and try again.')
      console.error('Upload error:', err)
    } finally {
      setUploading(false)
    }
  }

  const stepIndex = STEPS.findIndex((s) => s.key === step)

  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      {/* Nav */}
      <header className="border-b border-[#1e1e2e] bg-[#12121a]">
        <div className="max-w-3xl mx-auto px-4 md:px-6 h-14 flex items-center justify-between">
          <button
            onClick={() => navigate({ to: '/' })}
            className="text-xl font-black tracking-[0.2em] text-white hover:text-[#e63946] transition-colors"
          >
            TR<span className="text-[#e63946]">A</span>CK
          </button>
          <span className="text-sm text-[#6b7280]">New Session</span>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 md:px-6 py-6 md:py-10">
        {/* Progress steps */}
        <div className="flex items-center gap-0 mb-10">
          {STEPS.map((s, i) => (
            <div key={s.key} className="flex items-center flex-1">
              <div className="flex flex-col items-center gap-1.5">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                    i < stepIndex
                      ? 'bg-[#00e676] text-black'
                      : i === stepIndex
                      ? 'bg-[#e63946] text-white'
                      : 'bg-[#1e1e2e] text-[#6b7280]'
                  }`}
                >
                  {i < stepIndex ? (
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  ) : (
                    i + 1
                  )}
                </div>
                <span className={`text-xs ${i === stepIndex ? 'text-white font-medium' : 'text-[#6b7280]'}`}>
                  {s.label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`flex-1 h-px mx-3 mt-[-10px] ${i < stepIndex ? 'bg-[#00e676]/40' : 'bg-[#1e1e2e]'}`} />
              )}
            </div>
          ))}
        </div>

        <Card variant="elevated">
          {/* ── Step 1: Metadata ── */}
          {step === 'metadata' && (
            <>
              <CardHeader>
                <h2 className="text-base font-semibold text-white">Session Details</h2>
              </CardHeader>
              <CardBody className="space-y-5">
                <div>
                  <label className="block text-xs font-medium text-[#9ca3af] mb-1.5 uppercase tracking-wide">
                    Session Name
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Summit Point – Morning Practice"
                    className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-md px-3 py-2.5 text-sm text-white placeholder-[#374151] focus:outline-none focus:border-[#457b9d] focus:ring-1 focus:ring-[#457b9d] transition-colors"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-[#9ca3af] mb-1.5 uppercase tracking-wide">
                    Date
                  </label>
                  <input
                    type="date"
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                    className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-md px-3 py-2.5 text-sm text-white focus:outline-none focus:border-[#457b9d] focus:ring-1 focus:ring-[#457b9d] transition-colors"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-[#9ca3af] mb-1.5 uppercase tracking-wide">
                    Circuit <span className="text-[#e63946]">*</span>
                  </label>
                  <select
                    value={circuitId}
                    onChange={(e) => setCircuitId(e.target.value)}
                    className={`w-full bg-[#0a0a0f] border rounded-md px-3 py-2.5 text-sm text-white focus:outline-none focus:border-[#457b9d] focus:ring-1 focus:ring-[#457b9d] transition-colors ${!circuitId ? 'border-[#2e2e4e]' : 'border-[#1e1e2e]'}`}
                  >
                    <option value="">Select a circuit…</option>
                    {circuits?.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} — {c.country}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-[#6b7280] mt-1">Required for lap detection and sector analysis.</p>
                </div>

<div className="flex justify-end pt-2">
                  <Button variant="primary" onClick={handleMetadataSubmit} loading={metaLoading} disabled={!circuitId}>
                    Continue to Upload
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </Button>
                </div>
              </CardBody>
            </>
          )}

          {/* ── Step 2: Upload ── */}
          {step === 'upload' && (
            <>
              <CardHeader>
                <h2 className="text-base font-semibold text-white">Upload Telemetry File</h2>
                <span className="text-xs text-[#6b7280]">.vbo .csv .apexSession .ld .drk .xdrk</span>
              </CardHeader>
              <CardBody className="space-y-5">
                {/* Dropzone */}
                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`relative border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all duration-200 ${
                    dragOver
                      ? 'border-[#e63946] bg-[#e63946]/5'
                      : 'border-[#1e1e2e] hover:border-[#2e2e4e] hover:bg-[#0d0d14]'
                  }`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".vbo,.csv,.apexSession,.ld,.drk,.xdrk"
                    multiple
                    onChange={handleFileInput}
                    className="hidden"
                  />
                  <svg
                    className={`w-10 h-10 mx-auto mb-3 ${dragOver ? 'text-[#e63946]' : 'text-[#374151]'}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <p className="text-sm font-medium text-white">Drop files here or click to browse</p>
                  <p className="text-xs text-[#6b7280] mt-1">Supports .vbo, .csv, .apexSession, .ld, .drk, .xdrk</p>
                </div>

                {/* File list */}
                {files.length > 0 && (
                  <div className="space-y-2">
                    {files.map((file) => {
                      const pct = uploadProgress[file.name] ?? 0
                      return (
                        <div key={file.name} className="bg-[#0d0d14] border border-[#1e1e2e] rounded-lg px-4 py-3">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-mono text-white truncate">{file.name}</span>
                            <span className="text-xs text-[#6b7280] ml-2 flex-shrink-0">
                              {(file.size / 1024 / 1024).toFixed(1)} MB
                            </span>
                          </div>
                          {pct > 0 && (
                            <div className="w-full bg-[#1e1e2e] rounded-full h-1.5">
                              <div
                                className="bg-[#e63946] h-1.5 rounded-full transition-all duration-300"
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}

                {uploadError && (
                  <div className="bg-[#ff5252]/10 border border-[#ff5252]/30 rounded-lg px-4 py-3">
                    <p className="text-xs text-[#ff5252]">{uploadError}</p>
                  </div>
                )}

                <div className="flex items-center justify-between pt-2">
                  <Button variant="ghost" onClick={() => setStep('metadata')}>
                    Back
                  </Button>
                  <Button
                    variant="primary"
                    onClick={handleUpload}
                    loading={uploading}
                    disabled={files.length === 0}
                  >
                    Upload & Analyze
                  </Button>
                </div>
              </CardBody>
            </>
          )}

          {/* ── Step 3: Processing ── */}
          {step === 'processing' && sessionId && (
            <>
              <CardHeader>
                <h2 className="text-base font-semibold text-white">Analysis Pipeline</h2>
              </CardHeader>
              <CardBody>
                <ProcessingStep sessionId={sessionId} />
              </CardBody>
            </>
          )}
        </Card>
      </main>
    </div>
  )
}
