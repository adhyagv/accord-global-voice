# Demo Script (<3 minutes)

## Demo objective
Show end-to-end simulated flow for three roommates negotiating chores while preserving privacy boundaries.

## Timeline (approx. 2m 40s)

### 0:00-0:20 — Setup and framing
- Introduce Accord as a **simulated** Alexa+ household diplomat prototype.
- State scenario: three roommates with recurring chore conflict.

### 0:20-0:55 — Private interviews
- Show three separate private interview views.
- Call out hard privacy rule: raw member messages never cross prompts.

### 0:55-1:30 — Constraint extraction and fairness solve
- Display sanitized derived constraints.
- Run deterministic solver and show reproducible assignment output + fairness breakdown.

### 1:30-2:00 — Agreement creation
- Review proposed plan, perform one member-approved manual swap, confirm agreement version.

### 2:00-2:40 — Monitoring and 14-day drift
- Show simulated completion/activity/check-in timeline.
- Trigger drift example at day 14 and present renegotiation recommendation.

## Explicit simulation callouts
- Simulated Alexa+ voice
- Simulated notifications
- Simulated calendar
- Simulated household activity signals

## Non-goals for demo
- No real third-party integrations
- No production deployment/compliance claims

## Updated feature path (optional, 60–90 seconds)

- **Mediation room:** Enter two consented sample perspectives, explicitly tick each sharing-consent box, generate three options, and use one as a counteroffer draft. Point out that the option is not applied automatically.
- **Fairness lab:** Change the preference-influence slider and compare Accord with the round-robin baseline. Explain the projected workloads and that the score is a heuristic.
- **Agreement clause drafter:** Draft clauses from shareable derived summaries, show a potential conflict if present, and state that the clauses still need review.
- **Bills:** Run Optimize settle-up and show the suggested transfers. State clearly that no payment occurred.
- **Monitoring:** Generate the on-demand 7-day digest and call out the simulated-data notice.
- **Alexa adapter:** If demonstrating the handler, use the JSON request in `docs/ALEXA_INTENT.md`; say that a live Alexa Console deployment and signature verification remain separate integration work.


## Updated judge path (about 90 seconds)

1. Reset the demo once, then open **Private check-in** and complete a demo member interview with consent. Call out that shared planning uses only shareable derived constraints.
2. Open **Fair plan & decisions** and run the single allocation comparison. State the projected gap headline, then run the seeded eight-week simulation and show the cumulative chart. Say explicitly that these are synthetic projections from a deterministic heuristic, not a fairness guarantee.
3. Open **Mediation room**, add at least two perspectives with both household consent and per-statement sharing consent, and generate the neutral options. A saved session contains only restatements/options—not the raw statements. Vote as each consenting demo member, close voting, and show the winner plus the tie-break notice if a tie occurs. The resulting agreement is a draft.
4. Open **Agreements** and explicitly submit the draft for normal member review. Demonstrate that it cannot activate without required approvals.
5. Open **Bills**, record an expense with a subset/custom split if useful, and run settle-up. Explain that transfers are suggestions only and no payment is made.
6. Open **Monitoring**, generate the seven-day digest, then run the three-week workload drift check. Explain that it reads recorded completed tasks and only displays an on-demand suggestion—no notification or reassignment is automatic.
7. Open **Privacy dashboard** to show actual provider mode, data boundaries and the demo-identity limitation.
8. If demonstrating the Alexa adapter, keep it local, enable it only with an environment flag/shared-secret header, and state that Amazon signature verification and live Alexa+ deployment are still incomplete.
9. Where useful, press **Hear the verdict** on the fairness, mediation, agreement, settle-up or weekly digest card. Captions remain visible, speech uses the browser only, and the Voice on toggle controls playback. State that fairness remains a heuristic.
