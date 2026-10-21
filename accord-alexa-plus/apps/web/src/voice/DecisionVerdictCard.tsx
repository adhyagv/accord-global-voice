import { useState } from 'react'
import { Headphones, Volume2, AlertTriangle, CheckCircle2, Info } from 'lucide-react'
import { useVoice } from './voiceContext'
import { fairnessDisclaimer } from './verdict'
import type { VerdictTone } from './verdict'

type DecisionVerdictCardProps = {
  title: string
  captions: string[]
  tone?: VerdictTone
  needsConfirmation?: boolean
  badge?: string
  includeFairnessDisclaimer?: boolean
}

export default function DecisionVerdictCard({
  title,
  captions,
  tone = 'info',
  needsConfirmation = false,
  badge,
  includeFairnessDisclaimer = false,
}: DecisionVerdictCardProps) {
  const { speak, supported } = useVoice()
  const [speechMessage, setSpeechMessage] = useState('')
  const cleanCaptions = captions.map((line) => line.trim()).filter(Boolean)
  const speechText = [
    title,
    ...cleanCaptions,
    needsConfirmation ? 'This is a draft and needs household confirmation. Nothing has been applied.' : '',
    includeFairnessDisclaimer ? fairnessDisclaimer() : '',
  ].filter(Boolean).join('. ')

  function hearVerdict() {
    const result = speak(speechText, { interrupt: true, force: true })
    if (result === 'unsupported') setSpeechMessage('Speech is not supported in this browser. Read the captions below; no audio service is contacted.')
    else if (result === 'empty') setSpeechMessage('There is no verdict text to read yet.')
    else if (result === 'queued') setSpeechMessage('Playing this verdict in your browser.')
    else setSpeechMessage('Speech could not be started. Captions remain available below.')
  }

  const ToneIcon = tone === 'success' ? CheckCircle2 : tone === 'warning' ? AlertTriangle : Info
  return <section className={`decision-verdict-card verdict-${tone}`} aria-label={`${title} verdict`}>
    <div className="verdict-topline">
      <span className="verdict-icon"><ToneIcon size={17} /></span>
      <div className="verdict-heading"><strong>{title}</strong>{badge && <span className="verdict-badge">{badge}</span>}</div>
      <button className="secondary-button verdict-hear-button" type="button" onClick={hearVerdict}><Headphones size={14} /> Hear it</button>
    </div>
    <div className="verdict-captions" aria-live="polite">
      {cleanCaptions.map((caption, index) => <p key={`${index}-${caption}`}>{caption}</p>)}
      {includeFairnessDisclaimer && <p className="verdict-disclaimer">{fairnessDisclaimer()}</p>}
    </div>
    {needsConfirmation && <p className="verdict-confirmation"><AlertTriangle size={14} /> Draft — needs household confirmation. Nothing has been applied.</p>}
    {!supported && <p className="verdict-speech-status" role="status"><Volume2 size={13} /> Speech is unsupported. Captions remain available.</p>}
    {speechMessage && <p className="verdict-speech-status" role="status"><Volume2 size={13} /> {speechMessage}</p>}
  </section>
}
