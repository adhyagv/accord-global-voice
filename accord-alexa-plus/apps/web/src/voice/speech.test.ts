import { describe, expect, it } from 'vitest'
import { chunkText, cleanForSpeech } from './speech'

describe('cleanForSpeech', () => {
  it('removes markdown and normalizes money and durations', () => {
    expect(cleanForSpeech('**Pay ₹1,250.50** in 30 min. [Open plan](https://example.com)'))
      .toBe('Pay 1,250 rupees and 50 paise in 30 minutes. Open plan')
  })

  it('returns empty speech for empty input and removes code blocks', () => {
    expect(cleanForSpeech('')).toBe('')
    expect(cleanForSpeech('Use this:\n```tsx\nprivate answer\n```Done.')).toBe('Use this: code omitted Done.')
  })
})

describe('chunkText', () => {
  it('keeps short text as a single chunk', () => {
    expect(chunkText('Hello there.')).toEqual(['Hello there.'])
  })

  it('splits long text into bounded chunks and preserves every word', () => {
    const input = 'First sentence has several words. Second sentence has several more words. Third sentence finishes the message.'
    const chunks = chunkText(input, 45)
    expect(chunks.length).toBeGreaterThan(1)
    expect(chunks.every((chunk) => chunk.length <= 45)).toBe(true)
    expect(chunks.join(' ')).toBe(input)
  })
})
