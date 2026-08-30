# Flight Log: Engineering Decision Log

Hackathon Yuno x Nauta, challenge #4, "The Agent on the Line".

Period covered: 2026-08-29 to 2026-08-30.

## About this log

This log reconstructs the decisions made while building NextWave, later branded
as 21stAgent. It was prepared for submission from the complete hackaton history.

The original team did not write every decision down at the moment it happened.
To avoid inventing a cleaner story after the fact, every entry identifies its
basis:

- **Explicit:** rationale exists in a commit, comment, README or roadmap.
- **Reconstructed:** rationale is inferred from the change and its immediate
  follow-up fixes.

Dates and order come from Git author timestamps. Commit hashes are the evidence
trail, not release versions.

## Final system snapshot

At submission, the integrated architecture is:

```text
Expo driver app -> FastAPI -> Redis ping queue -> detector
                                                |
                                                v
React operations UI <- SQLite <- RabbitMQ event bus
                                    |
                    +---------------+----------------+
                    |                                |
              voice agent                       dispatcher
          Twilio + OpenAI                 dashboard + Resend
          Gather or Realtime
```

The deployable unit remains one FastAPI process. Detector, agent, dispatcher and
threshold tuner are separate modules connected by events. Docker Compose runs
FastAPI, Redis and RabbitMQ; web and Expo run as development processes. Paid
effects are simulated unless explicitly enabled.

## Decision timeline

### FL-001 - Ship a vertical slice immediately

**Time:** 2026-08-29 11:43-15:46.  
**Status:** Accepted with acknowledged process debt.  
**Basis:** Explicit.  
**Evidence:** `8a04ba8`, `f96d1ad`, [root README](../README.md).

**Context:** The team initially requested only repository structure so it could
agree on the database first. A complete backend was generated instead: API,
SQLite, Redis, detector, event bus, voice agent, dispatcher and simulator.

**Decision:** Keep the working vertical slice as a prototype rather than throw
it away, while clearly labeling the database and architecture as drafts.

**Alternatives:** Delete the generated backend and restart from an agreed data
model; or silently treat the prototype as final.

**Trade-off:** The team gained a runnable end-to-end path very early, but lost
shared ownership of several initial choices and had to reconcile contracts
after implementation.

**Outcome:** Later commits retained the architecture but formalized style,
events, schemas and module ownership. The README records the scope mistake
instead of hiding it.

### FL-002 - Remove secrets and runtime artifacts from Git

**Time:** 2026-08-29 15:48.  
**Status:** Active.  
**Basis:** Explicit.  
**Evidence:** `e109bc2`.

**Context:** The first prototype produced `.env`, SQLite and Python cache files.

**Decision:** Untrack `.env`, databases and caches and keep configuration in
environment variables.

**Alternatives:** Commit demo credentials and state to make setup easier.

### FL-003 - Use one process, but enforce internal boundaries

**Time:** 2026-08-29 15:46-16:02.  
**Status:** Active for the hackathon.  
**Basis:** Explicit.  
**Evidence:** `f96d1ad`, `724d153`, [CODESTYLE](../backend/CODESTYLE.md),
[backend README](../backend/README.md).

**Context:** Separate services would require deployment, health management,
network contracts and more coordination than the hackathon allowed.

**Decision:** Run detector, caller, dispatcher and cron as asyncio tasks in one
FastAPI process. Preserve strict modules so they can be extracted later.

**Alternatives:** Independent microservices; Celery workers; direct logic in API
endpoints.

**Trade-off:** The monolith is fast to run and debug, but one process shares a
failure and scaling boundary. Module separation adds some ceremony without
independent deployment.

**Outcome:** `worker` decides whether and why to call, `caller` owns telephony
and session state, and `brain` owns dialogue. No agent framework was added.

### FL-004 - Prefer functions and small modules over frameworks

**Time:** 2026-08-29 16:02.  
**Status:** Active.  
**Basis:** Explicit.  
**Evidence:** `724d153`, [CODESTYLE](../backend/CODESTYLE.md).

**Context:** Framework abstractions would slow down a team still changing the
domain model.

**Decision:** Use functions, native asyncio, raw parameterized SQL and Pydantic
only at HTTP boundaries. Do not introduce an ORM, Celery, LangChain or another
agent framework.

**Alternatives:** SQLAlchemy, migration tooling, task queues and agent SDKs.

**Trade-off:** Less boilerplate and faster changes versus fewer schema and
workflow guarantees. Some conventions must be enforced by discipline.

**Outcome:** The backend stayed compact and inspectable through the hackathon.

### FL-005 - Split persistent and volatile state

