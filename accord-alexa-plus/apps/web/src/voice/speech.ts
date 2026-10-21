/** Browser-only speech formatting helpers. No network calls are made here. */
export type SpeechWindow = Window & {
  SpeechRecognition?: new () => SpeechRecognitionLike
  webkitSpeechRecognition?: new () => SpeechRecognitionLike
}

type SpeechRecognitionLike = {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((event: unknown) => void) | null
  onerror: ((event: unknown) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
}

export function speechSupported(): boolean {
  return typeof window !== 'undefined'
    && 'speechSynthesis' in window
    && typeof window.SpeechSynthesisUtterance !== 'undefined'
}

function currencyPhrase(rawAmount: string): string {
  const amount = Number(rawAmount.replace(/,/g, ''))
  if (!Number.isFinite(amount) || amount < 0) return rawAmount
  const minor = Math.round(amount * 100)
  const rupees = Math.floor(minor / 100)
  const paise = minor % 100
  const rupeeText = `${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(rupees)} rupees`
  return paise ? `${rupeeText} and ${paise} paise` : rupeeText
}

/** Normalize UI copy for speech while preserving the visible captions unchanged. */
export function cleanForSpeech(input: string): string {
  if (!input) return ''
  const text = input
    .replace(/<[^>]*>/g, ' ')
    .replace(/!?\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/https?:\/\/\S+/gi, ' link omitted ')
    .replace(/(?:₹|\bINR\s*)([\d,]+(?:\.\d{1,2})?)/gi, (_match, amount: string) => currencyPhrase(amount))
    .replace(/\b(\d+(?:\.\d+)?)\s*(?:mins?|minutes?)\b/gi, (_match, amount: string) => `${amount} ${Number(amount) === 1 ? 'minute' : 'minutes'}`)
    .replace(/```[\s\S]*?```/g, ' code omitted ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/[*_~#>|]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  if (!text) return ''
  return text.slice(0, 4000)
}

/** Split long speech into natural sentence-sized chunks for browser speech synthesis. */
export function chunkText(input: string, maxLength = 220): string[] {
  const text = input.trim().replace(/\s+/g, ' ')
  if (!text) return []
  const limit = Math.max(40, Math.floor(maxLength))
  if (text.length <= limit) return [text]

  const sentences = text.match(/[^.!?]+[.!?]+|[^.!?]+$/g)?.map((part) => part.trim()).filter(Boolean) ?? [text]
  const chunks: string[] = []
  let current = ''
  const push = () => {
    if (current.trim()) chunks.push(current.trim())
    current = ''
  }

  for (const sentence of sentences) {
    if (sentence.length > limit) {
      push()
      const words = sentence.split(/\s+/)
      for (const word of words) {
        if (!current) current = word
        else if (`${current} ${word}`.length <= limit) current += ` ${word}`
        else { push(); current = word }
      }
      push()
      continue
    }
    if (!current) current = sentence
    else if (`${current} ${sentence}`.length <= limit) current += ` ${sentence}`
    else { push(); current = sentence }
  }
  push()
  return chunks
}
