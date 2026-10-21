import { useCallback, useEffect, useMemo, useRef, useState, useId, type FormEvent, type ReactNode } from 'react'
import { motion } from 'framer-motion'
import {
  Activity, ArrowUpRight, Check, ChevronRight,
  Home, LockKeyhole, MessageCircle, Plus, RefreshCw, Scale, ShieldCheck,
  Sparkles, Users, Waves, HeartHandshake, ListChecks, RotateCcw, Play,
  Mic, MicOff, Send, CalendarDays, Wallet, Settings,
  History, Utensils, Heart, House, Clock3, MessageSquareText, Search, X, Command,
} from 'lucide-react'
import './App.css'
import { apiGet, apiPatch, apiPost } from './api'
import DecisionVerdictCard from './voice/DecisionVerdictCard'
import VoiceControls from './voice/VoiceControls'
import { useVoice } from './voice/voiceContext'
import { speakRupees } from './voice/verdict'

const HOUSEHOLD_ID = 'household-1'
const HOUSEHOLD_TYPES = ['Family', 'Couple', 'Roommates', 'Shared home', 'Other'] as const
type HouseholdType = (typeof HOUSEHOLD_TYPES)[number]
type Tab = 'Home' | 'My Household' | 'Plans' | 'Chores' | 'Bills' | 'Calendar' | 'Chat History' | 'Settings' | 'Interviews' | 'Mediation' | 'Agreements' | 'Monitoring' | 'Tasks & expenses' | 'Roommates' | 'Overview' | 'Privacy'
type ChatAction = { kind: 'reassign'; assignmentId: string; targetMemberId: string; targetName: string; taskName: string; status: 'pending' | 'approved' | 'rejected' }
type ChatMessage = { id: string; role: 'user' | 'assistant'; text: string; actionLabel?: string; actionTab?: Tab; pendingAction?: ChatAction }
type SpeechResultLike = { 0?: { transcript?: string } }
type SpeechResultEventLike = { resultIndex: number; results: ArrayLike<SpeechResultLike> }
type SpeechRecognitionLike = {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((event: SpeechResultEventLike) => void) | null
  onerror: ((event: { error?: string }) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
}
type SpeechWindow = Window & {
  SpeechRecognition?: new () => SpeechRecognitionLike
  webkitSpeechRecognition?: new () => SpeechRecognitionLike
}
type BackendMember = { memberId: string; displayName: string; role: string; consentStatus: string; privacyStatus: string }
type Roommate = BackendMember & { initials: string; color: string }
type Agreement = { agreementId: string; householdId: string; version: number; status: string; proposal: Assignment[]; fairnessScore: number; rationale: string; approvals: string[]; vetoes: string[]; counteroffers: { memberId: string; message: string }[] }
type Assignment = { assignmentId: string; memberId: string; task: string; frequency: string; estimatedEffort: number; assignedDate: string; completedAt?: string | null; status: string }
type Expense = { expenseId: string; payerMemberId: string; description: string; amount: number; category: string; expenseDate: string }
type Interview = { sessionId: string; householdId: string; memberId: string; status: string; extractedConstraintReferences: string[] }
type Constraint = { constraintId: string; memberId: string; category: string; preferenceOrRequirement: string; privacyClassification: string }
type DriftReport = { driftId: string; severity: string; explanation: string; recommendedAction: string; affectedMembers: string[] }
type ApiList<T> = { members?: T[]; agreements?: T[]; assignments?: T[]; expenses?: T[]; constraints?: T[]; signals?: unknown[] }
type PaletteItem = { label: string; description: string; keywords: string; tab: Tab; icon: typeof Activity; memberId?: string; agreementId?: string; agreementVersion?: number }
type AssistantStatus = { configured: boolean; mode: 'configured' | 'guided'; message: string }
type AssistantChatResponse = { reply: string; mode: 'llm' | 'guided' | 'guided_fallback'; suggestedAction: string }
type MediationOption = { id: string; title: string; proposal: string; tradeOff: string; requiresHouseholdConfirmation: boolean }
type MediationResult = { sharedNeed: string; restatements: { memberId: string; label?: string; needsRestatement: string; privateDetailsOmitted?: boolean }[]; options: MediationOption[]; cautions: string[]; mode: string; requiresConfirmationBeforeAction: boolean; stored: boolean; privacyNote: string }
type FairnessMemberWorkload = { memberId: string; displayName: string; projectedMinutes: number; assignedTasks: string[]; explanation: string }
type FairnessScenario = { algorithm: string; fairnessScore: number; workloadSpreadMinutes: number; workloads: FairnessMemberWorkload[]; assignments: { task: string; memberId: string; estimatedEffort: number }[] }
type FairnessComparison = { householdId: string; preferenceWeight: number; taskCount: number; note: string; solver: FairnessScenario; roundRobin: FairnessScenario; explanationMode?: string }
type Settlement = { totalExpenses: number; memberCount: number; balances: { memberId: string; displayName: string; paid: number; fairShare: number; netBalance: number; direction: 'receive' | 'pay' | 'settled' }[]; transfers: { fromMemberId: string; toMemberId: string; amount: number }[]; note: string }
type WeeklyDigest = { generatedAt: string; windowDays: number; summary: { members: number; tasksInWindow: number; completedInWindow: number; openTasks: number; missedTasks: number; expensesInWindow: number; expensesTotal: number; pendingAgreements: number; openDriftReports: number }; insights: string[]; dataNote: string }
type DraftClauses = { mode: string; status: string; requiresMemberReview: boolean; activatesAgreement: boolean; clauses: { id: string; text: string; sourcePreference: string; sourceMemberId: string; conflictsWith: string[]; reviewNote: string }[]; conflicts: { clauseA?: string; clauseB?: string; reason?: string }[]; sourcePolicy: string }
type MediationSession = { sessionId: string; householdId: string; topic: string; status: 'open' | 'closed'; restatements: { memberId: string; label: string; needsRestatement: string }[]; options: MediationOption[]; votes: Record<string, string>; voteCounts: Record<string, number>; winningOptionId: string | null; tie: boolean; tieBreakRule: string; draftAgreementId: string | null; storedRawPrivateStatements: false }
type FairnessSimulation = { weeks: { week: number; accord: { workloadSpreadMinutes: number; workloads: { memberId: string; minutes: number }[] }; roundRobin: { workloadSpreadMinutes: number; workloads: { memberId: string; minutes: number }[] } }[]; weeksSimulated: number; seed: number; synthetic: boolean; accordCumulativeWorkloads: { memberId: string; displayName: string; minutes: number }[]; roundRobinCumulativeWorkloads: { memberId: string; displayName: string; minutes: number }[]; accordCumulativeGapMinutes: number; roundRobinCumulativeGapMinutes: number; headline: string; note: string }
type PrivacyDashboard = { llmMode: string; providerConfigured: boolean; provider: string; model: string; canSee: string[]; cannotSee: string[]; identityNote: string; limitations: string[] }
type MealPlanDraft = { schedule: { date: string; day: string; mealIdea: string; cookMemberId: string; cookDisplayName: string }[]; status: string; saved: boolean; requiresHouseholdConfirmation: boolean; shareableDataOnly: boolean; constraintsUsed: number; note: string }
type WorkloadDrift = { threshold: number; alert: { memberId: string; displayName: string; share: number; completedMinutes: number; threshold: number; message: string; suggestion: string } | null; memberShares: { memberId: string; displayName: string; completedMinutes: number; share: number }[]; totalCompletedMinutes: number; windowDays: number; mode: string; note: string }

function toRoommate(member: BackendMember, index: number): Roommate {
  const colors = ['rose', 'blue', 'green', 'violet', 'amber']
  return { ...member, initials: member.displayName.trim().split(/\s+/).map((part) => part[0] ?? '').join('').toUpperCase().slice(0, 2) || '?', color: colors[index % colors.length] }
}
function money(amount: number) { return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(amount) }
function agreementKey(agreement: Pick<Agreement, 'agreementId' | 'version'>): string { return `${agreement.agreementId}::${agreement.version}` }
function Panel({ title, description, children, action }: { title: string; description?: string; children: ReactNode; action?: ReactNode }) {
  return <section className="content-card workflow-panel"><div className="card-heading"><div><h3>{title}</h3>{description && <p>{description}</p>}</div>{action}</div><div className="workflow-body">{children}</div></section>
}
function Notice({ children, error = false }: { children: ReactNode; error?: boolean }) {
  return <p role={error ? 'alert' : 'status'} className={`notice ${error ? 'notice-error' : ''}`}>{children}</p>
}

function App() {
  const { stop: stopSpeech } = useVoice()
  const idPrefix = useId().replace(/[^a-zA-Z0-9]/g, '')
  const messageSequenceRef = useRef(0)
  function nextChatMessageId(prefix = 'message') {
    messageSequenceRef.current += 1
    return `${idPrefix}-${prefix}-${messageSequenceRef.current}`
  }
  const [activeTab, setActiveTab] = useState<Tab>('Home')
  const [apiStatus, setApiStatus] = useState('API not tested')
  const [apiLoading, setApiLoading] = useState(false)
  const [roommates, setRoommates] = useState<Roommate[]>([])
  const [membersLoading, setMembersLoading] = useState(true)
  const [membersError, setMembersError] = useState('')
  const [selectedMemberId, setSelectedMemberId] = useState('')
  const [showAddForm, setShowAddForm] = useState(false)
  const [newName, setNewName] = useState('')
  const [newRole, setNewRole] = useState('Parent')
  const [addLoading, setAddLoading] = useState(false)
  const [formMessage, setFormMessage] = useState('')
  const [formError, setFormError] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [constraints, setConstraints] = useState<Constraint[]>([])
  const [agreements, setAgreements] = useState<Agreement[]>([])
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [expenses, setExpenses] = useState<Expense[]>([])
  const [drift, setDrift] = useState<DriftReport | null>(null)
  const [mediationStatements, setMediationStatements] = useState<Record<string, string>>({})
  const [sharingConsents, setSharingConsents] = useState<Record<string, boolean>>({})
  const [mediationResult, setMediationResult] = useState<MediationResult | null>(null)
  const [mediationSession, setMediationSession] = useState<MediationSession | null>(null)
  const [mediationLoading, setMediationLoading] = useState(false)
  const [mediationVoteLoading, setMediationVoteLoading] = useState(false)
  const [chosenMediationOption, setChosenMediationOption] = useState<MediationOption | null>(null)
  const [fairnessWeight, setFairnessWeight] = useState(55)
  const [fairnessComparison, setFairnessComparison] = useState<FairnessComparison | null>(null)
  const [fairnessLoading, setFairnessLoading] = useState(false)
  const [fairnessSimulation, setFairnessSimulation] = useState<FairnessSimulation | null>(null)
  const [fairnessSimulationLoading, setFairnessSimulationLoading] = useState(false)
  const [draftedClauses, setDraftedClauses] = useState<DraftClauses | null>(null)
  const [clausesLoading, setClausesLoading] = useState(false)
  const [settlement, setSettlement] = useState<Settlement | null>(null)
  const [settlementLoading, setSettlementLoading] = useState(false)
  const [expenseSplitMode, setExpenseSplitMode] = useState<'all-equal' | 'subset-equal' | 'custom'>('all-equal')
  const [expenseSplitMemberIds, setExpenseSplitMemberIds] = useState<string[]>([])
  const [expenseSplitRatios, setExpenseSplitRatios] = useState<Record<string, number>>({})
  const [weeklyDigest, setWeeklyDigest] = useState<WeeklyDigest | null>(null)
  const [digestLoading, setDigestLoading] = useState(false)
  const [workloadDrift, setWorkloadDrift] = useState<WorkloadDrift | null>(null)
  const [workloadDriftLoading, setWorkloadDriftLoading] = useState(false)
  const [privacyDashboard, setPrivacyDashboard] = useState<PrivacyDashboard | null>(null)
  const [privacyLoading, setPrivacyLoading] = useState(false)
  const [mealPlanDraft, setMealPlanDraft] = useState<MealPlanDraft | null>(null)
  const [mealPlanLoading, setMealPlanLoading] = useState(false)
  const [newExpenseDescription, setNewExpenseDescription] = useState('Groceries')
  const [newExpenseAmount, setNewExpenseAmount] = useState('')
  const [newExpenseCategory, setNewExpenseCategory] = useState('shared')
  const [newTask, setNewTask] = useState('Clean kitchen')
  const [newTaskEffort, setNewTaskEffort] = useState('30')
  const [interviewAnswers, setInterviewAnswers] = useState({ availability: '', chores: '', expenses: '', preferences: '' })
  const [counterText, setCounterText] = useState('Please balance weekday tasks more evenly.')
  const [selectedSessionId, setSelectedSessionId] = useState('')
  const [selectedAgreementKey, setSelectedAgreementKey] = useState('')
  const [householdType, setHouseholdType] = useState<HouseholdType>(() => {
    try {
      const saved = window.localStorage.getItem('accord-household-type')
      return HOUSEHOLD_TYPES.includes(saved as HouseholdType) ? saved as HouseholdType : 'Family'
    } catch {
      return 'Family'
    }
  })
  const [chatInput, setChatInput] = useState('')
  const [assistantMode, setAssistantMode] = useState<'llm' | 'guided' | 'guided_fallback' | 'local'>('guided')
  const [assistantConfigured, setAssistantConfigured] = useState(false)
  const [assistantThinking, setAssistantThinking] = useState(false)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      text: "Hi! I'm Accord. I can help your household plan the week, organize chores, keep track of bills, and check in privately when someone needs support. What would you like to do today?",
    },
  ])
  const [isListening, setIsListening] = useState(false)
  const [voiceStatus, setVoiceStatus] = useState('')
  const [commandOpen, setCommandOpen] = useState(false)
  const [commandQuery, setCommandQuery] = useState('')
  const [commandIndex, setCommandIndex] = useState(0)
  const commandInputRef = useRef<HTMLInputElement | null>(null)
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const chatEndRef = useRef<HTMLDivElement | null>(null)

  const selectedMember = useMemo(() => roommates.find((person) => person.memberId === selectedMemberId) ?? roommates[0], [roommates, selectedMemberId])
  const selectedAgreement = useMemo(() => agreements.find((agreement) => agreementKey(agreement) === selectedAgreementKey) ?? agreements[agreements.length - 1], [agreements, selectedAgreementKey])
  const withNames = useCallback((text: string) => text.replace(/\bmember-\d+\b/g, (id) => roommates.find((person) => person.memberId === id)?.displayName ?? id), [roommates])
  const memberName = useCallback((id: string) => roommates.find((person) => person.memberId === id)?.displayName ?? id, [roommates])

  const loadMembers = useCallback(async () => {
    try {
      const result = await apiGet<ApiList<BackendMember>>(`/api/households/${encodeURIComponent(HOUSEHOLD_ID)}/members`)
      const next = (result.members ?? []).map(toRoommate)
      setMembersError('')
      setRoommates(next)
      setSelectedMemberId((current) => next.some((m) => m.memberId === current) ? current : (next[0]?.memberId ?? ''))
    } catch (e) { setMembersError(e instanceof Error ? e.message : 'Could not load household members.') }
    finally { setMembersLoading(false) }
  }, [])

  const loadWorkflow = useCallback(async () => {
    if (!selectedMemberId) return
    const options = { memberId: selectedMemberId }
    try {
      const [agreementResult, assignmentResult, expenseResult] = await Promise.all([
        apiGet<ApiList<Agreement>>(`/api/agreements/households/${HOUSEHOLD_ID}`, options),
        apiGet<ApiList<Assignment>>(`/api/assignments/households/${HOUSEHOLD_ID}`, options),
        apiGet<ApiList<Expense>>(`/api/expenses/households/${HOUSEHOLD_ID}`, options),
      ])
      setAgreements(agreementResult.agreements ?? [])
      setAssignments(assignmentResult.assignments ?? [])
      setExpenses(expenseResult.expenses ?? [])
      setSelectedAgreementKey((current) => { const items = agreementResult.agreements ?? []; return items.some((item) => agreementKey(item) === current) ? current : (items.length ? agreementKey(items[items.length - 1]) : '') })
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load household workflow data.') }
  }, [selectedMemberId])

  // Initial data loads: state is only set after the awaited API responses resolve.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void loadMembers() }, [loadMembers])
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { if (selectedMemberId) void loadWorkflow() }, [selectedMemberId, loadWorkflow])
  useEffect(() => {
    if (!selectedMemberId || mediationSession) return
    let savedSessionId = ''
    try { savedSessionId = window.localStorage.getItem('accord-active-mediation-session') ?? '' } catch { /* local restore optional */ }
    if (!savedSessionId) return
    let cancelled = false
    apiGet<{ session: MediationSession }>(`/api/mediation/sessions/${encodeURIComponent(savedSessionId)}`, { memberId: selectedMemberId })
      .then((result) => { if (!cancelled) { setMediationSession(result.session); if (result.session.status === 'closed' && result.session.winningOptionId) setChosenMediationOption(result.session.options.find((option) => option.id === result.session.winningOptionId) ?? null) } })
      .catch(() => { try { window.localStorage.removeItem('accord-active-mediation-session') } catch { /* optional */ } })
    return () => { cancelled = true }
  }, [selectedMemberId, mediationSession])
  useEffect(() => { if (activeTab === 'Privacy') void loadPrivacyDashboard() }, [activeTab])
  useEffect(() => {
    let cancelled = false
    apiGet<AssistantStatus>('/api/assistant/status')
      .then((status) => { if (!cancelled) setAssistantConfigured(status.configured) })
      .catch(() => { if (!cancelled) setAssistantMode('local') })
    return () => { cancelled = true }
  }, [])

  async function testBackend() {
    setApiLoading(true); setApiStatus('Connecting…')
    try { const result = await apiGet<{ status: string; mode: string }>('/healthz'); setApiStatus(`Connected · ${result.status} · ${result.mode}`) }
    catch (e) { setApiStatus(e instanceof Error ? e.message : 'Backend connection failed.') }
    finally { setApiLoading(false) }
  }
  async function resetDemo() {
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await apiPost<{ household: { name: string }; members: BackendMember[]; mode: string }>('/api/demo/roommates/reset', {})
      setMessage(`Demo household reset: ${result.household.name}. All data is simulated.`)
      setMediationResult(null); setMediationSession(null); setChosenMediationOption(null); setFairnessComparison(null); setFairnessSimulation(null); setSettlement(null); setWeeklyDigest(null); setWorkloadDrift(null)
      try { window.localStorage.removeItem('accord-active-mediation-session') } catch { /* optional */ }
      setMembersLoading(true)
      await loadMembers()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not reset demo data.') }
    finally { setBusy(false) }
  }
  async function addRoommate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const displayName = newName.trim()
    if (!displayName) { setFormError('Enter a name first.'); return }
    setAddLoading(true); setFormError(''); setFormMessage('')
    try {
      await apiPost(`/api/households/${encodeURIComponent(HOUSEHOLD_ID)}/members`, { displayName, role: newRole.trim() || 'roommate' })
      setNewName(''); setNewRole('roommate'); setFormMessage(`${displayName} added. Consent remains pending until they grant it.`); await loadMembers()
    } catch (e) { setFormError(e instanceof Error ? e.message : 'Could not add member.') }
    finally { setAddLoading(false) }
  }
  async function setConsent(person: Roommate, consentStatus: 'granted' | 'revoked') {
    setBusy(true); setError(''); setMessage('')
    try {
      await apiPatch(`/api/households/${HOUSEHOLD_ID}/members/${person.memberId}/consent`, { consentStatus }, { memberId: person.memberId })
      setMessage(`${person.displayName}'s consent is now ${consentStatus}.`); await loadMembers()
    } catch (e) { setError(e instanceof Error ? e.message : 'Consent update failed.') }
    finally { setBusy(false) }
  }
  async function startInterview(person: Roommate) {
    setSelectedMemberId(person.memberId)
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await apiPost<{ session: Interview }>('/api/interviews', { householdId: HOUSEHOLD_ID, memberId: person.memberId })
      setSelectedSessionId(result.session.sessionId); setInterviewAnswers({ availability: '', chores: '', expenses: '', preferences: '' })
      setMessage(`Private interview started for ${person.displayName}. Answers remain member-scoped.`); setActiveTab('Interviews')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not start interview.') }
    finally { setBusy(false) }
  }
  async function submitInterview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selectedMember || !selectedSessionId) return
    setBusy(true); setError(''); setMessage('')
    try {
      await apiPost(`/api/interviews/${selectedSessionId}/submit`, {
        transcriptReference: `local-demo://${HOUSEHOLD_ID}/${selectedMember.memberId}/${selectedSessionId}`,
        answers: interviewAnswers,
      }, { memberId: selectedMember.memberId })
      await apiPost(`/api/interviews/${selectedSessionId}/complete`, {}, { memberId: selectedMember.memberId })
      const result = await apiPost<{ constraints: Constraint[] }>(`/api/constraints/derive/${selectedSessionId}`, {}, { memberId: selectedMember.memberId })
      setConstraints(result.constraints ?? []); setMessage('Interview completed. Only derived summaries are eligible for sharing; raw answers stay private.')
    } catch (e) { setError(e instanceof Error ? e.message : 'Interview could not be completed.') }
    finally { setBusy(false) }
  }
  async function loadSharedConstraints() {
    if (!selectedMember) return
    setBusy(true); setError(''); setMessage('')
    try { const result = await apiGet<ApiList<Constraint>>(`/api/constraints/households/${HOUSEHOLD_ID}/shared`, { memberId: selectedMember.memberId }); setConstraints(result.constraints ?? []); setMessage(`Loaded ${(result.constraints ?? []).length} shareable derived constraints.`) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not load constraints.') }
    finally { setBusy(false) }
  }
  async function generateAgreement() {
    if (!selectedMember) return
    setBusy(true); setError(''); setMessage('')
    try {
      const shared = await apiGet<ApiList<Constraint>>(`/api/constraints/households/${HOUSEHOLD_ID}/shared`, { memberId: selectedMember.memberId })
      const ids = (shared.constraints ?? []).filter((c) => c.privacyClassification === 'shareable_derived').map((c) => c.constraintId)
      if (!ids.length) throw new Error('No shareable constraints yet. Complete a consented interview first, or reset the demo scenario.')
      const result = await apiPost<{ agreement: Agreement }>('/api/agreements/generate', { householdId: HOUSEHOLD_ID, derivedConstraintIds: ids }, { memberId: selectedMember.memberId })
      setAgreements((current) => [result.agreement, ...current.filter((a) => a.agreementId !== result.agreement.agreementId || a.version !== result.agreement.version)])
      setSelectedAgreementKey(agreementKey(result.agreement)); setMessage(`Proposal v${result.agreement.version} generated by the backend.`)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not generate proposal.') }
    finally { setBusy(false) }
  }
  async function agreementAction(action: 'approve' | 'veto' | 'activate' | 'counter') {
    if (!selectedMember || !selectedAgreement) return
    setBusy(true); setError(''); setMessage('')
    try {
      const path = `/api/agreements/${selectedAgreement.agreementId}/versions/${selectedAgreement.version}/${action}`
      const result = await apiPost<{ agreement: Agreement }>(path, action === 'counter' ? { memberId: selectedMember.memberId, proposalDeltaSummary: counterText } : {}, { memberId: selectedMember.memberId })
      setAgreements((current) => current.map((a) => a.agreementId === result.agreement.agreementId && a.version === result.agreement.version ? result.agreement : a))
      setMessage(`Agreement ${action} recorded. Current status: ${result.agreement.status}.`); await loadWorkflow()
    } catch (e) { setError(e instanceof Error ? e.message : `Could not ${action} agreement.`) }
    finally { setBusy(false) }
  }
  async function createAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selectedMember) return
    setBusy(true); setError(''); setMessage('')
    try {
      await apiPost('/api/assignments', { householdId: HOUSEHOLD_ID, memberId: selectedMember.memberId, task: newTask.trim(), frequency: 'weekly', estimatedEffort: Number(newTaskEffort), assignedDate: new Date().toISOString() }, { memberId: selectedMember.memberId })
      setMessage('Task created.'); await loadWorkflow()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not create task.') }
    finally { setBusy(false) }
  }
  async function updateAssignment(item: Assignment, status: string) {
    setBusy(true); setError(''); setMessage('')
    try { await apiPatch(`/api/assignments/${item.assignmentId}/status`, { status }, { memberId: item.memberId }); setMessage(`Task marked ${status}.`); await loadWorkflow() }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not update task.') }
    finally { setBusy(false) }
  }
  async function createExpense(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selectedMember) return
    setBusy(true); setError(''); setMessage('')
    try {
      const splitMemberIds = expenseSplitMode === 'all-equal' ? [] : expenseSplitMemberIds
      if (expenseSplitMode !== 'all-equal' && splitMemberIds.length < 1) throw new Error('Choose at least one member to share this expense with.')
      const splitRatios = expenseSplitMode === 'custom' ? Object.fromEntries(splitMemberIds.map((id) => [id, Math.max(1, Math.round(expenseSplitRatios[id] ?? 1))])) : undefined
      await apiPost('/api/expenses', { householdId: HOUSEHOLD_ID, payerMemberId: selectedMember.memberId, description: newExpenseDescription.trim(), amount: Number(newExpenseAmount), category: newExpenseCategory, expenseDate: new Date().toISOString(), ...(expenseSplitMode !== 'all-equal' ? { splitMemberIds, ...(splitRatios ? { splitRatios } : {}) } : {}) }, { memberId: selectedMember.memberId })
      setNewExpenseAmount(''); setExpenseSplitMode('all-equal'); setExpenseSplitMemberIds([]); setExpenseSplitRatios({}); setMessage('Expense recorded in the local demo backend.'); await loadWorkflow()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not record expense.') }
    finally { setBusy(false) }
  }
  async function generateDrift() {
    if (!selectedMember || !selectedAgreement) return
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await apiPost<{ driftReport: DriftReport }>('/api/drift/generate', { agreementId: selectedAgreement.agreementId, version: selectedAgreement.version }, { memberId: selectedMember.memberId })
      setDrift(result.driftReport); setMessage('Drift report generated from the current simulated monitoring signals.')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not generate drift report.') }
    finally { setBusy(false) }
  }
  async function startRenegotiation() {
    if (!selectedMember || !drift) return
    setBusy(true); setError(''); setMessage('')
    try { const result = await apiPost<{ renegotiation: { status: string } }>('/api/drift/renegotiations/start', { householdId: HOUSEHOLD_ID, driftId: drift.driftId }, { memberId: selectedMember.memberId }); setMessage(`Renegotiation started (${result.renegotiation.status}). Member check-ins were created.`) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not start renegotiation.') }
    finally { setBusy(false) }
  }
  async function proposeMediation() {
    if (!selectedMember) { setError('Initialize the demo household and select a member first.'); return }
    const perspectives = roommates
      .filter((person) => (mediationStatements[person.memberId] ?? '').trim() && sharingConsents[person.memberId] === true)
      .map((person) => ({ memberId: person.memberId, statement: mediationStatements[person.memberId].trim(), consentToShare: true }))
    if (perspectives.length < 2) { setError('At least two members must provide a statement and explicitly consent to share it for mediation.'); return }
    const unconsented = perspectives.find((perspective) => roommates.find((person) => person.memberId === perspective.memberId)?.consentStatus !== 'granted')
    if (unconsented) { setError('Every participating member must have current household consent before mediation.'); return }
    setMediationLoading(true); setError(''); setMessage('')
    try {
      const result = await apiPost<MediationResult>('/api/mediation/propose', { householdId: HOUSEHOLD_ID, perspectives }, { memberId: selectedMember.memberId })
      setMediationResult(result)
      await persistMediationSession(result)
      setMessage(`Mediation suggestions prepared in ${result.mode} mode. A session with only neutral summaries and options was saved; nothing was applied.`)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not prepare mediation options.') }
    finally { setMediationLoading(false) }
  }

  async function persistMediationSession(result: MediationResult) {
    if (!selectedMember) return
    const sessionResult = await apiPost<{ session: MediationSession }>('/api/mediation/sessions', {
      householdId: HOUSEHOLD_ID,
      topic: result.sharedNeed.slice(0, 160) || 'Shared household needs',
      restatements: result.restatements.map((row) => ({ memberId: row.memberId, label: row.label ?? memberName(row.memberId), needsRestatement: row.needsRestatement, privateDetailsOmitted: true })),
      options: result.options.map((option) => ({ id: option.id, title: option.title, proposal: option.proposal, tradeOff: option.tradeOff, requiresHouseholdConfirmation: true })),
    }, { memberId: selectedMember.memberId })
    setMediationSession(sessionResult.session)
    try { window.localStorage.setItem('accord-active-mediation-session', sessionResult.session.sessionId) } catch { /* session restoration is optional */ }
  }

  async function voteForMediationOption(optionId: string) {
    if (!selectedMember || !mediationSession) return
    setMediationVoteLoading(true); setError(''); setMessage('')
    try {
      const result = await apiPost<{ session: MediationSession; voteChanged: boolean }>(`/api/mediation/sessions/${mediationSession.sessionId}/vote`, { optionId }, { memberId: selectedMember.memberId })
      setMediationSession(result.session)
      setMessage(result.voteChanged ? 'Your vote was changed.' : 'Your vote was recorded. Voting remains open until the household closes it.')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not record your vote.') }
    finally { setMediationVoteLoading(false) }
  }

  async function closeMediationVoting() {
    if (!selectedMember || !mediationSession) return
    setMediationVoteLoading(true); setError(''); setMessage('')
    try {
      const result = await apiPost<{ session: MediationSession; agreement: Agreement | null }>(`/api/mediation/sessions/${mediationSession.sessionId}/close`, {}, { memberId: selectedMember.memberId })
      setMediationSession(result.session)
      const option = result.session.options.find((candidate) => candidate.id === result.session.winningOptionId) ?? null
      setChosenMediationOption(option)
      if (result.agreement) {
        await loadWorkflow()
        setMessage(`Voting closed. ${option?.title ?? 'A winning option'} produced a draft agreement. It still needs normal member review and approval${result.session.tie ? `; tie resolved by ${result.session.tieBreakRule}` : ''}.`)
        setSelectedAgreementKey(`${result.agreement.agreementId}::${result.agreement.version}`)
      }
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not close mediation voting.') }
    finally { setMediationVoteLoading(false) }
  }

  async function simulateFairnessWeeks() {
    if (!selectedMember) { setError('Initialize the demo household first.'); return }
    setFairnessSimulationLoading(true); setError(''); setMessage('')
    try {
      const result = await apiPost<FairnessSimulation>('/api/fairness/simulate-weeks', {
        householdId: HOUSEHOLD_ID, weeks: 8, seed: 7, preferenceWeight: fairnessWeight / 100,
        tasks: [{ task: 'Dishes', estimatedEffort: 30 }, { task: 'Trash and recycling', estimatedEffort: 15 }, { task: 'Bathroom cleaning', estimatedEffort: 40 }, { task: 'Kitchen floor', estimatedEffort: 25 }, { task: 'Laundry', estimatedEffort: 35 }, { task: 'Meal prep', estimatedEffort: 40 }],
      }, { memberId: selectedMember.memberId })
      setFairnessSimulation(result)
      setMessage('Eight-week synthetic simulation completed. No household assignments were saved.')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not run the eight-week simulation.') }
    finally { setFairnessSimulationLoading(false) }
  }

  async function createMealPlanDraft() {
    if (!selectedMember) { setError('Initialize the demo household first.'); return }
    setMealPlanLoading(true); setError(''); setMessage('')
    try {
      const result = await apiPost<MealPlanDraft>('/api/assistant/meal-plan', { householdId: HOUSEHOLD_ID }, { memberId: selectedMember.memberId })
      setMealPlanDraft(result); setMessage('Seven-day meal rota created as a draft. No tasks or calendar events were saved.')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not create a meal plan draft.') }
    finally { setMealPlanLoading(false) }
  }

  async function loadPrivacyDashboard() {
    setPrivacyLoading(true); setError('')
    try { setPrivacyDashboard(await apiGet<PrivacyDashboard>('/api/privacy/dashboard')) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not load the privacy dashboard.') }
    finally { setPrivacyLoading(false) }
  }

  async function loadWorkloadDrift() {
    if (!selectedMember) { setError('Initialize the demo household first.'); return }
    setWorkloadDriftLoading(true); setError('')
    try { setWorkloadDrift(await apiGet<WorkloadDrift>(`/api/monitoring/workload-drift/${HOUSEHOLD_ID}`, { memberId: selectedMember.memberId })) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not check recent workload balance.') }
    finally { setWorkloadDriftLoading(false) }
  }

  async function confirmChatAction(messageId: string, approve: boolean) {
    const item = chatMessages.find((message) => message.id === messageId)
    if (!item?.pendingAction || item.pendingAction.status !== 'pending') return
    const action = item.pendingAction
    if (!approve) {
      const outcomeMessageId = nextChatMessageId('rejected')
      setChatMessages((current) => [...current.map((message) => message.id === messageId ? { ...message, pendingAction: { ...message.pendingAction!, status: 'rejected' as const } } : message), { id: outcomeMessageId, role: 'assistant', text: `No change made. The proposed reassignment of ${action.taskName} was rejected.` }])
      try { window.localStorage.setItem('accord-chat-action-history', JSON.stringify([{ at: new Date().toISOString(), outcome: 'rejected', task: action.taskName }, ...JSON.parse(window.localStorage.getItem('accord-chat-action-history') ?? '[]')].slice(0, 50))) } catch { /* history storage is optional */ }
      return
    }
    if (!selectedMember) { setError('Choose a current household member before approving this action.'); return }
    setBusy(true); setError('')
    try {
      await apiPost(`/api/assignments/${action.assignmentId}/reassign`, { memberId: action.targetMemberId }, { memberId: selectedMember.memberId })
      const outcomeMessageId = nextChatMessageId('approved')
      setChatMessages((current) => [...current.map((message) => message.id === messageId ? { ...message, pendingAction: { ...message.pendingAction!, status: 'approved' as const } } : message), { id: outcomeMessageId, role: 'assistant', text: `Confirmed: ${action.taskName} is now assigned to ${action.targetName}.` }])
      try { window.localStorage.setItem('accord-chat-action-history', JSON.stringify([{ at: new Date().toISOString(), outcome: 'approved', task: action.taskName }, ...JSON.parse(window.localStorage.getItem('accord-chat-action-history') ?? '[]')].slice(0, 50))) } catch { /* history storage is optional */ }
      await loadWorkflow(); setMessage('Confirmed action completed through the backend.')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not apply the confirmed action.') }
    finally { setBusy(false) }
  }

  function selectMediationOption(option: MediationOption) {
    setCounterText(`${option.title}: ${option.proposal} Trade-off: ${option.tradeOff}`)
    setActiveTab('Agreements')
    setMessage('This is only a draft. Review the proposal and explicitly submit a counteroffer if the household agrees.')
    setError('')
  }

  async function compareFairness() {
    if (!selectedMember) { setError('Initialize the demo household first.'); return }
    setFairnessLoading(true); setError(''); setMessage('')
    try {
      const result = await apiPost<FairnessComparison>('/api/fairness/compare', {
        householdId: HOUSEHOLD_ID,
        preferenceWeight: fairnessWeight / 100,
        tasks: [
          { task: 'Dishes', estimatedEffort: 30 },
          { task: 'Trash and recycling', estimatedEffort: 15 },
          { task: 'Bathroom cleaning', estimatedEffort: 40 },
          { task: 'Kitchen floor', estimatedEffort: 25 },
          { task: 'Laundry', estimatedEffort: 35 },
        ],
      }, { memberId: selectedMember.memberId })
      setFairnessComparison(result)
      setMessage('What-if comparison calculated. No assignments were saved.')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not compare the allocation methods.') }
    finally { setFairnessLoading(false) }
  }

  async function draftAgreementClauses() {
    if (!selectedMember) { setError('Initialize the demo household first.'); return }
    setClausesLoading(true); setError(''); setMessage('')
    try {
      const shared = await apiGet<ApiList<Constraint>>(`/api/constraints/households/${HOUSEHOLD_ID}/shared`, { memberId: selectedMember.memberId })
      const ids = (shared.constraints ?? []).filter((constraint) => constraint.privacyClassification === 'shareable_derived').map((constraint) => constraint.constraintId)
      if (!ids.length) throw new Error('No shareable preferences are available. Complete consented check-ins first.')
      const result = await apiPost<DraftClauses>('/api/agreements/draft-clauses', { householdId: HOUSEHOLD_ID, derivedConstraintIds: ids }, { memberId: selectedMember.memberId })
      setDraftedClauses(result)
      setMessage(`Created ${result.clauses.length} draft clause(s). They are not an active agreement.`)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not draft agreement clauses.') }
    finally { setClausesLoading(false) }
  }

  async function calculateSettlement() {
    if (!selectedMember) { setError('Initialize the demo household first.'); return }
    setSettlementLoading(true); setError(''); setMessage('')
    try {
      const result = await apiGet<Settlement>(`/api/expenses/households/${HOUSEHOLD_ID}/settle-up`, { memberId: selectedMember.memberId })
      setSettlement(result)
      setMessage('Split-aware settlement suggestions calculated. No payment was made.')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not calculate settlement.') }
    finally { setSettlementLoading(false) }
  }

  async function loadWeeklyDigest() {
    if (!selectedMember) { setError('Initialize the demo household first.'); return }
    setDigestLoading(true); setError(''); setMessage('')
    try {
      const result = await apiGet<WeeklyDigest>(`/api/monitoring/weekly-digest/${HOUSEHOLD_ID}`, { memberId: selectedMember.memberId })
      setWeeklyDigest(result)
      setMessage('Seven-day digest generated from recorded prototype data.')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not generate the weekly digest.') }
    finally { setDigestLoading(false) }
  }

  async function refreshAll() { setRefreshing(true); setMembersLoading(true); setError(''); await loadMembers(); await loadWorkflow(); setRefreshing(false) }


  useEffect(() => {
    try { window.localStorage.setItem('accord-household-type', householdType) } catch { /* local preference is optional */ }
  }, [householdType])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [chatMessages])

  useEffect(() => {
    function handleGlobalShortcut(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setCommandOpen(true)
        setCommandQuery('')
        setCommandIndex(0)
      } else if (event.key === 'Escape') {
        setCommandOpen(false)
      }
    }
    window.addEventListener('keydown', handleGlobalShortcut)
    return () => window.removeEventListener('keydown', handleGlobalShortcut)
  }, [])

  useEffect(() => {
    if (commandOpen) commandInputRef.current?.focus()
  }, [commandOpen])

  function startOrStopVoice() {
    stopSpeech()
    if (isListening) {
      recognitionRef.current?.stop()
      setIsListening(false)
      setVoiceStatus('Microphone stopped.')
      return
    }
    const browserWindow = window as SpeechWindow
    const Recognition = browserWindow.SpeechRecognition ?? browserWindow.webkitSpeechRecognition
    if (!Recognition) {
      setVoiceStatus('Voice input is not supported in this browser. You can type in the message box instead.')
      return
    }
    try {
      const recognition = new Recognition()
      recognition.lang = 'en-IN'
      recognition.interimResults = false
      recognition.continuous = false
      recognition.onresult = (event) => {
        const transcript = event.results[event.resultIndex]?.[0]?.transcript?.trim() ?? ''
        if (transcript) {
          setChatInput(transcript)
          setVoiceStatus('Got it. Review your words, then press Send.')
        }
      }
      recognition.onerror = (event) => {
        setVoiceStatus(event.error === 'not-allowed'
          ? 'Microphone permission was blocked. Allow microphone access or type your message.'
          : `Voice input stopped${event.error ? ` (${event.error})` : ''}. You can type instead.`)
      }
      recognition.onend = () => setIsListening(false)
      recognitionRef.current = recognition
      recognition.start()
      setIsListening(true)
      setVoiceStatus('Listening… speak naturally, then pause.')
    } catch {
      setIsListening(false)
      setVoiceStatus('Could not start the microphone. Please type your message instead.')
    }
  }

  function makeAssistantReply(rawText: string): ChatMessage {
    const text = rawText.toLowerCase()
    let reply: string
    let actionTab: Tab | undefined
    let actionLabel: string | undefined

    // Conflict language must win over topic keywords such as “chores” or “bills”.
    if (/fight|argue|argument|disagree|conflict|unfair|upset|problem|mediat/.test(text)) {
      if (!selectedMember || selectedMember.consentStatus !== 'granted') {
        reply = selectedMember
          ? `Before starting a private check-in, ${selectedMember.displayName} must explicitly grant consent in My Household. Participation is optional; nobody is required to take part.`
          : 'First initialize your household and choose a member. Private check-ins require the selected member to have explicitly granted consent.'
        actionTab = 'My Household'
        actionLabel = 'Review household consent'
      } else {
        reply = 'We can slow things down and hear each person privately before suggesting anything. Start a private check-in; I will not force a decision, and shared plans should use only permitted derived information.'
        actionTab = 'Interviews'
        actionLabel = 'Start a private check-in'
      }
    } else if (/meal|dinner|breakfast|lunch|who cooks|meal plan/.test(text)) {
      reply = 'I can prepare a seven-day meal rota using only currently consenting household members and shareable meal or availability preferences. It will be a draft, not saved assignments.'
      actionTab = 'Plans'
      actionLabel = 'Create meal-plan draft'
    } else if (/agreement|proposal|approve|counteroffer|fair plan|decision/.test(text)) {
      reply = 'Let’s review the proposal before anyone commits. Open Fair plan & decisions to compare its rationale, approvals, requested changes and counteroffers. A proposal becomes active only when the backend confirms that the required approval conditions are met.'
      actionTab = 'Agreements'
      actionLabel = 'Review fair plan'
    } else if (/plan|week|schedule/.test(text)) {
      const openTasks = assignments.filter((item) => item.status !== 'completed').length
      reply = `Let's make the week easier. I can use the current household tasks${openTasks ? ` (${openTasks} still open)` : ''} and any agreed plan as a starting point. Open Plans to review tasks and build an agreement. Meal ideas in this demo are suggestions, not saved bookings.`
      actionTab = 'Plans'
      actionLabel = 'Open weekly plan'
    } else if (/chore|clean|laundry|trash|vacuum|dishes|task/.test(text)) {
      reply = `Let's organize the chores. There are ${assignments.filter((item) => item.status !== 'completed').length} task(s) not marked complete right now. You can create a task, choose a household member, and update its status in Chores.`
      actionTab = 'Chores'
      actionLabel = 'Open chores'
    } else if (/bill|expense|electricity|rent|internet|pay|payment|grocery|groceries|budget/.test(text)) {
      reply = `Let's check household spending. The backend currently has ${expenses.length} recorded expense(s), totaling ${money(totalExpenses)}. Open Bills to record an expense or review the entries.`
      actionTab = 'Bills'
      actionLabel = 'Open bills'
    } else if (/member|family|roommate|partner|sibling|parent|household|home/.test(text)) {
      reply = `Your current household type is ${householdType.toLowerCase()}. Open My Household to choose another household type, add family members or housemates, and review each person's consent.`
      actionTab = 'My Household'
      actionLabel = 'Open my household'
    } else if (/monitor|balance|drift|renegotiat/.test(text)) {
      reply = 'You can review how the current plan is going in Monitoring. This prototype uses simulated monitoring signals, not live home sensors.'
      actionTab = 'Monitoring'
      actionLabel = 'Open monitoring'
    } else {
      reply = 'I can help with a weekly plan, chores, bills, household members, or a private check-in. Choose one of the quick actions or tell me a little more. This local demo uses guided responses; a generative AI provider is not connected yet.'
    }

    return {
      id: nextChatMessageId('chat'),
      role: 'assistant',
      text: reply,
      actionLabel,
      actionTab,
    }
  }

  async function sendChatMessage(textOverride?: string) {
    const text = (textOverride ?? chatInput).trim()
    if (!text || assistantThinking) return
    const userMessage: ChatMessage = {
      id: nextChatMessageId('chat'),
      role: 'user',
      text,
    }
    const localIntent = makeAssistantReply(text)
    setChatMessages((current) => [...current, userMessage])
    setChatInput('')
    setVoiceStatus('')
    setAssistantThinking(true)
    let reply: ChatMessage
    try {
      const result = await apiPost<AssistantChatResponse>('/api/assistant/chat', { message: text })
      const actionTabs: Record<string, Tab> = {
        plan: 'Plans', meals: 'Plans', chores: 'Chores', bills: 'Bills', mediation: 'Interviews',
        household: 'My Household', monitoring: 'Monitoring', agreements: 'Agreements',
      }
      const actionLabels: Record<string, string> = {
        plan: 'Open weekly plan', meals: 'Create meal-plan draft', chores: 'Open chores', bills: 'Open bills',
        mediation: 'Start a private check-in', household: 'Open my household',
        monitoring: 'Open household balance', agreements: 'Review fair plan',
      }
      if (result.suggestedAction === 'meals' && selectedMember) {
        try {
          const draft = await apiPost<MealPlanDraft>('/api/assistant/meal-plan', { householdId: HOUSEHOLD_ID }, { memberId: selectedMember.memberId })
          setMealPlanDraft(draft)
        } catch (mealError) { setError(mealError instanceof Error ? mealError.message : 'Could not create the meal-plan draft.') }
      }
      const needsConsentReview = result.suggestedAction === 'mediation' && (!selectedMember || selectedMember.consentStatus !== 'granted')
      const suggestedTab = needsConsentReview ? 'My Household' : actionTabs[result.suggestedAction]
      reply = {
        id: nextChatMessageId('chat'),
        role: 'assistant',
        text: needsConsentReview
          ? selectedMember
            ? `Before starting a private check-in, ${selectedMember.displayName} must explicitly grant consent in My Household. Participation is optional; nobody is required to take part.`
            : 'First initialize your household and choose a member. Private check-ins require the selected member to have explicitly granted consent.'
          : result.reply,
        actionTab: suggestedTab ?? localIntent.actionTab,
        actionLabel: needsConsentReview ? 'Review household consent' : (suggestedTab ? actionLabels[result.suggestedAction] : localIntent.actionLabel),
      }
      const reassignMatch = text.match(/\breassign\s+(.+?)\s+to\s+(.+?)\??$/i)
      if (reassignMatch && selectedMember) {
        const requestedTask = reassignMatch[1].trim().toLowerCase()
        const target = roommates.find((person) => person.displayName.toLowerCase() === reassignMatch[2].trim().replace(/[?.!]+$/, '').toLowerCase())
        const task = assignments.find((assignment) => assignment.task.toLowerCase() === requestedTask || assignment.task.toLowerCase().includes(requestedTask))
        if (task && target) {
          reply = { ...reply, text: `I found “${task.task}” and ${target.displayName}. Review this draft before changing the assignment.`, pendingAction: { kind: 'reassign', assignmentId: task.assignmentId, targetMemberId: target.memberId, targetName: target.displayName, taskName: task.task, status: 'pending' } }
        }
      }
      setAssistantMode(result.mode)
    } catch {
      // Keep chat usable if the API is temporarily unavailable. This is a local
      // guided fallback, not a claim that a generative model answered.
      reply = {
        ...localIntent,
        text: `${localIntent.text}\n\nI'm using the local guided fallback because the assistant API is currently unreachable.`,
      }
      setAssistantMode('local')
    } finally {
      setAssistantThinking(false)
    }
    setChatMessages((current) => [...current, reply])
  }

  const roleOptions = householdType === 'Family'
    ? ['Parent', 'Child', 'Sibling', 'Grandparent', 'Relative', 'Family member', 'Other']
    : householdType === 'Couple'
      ? ['Partner', 'Spouse', 'Other']
      : householdType === 'Roommates'
        ? ['Roommate', 'Housemate', 'Other']
        : householdType === 'Shared home'
          ? ['Parent', 'Partner', 'Sibling', 'Roommate', 'Housemate', 'Other']
          : ['Member', 'Other']

  const mainNav: { name: Tab; icon: typeof Activity }[] = [
    { name: 'Home', icon: Home },
    { name: 'My Household', icon: Users },
    { name: 'Plans', icon: CalendarDays },
    { name: 'Chores', icon: ListChecks },
    { name: 'Bills', icon: Wallet },
    { name: 'Calendar', icon: CalendarDays },
    { name: 'Chat History', icon: History },
    { name: 'Settings', icon: Settings },
  ]
  const toolNav: { name: Tab; label: string; icon: typeof Activity }[] = [
    { name: 'Interviews', label: 'Private check-in', icon: HeartHandshake },
    { name: 'Mediation', label: 'Mediation room', icon: MessageCircle },
    { name: 'Agreements', label: 'Fair plan & decisions', icon: Scale },
    { name: 'Monitoring', label: 'Household balance', icon: Activity },
    { name: 'Privacy', label: 'Privacy dashboard', icon: ShieldCheck },
  ]
  const totalExpenses = expenses.reduce((sum, expense) => sum + expense.amount, 0)
  const greeting = new Date().getHours() < 12 ? 'Good morning' : new Date().getHours() < 17 ? 'Good afternoon' : 'Good evening'
  const householdDescription = householdType === 'Family' ? 'Parents, children, siblings and extended family'
    : householdType === 'Couple' ? 'You and your partner'
      : householdType === 'Roommates' ? 'Friends or housemates sharing a home'
        : householdType === 'Shared home' ? 'A mix of family, friends and housemates'
          : 'Create a setup that fits your home'

  const paletteItems = useMemo<PaletteItem[]>(() => {
    const navigation: PaletteItem[] = [
      { label: 'Home dashboard', description: 'Overview, chat and household status', keywords: 'home overview dashboard start', tab: 'Home', icon: Home },
      { label: 'My Household', description: 'Members, roles and consent', keywords: 'members family roommates consent', tab: 'My Household', icon: Users },
      { label: 'Plans', description: 'Weekly plan and upcoming responsibilities', keywords: 'plan weekly schedule calendar', tab: 'Plans', icon: CalendarDays },
      { label: 'Chores', description: 'Create tasks and update progress', keywords: 'chores tasks assignments clean', tab: 'Chores', icon: ListChecks },
      { label: 'Bills & expenses', description: 'Record shared spending and review totals', keywords: 'bills money expenses budget', tab: 'Bills', icon: Wallet },
      { label: 'Private check-in', description: 'Start an optional private interview', keywords: 'interview private talk disagreement', tab: 'Interviews', icon: HeartHandshake },
      { label: 'Mediation room', description: 'Create consented, neutral compromise options', keywords: 'mediation conflict compromise neutral', tab: 'Mediation', icon: MessageCircle },
      { label: 'Fair plan & decisions', description: 'Review proposals, approvals and counteroffers', keywords: 'agreement fairness proposal decisions', tab: 'Agreements', icon: Scale },
      { label: 'Household balance', description: 'Review drift signals and revisit a plan', keywords: 'monitoring drift balance renegotiate', tab: 'Monitoring', icon: Activity },
      { label: 'Privacy dashboard', description: 'Inspect the current AI mode and data boundaries', keywords: 'privacy provider llm data boundaries consent', tab: 'Privacy', icon: ShieldCheck },
      { label: 'Calendar', description: 'See assigned tasks by date', keywords: 'calendar dates upcoming', tab: 'Calendar', icon: CalendarDays },
      { label: 'Settings & connection', description: 'Test API, refresh data or reset demo', keywords: 'settings api backend reset demo refresh', tab: 'Settings', icon: Settings },
    ]
    const records: PaletteItem[] = [
      ...roommates.map((person) => ({ label: person.displayName, description: `${person.role} · consent ${person.consentStatus}`, keywords: `member ${person.role} ${person.consentStatus}`, tab: 'My Household' as Tab, icon: Users, memberId: person.memberId })),
      ...assignments.map((item) => ({ label: item.task, description: `${memberName(item.memberId)} · ${item.status} · ${item.estimatedEffort} min`, keywords: `task chore ${item.status} ${item.frequency}`, tab: 'Chores' as Tab, icon: ListChecks })),
      ...agreements.map((item) => ({ label: `Agreement v${item.version}`, description: `${item.status} · fairness heuristic ${Math.round(item.fairnessScore * 100)}%`, keywords: `agreement ${item.status} fairness proposal`, tab: 'Agreements' as Tab, icon: Scale, agreementId: item.agreementId, agreementVersion: item.version })),
      ...expenses.map((item) => ({ label: item.description, description: `${money(item.amount)} · ${item.category}`, keywords: `expense bill ${item.category}`, tab: 'Bills' as Tab, icon: Wallet })),
    ]
    const allItems = [...navigation, ...records]
    const query = commandQuery.trim().toLowerCase()
    if (!query) return allItems.slice(0, 18)
    return allItems.filter((item) => `${item.label} ${item.description} ${item.keywords}`.toLowerCase().includes(query)).slice(0, 18)
  }, [commandQuery, roommates, assignments, agreements, expenses, memberName])

  function openPaletteItem(item: PaletteItem) {
    setActiveTab(item.tab)
    if (item.memberId) setSelectedMemberId(item.memberId)
    if (item.agreementId && item.agreementVersion !== undefined) setSelectedAgreementKey(`${item.agreementId}::${item.agreementVersion}`)
    setCommandOpen(false)
    setCommandQuery('')
    setError('')
    setMessage('')
  }

  return <main className="app-shell accord-shell">
    <aside className="sidebar accord-sidebar" data-voice-skip>
      <button className="brand brand-button" type="button" onClick={() => setActiveTab('Home')} aria-label="Accord home">
        <div className="brand-mark"><Waves size={23} /></div>
        <div><strong>accord</strong><span>HOUSEHOLD ASSISTANT</span></div>
      </button>
      <button className="home-switcher" type="button" onClick={() => setActiveTab('My Household')}>
        <div className="home-icon"><House size={19} /></div>
        <div><span>YOUR HOUSEHOLD</span><strong>Our {householdType.toLowerCase()}</strong><small>{roommates.length} member{roommates.length === 1 ? '' : 's'}</small></div>
        <ChevronRight size={17} />
      </button>
      <span className="nav-label">YOUR SPACE</span>
      <nav className="sidebar-nav" aria-label="Main navigation">
        {mainNav.map(({ name, icon: Icon }) => <button key={name} className={`nav-item ${activeTab === name ? 'active' : ''}`} onClick={() => { setActiveTab(name); setError(''); setMessage('') }} type="button"><Icon size={17} /><span>{name}</span>{name === 'Bills' && expenses.length > 0 && <span className="nav-count">{expenses.length}</span>}</button>)}
      </nav>
      <span className="nav-label tool-nav-label">HOUSEHOLD TOOLS</span>
      <nav className="sidebar-nav tool-nav" aria-label="Household tools">
        {toolNav.map(({ name, label, icon: Icon }) => <button key={name} className={`nav-item ${activeTab === name ? 'active' : ''}`} onClick={() => { setActiveTab(name); setError(''); setMessage('') }} type="button"><Icon size={17} /><span>{label}</span></button>)}
      </nav>
      <div className="sidebar-bottom">
        <div className="privacy-note"><ShieldCheck size={20} /><strong>Your privacy comes first</strong><p>Private check-ins stay private. Only permitted shared summaries can inform a household plan.</p><span><LockKeyhole size={13} /> PRIVACY BY DESIGN</span></div>
        <div className="profile"><div className="avatar profile-avatar">{selectedMember?.initials ?? 'A'}</div><div><strong>{selectedMember?.displayName ?? 'Your profile'}</strong><span>{selectedMember?.role ?? 'Household member'}</span></div><span className="online-dot" /></div>
      </div>
    </aside>

    <section className="main-panel">
      <header className="topbar accord-topbar">
        <div className="breadcrumb"><span className="breadcrumb-home">{householdType} home</span><ChevronRight size={14} /><span>{activeTab === 'Overview' ? 'Home' : activeTab}</span></div>
        <div className="top-actions">
          <span className="demo-badge"><span /> LOCAL DEMO</span>
          <button className="command-trigger" type="button" onClick={() => { setCommandOpen(true); setCommandQuery(''); setCommandIndex(0) }} aria-label="Open quick navigation" aria-keyshortcuts="Control+K Meta+K"><Search size={15} /><span>Quick jump</span><kbd>Ctrl K</kbd></button>
          <VoiceControls />
          <button className="icon-button" aria-label="Open chat history" type="button" onClick={() => setActiveTab('Chat History')}><MessageCircle size={18} /></button>
          <div className="avatar top-avatar">{selectedMember?.initials ?? 'A'}</div>
        </div>
      </header>

      <div className="page-content accord-page">
        {message && <div data-speak={message}><Notice>{message}</Notice></div>}{error && <div data-speak="Accord encountered an error. Check the on-screen message for details."><Notice error>{error}</Notice></div>}
        {membersError && /404|not found|resource_not_found/i.test(membersError) && <section className="first-run-recovery"><div className="recovery-mark"><Sparkles size={18} /></div><div className="recovery-copy"><strong>Your demo household hasn't been initialized yet</strong><p>Initialize the sample household so the member list, agreements, chores and monitoring demo can load. This replaces the current demo dataset.</p></div><button className="primary-button" type="button" disabled={busy} onClick={() => { if (window.confirm('Reset the local Accord demo data and create the sample household? Existing demo data will be replaced.')) void resetDemo() }}>{busy ? 'Initializing…' : 'Initialize demo household'}</button></section>}

        {activeTab === 'Home' && <>
          <section className="voice-home-hero">
            <div className="voice-home-copy">
              <div className="eyebrow"><Sparkles size={14} /> A CALMER HOME, BUILT TOGETHER</div>
              <h1>{greeting}{selectedMember?.displayName ? `, ${selectedMember.displayName.split(' ')[0]}` : ''}! <span aria-hidden="true">👋</span></h1>
              <h2>Make home life work better for everyone.</h2>
              <p>Plan the week, balance responsibilities, track shared costs, or work through a disagreement. Start with a message and Accord will help you take the next step.</p>
              <div className="home-trust-row"><span><LockKeyhole size={14} /> Private by design</span><span><Users size={14} /> {roommates.length} household member{roommates.length === 1 ? '' : 's'}</span></div>
            </div>
            <div className="voice-hero-orb" data-voice-skip aria-hidden="true">
              <div className="orb-halo halo-one" /><div className="orb-halo halo-two" />
              <motion.div className={`orb ${isListening ? 'orb-listening' : ''}`} animate={{ y: [0, -10, 0], rotate: [0, 4, 0], scale: isListening ? [1, 1.06, 1] : [1, 1.015, 1] }} transition={{ duration: isListening ? 1.2 : 4.8, repeat: Infinity, ease: 'easeInOut' }}>
                <div className="orb-shine" /><div className="orb-core" /><div className="orb-ring ring-one" /><div className="orb-ring ring-two" />
              </motion.div>
              <span className="orb-listening-label">{isListening ? 'Listening…' : 'Ready when you are'}</span>
            </div>
          </section>

          <div className="home-content-grid">
            <section className="chat-card">
              <div className="chat-card-heading">
                <div className="assistant-name"><div className="mini-orb"><Waves size={18} /></div><div><strong>Talk to Accord</strong><span>Voice or text · {assistantMode === 'llm' ? 'AI response received' : assistantMode === 'local' ? 'Local guided fallback' : assistantMode === 'guided_fallback' ? 'AI unavailable · guided fallback' : assistantConfigured ? 'AI provider configured' : 'Guided assistant'}</span></div></div>
                <span className="chat-secure-pill" title={assistantConfigured ? 'Your current chat message is sent to the configured AI provider; household records and private interviews are not attached.' : 'The guided assistant handles your message using local rules.'}><LockKeyhole size={12} />{assistantConfigured ? 'AI provider' : 'Local guidance'}</span>
              </div>
              <div className="chat-messages" role="log" aria-live="polite" aria-label="Conversation with Accord" aria-busy={assistantThinking}>
                {chatMessages.slice(-8).map((chat) => <div key={chat.id} className={`chat-line ${chat.role === 'user' ? 'chat-line-user' : 'chat-line-assistant'}`}>
                  {chat.role === 'assistant' && <div className="chat-avatar"><Waves size={15} /></div>}
                  <div className="chat-bubble-wrap">
                    <span className="chat-sender">{chat.role === 'user' ? 'You' : 'Accord'}</span>
                    <div className="chat-bubble" data-speak={chat.role === 'assistant' ? chat.text : undefined}>{chat.text}</div>
                    {chat.actionLabel && chat.actionTab && <button className="chat-action-link" type="button" onClick={() => setActiveTab(chat.actionTab!)}>{chat.actionLabel}<ArrowUpRight size={14} /></button>}{chat.pendingAction && <div className="pending-action-card"><strong>Confirm task reassignment</strong><p>Reassign “{chat.pendingAction.taskName}” to {chat.pendingAction.targetName}?</p>{chat.pendingAction.status === 'pending' ? <div className="action-row"><button className="primary-button" type="button" disabled={busy} onClick={() => void confirmChatAction(chat.id, true)}>Approve & reassign</button><button className="secondary-button" type="button" onClick={() => void confirmChatAction(chat.id, false)}>Reject</button></div> : <Notice>{chat.pendingAction.status === 'approved' ? 'Approved and applied.' : 'Rejected. No change was made.'}</Notice>}<Notice>This action is a draft until you approve it. Approval runs the existing backend workflow as the selected demo member.</Notice></div>}
                  </div>
                </div>)}
                {assistantThinking && <div className="chat-thinking" role="status" data-voice-skip><span className="thinking-dots"><i /><i /><i /></span><span>Accord is preparing a response…</span></div>}
                <div ref={chatEndRef} />
              </div>
              <form className="voice-composer" onSubmit={(event) => { event.preventDefault(); sendChatMessage() }}>
                <button className={`mic-button ${isListening ? 'mic-button-active' : ''}`} type="button" onClick={startOrStopVoice} aria-label={isListening ? 'Stop listening' : 'Talk to Accord'} title={isListening ? 'Stop listening' : 'Talk to Accord'}>{isListening ? <MicOff size={21} /> : <Mic size={21} />}</button>
                <input value={chatInput} onChange={(event) => { stopSpeech(); setChatInput(event.target.value) }} placeholder={isListening ? 'Listening…' : 'Try “Help plan our week”'} aria-label="Message Accord" disabled={assistantThinking} />
                <button className="send-button" type="submit" disabled={!chatInput.trim() || assistantThinking} aria-label="Send message">{assistantThinking ? <RefreshCw size={17} className="spin-icon" data-voice-skip aria-hidden="true" /> : <Send size={17} />}</button>
              </form>
              {voiceStatus && <p className="voice-status" role="status">{voiceStatus}</p>}
              <div className="chat-footer-note"><span>Microphone support depends on your browser permissions.</span><VoiceControls /></div>
            </section>

            <aside className="home-side-column">
              <section className="quick-action-card">
                <div className="section-heading compact-heading"><div><h2>What would make today easier?</h2><p>Choose a shortcut or tell Accord in your own words.</p></div></div>
                <div className="quick-action-grid">
                  <button type="button" className="quick-action-tile" onClick={() => sendChatMessage('Help me plan our week with chores, meals and schedules.')}><span className="quick-icon quick-purple"><CalendarDays size={17} /></span><strong>Plan my week</strong><small>Routines and schedules</small><ChevronRight size={14} /></button>
                  <button type="button" className="quick-action-tile" onClick={() => sendChatMessage('Help us organize the chores fairly.')}><span className="quick-icon quick-green"><ListChecks size={17} /></span><strong>Organize chores</strong><small>Tasks and rotations</small><ChevronRight size={14} /></button>
                  <button type="button" className="quick-action-tile" onClick={() => sendChatMessage('Help track bills and shared expenses.')}><span className="quick-icon quick-amber"><Wallet size={17} /></span><strong>Track bills</strong><small>Expenses and payments</small><ChevronRight size={14} /></button>
                  <button type="button" className="quick-action-tile" onClick={() => setActiveTab('Mediation')}><span className="quick-icon quick-pink"><HeartHandshake size={17} /></span><strong>Mediation room</strong><small>Compare perspectives respectfully</small><ChevronRight size={14} /></button>
                  <button type="button" className="quick-action-tile" onClick={() => setActiveTab('Agreements')}><span className="quick-icon quick-purple"><Scale size={17} /></span><strong>Build a fair plan</strong><small>Review proposals and decisions</small><ChevronRight size={14} /></button>
                  <button type="button" className="quick-action-tile" onClick={() => setActiveTab('Monitoring')}><span className="quick-icon quick-green"><Activity size={17} /></span><strong>Check household balance</strong><small>Spot friction and revisit plans</small><ChevronRight size={14} /></button>
                </div>
              </section>

              <section className="home-today-card">
                <div className="section-heading compact-heading"><div><h2>Your household, at a glance</h2><p>From the local demo backend.</p></div><button className="text-button" type="button" onClick={() => setActiveTab('My Household')}>View all <ChevronRight size={14} /></button></div>
                <div className="today-metrics"><button type="button" onClick={() => setActiveTab('My Household')}><Users size={16} /><strong>{roommates.length}</strong><span>Members</span></button><button type="button" onClick={() => setActiveTab('Chores')}><ListChecks size={16} /><strong>{assignments.filter((item) => item.status !== 'completed').length}</strong><span>Open tasks</span></button><button type="button" onClick={() => setActiveTab('Bills')}><Wallet size={16} /><strong>{expenses.length}</strong><span>Expenses</span></button></div>
                <div className="home-plan-note"><div className="home-plan-icon"><Heart size={17} /></div><div><strong>A calmer home starts small</strong><p>Plans are suggestions. Your household decides what works for everyone.</p></div></div>
              </section>
            </aside>
          </div>
        </>}

        {activeTab !== 'Home' && <div className="section-page-heading"><div><div className="eyebrow"><Sparkles size={14} /> YOUR HOUSEHOLD WORKSPACE</div><h1>{activeTab === 'Roommates' ? 'My Household' : activeTab === 'Tasks & expenses' ? 'Tasks & expenses' : activeTab}</h1><p className="subtitle">{activeTab === 'My Household' || activeTab === 'Roommates' ? 'Everyone who shares your home belongs here.' : activeTab === 'Plans' ? 'One place to plan routines and agree on what works.' : activeTab === 'Chores' ? 'Create tasks and keep track of what is done.' : activeTab === 'Bills' ? 'Track shared expenses with clear, simple records.' : activeTab === 'Calendar' ? 'A simple view of what is coming up.' : activeTab === 'Chat History' ? 'Messages from this browser session only.' : activeTab === 'Settings' ? 'Manage your local demo settings and connections.' : activeTab === 'Interviews' ? 'A private check-in is optional and consent comes first.' : activeTab === 'Mediation' ? 'Turn explicitly shared perspectives into neutral options that people review before acting.' : activeTab === 'Agreements' ? 'Review a proposal, suggest changes, or choose not to agree.' : 'Review simulated signals and optionally start renegotiation.'}</p></div><button className="secondary-button page-heading-action" type="button" onClick={() => setActiveTab('Home')}><Home size={15} /> Back to home</button></div>}

        {(activeTab === 'My Household' || activeTab === 'Roommates') && <>
          <section className="household-type-section">
            <div className="section-heading"><div><h2>What kind of household is this?</h2><p>Choose what best describes your home. You can change this anytime.</p></div></div>
            <div className="household-type-grid">
              {([
                { name: 'Family' as HouseholdType, emoji: '🏡', caption: 'Parents, children and relatives' },
                { name: 'Couple' as HouseholdType, emoji: '💜', caption: 'You and your partner' },
                { name: 'Roommates' as HouseholdType, emoji: '🧑‍🤝‍🧑', caption: 'Friends sharing a home' },
                { name: 'Shared home' as HouseholdType, emoji: '🏠', caption: 'A mix of family or housemates' },
                { name: 'Other' as HouseholdType, emoji: '✨', caption: 'A setup that fits your life' },
              ]).map((item) => <button className={`household-type-tile ${householdType === item.name ? 'selected' : ''}`} key={item.name} type="button" onClick={() => { setHouseholdType(item.name); setNewRole(item.name === 'Family' ? 'Parent' : item.name === 'Couple' ? 'Partner' : item.name === 'Roommates' ? 'Roommate' : 'Member') }}><span className="household-emoji">{item.emoji}</span><strong>{item.name}</strong><small>{item.caption}</small>{householdType === item.name && <span className="selected-check"><Check size={13} /> Selected</span>}</button>)}
            </div>
            <p className="household-type-note"><ShieldCheck size={14} /> The type choice is saved in this browser. It does not change server-side household data.</p>
          </section>
          <div className="workflow-grid household-workflow-grid">
            <Panel title="Who lives in your household?" description="Add everyone who shares the home. New members begin with consent pending." action={<button className="round-arrow" aria-label="Add household member" onClick={() => setShowAddForm((value) => !value)} type="button"><Plus size={17} /></button>}>
              {showAddForm && <form className="workflow-form" onSubmit={addRoommate}><label>Member name<input value={newName} onChange={(event) => setNewName(event.target.value)} required maxLength={80} placeholder={householdType === 'Family' ? 'e.g. Mum, Dad, Ananya' : householdType === 'Couple' ? 'e.g. Alex' : 'e.g. Priya'} /></label><label>Relationship / role<select value={newRole} onChange={(event) => setNewRole(event.target.value)}>{Array.from(new Set([newRole, ...roleOptions])).map((role) => <option key={role} value={role}>{role}</option>)}</select></label><button className="primary-button" disabled={addLoading} type="submit"><Plus size={15} />{addLoading ? 'Adding member…' : 'Add household member'}</button>{formMessage && <div data-speak={formMessage}><Notice>{formMessage}</Notice></div>}{formError && <div data-speak="The form could not be completed. Check the on-screen error for details."><Notice error>{formError}</Notice></div>}</form>}
              <RoommateList roommates={roommates} loading={membersLoading} error={membersError} retry={() => { setMembersLoading(true); void loadMembers() }} memberName={memberName} onConsent={setConsent} onInterview={startInterview} busy={busy} />
            </Panel>
            <Panel title={`A plan for ${householdType.toLowerCase()}`} description={householdDescription}>
              <div className="household-plan-benefit"><span>01</span><div><strong>Shared routines</strong><p>Keep regular chores, meals and schedules in one place.</p></div></div>
              <div className="household-plan-benefit"><span>02</span><div><strong>Clear responsibilities</strong><p>Make tasks visible without turning home life into a competition.</p></div></div>
              <div className="household-plan-benefit"><span>03</span><div><strong>Private by choice</strong><p>Private check-ins are optional. Only permitted summaries inform a shared plan.</p></div></div>
              <button className="primary-button full-width-button" type="button" onClick={() => setActiveTab('Plans')}><CalendarDays size={15} /> Open household plan</button>
              <p className="muted-copy">Roles and household type are flexible. Consent is managed per member.</p>
            </Panel>
          </div>
        </>}

        {activeTab === 'Plans' && <div className="workflow-grid plans-layout">
          <Panel title="This week's plan" description="A practical overview of tasks already recorded for your household." action={<button className="secondary-button" type="button" onClick={() => setActiveTab('Calendar')}><CalendarDays size={15} /> Calendar</button>}>
            <div className="plan-overview-stats"><div><span>Members</span><strong>{roommates.length}</strong></div><div><span>Open tasks</span><strong>{assignments.filter((item) => item.status !== 'completed').length}</strong></div><div><span>Expense entries</span><strong>{expenses.length}</strong></div></div>
            {assignments.length ? assignments.slice(0, 6).map((item) => <div className="data-row" key={item.assignmentId}><div><strong>{item.task}</strong><p>{memberName(item.memberId)} · {item.frequency} · {item.estimatedEffort} min</p></div><span className={`status-pill ${item.status === 'completed' ? 'status-green' : 'status-blue'}`}>{item.status.replaceAll('_', ' ')}</span></div>) : <p className="muted-copy">No chores have been added yet. Start with one small task, or reset the demo to load sample tasks.</p>}
            <div className="action-row"><button className="primary-button" type="button" onClick={() => setActiveTab('Chores')}><ListChecks size={15} /> Organize chores</button><button className="secondary-button" type="button" onClick={() => setActiveTab('Bills')}><Wallet size={15} /> Review bills</button></div>
          </Panel>
          <Panel title="Fair shared plan" description="Only generate a proposal after consented check-ins create shareable constraints.">
            {selectedAgreement ? <><div className="agreement-title" data-speak={`Agreement version ${selectedAgreement.version}. Status ${selectedAgreement.status}. Fairness score ${Math.round(selectedAgreement.fairnessScore * 100)} percent, heuristic, not a guarantee of fairness.`}><div className="agreement-symbol"><Scale size={20} /></div><div><strong>Agreement v{selectedAgreement.version}</strong><span>{selectedAgreement.status} · fairness score {Math.round(selectedAgreement.fairnessScore * 100)}% (heuristic)</span></div></div><p className="muted-copy">{withNames(selectedAgreement.rationale)}</p><button className="primary-button full-width-button" type="button" onClick={() => setActiveTab('Agreements')}>Review plan <ArrowUpRight size={15} /></button></> : <><div className="empty-plan-illustration"><Scale size={26} /><strong>No shared plan yet</strong><p>Start with private check-ins, then Accord can suggest a plan using permitted summaries.</p></div><button className="primary-button full-width-button" type="button" onClick={() => setActiveTab('Interviews')}><HeartHandshake size={15} /> Start private check-in</button><button className="secondary-button full-width-button" type="button" onClick={() => setActiveTab('Agreements')}><Scale size={15} /> Go to fair plans</button></>}
          </Panel>
          <Panel title="Meals & routines" description="A place for the whole household, beyond conflict resolution.">
            <div className="routine-suggestion"><Utensils size={18} /><div><strong>Plan a few meals</strong><p>Generate a seven-day rota using only shareable meal preferences and availability. The result remains a draft.</p></div></div>
            <button className="primary-button" type="button" disabled={mealPlanLoading || !selectedMember} onClick={() => void createMealPlanDraft()}>{mealPlanLoading ? 'Creating draft…' : 'Create 7-day meal-plan draft'}</button>
            {mealPlanDraft && <div className="meal-plan-draft" data-speak={`Weekly meal plan draft. ${mealPlanDraft.schedule.map((day) => `${day.day}: ${day.mealIdea}, suggested cook ${day.cookDisplayName}`).join(". ")}. ${mealPlanDraft.note} This is a draft and needs household confirmation.`}><DecisionVerdictCard title="Weekly meal rota draft" needsConfirmation captions={[`Prepared ${mealPlanDraft.schedule.length} suggested meals from shareable data only.`, mealPlanDraft.note]} />{mealPlanDraft.schedule.map((day) => <div className="data-row" key={day.date}><div><strong>{day.day} · {day.mealIdea}</strong><p>Suggested cook: {day.cookDisplayName}</p></div><span className="status-pill status-blue">Draft</span></div>)}</div>}
            <div className="routine-suggestion"><Clock3 size={18} /><div><strong>Find a routine that fits</strong><p>Use member availability in private check-ins before agreeing to recurring task times.</p></div></div>
          </Panel>
        </div>}

        {(activeTab === 'Chores' || activeTab === 'Bills' || activeTab === 'Tasks & expenses') && <div className={`workflow-grid ${activeTab === 'Tasks & expenses' ? '' : 'single-workflow-grid'}`}>
          {(activeTab === 'Chores' || activeTab === 'Tasks & expenses') && <Panel title="Chores & tasks" description="Create a responsibility, assign it to a member, then update its status.">
            <form className="workflow-form" onSubmit={createAssignment}><label>Task<input value={newTask} onChange={(event) => setNewTask(event.target.value)} required maxLength={120} placeholder="e.g. Take out the trash" /></label><label>Assigned to<select value={selectedMemberId} onChange={(event) => setSelectedMemberId(event.target.value)} required>{roommates.map((person) => <option key={person.memberId} value={person.memberId}>{person.displayName}</option>)}</select></label><label>Estimated effort (minutes)<input type="number" min="1" max="1000" value={newTaskEffort} onChange={(event) => setNewTaskEffort(event.target.value)} required /></label><button className="primary-button" disabled={busy || !selectedMember} type="submit"><Plus size={15} /> Create task</button></form>
            {assignments.length ? assignments.map((item) => <div className="data-row" key={item.assignmentId}><div><strong>{item.task}</strong><p>{memberName(item.memberId)} · {item.frequency} · {item.estimatedEffort} min</p></div><select aria-label={`Update ${item.task} status`} value={item.status} onChange={(event) => void updateAssignment(item, event.target.value)} disabled={busy}><option value="scheduled">To do</option><option value="in_progress">In progress</option><option value="completed">Completed</option><option value="missed">Missed</option></select></div>) : <p className="muted-copy">No chores yet. Create the first task above or reset the demo to load sample tasks.</p>}
          </Panel>}
          {(activeTab === 'Bills' || activeTab === 'Tasks & expenses') && <Panel title="Bills & shared expenses" description={`Recorded total: ${money(totalExpenses)} · ${expenses.length} entries`}>
            <form className="workflow-form" onSubmit={createExpense}><label>What was paid for?<input value={newExpenseDescription} onChange={(event) => setNewExpenseDescription(event.target.value)} required maxLength={160} placeholder="e.g. Electricity bill" /></label><label>Paid by<select value={selectedMemberId} onChange={(event) => setSelectedMemberId(event.target.value)} required>{roommates.map((person) => <option key={person.memberId} value={person.memberId}>{person.displayName}</option>)}</select></label><label>Amount (₹)<input type="number" min="0.01" max="1000000" step="0.01" value={newExpenseAmount} onChange={(event) => setNewExpenseAmount(event.target.value)} required placeholder="e.g. 1200" /></label><label>Category<select value={newExpenseCategory} onChange={(event) => setNewExpenseCategory(event.target.value)}><option value="shared">Shared</option><option value="groceries">Groceries</option><option value="utilities">Utilities</option><option value="rent">Rent</option><option value="other">Other</option></select></label><label>Split with<select value={expenseSplitMode} onChange={(event) => { const mode = event.target.value as typeof expenseSplitMode; setExpenseSplitMode(mode); if (mode !== 'all-equal' && !expenseSplitMemberIds.length) setExpenseSplitMemberIds(roommates.map((person) => person.memberId)) }}><option value="all-equal">Everyone equally</option><option value="subset-equal">Selected members equally</option><option value="custom">Custom ratios</option></select></label>{expenseSplitMode !== 'all-equal' && <div className="expense-split-controls"><span className="field-label">Who shares this expense?</span>{roommates.map((person) => <label className="split-member-option" key={person.memberId}><input type="checkbox" checked={expenseSplitMemberIds.includes(person.memberId)} onChange={(event) => { setExpenseSplitMemberIds((current) => event.target.checked ? [...current, person.memberId] : current.filter((id) => id !== person.memberId)) }} /> <span>{person.displayName}</span>{expenseSplitMode === 'custom' && expenseSplitMemberIds.includes(person.memberId) && <input aria-label={`${person.displayName} split ratio`} className="ratio-input" type="number" min="1" max="1000" value={expenseSplitRatios[person.memberId] ?? 1} onChange={(event) => setExpenseSplitRatios((current) => ({ ...current, [person.memberId]: Number(event.target.value) }))} />}</label>)}</div>}<button className="primary-button" disabled={busy || !selectedMember || (expenseSplitMode !== 'all-equal' && expenseSplitMemberIds.length === 0)} type="submit"><Plus size={15} /> Record expense</button></form>
            {expenses.length ? expenses.map((item) => <div className="data-row" key={item.expenseId}><div><strong>{item.description}</strong><p>Paid by {memberName(item.payerMemberId)} · {item.category} · {new Date(item.expenseDate).toLocaleDateString()}</p></div><strong>{money(item.amount)}</strong></div>) : <p className="muted-copy">No expense entries yet.</p>}
            <div className="feature-divider" />
            <div className="feature-action-heading"><div><strong>Settle up, without the spreadsheet</strong><p>Find a minimal set of reimbursements based on each expense’s participants and split weights.</p></div><button className="secondary-button" type="button" disabled={settlementLoading || !selectedMember} onClick={() => void calculateSettlement()}>{settlementLoading ? 'Calculating…' : 'Optimize settle-up'}</button></div>
            {settlement && <div className="settlement-results" data-speak={`Settle-up suggestions only; no payments have been made. Total recorded shared spend is ${speakRupees(settlement.totalExpenses)}. ${settlement.transfers.map((transfer) => `${memberName(transfer.fromMemberId)} is suggested to pay ${memberName(transfer.toMemberId)} ${speakRupees(transfer.amount)}`).join(". ")}. ${settlement.note}`}><DecisionVerdictCard title="Settle-up suggestions" badge="Suggestions only · no payment" captions={[`Recorded shared spend totals ${speakRupees(settlement.totalExpenses)}.`, ...settlement.transfers.map((transfer) => `${memberName(transfer.fromMemberId)} is suggested to pay ${memberName(transfer.toMemberId)} ${speakRupees(transfer.amount)}.`), settlement.note]} /><div className="digest-metric-row"><div><span>Total shared spend</span><strong>{money(settlement.totalExpenses)}</strong></div><div><span>Members</span><strong>{settlement.memberCount}</strong></div><div><span>Transfers suggested</span><strong>{settlement.transfers.length}</strong></div></div><h4>Suggested reimbursements</h4>{settlement.transfers.length ? settlement.transfers.map((transfer, index) => <div className="data-row" key={`${transfer.fromMemberId}-${transfer.toMemberId}-${index}`}><div><strong>{memberName(transfer.fromMemberId)} pays {memberName(transfer.toMemberId)}</strong><p>Suggested split-aware reimbursement</p></div><strong>{money(transfer.amount)}</strong></div>) : <p className="muted-copy">Everyone is settled against the recorded expenses.</p>}<div className="digest-balance-list">{settlement.balances.map((balance) => <div className="data-row" key={balance.memberId}><div><strong>{balance.displayName}</strong><p>Paid {money(balance.paid)} · fair share {money(balance.fairShare)}</p></div><span className={`status-pill ${balance.direction === 'receive' ? 'status-green' : balance.direction === 'pay' ? 'status-amber' : 'status-blue'}`}>{balance.direction === 'receive' ? `Receive ${money(balance.netBalance)}` : balance.direction === 'pay' ? `Pay ${money(Math.abs(balance.netBalance))}` : 'Settled'}</span></div>)}</div><Notice>{settlement.note}</Notice></div>}
          </Panel>}
        </div>}

        {activeTab === 'Calendar' && <Panel title="Household calendar" description="The upcoming items below come from saved tasks. Calendar events and meal plans are not persisted yet."><div className="calendar-week-strip">{Array.from({ length: 7 }, (_, index) => { const date = new Date(); date.setDate(date.getDate() + index); return <div key={date.toISOString()} className={`calendar-day ${index === 0 ? 'calendar-day-today' : ''}`}><span>{date.toLocaleDateString(undefined, { weekday: 'short' })}</span><strong>{date.getDate()}</strong></div> })}</div>{assignments.length ? [...assignments].sort((a, b) => a.assignedDate.localeCompare(b.assignedDate)).map((item) => <div className="calendar-event-row" key={item.assignmentId}><span className="calendar-event-dot" /><div><strong>{item.task}</strong><p>{new Date(item.assignedDate).toLocaleString()} · {memberName(item.memberId)}</p></div><span className={`status-pill ${item.status === 'completed' ? 'status-green' : 'status-blue'}`}>{item.status.replaceAll('_', ' ')}</span></div>) : <p className="muted-copy">No upcoming tasks yet. Add chores in the Chores section.</p>}</Panel>}

        {activeTab === 'Chat History' && <Panel title="Recent conversation" description="Messages and confirm/reject outcomes are shown here for this browser session; this is not a shared household transcript."><div className="history-messages">{chatMessages.map((chat) => <div key={chat.id} className={`chat-line ${chat.role === 'user' ? 'chat-line-user' : 'chat-line-assistant'}`}><div className="chat-bubble-wrap"><span className="chat-sender">{chat.role === 'user' ? 'You' : 'Accord'}</span><div className="chat-bubble">{chat.text}</div>{chat.actionLabel && chat.actionTab && <button className="chat-action-link" type="button" onClick={() => setActiveTab(chat.actionTab!)}>{chat.actionLabel}<ArrowUpRight size={14} /></button>}{chat.pendingAction && <div className="pending-action-card"><strong>Confirm task reassignment</strong><p>Reassign “{chat.pendingAction.taskName}” to {chat.pendingAction.targetName}?</p>{chat.pendingAction.status === 'pending' ? <div className="action-row"><button className="primary-button" type="button" disabled={busy} onClick={() => void confirmChatAction(chat.id, true)}>Approve & reassign</button><button className="secondary-button" type="button" onClick={() => void confirmChatAction(chat.id, false)}>Reject</button></div> : <Notice>{chat.pendingAction.status === 'approved' ? 'Approved and applied.' : 'Rejected. No change was made.'}</Notice>}<Notice>This action is a draft until you approve it. Approval runs the existing backend workflow as the selected demo member.</Notice></div>}</div></div>)}<button className="primary-button" type="button" onClick={() => setActiveTab('Home')}>Continue chatting</button></div></Panel>}

        {activeTab === 'Settings' && <div className="workflow-grid">
          <Panel title="Connection & demo data" description="Manage the local prototype. Reset replaces the current local demo dataset, so use it only when you want to start over.">
            <div className="settings-action-row"><button className="secondary-button" onClick={testBackend} disabled={apiLoading} type="button"><Activity size={15} />{apiLoading ? 'Testing…' : 'Test backend'}</button><span className="api-status" data-voice-skip>{apiStatus}</span></div>
            <button className="secondary-button full-width-button" onClick={() => void refreshAll()} disabled={refreshing} type="button"><RefreshCw size={15} />{refreshing ? 'Refreshing…' : 'Refresh household data'}</button>
            <button className="primary-button full-width-button" onClick={() => { if (window.confirm('Replace the current local demo data with the sample household? This cannot be undone.')) void resetDemo() }} disabled={busy} type="button"><RotateCcw size={15} />{busy ? 'Resetting…' : 'Reset demo scenario'}</button>
            <Notice>Prototype note: data is saved to a local SQLite file. The demo reset replaces this dataset. X-Member-Id is demo identity, not real authentication.</Notice>
          </Panel>
          <Panel title="Voice & assistant" description="The browser provides speech input and spoken replies where supported.">
            <VoiceControls compact />
            <div className="settings-info-row"><Mic size={17} /><div><strong>Voice input</strong><p>Uses browser speech recognition. Chrome support and microphone permission are required.</p></div></div>
            <div className="settings-info-row"><MessageSquareText size={17} /><div><strong>Assistant mode · {assistantMode === 'llm' ? 'LLM responding' : assistantMode === 'local' ? 'API unavailable' : assistantMode === 'guided_fallback' ? 'guided fallback' : assistantConfigured ? 'LLM configured' : 'guided mode'}</strong><p>Without an API key, Accord uses guided replies. An optional OpenAI-compatible model can be configured on the backend. Chat messages suggest workflows but cannot modify records directly. No live Alexa Skill is connected.</p></div></div>
            <div className="settings-info-row"><House size={17} /><div><strong>Household type</strong><p>{householdType} · {householdDescription}</p></div></div>
          </Panel>
        </div>}

        {activeTab === 'Interviews' && <div className="workflow-grid"><Panel title="Private check-in" description="Choose a consenting member, then submit their answers. Raw answers remain private."><label className="field-label">Checking in as<select value={selectedMemberId} onChange={(event) => setSelectedMemberId(event.target.value)}>{roommates.map((person) => <option key={person.memberId} value={person.memberId}>{person.displayName} · consent {person.consentStatus}</option>)}</select></label><button className="primary-button" disabled={busy || !selectedMember || selectedMember.consentStatus !== 'granted'} onClick={() => selectedMember && void startInterview(selectedMember)} type="button"><Play size={15} /> Start private check-in</button>{selectedMember?.consentStatus !== 'granted' && <Notice error>Consent needs to be granted before a private check-in can begin. Participation is optional.</Notice>}<form className="workflow-form" onSubmit={submitInterview} data-voice-skip aria-label="Private check-in form"><label>When are you usually busy?<textarea data-voice-skip value={interviewAnswers.availability} onChange={(event) => setInterviewAnswers((answers) => ({ ...answers, availability: event.target.value }))} placeholder="e.g. I have classes on weekdays until 4 PM" /></label><label>Tasks you prefer or want help with<textarea data-voice-skip value={interviewAnswers.chores} onChange={(event) => setInterviewAnswers((answers) => ({ ...answers, chores: event.target.value }))} placeholder="e.g. I can cook, but laundry is hard during exams" /></label><label>Shared bills or shopping preferences<textarea data-voice-skip value={interviewAnswers.expenses} onChange={(event) => setInterviewAnswers((answers) => ({ ...answers, expenses: event.target.value }))} placeholder="e.g. Split groceries equally" /></label><label>Anything else you want kept private?<textarea data-voice-skip value={interviewAnswers.preferences} onChange={(event) => setInterviewAnswers((answers) => ({ ...answers, preferences: event.target.value }))} placeholder="Optional. Don't include urgent safety details here." /></label><label>Interview session ID<input value={selectedSessionId} onChange={(event) => setSelectedSessionId(event.target.value)} placeholder="Start a check-in first" required /></label><button className="primary-button" disabled={busy || !selectedMember || selectedMember.consentStatus !== 'granted'} type="submit">{busy ? 'Saving…' : 'Complete private check-in'}</button></form></Panel><Panel title="Shared preferences" description="Only shareable derived summaries should be used in a joint plan.">{constraints.length === 0 ? <p className="muted-copy">No constraints loaded. Complete an interview or load shared summaries.</p> : constraints.map((constraint) => <div className="data-row" key={constraint.constraintId}><div><strong>{constraint.category.replaceAll('_', ' ')}</strong><p>{constraint.privacyClassification === 'private' ? 'Private preference — not shown to the household' : constraint.preferenceOrRequirement}</p></div><span className={`status-pill ${constraint.privacyClassification === 'private' ? 'status-rose' : 'status-green'}`}>{constraint.privacyClassification.replaceAll('_', ' ')}</span></div>)}<button className="secondary-button" onClick={() => void loadSharedConstraints()} disabled={busy} type="button">Load permitted shared preferences</button><Notice>Local rule-based extraction only. No external AI model is connected to this interview flow.</Notice></Panel></div>}

        {activeTab === 'Mediation' && <div className="workflow-grid mediation-layout">
          <Panel title="Share perspectives by consent" description="Each participant writes their own statement and explicitly opts into sharing it for this mediation. Raw statements are used only for this request and are not saved.">
            <div className="mediation-guidance"><ShieldCheck size={18} /><p>Household consent and per-statement sharing consent are separate. No private statement is included unless its member checks the sharing box.</p></div>
            {roommates.map((person) => <div className="mediation-member-input" key={person.memberId} data-voice-skip><div className="mediation-member-heading"><div className={`avatar ${person.color}`}>{person.initials}</div><div><strong>{person.displayName}</strong><span>{person.consentStatus === 'granted' ? 'Household consent granted' : `Household consent ${person.consentStatus}`}</span></div></div><label className="field-label" htmlFor={`mediation-${person.memberId}`}>What do you want Accord to understand?</label><textarea id={`mediation-${person.memberId}`} className="mediation-statement-input" data-voice-skip disabled={person.consentStatus !== 'granted'} maxLength={1600} value={mediationStatements[person.memberId] ?? ''} onChange={(event) => { const value = event.target.value; setMediationStatements((current) => ({ ...current, [person.memberId]: value })); if (!value.trim()) setSharingConsents((current) => ({ ...current, [person.memberId]: false })) }} placeholder={person.consentStatus === 'granted' ? 'Describe the problem and the need behind it without sharing anything you want to keep private.' : 'This member must grant household consent first.'} /><label className="sharing-consent-row"><input type="checkbox" checked={sharingConsents[person.memberId] === true} disabled={person.consentStatus !== 'granted' || !(mediationStatements[person.memberId] ?? '').trim()} onChange={(event) => setSharingConsents((current) => ({ ...current, [person.memberId]: event.target.checked }))} /><span>I agree to share this statement for this mediation request.</span></label></div>)}
            <button className="primary-button" type="button" disabled={mediationLoading || roommates.filter((person) => (mediationStatements[person.memberId] ?? '').trim() && sharingConsents[person.memberId] === true && person.consentStatus === 'granted').length < 2} onClick={() => void proposeMediation()}>{mediationLoading ? 'Preparing neutral options…' : 'Find three compromise options'}</button>
            <Notice>Only participants with granted household consent and checked sharing consent can be submitted. The result is a proposal, never an automatic action.</Notice>
          </Panel>
          <Panel title="Mediator output" description="A neutral restatement, the shared need, and three options with trade-offs.">
            {!mediationResult && <div className="empty-plan-illustration"><HeartHandshake size={24} /><strong>No mediation prepared yet</strong><p>Complete the consented perspectives on the left, then ask Accord to suggest compromises.</p></div>}
            {mediationResult && <div className="mediation-output" data-speak={`Mediation proposal. Shared underlying need: ${mediationResult.sharedNeed}. ${mediationResult.restatements.map((row) => `${memberName(row.memberId)} needs: ${row.needsRestatement}`).join(". ")}. Options: ${mediationResult.options.map((option, index) => `Option ${index + 1}, ${option.title}: ${option.proposal}. Trade-off: ${option.tradeOff}`).join(". ")}. Any chosen option is a draft and needs household confirmation.`}><span className={`status-pill ${mediationResult.mode === 'llm' ? 'status-green' : 'status-blue'}`}>{mediationResult.mode === 'llm' ? 'AI-assisted JSON' : 'Guided fallback'}</span><DecisionVerdictCard title="Mediation proposal" needsConfirmation captions={[`Shared underlying need: ${mediationResult.sharedNeed}.`, ...mediationResult.options.map((option, index) => `Option ${index + 1}: ${option.title}. ${option.proposal}. Trade-off: ${option.tradeOff}.`)]} /><h3>Shared underlying need</h3><p>{mediationResult.sharedNeed}</p><h3>Non-blaming restatements</h3>{mediationResult.restatements.map((row) => <div className="mediation-restatement" key={row.memberId}><strong>{memberName(row.memberId)}</strong><p>{row.needsRestatement}</p></div>)}<h3>Compromise options</h3>{mediationResult.options.map((option) => <div className="mediation-option-card" key={option.id}><div className="mediation-option-title"><strong>{option.title}</strong><span>Requires review</span></div><p>{option.proposal}</p><div className="mediation-tradeoff"><strong>Trade-off</strong><p>{option.tradeOff}</p></div><div className="mediation-option-actions"><button className="secondary-button" type="button" onClick={() => selectMediationOption(option)}>Use as counteroffer draft <ChevronRight size={14} /></button>{mediationSession?.status === 'open' && <button className="primary-button" type="button" disabled={mediationVoteLoading || !selectedMember || selectedMember.consentStatus !== 'granted'} onClick={() => void voteForMediationOption(option.id)}>{mediationSession.votes[selectedMember?.memberId ?? ''] === option.id ? 'Your vote ✓' : 'Vote for option'}</button>}</div>{mediationSession && <div className="vote-count-line">{mediationSession.voteCounts[option.id] ?? 0} household vote(s)</div>}</div>)}{mediationSession && <section className="mediation-voting-panel" data-speak={mediationSession.status === 'closed' ? `Mediation vote outcome. ${chosenMediationOption?.title ?? 'Winning option selected'}. ${chosenMediationOption?.proposal ?? ''}. ${mediationSession.tie ? `A tie was resolved by ${mediationSession.tieBreakRule}.` : ''} The result is a draft and needs household confirmation.` : undefined}><div><strong>{mediationSession.status === 'closed' ? 'Voting is closed' : 'Vote as the selected member'}</strong><p>{Object.keys(mediationSession.votes).length} vote(s) recorded. Votes may be changed until the session closes.</p><small>Stored: neutral restatements and options only. Raw private statements are not stored.</small></div>{mediationSession.status === 'open' ? <button className="primary-button" type="button" disabled={mediationVoteLoading || !selectedMember || !roommates.filter((person) => person.consentStatus === 'granted').every((person) => Boolean(mediationSession.votes[person.memberId]))} onClick={() => void closeMediationVoting()}>{mediationVoteLoading ? 'Closing…' : 'Close voting & create draft'}</button> : <Notice>{mediationSession.tie ? `Tie flagged. Tie-break rule: ${mediationSession.tieBreakRule}` : `Winning option: ${mediationSession.options.find((option) => option.id === mediationSession.winningOptionId)?.title ?? 'selected'}.`} Draft {mediationSession.draftAgreementId ?? 'agreement'} still needs ordinary member review and approval.</Notice>}</section>}{mediationSession?.status === 'closed' && chosenMediationOption && <DecisionVerdictCard title={`Mediation verdict: ${chosenMediationOption.title}`} needsConfirmation tone="success" badge={mediationSession.tie ? 'Tie-break applied' : 'Vote result'} captions={[chosenMediationOption.proposal, `Trade-off: ${chosenMediationOption.tradeOff}.`, mediationSession.tie ? `The tie was resolved with this documented rule: ${mediationSession.tieBreakRule}.` : 'This vote creates a draft only; normal agreement approval is still required.']} />}{mediationResult.cautions.map((caution, index) => <p key={index} className="muted-copy">{caution}</p>)}<Notice>{mediationResult.privacyNote}</Notice></div>}
          </Panel>
        </div>}

        {activeTab === 'Agreements' && <div className="workflow-grid"><Panel title="Fair plan & decisions" description="Generate a proposal from permitted derived constraints and make a voluntary decision."><label className="field-label">Acting as<select value={selectedMemberId} onChange={(event) => setSelectedMemberId(event.target.value)}>{roommates.map((person) => <option key={person.memberId} value={person.memberId}>{person.displayName}</option>)}</select></label><button className="primary-button" disabled={busy || !selectedMember} onClick={() => void generateAgreement()} type="button"><Sparkles size={15} /> Suggest a fair plan</button>{agreements.length > 0 && <label className="field-label">Choose plan<select value={selectedAgreement ? agreementKey(selectedAgreement) : ''} onChange={(event) => setSelectedAgreementKey(event.target.value)}>{agreements.map((agreement) => <option key={`${agreement.agreementId}-${agreement.version}`} value={agreementKey(agreement)}>{agreement.agreementId} · v{agreement.version} · {agreement.status}</option>)}</select></label>}{selectedAgreement ? <><div className="agreement-title" data-speak={`Agreement version ${selectedAgreement.version}. Status ${selectedAgreement.status}. Fairness score ${Math.round(selectedAgreement.fairnessScore * 100)} percent, heuristic, not a guarantee of fairness.`}><div className="agreement-symbol"><Scale size={20} /></div><div><strong>Plan version {selectedAgreement.version}</strong><span>{selectedAgreement.status} · fairness score {Math.round(selectedAgreement.fairnessScore * 100)}% (heuristic)</span></div></div><p className="muted-copy">{withNames(selectedAgreement.rationale)}</p>{selectedAgreement.status === 'draft' && <button className="primary-button" type="button" disabled={busy} onClick={async () => { if (!selectedMember) return; setBusy(true); setError(''); try { const result = await apiPost<{ agreement: Agreement }>(`/api/agreements/${selectedAgreement.agreementId}/versions/${selectedAgreement.version}/submit`, {}, { memberId: selectedMember.memberId }); setAgreements((current) => current.map((item) => item.agreementId === result.agreement.agreementId && item.version === result.agreement.version ? result.agreement : item)); setMessage('Draft submitted into the existing member-review workflow; it is not activated.'); await loadWorkflow() } catch (e) { setError(e instanceof Error ? e.message : 'Could not submit draft for review.') } finally { setBusy(false) } }}>Submit draft for member review</button>}{['active', 'changes_requested'].includes(selectedAgreement.status.toLowerCase()) && <DecisionVerdictCard title={selectedAgreement.status === 'active' ? 'Agreement activated' : 'Changes requested'} tone={selectedAgreement.status === 'active' ? 'success' : 'warning'} needsConfirmation={selectedAgreement.status !== 'active'} captions={[`The agreement is active after the required approvals.`, `${selectedAgreement.approvals.length} approval(s) and ${selectedAgreement.vetoes.length} change request(s) recorded.`]} />}{selectedAgreement.status === 'draft' && <DecisionVerdictCard title="Agreement draft" needsConfirmation captions={[`This is a draft agreement with ${selectedAgreement.proposal.length} proposed assignment(s). Review it before sharing; nothing is active yet.`]} /> }<div className="agreement-detail"><span>Approvals</span><strong>{selectedAgreement.approvals.length} / {roommates.length}</strong></div><div className="agreement-detail"><span>Vetoes</span><strong>{selectedAgreement.vetoes.length}</strong></div><div className="proposal-list">{selectedAgreement.proposal.map((item) => <div className="data-row" key={item.assignmentId}><div><strong>{item.task}</strong><p>{memberName(item.memberId)} · {item.frequency} · {item.estimatedEffort} min</p></div><span className="status-pill status-blue">{item.status}</span></div>)}</div><div className="action-row"><button className="primary-button" disabled={busy || selectedAgreement.status !== 'proposed'} onClick={() => void agreementAction('approve')} type="button"><Check size={15} /> Agree as {selectedMember?.displayName ?? 'member'}</button><button className="secondary-button" disabled={busy || selectedAgreement.status !== 'proposed'} onClick={() => void agreementAction('veto')} type="button">Request changes</button></div><form className="workflow-form" onSubmit={(event) => { event.preventDefault(); void agreementAction('counter') }}><label>Suggest a change<textarea value={counterText} onChange={(event) => setCounterText(event.target.value)} required maxLength={500} /></label><button className="secondary-button" disabled={busy || selectedAgreement.status !== 'proposed'} type="submit">Send suggestion</button></form><button className="primary-button" disabled={busy || selectedAgreement.status !== 'approved'} onClick={() => void agreementAction('activate')} type="button">Activate after required approvals</button><Notice>Participation is optional. The backend decides whether the plan meets activation requirements.</Notice></> : <div className="empty-plan-illustration"><Scale size={24} /><strong>No shared plan yet</strong><p>Complete a consented private check-in to create eligible shared preferences, then suggest a fair plan.</p></div>}</Panel><Panel title="Plan history" description="Version and decision history loaded from the backend.">{agreements.length ? agreements.map((agreement) => <div className="data-row" key={`${agreement.agreementId}-${agreement.version}`}><div><strong>{agreement.agreementId} · v{agreement.version}</strong><p>{agreement.status} · {agreement.approvals.length} approvals · {agreement.counteroffers.length} suggestions</p></div><button className="secondary-button" onClick={() => setSelectedAgreementKey(agreementKey(agreement))} type="button">Review</button></div>) : <p className="muted-copy">No plan versions yet.</p>}</Panel>
          <Panel title="Fairness lab · what if?" description="Compare Accord's workload-aware solver against round-robin. Preview only; no assignments are saved.">
            <label className="slider-label" htmlFor="preference-weight"><span>Preference influence</span><strong>{fairnessWeight}%</strong></label><input id="preference-weight" className="accord-range" type="range" min="0" max="100" step="5" value={fairnessWeight} onChange={(event) => setFairnessWeight(Number(event.target.value))} /><div className="range-scale"><span>Workload first</span><span>Preferences matter more</span></div><button className="primary-button" type="button" disabled={fairnessLoading || !selectedMember} onClick={() => void compareFairness()}>{fairnessLoading ? 'Comparing…' : 'Compare allocation methods'}</button>
            {fairnessComparison && <div className="fairness-comparison" data-speak={`Fairness comparison simulation. Accord workload spread is ${fairnessComparison.solver.workloadSpreadMinutes} minutes versus ${fairnessComparison.roundRobin.workloadSpreadMinutes} minutes for round-robin. ${fairnessComparison.note} This is a heuristic, not a guarantee of fairness.`}><h3 className="comparison-headline">Accord gap {fairnessComparison.solver.workloadSpreadMinutes} min vs {fairnessComparison.roundRobin.workloadSpreadMinutes} min for round-robin</h3><DecisionVerdictCard title="Fairness comparison" includeFairnessDisclaimer captions={[`Accord workload spread: ${fairnessComparison.solver.workloadSpreadMinutes} minutes. Round-robin workload spread: ${fairnessComparison.roundRobin.workloadSpreadMinutes} minutes.`, fairnessComparison.note]} /><div className="comparison-score-grid"><div><span>Accord heuristic</span><strong>{Math.round(fairnessComparison.solver.fairnessScore * 100)}%</strong><small>{fairnessComparison.solver.workloadSpreadMinutes} min workload spread</small></div><div><span>Round-robin</span><strong>{Math.round(fairnessComparison.roundRobin.fairnessScore * 100)}%</strong><small>{fairnessComparison.roundRobin.workloadSpreadMinutes} min workload spread</small></div></div>{(() => { const maxLoad = Math.max(1, ...fairnessComparison.solver.workloads.map((row) => row.projectedMinutes), ...fairnessComparison.roundRobin.workloads.map((row) => row.projectedMinutes)); return <><h4>Projected workload</h4><div className="comparison-method"><strong>{fairnessComparison.solver.algorithm}</strong>{fairnessComparison.solver.workloads.map((row) => <div className="workload-bar-row" key={`solver-${row.memberId}`}><div><span>{row.displayName}</span><strong>{row.projectedMinutes} min</strong></div><div className="workload-track"><span className="workload-fill workload-fill-violet" style={{ width: `${Math.max(2, row.projectedMinutes / maxLoad * 100)}%` }} /></div><p>{row.assignedTasks.length ? row.assignedTasks.join(', ') : 'No new tasks'}</p><small>{row.explanation}</small></div>)}</div><div className="comparison-method"><strong>{fairnessComparison.roundRobin.algorithm}</strong>{fairnessComparison.roundRobin.workloads.map((row) => <div className="workload-bar-row" key={`rr-${row.memberId}`}><div><span>{row.displayName}</span><strong>{row.projectedMinutes} min</strong></div><div className="workload-track"><span className="workload-fill workload-fill-blue" style={{ width: `${Math.max(2, row.projectedMinutes / maxLoad * 100)}%` }} /></div><p>{row.assignedTasks.length ? row.assignedTasks.join(', ') : 'No new tasks'}</p></div>)}</div></> })()}<Notice>{fairnessComparison.note}</Notice><p className="muted-copy">Explanation mode: {fairnessComparison.explanationMode ?? 'deterministic'}.</p></div>}
            <div className="feature-divider" />
            <div className="feature-action-heading"><div><strong>Eight-week fairness simulation</strong><p>Compare cumulative and weekly workload spreads on synthetic tasks. Reproducible seed: 7.</p></div><button className="secondary-button" type="button" disabled={fairnessSimulationLoading || !selectedMember} onClick={() => void simulateFairnessWeeks()}>{fairnessSimulationLoading ? 'Simulating…' : 'Run 8-week simulation'}</button></div>
            {fairnessSimulation && <div className="fairness-simulation" data-speak={`Eight-week synthetic data simulation. Accord keeps the cumulative gap at ${fairnessSimulation.accordCumulativeGapMinutes} minutes versus ${fairnessSimulation.roundRobinCumulativeGapMinutes} minutes for round-robin. This is a heuristic, not a guarantee of fairness. ${fairnessSimulation.note}`}><h3 className="comparison-headline">Accord keeps the cumulative gap at {fairnessSimulation.accordCumulativeGapMinutes} min vs {fairnessSimulation.roundRobinCumulativeGapMinutes} min for round-robin</h3><DecisionVerdictCard title="Eight-week simulation result" includeFairnessDisclaimer badge="Synthetic data" captions={[fairnessSimulation.headline, fairnessSimulation.note]} /><div className="simulation-weeks">{fairnessSimulation.weeks.map((week) => <div className="sim-week-row" key={week.week}><span>W{week.week}</span><div className="sim-bars"><div title={`Accord spread ${week.accord.workloadSpreadMinutes} min`}><small>A</small><span style={{ width: `${Math.max(2, week.accord.workloadSpreadMinutes / Math.max(1, week.accord.workloadSpreadMinutes, week.roundRobin.workloadSpreadMinutes) * 100)}%` }} /></div><div title={`Round-robin spread ${week.roundRobin.workloadSpreadMinutes} min`}><small>RR</small><span style={{ width: `${Math.max(2, week.roundRobin.workloadSpreadMinutes / Math.max(1, week.accord.workloadSpreadMinutes, week.roundRobin.workloadSpreadMinutes) * 100)}%` }} /></div></div><strong>{week.accord.workloadSpreadMinutes} / {week.roundRobin.workloadSpreadMinutes} min</strong></div>)}</div><h4>Cumulative workload by member</h4><div className="cumulative-workload-grid">{fairnessSimulation.accordCumulativeWorkloads.map((row) => { const baseline = fairnessSimulation.roundRobinCumulativeWorkloads.find((item) => item.memberId === row.memberId); return <div className="cumulative-workload-card" key={row.memberId}><strong>{row.displayName}</strong><span>Accord · {row.minutes} min</span><span>Round-robin · {baseline?.minutes ?? 0} min</span></div> })}</div><Notice>This is an eight-week synthetic-data simulation. Fairness scores and differences are heuristics, not guarantees.</Notice></div>}
          </Panel>
          <Panel title="Agreement clause drafter" description="Draft plain-English clauses from permitted derived summaries. Raw private interview answers are never sent to the drafter."><button className="primary-button" type="button" disabled={clausesLoading || !selectedMember} onClick={() => void draftAgreementClauses()}>{clausesLoading ? 'Drafting clauses…' : 'Draft shareable clauses'}</button>{draftedClauses && <div className="drafted-clauses"><span className="status-pill status-blue">{draftedClauses.mode} · {draftedClauses.status}</span>{draftedClauses.clauses.map((clause) => <div className="clause-card" key={clause.id}><strong>{clause.text}</strong><p>Source preference: {clause.sourcePreference}</p><small>{clause.reviewNote}</small>{clause.conflictsWith.length > 0 && <Notice error>Possible conflict with {clause.conflictsWith.join(', ')}. Discuss before agreeing.</Notice>}</div>)}{draftedClauses.conflicts.length > 0 && <div className="clause-conflicts"><strong>Potential conflicts to resolve</strong>{draftedClauses.conflicts.map((conflict, index) => <p key={index}>{conflict.reason ?? 'These preferences may be in tension.'}</p>)}</div>}<Notice>{draftedClauses.sourcePolicy} This draft does not activate an agreement.</Notice></div>}<Notice>Every clause needs member review; a generated draft is not an agreed household rule.</Notice></Panel>
        </div>}

        {activeTab === 'Privacy' && <div className="workflow-grid privacy-dashboard-grid"><Panel title="What Accord can see" description="Live configuration and data-boundary notes from the backend."><button className="secondary-button" type="button" disabled={privacyLoading} onClick={() => void loadPrivacyDashboard()}>{privacyLoading ? 'Refreshing…' : 'Refresh privacy configuration'}</button>{privacyDashboard ? <><DecisionVerdictCard title="Privacy dashboard summary" captions={[`Assistant mode: ${privacyDashboard.llmMode}. Provider: ${privacyDashboard.provider || 'none'}; model: ${privacyDashboard.model || 'not configured'}.`, `Can see: ${privacyDashboard.canSee.join("; ")}.`, `Excluded from processing: ${privacyDashboard.cannotSee.join("; ")}.`, privacyDashboard.identityNote]} /><div className="privacy-mode-card" data-speak={`Privacy dashboard. Current assistant mode: ${privacyDashboard.llmMode}. Provider: ${privacyDashboard.provider || 'none'}. Model: ${privacyDashboard.model || 'not configured'}. Can see: ${privacyDashboard.canSee.join("; ")}. Excluded from processing: ${privacyDashboard.cannotSee.join("; ")}. ${privacyDashboard.identityNote}`}><span>Current assistant mode</span><strong>{privacyDashboard.llmMode === 'provider' || privacyDashboard.llmMode === 'configured' ? 'Provider configured' : 'Deterministic / guided mode'}</strong><small>Provider: {privacyDashboard.provider || 'none'} · Model: {privacyDashboard.model || 'not configured'}</small><span className={`status-pill ${privacyDashboard.providerConfigured ? 'status-green' : 'status-blue'}`}>{privacyDashboard.providerConfigured ? 'Provider credentials configured' : 'No provider credentials configured'}</span></div><h4>Can see</h4>{privacyDashboard.canSee.map((item, index) => <div className="privacy-list-item" key={`can-${index}`}><Check size={15} /><span>{item}</span></div>)}<h4>Cannot see / excluded from processing</h4>{privacyDashboard.cannotSee.map((item, index) => <div className="privacy-list-item privacy-list-excluded" key={`cannot-${index}`}><ShieldCheck size={15} /><span>{item}</span></div>)}<Notice>{privacyDashboard.identityNote}</Notice>{privacyDashboard.limitations.map((limitation, index) => <Notice key={index}>{limitation}</Notice>)}</> : <p className="muted-copy">Loading privacy configuration…</p>}</Panel><Panel title="Privacy principles" description="These controls are intended to be visible and reviewable, not hidden behind AI branding."><div className="step-list"><div><span>01</span><section><strong>Consent before sharing</strong><p>Private perspectives are processed locally into neutral needs. Only permitted summaries and options may be saved for group voting.</p></section></div><div><span>02</span><section><strong>Explicit confirmation</strong><p>Proposals, meal plans and settle-up suggestions stay drafts until people confirm them through the relevant workflow.</p></section></div><div><span>03</span><section><strong>Prototype identity limitation</strong><p>The selected member header is a local demo identity. This build is not production-grade authentication.</p></section></div></div></Panel></div>}

        {activeTab === 'Monitoring' && <div className="workflow-grid"><Panel title="Household harmony" description="Review simulated signals, then decide whether to revisit a plan."><label className="field-label">Plan<select value={selectedAgreement ? agreementKey(selectedAgreement) : ''} onChange={(event) => setSelectedAgreementKey(event.target.value)}>{agreements.map((agreement) => <option key={`${agreement.agreementId}-${agreement.version}`} value={agreementKey(agreement)}>{agreement.agreementId} · v{agreement.version} · {agreement.status}</option>)}</select></label><button className="primary-button" disabled={busy || !selectedAgreement || !selectedMember} onClick={() => void generateDrift()} type="button"><Activity size={15} /> Check how the plan is going</button>{drift && <div className="drift-card"><span className="status-pill status-rose">{drift.severity} signal</span><h3>{drift.explanation}</h3><p>{drift.recommendedAction}</p><p className="muted-copy">Affected members: {drift.affectedMembers.map(memberName).join(', ') || 'Not specified'}</p><button className="primary-button" disabled={busy} onClick={() => void startRenegotiation()} type="button"><HeartHandshake size={15} /> Start a new check-in</button></div>}<div className="feature-divider" /><div className="feature-action-heading"><div><strong>Three-week workload drift</strong><p>On-demand check for members carrying more than the configured share of completed work.</p></div><button className="secondary-button" type="button" disabled={workloadDriftLoading || !selectedMember} onClick={() => void loadWorkloadDrift()}>{workloadDriftLoading ? 'Checking…' : 'Check workload drift'}</button></div>{workloadDrift && <div className="workload-drift-card" data-speak={`Three-week workload drift check. ${workloadDrift.alert ? workloadDrift.alert.message + ". Suggested rebalance: " + workloadDrift.alert.suggestion : `No member exceeded the ${Math.round(workloadDrift.threshold * 100)} percent review threshold in the last three weeks.`} This is a review suggestion, not an automatic reassignment.`}><DecisionVerdictCard title="Workload drift review" tone={workloadDrift.alert ? "warning" : "info"} captions={[workloadDrift.alert?.message ?? `No member exceeded the ${Math.round(workloadDrift.threshold * 100)} percent threshold.`, workloadDrift.alert?.suggestion ?? "No rebalance is suggested based on recorded data.", workloadDrift.note]} /><strong>{workloadDrift.alert ? 'Potential imbalance detected' : 'No threshold breach detected'}</strong><p>{workloadDrift.alert?.message ?? `No member exceeded the ${Math.round(workloadDrift.threshold * 100)}% review threshold in the last three weeks.`}</p>{workloadDrift.alert && <Notice>{workloadDrift.alert.suggestion}</Notice>}<div className="drift-member-grid">{workloadDrift.memberShares.map((member) => <div className="drift-member" key={member.memberId}><span>{member.displayName}</span><strong>{Math.round(member.share * 100)}%</strong><small>{member.completedMinutes} completed minutes</small></div>)}</div><Notice>{workloadDrift.note} This is not a judgment or an automatic task reassignment.</Notice></div>}<Notice>The timeline is simulated prototype data, not a live sensor or real Alexa event.</Notice></Panel><Panel title="How this works" description="Accord helps, but your household stays in control."><div className="step-list"><div><span>01</span><section><strong>Review what changed</strong><p>See which agreed task signals were flagged.</p></section></div><div><span>02</span><section><strong>Decide together</strong><p>Members can pause, decline or ask to revisit a plan.</p></section></div><div><span>03</span><section><strong>Check in privately</strong><p>Start optional member-specific check-ins before a new proposal.</p></section></div></div></Panel><Panel title="Weekly household digest" description="An on-demand seven-day summary of recorded tasks, spending and pending decisions."><button className="primary-button" type="button" disabled={digestLoading || !selectedMember} onClick={() => void loadWeeklyDigest()}>{digestLoading ? 'Preparing digest…' : 'Generate 7-day digest'}</button>{weeklyDigest && <div className="weekly-digest" data-speak={`Weekly household digest. ${weeklyDigest.summary.completedInWindow} of ${weeklyDigest.summary.tasksInWindow} tasks were completed over the last ${weeklyDigest.windowDays} days. ${weeklyDigest.summary.pendingAgreements} agreement decisions are pending. Recorded spending is ${speakRupees(weeklyDigest.summary.expensesTotal)}. ${weeklyDigest.insights.join(". ")}.`}><div className="digest-metric-row"><div><span>Tasks in window</span><strong>{weeklyDigest.summary.tasksInWindow}</strong></div><div><span>Completed</span><strong>{weeklyDigest.summary.completedInWindow}</strong></div><div><span>Missed</span><strong>{weeklyDigest.summary.missedTasks}</strong></div><div><span>Pending decisions</span><strong>{weeklyDigest.summary.pendingAgreements}</strong></div><div><span>Recorded spend</span><strong>{money(weeklyDigest.summary.expensesTotal)}</strong></div></div><h4>Suggested attention</h4>{weeklyDigest.insights.map((insight, index) => <p key={index} className="digest-insight"><Sparkles size={14} />{insight}</p>)}<DecisionVerdictCard title="Weekly household digest" captions={[`${weeklyDigest.summary.completedInWindow} of ${weeklyDigest.summary.tasksInWindow} tasks were completed in the last ${weeklyDigest.windowDays} days.`, `${weeklyDigest.summary.pendingAgreements} agreement decision(s) are pending. Recorded spending: ${speakRupees(weeklyDigest.summary.expensesTotal)}.`, ...weeklyDigest.insights]} /><Notice>{weeklyDigest.dataNote}</Notice></div>}</Panel></div>}

        <footer className="page-footer"><span>ACCORD © 2026 · BUILT FOR BETTER SHARED LIVING</span><span><LockKeyhole size={12} /> PRIVACY BY DESIGN <span className="footer-separator">·</span><Activity size={12} /> LOCAL DEMO · SIMULATED INTEGRATIONS</span></footer>
      </div>
    </section>
    {commandOpen && <div className="command-palette-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setCommandOpen(false) }}>
      <section className="command-palette" role="dialog" aria-modal="true" aria-labelledby="command-palette-title">
        <div className="command-palette-search"><Search size={18} /><label className="sr-only" id="command-palette-title" htmlFor="command-palette-input">Search Accord actions and records</label><input ref={commandInputRef} id="command-palette-input" value={commandQuery} onChange={(event) => { setCommandQuery(event.target.value); setCommandIndex(0) }} onKeyDown={(event) => { if (event.key === 'ArrowDown') { event.preventDefault(); setCommandIndex((current) => Math.min(current + 1, Math.max(paletteItems.length - 1, 0))) } else if (event.key === 'ArrowUp') { event.preventDefault(); setCommandIndex((current) => Math.max(0, current - 1)) } else if (event.key === 'Enter' && paletteItems[commandIndex]) { event.preventDefault(); openPaletteItem(paletteItems[commandIndex]) } }} placeholder="Search pages, members, tasks, agreements…" autoComplete="off" /><kbd>ESC</kbd><button type="button" className="palette-close" onClick={() => setCommandOpen(false)} aria-label="Close quick navigation"><X size={17} /></button></div>
        <div className="command-palette-results">
          {paletteItems.length ? paletteItems.map((item, index) => { const Icon = item.icon; return <button className={`command-result ${index === commandIndex ? 'command-result-active' : ''}`} type="button" key={`${item.tab}-${item.label}-${index}`} onMouseEnter={() => setCommandIndex(index)} onClick={() => openPaletteItem(item)}><span className="command-result-icon"><Icon size={16} /></span><span className="command-result-copy"><strong>{item.label}</strong><small>{item.description}</small></span><ChevronRight size={15} /></button> }) : <div className="command-empty"><Search size={20} /><strong>No matching results</strong><p>Try a page name, member name, task, or expense.</p></div>}
        </div>
        <div className="command-palette-footer"><span><Command size={13} /> Search across Accord</span><span>↑ ↓ move · Enter open</span></div>
      </section>
    </div>}
  </main>
}

function RoommateList({ roommates, loading, error, retry, memberName, onConsent, onInterview, busy }: { roommates: Roommate[]; loading: boolean; error: string; retry: () => void; memberName: (id: string) => string; onConsent: (person: Roommate, status: 'granted' | 'revoked') => void; onInterview: (person: Roommate) => void; busy: boolean }) {
  void memberName
  if (loading) return <p className="muted-copy">Loading household members…</p>
  if (error) return <div><Notice error>{error}</Notice><button className="secondary-button" onClick={retry} type="button">Try again</button></div>
  if (!roommates.length) return <div><p className="muted-copy">No household found. Use “Reset demo scenario” above to create the demo household and starter data.</p><p className="muted-copy">Demo reset replaces the current local demo dataset.</p></div>
  return <div className="roommate-list">{roommates.map((person, index) => <motion.div key={person.memberId} className="roommate-row roommate-row-expanded" initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: index * 0.04 }}><div className={`avatar large ${person.color}`}>{person.initials}</div><div className="roommate-info"><strong>{person.displayName}</strong><span>{person.role} · {person.privacyStatus.replaceAll('_', ' ')}</span></div><span className={`status-pill ${person.consentStatus === 'granted' ? 'status-green' : 'status-rose'}`}>Consent {person.consentStatus}</span><div className="member-actions">{person.consentStatus !== 'granted' ? <button className="secondary-button" disabled={busy} onClick={() => onConsent(person, 'granted')} type="button">Grant consent</button> : <><button className="secondary-button" disabled={busy} onClick={() => onInterview(person)} type="button">Interview</button><button className="secondary-button" disabled={busy} onClick={() => onConsent(person, 'revoked')} type="button">Revoke</button></>}</div></motion.div>)}</div>
}

export default App
