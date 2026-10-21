import { createContext, useContext, useEffect, useRef } from 'react'

export type SpeakOptions = {
  /** Stop any currently speaking result before reading this one. */
  interrupt?: boolean
  /** Explicit user action may speak even when automatic voice is disabled. */
  force?: boolean
}

export type SpeakResult = 'queued' | 'disabled' | 'unsupported' | 'empty'

export type VoiceContextValue = {
  enabled: boolean
  setEnabled: (enabled: boolean) => void
  speak: (text: string, options?: SpeakOptions) => SpeakResult
  stop: () => void
  supported: boolean
  status: string
}

export const VoiceContext = createContext<VoiceContextValue | null>(null)

export function useVoice(): VoiceContextValue {
  const context = useContext(VoiceContext)
  if (!context) throw new Error('useVoice must be used inside VoiceProvider')
  return context
}

/** Speak when an explicitly curated result string changes; raw/private inputs should never be passed here. */
export function useSpeakOnChange(text: string | null | undefined): void {
  const { enabled, speak } = useVoice()
  const previous = useRef<string | null | undefined>(undefined)
  useEffect(() => {
    if (!text || !enabled || previous.current === text) return
    previous.current = text
    speak(text, { interrupt: true })
  }, [enabled, speak, text])
}
