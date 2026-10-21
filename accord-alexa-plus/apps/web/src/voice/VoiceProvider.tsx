import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { cleanForSpeech, chunkText, speechSupported } from './speech'
import { VoiceContext, type SpeakOptions, type VoiceContextValue } from './voiceContext'

const STORAGE_KEY = 'accord-voice-enabled'

function initialEnabled(): boolean {
  if (typeof window === 'undefined') return true
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return stored == null ? true : stored === 'true'
  } catch {
    return true
  }
}

export default function VoiceProvider({ children }: { children: ReactNode }) {
  const [enabled, setEnabledState] = useState(initialEnabled)
  const [status, setStatus] = useState('')
  const runId = useRef(0)
  const speakRef = useRef<VoiceContextValue['speak']>(() => 'empty')
  const enabledRef = useRef(enabled)
  useEffect(() => { enabledRef.current = enabled }, [enabled])

  const stop = useCallback(() => {
    runId.current += 1
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel()
    setStatus('Speech stopped.')
  }, [])

  const setEnabled = useCallback((next: boolean) => {
    setEnabledState(next)
    try { window.localStorage.setItem(STORAGE_KEY, String(next)) } catch { /* browser storage is optional */ }
    if (!next) {
      runId.current += 1
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel()
      setStatus('Spoken replies are off. Captions remain available.')
    } else {
      setStatus(speechSupported() ? 'Spoken replies are on.' : 'Spoken replies are on, but this browser does not support speech synthesis.')
    }
  }, [])

  const speak = useCallback((rawText: string, options: SpeakOptions = {}) => {
    if (!options.force && !enabledRef.current) return 'disabled' as const
    if (!speechSupported()) {
      setStatus('Speech is not supported in this browser. Read the captions instead.')
      return 'unsupported' as const
    }
    const text = cleanForSpeech(rawText)
    const chunks = chunkText(text)
    if (!chunks.length) return 'empty' as const
    if (options.interrupt !== false) window.speechSynthesis.cancel()
    const run = ++runId.current
    chunks.forEach((chunk, index) => {
      const utterance = new SpeechSynthesisUtterance(chunk)
      utterance.lang = 'en-IN'
      utterance.rate = 0.98
      utterance.onstart = () => { if (run === runId.current) setStatus('Reading captions aloud in your browser.') }
      utterance.onend = () => {
        if (run === runId.current && index === chunks.length - 1) setStatus('Finished reading.')
      }
      utterance.onerror = () => {
        if (run === runId.current) setStatus('Speech failed in this browser. Captions remain available.')
      }
      window.speechSynthesis.speak(utterance)
    })
    return 'queued' as const
  }, [])
  useEffect(() => { speakRef.current = speak }, [speak])

  useEffect(() => {
    try { window.localStorage.setItem(STORAGE_KEY, String(enabled)) } catch { /* browser storage is optional */ }
  }, [enabled])

  // data-speak is an explicit, curated speech string; never infer speech from arbitrary page text.
  // Queue result announcements rather than interrupting siblings discovered in the same React commit.
  useEffect(() => {
    if (typeof document === 'undefined' || !document.body) return
    const seen = new WeakMap<Element, string>()
    const maybeSpeak = (element: Element) => {
      if (element.closest('[data-voice-skip], [aria-hidden="true"], nav, .accord-sidebar, .sidebar')) return
      const text = element.getAttribute('data-speak')?.trim() ?? ''
      if (!text || seen.get(element) === text) return
      seen.set(element, text)
      speakRef.current(text, { interrupt: false })
    }
    const scan = (node: Node) => {
      if (!(node instanceof Element)) return
      if (node.matches('[data-speak]')) maybeSpeak(node)
      node.querySelectorAll('[data-speak]').forEach(maybeSpeak)
    }
    const observer = new MutationObserver((records) => {
      for (const record of records) {
        if (record.type === 'attributes' && record.target instanceof Element) maybeSpeak(record.target)
        for (const node of Array.from(record.addedNodes)) scan(node)
      }
    })
    observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['data-speak'] })
    return () => observer.disconnect()
  }, [])

  const value = useMemo<VoiceContextValue>(() => ({ enabled, setEnabled, speak, stop, supported: speechSupported(), status }), [enabled, setEnabled, speak, stop, status])
  return <VoiceContext.Provider value={value}>{children}</VoiceContext.Provider>
}
