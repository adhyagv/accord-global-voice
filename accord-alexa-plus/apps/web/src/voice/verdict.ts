/** Browser-only voice helpers for final household decisions. */
export type VerdictTone = 'info' | 'success' | 'warning'

export function speakRupees(amount: number): string {
  const cents = Math.max(0, Math.round(Number.isFinite(amount) ? amount * 100 : 0))
  const rupees = Math.floor(cents / 100)
  const paise = cents % 100
  const rupeeLabel = `${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(rupees)} rupees`
  return paise ? `${rupeeLabel} and ${paise} paise` : rupeeLabel
}

export function fairnessDisclaimer(): string {
  return 'This is a heuristic, not a guarantee of fairness. Review it together before deciding.'
}

export function verdictRequiresConfirmation(status: string): boolean {
  return ['draft', 'proposed', 'changes_requested', 'counteroffer'].includes(status.toLowerCase())
}
