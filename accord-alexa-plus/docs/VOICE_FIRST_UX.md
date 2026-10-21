# Accord voice-first UX design

## Product direction

Accord is a household planner first and a mediator when a member chooses to use that feature. It supports families, couples, roommates, shared homes and other arrangements.

## Main user journey

1. **Home** — “What would you like to plan at home today?” with one chat composer, voice input and simple suggested actions.
2. **My Household** — choose a household type, view members and consent, and add people with flexible roles.
3. **Plans** — review the tasks and existing agreement state.
4. **Chores / Bills / Calendar** — manage actual backend tasks and expenses, and view due assignments.
5. **Private check-in / Fair plan / Household balance** — optional, separate workflows for mediation, negotiation and simulated drift.

## Voice and assistant boundary

The browser microphone uses SpeechRecognition/webkitSpeechRecognition when available; spoken replies use SpeechSynthesis. This is cross-browser local voice support, not an Alexa-branded voice and not an Alexa Skill. The current chat assistant is deterministic guided routing and does not call an external GenAI service. A production GenAI integration should be server-side, configured through environment variables, and should receive only data authorized for the current request.

## Household type choice

Family, Couple, Roommates, Shared home and Other are presentation/onboarding preferences stored in browser localStorage. The backend member role is still a free string so role labels can represent Parent, Child, Partner, Sibling, Roommate, Housemate, Grandparent and other household-specific relationships. Changing the type in the current prototype does not create a new server-side household.

## Privacy notes

- Keep pending consent as pending; do not treat it as approval.
- Private check-ins remain optional.
- Chat messages are held in React state for the current page session and are not stored by the backend.
- The in-memory backend and `X-Member-Id` remain prototype-only, not production authentication or persistent storage.
