# Accord Alexa intent adapter (prototype)

Accord now includes an Alexa Skills Kit request/response adapter at `POST /api/alexa/skill-request`. It handles `LaunchRequest`, `SessionEndedRequest`, built-in help/stop/cancel/fallback intents, and these custom intent names:

- `AccordHelpIntent`
- `PlanMyWeekIntent` (also accepts `HouseholdPlanIntent`)
- `ResolveDisagreementIntent` (also accepts `MediationHelpIntent`)

Example test request:

```json
{
  "version": "1.0",
  "request": {
    "type": "IntentRequest",
    "intent": { "name": "PlanMyWeekIntent", "slots": {} }
  }
}
```

Expected response shape:

```json
{
  "version": "1.0",
  "response": {
    "outputSpeech": { "type": "PlainText", "text": "Let's plan a calmer week..." },
    "shouldEndSession": false
  }
}
```

## Alexa Developer Console setup

1. Create an Alexa-hosted or custom skill in the Alexa Developer Console.
2. Add `AccordHelpIntent`, `PlanMyWeekIntent`, and `ResolveDisagreementIntent` with sample utterances such as:
   - `what can you help with`
   - `help me plan my week`
   - `help us divide chores`
   - `help us resolve a disagreement`
3. Configure the custom endpoint only after the backend is deployed behind HTTPS and Alexa request signature and timestamp verification are implemented.
4. Test the request envelope locally with the JSON above before configuring a real skill endpoint.

## Security boundary

This is a local Skills Kit-compatible request handler, **not a deployed or production-verified Alexa Skill**. It intentionally does not claim to authenticate the caller or read private interview content. Do not expose `/api/alexa/skill-request` publicly until Alexa signature/timestamp verification, replay protection, rate limiting, account/household authorization, and HTTPS deployment are implemented. For the prototype, the intent helps users discover supported workflows and directs sensitive steps back to Accord's consent-aware interface.

## Local adapter protection (prototype only)

The route is disabled by default. To exercise it locally, set `ACCORD_ALEXA_ENABLED=true` and configure `ACCORD_ALEXA_SHARED_SECRET`. Requests must include an `X-Accord-Alexa-Secret` header with that value. Do not use a real secret in a public demo or commit it to the repository. This header is only a temporary local guard: it does **not** verify Amazon's request signature or timestamp and does not provide account linking or household authorization. Keep the route inaccessible from the public internet until real Skills Kit verification, replay protection and authorization are implemented.