**Time:** 2026-08-29 15:46.  
**Status:** Active; schema remains provisional.  
**Basis:** Explicit.  
**Evidence:** `f96d1ad`, `724d153`, [backend README](../backend/README.md).

**Context:** Trips, calls and alerts must survive restarts, while ping windows,
locks and active calls expire naturally.

**Decision:** Use SQLite as durable business truth and Redis for transient state
with TTLs.

**Alternatives:** Store everything in Redis; add PostgreSQL; keep everything in
process memory.

**Trade-off:** SQLite made the demo self-contained and durable with no database
service, but offers limited concurrency and no migration history. Two stores
require explicit ownership rules.

**Outcome:** SQLite stores trips, pings, events, calls, alerts and thresholds.
Redis stores last positions, detector windows, idempotency locks and call
sessions. The final schema was never formally approved as a production model.

### FL-006 - Make events the integration boundary

**Time:** 2026-08-29 15:46-16:02.  
**Status:** Active.  
**Basis:** Explicit.  
**Evidence:** `f96d1ad`, `724d153`, [backend README](../backend/README.md).

**Context:** The detector should not know about Twilio, and adding an alert
channel should not modify GPS ingestion.

**Decision:** Business facts pass through `bus.publish`; consumers register
with `bus.on`. API endpoints stay thin and do not call the agent directly.

**Alternatives:** Direct function calls between detector, agent and dispatcher.

**Trade-off:** Asynchronous processing adds eventual consistency and requires
idempotency, but decouples responsibilities and enables future extraction.

**Outcome:** Ping responses can show the prior status; clients poll operations
state. Event names live in one module.

### FL-007 - Persist the event before publishing it

**Time:** 2026-08-29 15:46.  
**Status:** Active.  
**Basis:** Explicit.  
**Evidence:** `f96d1ad`, [backend README](../backend/README.md).

**Context:** The operations timeline should not disappear when Redis or
RabbitMQ is unavailable.

**Decision:** Insert every business event into SQLite before sending it to the
transport.

**Alternatives:** Treat the broker as the only event record; implement a full
transactional outbox.

**Trade-off:** Synchronous SQLite writes add latency and are not a complete
outbox, but provide a durable audit trail with minimal implementation cost.

**Outcome:** The dashboard timeline survives broker restarts. Automatic replay
from SQLite was left out of scope.

### FL-008 - Support Redis locally and RabbitMQ in the integrated stack

