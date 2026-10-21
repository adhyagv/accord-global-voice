import { Volume2, VolumeX } from 'lucide-react'
import { useVoice } from './voiceContext'

type VoiceControlsProps = { compact?: boolean }

export default function VoiceControls({ compact = false }: VoiceControlsProps) {
  const { enabled, setEnabled, supported, status } = useVoice()
  return <div className={`voice-controls${compact ? ' voice-controls-compact' : ''}`} data-voice-skip>
    <button
      className={compact ? 'secondary-button full-width-button voice-controls-button' : 'voice-reply-toggle'}
      type="button"
      onClick={() => setEnabled(!enabled)}
      aria-pressed={enabled}
      title={enabled ? 'Turn spoken replies off' : 'Turn spoken replies on'}
    >
      {enabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
      <span>{compact ? (enabled ? 'Turn spoken replies off' : 'Turn spoken replies on') : (enabled ? 'Voice on' : 'Voice off')}</span>
    </button>
    <span className="sr-only" role="status" aria-live="polite">{status || (supported ? 'Browser speech synthesis available.' : 'Speech synthesis unavailable; captions remain visible.')}</span>
  </div>
}