**Time:** 2026-08-29 15:46; hardened at 18:21.  
**Status:** Active.  
**Basis:** Explicit.  
**Evidence:** `f96d1ad`, `0d1ccd1`, [PR #3](https://github.com/sleepydogo/next-wave-jaimeros/pull/3).

**Context:** Redis was already needed for state and was the cheapest local bus.
RabbitMQ offered durable delivery and a clearer future service boundary.

**Decision:** Select transport with `RABBITMQ_URL`: Redis pub/sub without it,
RabbitMQ when Compose provides it.

**Alternatives:** Require RabbitMQ everywhere; use only Redis; build a custom
queue.

**Trade-off:** Two paths improve local resilience and portability but increase
the test matrix. Redis pub/sub has no replay.

**Outcome:** Docker Compose always uses RabbitMQ. Redis remains a lightweight
fallback outside Compose.

### FL-009 - Default every paid effect to simulation

**Time:** 2026-08-29 15:46-16:02.  
**Status:** Active.  
**Basis:** Explicit.  
**Evidence:** `f96d1ad`, `724d153`, `4f71637`.

**Context:** Development could accidentally call real drivers, send email or
consume provider credit.

**Decision:** Default to `SIMULATE_CALLS=1` and
`SIMULATE_DISPATCH=1`. Require explicit flags and credentials for external
effects.

**Alternatives:** Use provider trial accounts in every development run.

**Trade-off:** Simulation cannot prove carrier behavior, but gives the team a
repeatable offline demo and a safe fallback.

**Outcome:** Simulated driver replies still traverse the brain and report path.
Startup was later changed to send no automatic pings after one version triggered
a real paid call.

### FL-010 - Keep the product scope to operational exceptions

**Time:** 2026-08-29 15:46.  
**Status:** Active, later expanded by off-route detection.  
**Basis:** Explicit.  
**Evidence:** `f96d1ad`, [root README](../README.md).

**Context:** The monitorista workflow includes many possible logistics actions,
but only a few could be demonstrated safely.

**Decision:** Start with arrival, port-ready, prolonged stop and abrupt slowdown.
Use a manual operations action for port authorization.

**Alternatives:** Integrate directly with port systems; build a general logistics
automation platform.

**Trade-off:** Narrow coverage makes the complete loop demonstrable. The manual
`port-ready` action is not a production integration.

**Outcome:** Four events map to three call goals. A later commit added off-route
as another explainable exception.

### FL-011 - Version and enrich the event contract

**Time:** 2026-08-29 16:51.  
**Status:** Active.  
**Basis:** Explicit.  
**Evidence:** `9777e26`, [event contract](../backend/agent/EVENTS.md).

**Context:** Agent and backend work proceeded in parallel. A call could not wait
for an unfinished context API or direct database lookup.

**Decision:** Standardize `{schema_version, event_id, type, payload, ts}` and put
worker identity, E.164 phone and operational context in triggering events.

**Alternatives:** Give the agent a context endpoint; let it query shared tables;
support both paths.

**Trade-off:** Enriched messages duplicate mutable data, but remove synchronous
runtime coupling. The team deliberately avoided implementing two context paths.

**Outcome:** `trip_id` became the MVP operation identifier and maps to
`report.operation_id`. Incompatible changes require schema version 2.

### FL-012 - Generate reports deterministically

**Time:** 2026-08-29 17:06.  
**Status:** Active.  
**Basis:** Explicit.  
**Evidence:** `a7e7565`, [agent specs](../backend/agent/SPECS.md).

**Context:** The dashboard needed a stable report containing what happened,
where, triage, resolution, next steps, diagnosis and worker feedback.

**Decision:** Build the report from the original event, call outcome and voice
signals with rules. Do not make a second LLM call.

**Alternatives:** Ask the model to synthesize the complete final report.

**Trade-off:** Deterministic prose is less flexible, but lowers token cost,
latency, hallucination risk and schema variance.

**Outcome:** Facts such as location never come from model invention. Every
terminal call status can produce the same report shape.

### FL-013 - Safety rules outrank model judgment

**Time:** 2026-08-29 17:06.  
**Status:** Active.  
**Basis:** Explicit.  
**Evidence:** `a7e7565`, `4f612ff`, [agent specs](../backend/agent/SPECS.md).

**Context:** Stress and fatigue inference from phone audio is uncertain and is
not a medical diagnosis.

**Decision:** The model may raise severity but may not lower rule-based triage.
High and critical cases require human review. Unknown results remain `unknown`,
not `normal`.

**Alternatives:** Let the LLM make the final safety decision; treat missing
analysis as a normal outcome.

**Trade-off:** More false-positive escalations in exchange for safer failure
behavior.

**Outcome:** Missing keys, invalid output and provider failures take a fallback
path with `needs_human=true`.

### FL-014 - Bound the conversation and require structured model output

**Time:** 2026-08-29 15:46; hardened at 17:06.  
**Status:** Active in Gather mode.  
**Basis:** Explicit.  
**Evidence:** `f96d1ad`, `a7e7565`, `c7658d3`.

**Context:** Phone calls need predictable duration, cost and parsing.

**Decision:** Use short Rioplatense Spanish, at most two questions, low
temperature, a small token budget and JSON output. Keep the OpenAI model
configurable, initially `gpt-4o-mini`.

**Alternatives:** Free-form dialogue; a larger model; unbounded retries.

**Trade-off:** Less natural conversation, but bounded spend and deterministic
downstream fields.

**Outcome:** Output is clamped and validated. Invalid output falls back safely.

### FL-015 - Make event delivery and call completion idempotent

**Time:** 2026-08-29 17:10.  
**Status:** Active, incomplete across related event types.  
**Basis:** Explicit.  
**Evidence:** `c7658d3`, `7822753`.

**Context:** RabbitMQ can redeliver and Twilio can repeat callbacks. Duplicate
calls are expensive and disruptive.

**Decision:** Lock source events by `event_id` and terminal completion by
`call_id` using Redis TTL keys.

**Alternatives:** Rely on providers for exactly-once delivery; create a database
idempotency table.

**Trade-off:** Redis locks are quick to add but depend on retention and do not
correlate different events from one physical incident.

**Outcome:** Exact redelivery does not duplicate calls or reports. A slowdown
followed by stopped can still create two emergency calls because IDs differ.

### FL-016 - Move ping detection off the HTTP request path

**Time:** 2026-08-29 17:32.  
**Status:** Active.  
**Basis:** Explicit.  
**Evidence:** `93ae7cc`, `60526da`.

**Context:** GPS ingestion should stay fast even when rules, geocoding or event
publication take longer.

**Decision:** Push pings to Redis list `pings:queue`; consume them with a
background detector using blocking pop.

**Alternatives:** Run detection synchronously inside `/driver/ping`.

**Trade-off:** Lower API latency and natural buffering versus eventual state and
new races in scripts that expected immediate processing.

**Outcome:** The simulator was changed to poll state rather than trust the ping
response.

### FL-017 - Tune thresholds, but constrain the tuner

**Time:** 2026-08-29 15:46; interval revised at 18:14.  
**Status:** Active experiment.  
**Basis:** Explicit plus reconstructed interval rationale.  
**Evidence:** `f96d1ad`, `bc9a4f4`.

**Context:** Fixed detector thresholds create false positives as conditions
change, but the hackathon had very little feedback data.

**Decision:** Add a threshold agent with heuristic fallback, strict bounds and
manual triggering. Increase its automatic interval from 5 to 30 minutes.

**Alternatives:** Static thresholds; unconstrained LLM tuning; frequent tuning.

**Trade-off:** Adaptation can improve detection, but sparse data makes aggressive
changes risky. Bounds preserve safety.

**Outcome:** Thresholds remain explainable, manually adjustable and clamped.

### FL-018 - Package the stack as a one-command demo

**Time:** 2026-08-29 17:49.  
**Status:** Active.  
**Basis:** Explicit.  
**Evidence:** `a6dfbd7`, `4f71637`, [Docker Compose](../docker-compose.yml),
[`start.sh`](../start.sh).

**Context:** Judges and teammates should not need to install Python, Redis and
RabbitMQ separately.

**Decision:** Use Docker Compose for backend infrastructure and `start.sh` to
start backend, web and Expo, seed one trip and print access URLs.

**Alternatives:** Manual local setup; containerize every frontend process.

**Trade-off:** One-command onboarding versus a development-oriented Compose with
host-mounted source and multiple local runtimes.

**Outcome:** Redis, RabbitMQ and SQLite use persistent volumes. External effects
remain opt-in through `--calls` and environment checks.

### FL-019 - Check RabbitMQ readiness at the protocol port

**Time:** 2026-08-29 18:07.  
**Status:** Active.  
**Basis:** Explicit.  
**Evidence:** `45d0e63`.

**Context:** RabbitMQ node `ping` succeeded before AMQP port 5672 accepted
connections, causing intermittent startup failures.

**Decision:** Use `rabbitmq-diagnostics check_port_connectivity` in the
healthcheck.

**Alternatives:** Keep node ping and add arbitrary sleeps.

**Trade-off:** A slightly more specific healthcheck removes timing guesses and
tests the dependency the backend actually uses.

**Outcome:** Compose waits for AMQP connectivity before starting FastAPI.

### FL-020 - Harden RabbitMQ without redesigning routing

**Time:** 2026-08-29 18:21.  
**Status:** Active.  
**Basis:** Explicit.  
**Evidence:** `0d1ccd1`, [PR #3](https://github.com/sleepydogo/next-wave-jaimeros/pull/3).

**Context:** The initial fanout path could lose messages and acknowledge handler
failures.

**Decision:** Keep one fanout exchange and worker queue, but make exchange,
queue and messages durable; add prefetch, dead-letter routing, envelope
validation, explicit ack/reject and clean shutdown.

**Alternatives:** Topic routing with one queue per component; leave the broker
ephemeral; retry forever.

**Trade-off:** Fanout matches the single-process consumer and avoids premature
service topology. It will need separate queues if modules become services.

**Outcome:** Failed or malformed messages reach `nextwave.dead`; `/ready`
reports transport readiness.

### FL-021 - Reverse geocode only emitted incidents

**Time:** 2026-08-29 18:14-18:19.  
**Status:** Active.  
**Basis:** Explicit.  
**Evidence:** `bc9a4f4`, `af93ba1`.

**Context:** A location label makes phone calls and reports understandable, but
geocoding every GPS ping would be expensive and slow.

**Decision:** Reverse geocode only when publishing an off-port incident, cache
for 24 hours at roughly 110-meter precision, and fall back to coordinates.

**Alternatives:** Geocode every ping; require Google for detection; show raw
coordinates only.

**Trade-off:** Cached labels can be slightly stale, but cost and provider
dependency fall dramatically.

**Outcome:** Plus codes and unnamed roads are discarded because they sound
unnatural when read over the phone.

### FL-022 - Replace WhatsApp dispatch with Resend email

**Time:** 2026-08-29 18:16.  
**Status:** Active.  
**Basis:** Explicit.  
**Evidence:** `99ec166`.

**Context:** Twilio WhatsApp onboarding would take too long, and the prototype
incorrectly used an email value as the WhatsApp destination.

**Decision:** Persist every alert for the dashboard. Send medium/high alerts by
Resend email using `httpx`; keep low alerts dashboard-only.

**Alternatives:** Wait for WhatsApp approval; dashboard only; add a Resend SDK.

**Trade-off:** Email is less immediate than WhatsApp but can be configured in
minutes. Plain HTTP avoids another dependency.

**Outcome:** Email is simulated by default, provider failure never rolls back
the alert, and an `event_id` lock suppresses duplicate emails. Duplicate alert
rows on redelivery remain possible.

### FL-023 - Start with Twilio Gather for the voice MVP

**Time:** 2026-08-29 15:46; hardened at 18:20.  
**Status:** Active as the default and fallback; no longer the only mode.  
**Basis:** Explicit.  
**Evidence:** `f96d1ad`, `20af62d`.

**Context:** A natural streaming voice agent was desirable, but the initial
deadline favored a predictable request-response flow.

**Decision:** Use Twilio `<Gather input="speech">` for transcription, OpenAI
chat completions for decisions and TwiML `<Say>` for responses.

**Alternatives:** Twilio Media Streams with OpenAI Realtime.

**Trade-off:** Gather is simpler, cheaper and easier to debug, but has rigid
turns, audible pauses and limited interruption.

**Outcome:** Three HTTP webhooks handle voice, speech and terminal status.
Twilio SDK work moved off the event loop; signatures, empty turns, CallSid and
terminal failures were hardened.

### FL-024 - Close provider gates before real calls

**Time:** 2026-08-29 18:59.  
**Status:** Active.  
**Basis:** Explicit.  
**Evidence:** `f6f2bea`, [PR #4](https://github.com/sleepydogo/next-wave-jaimeros/pull/4).

**Context:** Integration review found that Compose ignored real-mode flags,
nonterminal Twilio callbacks could close calls, `/voice` signed the wrong form
and runtime output violated its JSON Schema.

**Decision:** Make simulation flags overridable but safe by default; request only
terminal callbacks; validate full POST parameters; align runtime
`call.finished` with schema; configure the demo phone through env.

**Alternatives:** Disable validation for the demo or patch provider behavior
manually during presentation.

**Trade-off:** More preflight configuration in exchange for preventing paid,
invalid or prematurely terminated calls.

**Outcome:** `start.sh --calls` now checks all required values and warns which
number will be called before spending credit.

### FL-025 - Build web and mobile in parallel with mocks

**Time:** 2026-08-29 16:35-20:59.  
**Status:** Superseded by real API integration.  
**Basis:** Explicit and reconstructed.  
**Evidence:** `01622db`, `674bb48`, `b39203e`.

**Context:** UI development could not wait for every backend shape to settle.

**Decision:** Create independent Vite/React and Expo workspaces and allow mock
data while product flows and visual structure were designed.

**Alternatives:** Block UI work on final APIs; build UI directly against a
changing backend.

**Trade-off:** Parallel speed and visual iteration versus temporary contract
drift and duplicate data mappings.

**Outcome:** Web gained operations views and mobile gained trip/location flows.
Mocks were later removed from the production path.

### FL-026 - Add Realtime as a second voice architecture

**Time:** 2026-08-29 22:29-23:34.  
**Status:** Active, selectable with `VOICE_MODE`; Gather remains default.  
**Basis:** Explicit.  
**Evidence:** `ee793bd`, `162fa10`.

**Context:** Gather worked but sounded mechanical because every turn required a
webhook, transcription and new TwiML response.

**Decision:** Add Twilio Media Streams connected to OpenAI Realtime while
retaining `VOICE_MODE=gather` as a known fallback.

**Alternatives:** Replace Gather entirely; accept rigid turns; use another
managed voice-agent provider.

**Trade-off:** Realtime supports interruption and natural pacing but introduces
WebSockets, streaming state, more failure modes and materially higher OpenAI
audio cost.

**Outcome:** The final code supports both modes. Existing README statements that
Realtime is out of scope describe the earlier decision and are historically
stale.

### FL-027 - Keep audio in G.711 mu-law end to end

**Time:** 2026-08-29 22:29.  
**Status:** Active in Realtime mode.  
**Basis:** Explicit.  
**Evidence:** `ee793bd`.

**Context:** Twilio streams 8 kHz G.711 mu-law. Transcoding would add CPU,
latency and quality loss.

**Decision:** Configure OpenAI Realtime for the same wire format and relay audio
without transcoding.

**Alternatives:** Convert to PCM and back; use a separate audio pipeline.

**Trade-off:** Telephone-band audio limits fidelity, but removes a fragile
conversion layer.

**Outcome:** Media can flow directly between Twilio and OpenAI.

### FL-028 - Favor semantic turn detection over instant interruption

**Time:** 2026-08-29 23:34-00:14.  
**Status:** Active and tuned.  
**Basis:** Explicit.  
**Evidence:** `162fa10`, `87745d9`.

**Context:** Truck cabins contain engine noise, radio and brief sounds that can
falsely interrupt the agent or produce Whisper hallucinations.

**Decision:** Use semantic VAD, low eagerness, delayed interruption, an adaptive
noise floor and known-noise transcript filtering.

**Alternatives:** Interrupt on any audio; use only a fixed amplitude gate.

**Trade-off:** Waiting reduces false interruptions but can make genuine
interruptions feel slower. The first noise gate also hid soft yawns and needed
revision.

**Outcome:** Raw audio remained available for signal analysis while confidence
used the noise floor. Parameters are environment-configurable.

### FL-029 - Detect yawns acoustically, outside the LLM

**Time:** 2026-08-29 23:34.  
**Status:** Active experimental signal.  
**Basis:** Explicit.  
**Evidence:** `162fa10`.

**Context:** Fatigue may be audible even when the driver does not state it, but
asking a language model to infer every acoustic event is opaque.

**Decision:** Add explainable signal processing for sustained low-frequency,
low-variation audio and expose a browser microphone tester using the same
Realtime configuration.

**Alternatives:** LLM-only fatigue inference; no acoustic analysis; a trained
audio classifier.

**Trade-off:** Heuristics are interpretable and cheap but can produce false
positives and are not a medical diagnosis.

**Outcome:** Yawn evidence can raise operational risk. Human review remains the
final safety action.

### FL-030 - Add off-route detection with a simple corridor

**Time:** 2026-08-30 02:01.  
**Status:** Active demo approximation.  
**Basis:** Explicit.  
**Evidence:** `9f1f1c0`.

**Context:** The product needed to detect a driver going elsewhere, but no road
route geometry or navigation provider had been integrated.

**Decision:** Compare the current point against a tolerant 3 km straight-line
corridor from the first ping to the destination.

**Alternatives:** Google Directions route geometry; no deviation detection;
strict point-to-line distance.

**Trade-off:** The corridor is explainable and demo-ready but does not model
actual roads and can misclassify legitimate detours.

**Outcome:** `truck.off_route` became a runtime event and mobile gained manual
incident triggers. The formal JSON Schema was not updated, leaving contract
drift to resolve.

### FL-031 - Store mixed call audio locally

**Time:** 2026-08-30 02:01.  
**Status:** Active for demo observability.  
**Basis:** Explicit.  
**Evidence:** `9f1f1c0`.

**Context:** Operations needed playback alongside transcripts, while Twilio
recording added another paid service and provider dependency.

**Decision:** Mix available call audio locally, persist files beside SQLite and
expose them through operations APIs.

**Alternatives:** Twilio recording; transcript only; object storage.

**Trade-off:** Local recording controls cost and demo access but adds disk,
retention and privacy responsibility.

**Outcome:** Calls can be inspected with transcript and audio. Production
retention and consent remain unresolved.

### FL-032 - Correlate operational context by event time

**Time:** 2026-08-30 02:01.  
**Status:** Active.  
**Basis:** Explicit.  
**Evidence:** `9f1f1c0`.

**Context:** Showing the latest GPS point beside an old call can attach the
wrong location to the incident.

**Decision:** Match alerts and calls to the nearest ping by timestamp.

**Alternatives:** Always show the current/last position; store no location with
call context.

**Trade-off:** Timestamp joins are slightly more complex but preserve the
historical meaning of the event.

**Outcome:** Operations views show where the issue happened, not merely where
the truck is now.

### FL-033 - Prefer ngrok for mobile connectivity

**Time:** 2026-08-30 02:01.  
**Status:** Active for development.  
**Basis:** Explicit.  
**Evidence:** `9f1f1c0`, [`start.sh`](../start.sh).

**Context:** `localhost` on a physical phone points to the phone, and LAN IPs
only work when laptop and phone share a network.

**Decision:** Set Expo API URL to ngrok when configured, with LAN IP as fallback.

**Alternatives:** Require same-WiFi LAN access; deploy a permanent backend.

**Trade-off:** ngrok adds a tunnel and domain configuration but works across
networks and also serves Twilio webhooks.

**Outcome:** One public endpoint supports both physical mobile and telephony
integration.

### FL-034 - Keep the last good UI snapshot during outages

**Time:** 2026-08-30 02:01 and 08:18.  
**Status:** Active.  
**Basis:** Explicit.  
**Evidence:** `9f1f1c0`, `f43f4b6`.

**Context:** Operations data updates asynchronously and the backend can restart
during live development.

**Decision:** Poll backend data every five seconds, expose connection state and
retain the last successful snapshot on transient failure.

**Alternatives:** Clear the dashboard on every failed request; add WebSockets or
server-sent events.

**Trade-off:** Polling is simpler and resilient but data can be five seconds
stale. Retaining data requires clearly showing degraded connectivity.

**Outcome:** The dashboard remains useful through short backend reloads.

### FL-035 - Use mocks for design, then remove them from runtime

**Time:** 2026-08-30 04:05-08:20.  
**Status:** Completed transition.  
**Basis:** Explicit.  
**Evidence:** `efcc093`, `8774671`, `7aa3e1e`, `fd50228`, `e300fe1`,
`f43f4b6`.

**Context:** The operations UI needed rapid visual iteration while API mappings
and status vocabulary were changing.

**Decision:** Temporarily make mock data the design default, iterate on a common
operational workspace, then remove the switch and reconnect every view to
backend APIs before submission.

**Alternatives:** Design only against live data; ship a mock toggle in the final
product.

**Trade-off:** Mocks accelerated UI work but created integration debt. Removing
them late concentrated API reconciliation risk near the deadline.

**Outcome:** Trips, calls, alerts, metrics, maps, transcript and audio use real
backend data. UI connection state is visible.

### FL-036 - Distill the visual system around operations

**Time:** 2026-08-30 04:05-08:41.  
**Status:** Active.  
**Basis:** Reconstructed from iterative commits and design documents.  
**Evidence:** `efcc093`, `8774671`, `7aa3e1e`, `fd50228`, `e300fe1`,
`2c0e1f2`, `923840d`,
[design system](./autonomous-logistics-design-system.md).

**Context:** Early documents proposed competing palettes, typography and card
styles. The product needed a coherent operations surface rather than a generic
template.

**Decision:** Unify themes, reduce decorative landing complexity, standardize
lists/details/statuses and finish with responsive 21agents branding.

**Alternatives:** Preserve both visual systems; keep starter branding; optimize
for marketing visuals over operational density.

**Trade-off:** Repeated refinement consumed frontend time but produced a more
coherent workspace and removed generated artifacts.

**Outcome:** Brand identity and operational components share one shell. An
unintended README edit was reverted separately (`9566dca`) rather than bundled.

### FL-037 - Compare cost per managed event

**Time:** 2026-08-29 15:46.  
**Status:** Active model, stale for Realtime.  
**Basis:** Explicit.  
**Evidence:** `f96d1ad`, [cost model](../backend/app/costs.py).

**Context:** A monitorista spends time watching, retrying and recording outcomes,
not only speaking. Call-minute comparison understates human work.

**Decision:** Compare agent and human per managed event. Parameterize provider
rates and record usage per call.

**Alternatives:** Compare only voice minutes; present no cost claim.

**Trade-off:** The metric better reflects operations but depends on assumed
human minutes and provider tariffs.

**Outcome:** The dashboard shows modeled agent cost versus human equivalent.
Rates were estimates, and the model still counts Gather ASR rather than Realtime
audio tokens when Realtime mode is used.

### FL-038 - Test one external boundary at a time

**Time:** 2026-08-29 22:29.  
**Status:** Adopted strategy; automation incomplete.  
**Basis:** Explicit.  
**Evidence:** `efc4ed3`,
[unmerged E2E roadmap](https://github.com/sleepydogo/next-wave-jaimeros/blob/agent-service/backend/agent/E2E_TESTING_ROADMAP.md).

**Context:** Twilio, OpenAI, ngrok, RabbitMQ and Resend can all fail independently
and some spend money.

**Decision:** Validate in layers: all simulated; real OpenAI with simulated
phone; Resend; Twilio; then one complete external-effects run.

**Alternatives:** Enable every provider and debug the full system at once.

**Trade-off:** Layered testing takes more setup but isolates failure and controls
spend.

**Outcome:** Integration gates found and fixed several real issues in `f6f2bea`.
No automated test files were merged; final verification still relies heavily on
simulators, Swagger and provider smoke tests.

## Decisions that changed

| Earlier decision                      | Later decision                               | Why it changed                                                         |
| ------------------------------------- | -------------------------------------------- | ---------------------------------------------------------------------- |
| Build only folder structure           | Keep an unexpectedly complete vertical slice | Working software accelerated the hackathon, despite process debt       |
| Redis pub/sub as practical default    | RabbitMQ in Compose, Redis fallback locally  | Durable delivery became valuable once modules integrated               |
| Twilio Gather only                    | Gather plus selectable OpenAI Realtime       | Natural interruption and pacing justified added complexity             |
| Email + WhatsApp dispatcher           | Dashboard + Resend email                     | WhatsApp onboarding and an unsafe destination mapping blocked the demo |
| Synchronous ping detection            | Redis-backed asynchronous detector           | API latency and buffering mattered more than immediate status          |
| UI backed by mocks                    | UI backed only by live API data              | Visual work finished and integration correctness became the priority   |
| Seed startup pings                    | Seed no automatic pings                      | Any automatic detection could trigger a paid real call                 |
| Show latest truck position with calls | Match nearest ping by timestamp              | Historical incidents need historical location                          |

## Deliberately deferred

These were conscious scope boundaries, not accidental omissions:

- Separate deployment of agent, detector and dispatcher.
- PostgreSQL, ORM and formal migrations.
- Direct integration with port/depot systems.
- Production route geometry for off-route detection.
- WhatsApp notifications.
- Irreversible autonomous actions without human approval.
- Production audio retention, consent and access policy.
- A trained acoustic fatigue classifier.

## Open risks at submission

### Cross-event duplicate calls

Event-level idempotency does not correlate `truck.slowdown` followed by
`truck.stopped`. One physical incident can still produce two emergency calls.

### Contract drift for off-route

`truck.off_route` exists in runtime code but is absent from
`backend/agent/event.schema.json`.

### Realtime cost visibility

The dashboard cost model uses Gather/ASR assumptions and does not include
OpenAI Realtime audio-token pricing.

### Alert row duplication

Resend delivery is deduplicated, but SQLite alert insertion occurs before the
email lock and can duplicate rows after broker redelivery.

### Provisional data model

SQLite shipped successfully for the demo, but the team never recorded formal
approval of the schema or trip state machine for production.

### Test automation gap

The E2E strategy is documented and provider gates were fixed, but no automated
pytest, browser or mobile test suite was merged.

### Documentation drift

Some earlier READMEs still describe web/mobile as empty, Gather as the only
voice path, WhatsApp dispatch and unmerged decisions. This log uses current code
and commit history as the final source of truth.

### Provider validation and pricing

Real provider behavior depends on credentials, geo permissions, verified phone
numbers and account limits. Twilio Argentina mobile pricing and OpenAI Realtime
costs must be checked against actual invoices before making production claims.

## Evidence index

### Pull requests

- [PR #1: backend documentation and API contract](https://github.com/sleepydogo/next-wave-jaimeros/pull/1)
- [PR #2: agent contract, reports and idempotency](https://github.com/sleepydogo/next-wave-jaimeros/pull/2)
- [PR #3: detector, providers and infrastructure](https://github.com/sleepydogo/next-wave-jaimeros/pull/3)
- [PR #4: integration/provider gates](https://github.com/sleepydogo/next-wave-jaimeros/pull/4)
- [PR #5: manual call trigger documentation](https://github.com/sleepydogo/next-wave-jaimeros/pull/5)
- [PR #6: final operations UI](https://github.com/sleepydogo/next-wave-jaimeros/pull/6)

### Core documents

- [Root project README](../README.md)
- [Backend architecture](../backend/README.md)
- [Backend code style](../backend/CODESTYLE.md)
- [Agent specification](../backend/agent/SPECS.md)
- [Event contract](../backend/agent/EVENTS.md)
- [Agent implementation roadmap](../backend/agent/ROADMAP.md)
- [Dispatcher roadmap](../backend/agent/DISPATCHER_ROADMAP.md)
- [Twilio roadmap](../backend/agent/TWILIO_ROADMAP.md)
- [RabbitMQ and Docker roadmap](../backend/agent/RABBITMQ_DOCKER_ROADMAP.md)
- [E2E testing roadmap on `agent-service`](https://github.com/sleepydogo/next-wave-jaimeros/blob/agent-service/backend/agent/E2E_TESTING_ROADMAP.md)
- [Manual call trigger](../backend/agent/TRIGGER_CALL.md)
- [Operations design system](./autonomous-logistics-design-system.md)
- [Earlier product design proposal](./nextwave-plan-diseño.md)

## Closing note

The central hackathon trade-off was consistent: choose the smallest mechanism
that completed the operational loop, retain a simulated fallback, and add
reliability only where failure would call a real person, lose an event or hide a
safety issue. The largest deliberate reversal was adding Realtime voice after
Gather had already proven the flow. Keeping both modes preserved the reliable
demo path while allowing the team to show a more natural agent.
