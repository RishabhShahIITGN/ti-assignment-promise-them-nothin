User: # RelayAPI Rate Limiter Assignment — Build, Verify, and Document
You are helping me complete the RelayAPI rate-limiting engineering assignment in this repository.

## 1. First: read and understand the assignment
Before writing any code, inspect:

- `assignment.md`
- `briefs/cto-memo.md`
- `briefs/support-lead-memo.md`
- `briefs/platform-context.md`
The assignment intentionally contains a conflict between the CTO and Head of Customer Support. **Do not treat `assignment.md` as a cleaned-up specification that overrides the memos.**

Your first task is to identify:

1. What the CTO requires.
2. What the Support Lead requires.
3. Where the requirements genuinely conflict.
4. Which requirement you will prioritize and why.
5. What behavior you will explicitly reject or compromise on.
6. The implications of that decision for the rate-limiting algorithm and distributed architecture.
Do not start implementation until you have reasoned through these points.

---

# 2. Goal
Build a **thin but realistic vertical slice** of RelayAPI that demonstrates:

- Per-customer RPM rate limiting.
- Correct behavior at quota boundaries.
- Correct behavior when requests are distributed across multiple application instances.
- A realistic distributed coordination mechanism.
- A load-generating harness that clearly demonstrates the limiter's behavior.
- Tests that specifically target common naive/incorrect implementations.
The solution should be narrow, robust, easy to run locally, and honest about its limitations.

Do NOT build unnecessary production features such as authentication, billing, dashboards, Kubernetes deployment, a frontend, or a full API gateway.

---

# 3. Technology choice
You may choose the language, framework, and dependencies.

Prefer a stack that:

- Is free and easy to install.
- Can run on a normal laptop.
- Can realistically demonstrate multiple application instances.
- Has good support for concurrency and HTTP.
- Allows us to keep the implementation small and understandable.
Before implementation, briefly explain why you selected the stack.

For distributed coordination, prefer a lightweight local setup such as Redis if appropriate.

If Redis is used:

- Document why it is needed.
- Provide an easy local setup.
- Keep the number of dependencies minimal.
- Do not pretend Redis makes the system infinitely scalable.

---

# 4. Algorithm decision
Choose one of:

- Token bucket
- Sliding window
- Fixed window
- Leaky bucket
- Hybrid
Do not choose based only on implementation simplicity.

Evaluate the algorithm against RelayAPI's actual constraints:

- Per-customer contracted RPM quota.
- Northwind's nightly traffic spike.
- Fairness.
- Burst behavior.
- Boundary correctness.
- Three stateless application nodes.
- No sticky sessions.
- Distributed coordination.
- Race conditions under concurrent requests.
Document why the selected algorithm is appropriate.

Pay particular attention to what "RPM" actually means and whether a customer's quota should permit bursts.

If you choose token bucket, explicitly define:

- Rate/refill rate.
- Bucket capacity.
- Whether capacity equals RPM or is different.
- How timestamps are handled.
- What happens when the bucket has insufficient tokens.
- Whether requests consume one token.
- How `Retry-After` is calculated.
If you choose another algorithm, provide the equivalent precise definition.

---

# 5. Distributed architecture
The application must NOT rely on in-process memory for the authoritative rate-limit state.

The service should behave correctly when requests are distributed across three independent application instances.

For example:

Client
↓
Load Balancer
↓
┌─────────────┬─────────────┬─────────────┐
│ App Node 1 │ App Node 2 │ App Node 3 │
└──────┬──────┴──────┬──────┴──────┬──────┘
│ │ │
└─────────────┼─────────────┘
↓
Redis

The exact architecture may differ if you have a better design, but the important requirement is that rate-limit state is shared and atomic.

Explain:

- Why local process memory is incorrect.
- How multiple nodes coordinate.
- How concurrent requests are handled atomically.
- What race condition a naive GET → modify → SET implementation would have.
- How your implementation avoids that race.
If Redis is used, prefer an atomic operation or Lua script/transaction where necessary.

---

# 6. HTTP API
Create a minimal API.

For example:

`GET /health`

should return a successful health response.

Create one endpoint representing a metered RelayAPI operation, for example:

`GET /api/resource`

The request must identify a customer, e.g.:

`X-Customer-ID: northwind`

The endpoint should return:

### Allowed request
HTTP `200`

Include useful rate-limit information in headers, such as:

- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`

### Rejected request
HTTP `429`

Include:

- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `Retry-After`
Use sensible semantics and document them.

Do not over-engineer the API.

---

# 7. Customer configuration
Support at least multiple customers with different quotas.

For example:

- Northwind: high contracted RPM
- Another customer: lower RPM
Do not hard-code the implementation specifically around Northwind.

The rate limiter should conceptually operate as:

customer_id → independent rate-limit state

Demonstrate that one customer's traffic does not consume another customer's quota.

---

# 8. Boundary correctness is extremely important
This assignment explicitly evaluates whether the limiter behaves correctly at boundaries.

Write tests and harness scenarios for:

### Scenario A — exactly at quota
If the quota is N requests/minute, demonstrate what happens when exactly N valid requests are made.

### Scenario B — one request beyond quota
Send N + 1 requests in the relevant time interval.

The output must make it immediately obvious that the first N are allowed and the additional request is rejected, according to the algorithm semantics you documented.

### Scenario C — concurrent requests
Fire many requests concurrently when only a small number of tokens/requests remain.

Verify that the limiter does not accidentally allow more requests than the available quota.

This is especially important because:

```
read state
→ calculate new state
→ write state
```
is unsafe when multiple requests execute simultaneously.

### Scenario D — multiple application instances
Run three application instances.

Send traffic through them in a way that causes requests from the same customer to reach different instances.

Verify that the customer's quota is enforced globally rather than independently per process.

This test should expose an incorrect implementation such as:

```
Node 1: 10 requests allowed
Node 2: 10 requests allowed
Node 3: 10 requests allowed

Actual customer quota: 10
```
which would incorrectly allow 30 requests.

### Scenario E — independent customers
Verify that:

```
customer A traffic
```
does not consume:

```
customer B quota
```

### Scenario F — refill / recovery
If your algorithm supports gradual token refill, demonstrate that rejected traffic can become allowed again after sufficient time.

Keep this test deterministic and avoid unnecessarily long sleeps.

### Scenario G — boundary timing
Test requests immediately before and immediately after the relevant rate-limit boundary.

Explain exactly what your algorithm considers the boundary.

Do not claim behavior that the chosen algorithm does not guarantee.

---

# 9. Load-generation harness
The harness is a first-class deliverable.

Build a separate executable/script such as:

```
harness/
    ...
```
It should be able to drive the running service and produce clear results.

The output should be understandable without opening the implementation.

For example:

```
Scenario: quota boundary
Customer: test-customer
Configured quota: 10 RPM

Requests sent:       11
Successful (200):    10
Rejected (429):        1
Unexpected responses:  0

PASS
```
For concurrency:

```
Scenario: concurrent boundary
Quota: 10
Concurrent requests: 50

Allowed: 10
Rejected: 40
Unexpected: 0

PASS
```
For three nodes:

```
Scenario: distributed enforcement

Nodes:
  node-1
  node-2
  node-3

Customer quota: 10

Total requests: 30
Allowed:        10
Rejected:       20

PASS — quota enforced globally
```
The exact format is up to you, but make the results legible.

The harness should fail clearly when expected behavior is violated.

Prefer exit code `0` for success and non-zero for failed scenarios.

---

# 10. Testing strategy
Do not rely only on unit tests.

Use multiple layers:

### Unit tests
Test the core rate-limit logic independently where practical.

### Integration tests
Test the HTTP service + shared state store.

### Distributed test
Run three application instances and verify shared quota enforcement.

### Load harness
Use the actual HTTP API and produce human-readable evidence.

Tests should intentionally target naive implementations.

For every important test, explain:

> What incorrect implementation would this test catch?
This is important.

---

# 11. Time handling
Be very careful with time.

Do not implement rate limiting using arbitrary integer-second assumptions if that introduces boundary bugs.

Prefer monotonic/precise timing where appropriate.

Avoid flaky tests caused by tiny timing differences.

If exact wall-clock timestamps are stored in Redis, clearly document the approach.

If your design requires server-side Redis time or another mechanism to avoid clock-skew problems, consider it.

Remember that in a distributed deployment, application nodes may not have exactly identical clocks.

You don't need to solve every distributed-systems problem, but identify the relevant trade-off.

---

# 12. Failure behavior
Think about what happens if Redis becomes unavailable.

Do not silently invent a policy.

Decide explicitly whether RelayAPI should:

- Fail open, or
- Fail closed.
Tie the decision to the assignment's business context, especially Northwind and quota enforcement.

Document the decision and its trade-offs.

You do not need to implement a sophisticated HA Redis setup.

---

# 13. Northwind scenario
The memos specifically mention Northwind's nightly 02:00–04:00 UTC traffic spike.

Your implementation should reflect the conflict rather than pretending it does not exist.

If your resolution involves allowing controlled bursts, make the behavior explicit.

If your resolution does NOT allow Northwind to exceed its contracted quota, explain why.

Do not create a secret special-case such as:

```
if customer == "northwind":
    bypass_rate_limit()
```
unless the source memos explicitly justify such behavior and you clearly document it.

The goal is to resolve the policy conflict at the system-design level, not hide it in customer-specific code.

---

# 14. DECISIONS.md
Create:

```
DECISIONS.md
```
Keep it to one page or less.

It must clearly cover:

## Conflict resolution

- What the CTO requires.
- What Support requires.
- Which requirement you prioritized.
- Why.
- What you explicitly rejected.
- How Northwind is treated.

## Algorithm

- Selected algorithm.
- Why it fits the requirements.
- Burst behavior.
- Boundary semantics.

## Distributed coordination

- Why shared state is required.
- How the three application nodes coordinate.
- How atomicity is achieved.

## Harness

- What it proves.
- What it does not prove.

## Next four hours
Describe the highest-value improvements you would make with another four hours.

Be specific rather than saying "improve scalability."

---

# 15. README.md
Create a reviewer-friendly:

```
solution/README.md
```
The reviewer should be able to run the project in ≤15 minutes on a normal laptop using free tools.

README should contain:

1. Architecture overview.
2. Conflict-resolution summary.
3. Algorithm explanation.
4. Prerequisites.
5. Installation.
6. How to start Redis.
7. How to start application nodes.
8. How to run tests.
9. How to run the load harness.
10. Example expected output.
11. Known limitations.
12. Why the implementation is intentionally narrow.
Include exact commands.

Prefer a simple startup process.

If Docker Compose makes the three-node setup substantially easier, consider using it, but don't introduce unnecessary complexity.

---

# 16. AI session requirement
The assignment explicitly requires:

```
sessions/
```
containing the complete AI working-session exports.

Do NOT fabricate or summarize previous conversations.

As we work, keep the actual prompts, tool interactions, code changes, errors, retries, and reasoning available so I can export the sessions later.

Do not create fake "AI transcripts."

If you make an important design decision, explain it in your response so the actual working process remains auditable.

---

# 17. Code quality
Prioritize:

- Small functions.
- Clear names.
- Explicit error handling.
- Type hints/types where appropriate.
- Minimal dependencies.
- Useful comments around distributed/concurrency-sensitive code.
- No unnecessary abstractions.
- No premature optimization.
Most importantly, I should be able to explain every significant part of the implementation in an interview.

Do not generate a huge codebase.

---

# 18. Development process
Work incrementally.

### Phase 1 — Understand
Read the assignment and all three memos.

Give me:

- Conflict analysis.
- Requirements matrix.
- Proposed resolution.
- Proposed algorithm.
- Proposed architecture.
- Test strategy.
Do NOT code yet.

### Phase 2 — Implement minimal vertical slice
Implement:

- Shared rate-limit state.
- HTTP endpoint.
- Rate-limiting middleware/service.
- Customer configuration.
- Multiple app instances.
- Basic health endpoint.
Then run it.

### Phase 3 — Verify
Implement tests for:

- Exact quota.
- Quota + 1.
- Concurrent requests.
- Multiple nodes.
- Multiple customers.
- Refill/recovery.
- Boundary timing.
Run the tests and show failures if any.

Do not hide failures.

### Phase 4 — Harness
Build the load harness.

Run it against the actual service.

Make the output clearly show PASS/FAIL and counts.

### Phase 5 — Documentation
Write:

- `solution/README.md`
- `DECISIONS.md`
Ensure documentation matches actual behavior.

### Phase 6 — Final audit
Before declaring the assignment complete, inspect the entire repository and check:

- Does the implementation actually satisfy the documented decision?
- Does distributed enforcement really work?
- Are boundary tests meaningful?
- Does the harness exercise the real HTTP API?
- Are any claims in README/DECISIONS unsupported?
- Are there unnecessary files/dependencies?
- Can a reviewer run it within 15 minutes?
- Are there any flaky tests?
- Are there any hidden Northwind special cases?
- Does the code have race conditions?
- Does the failure behavior match the documented policy?
Then provide me with a concise final report containing:

```
Implementation summary
Conflict resolution
Algorithm
Distributed design
Tests performed
Harness results
Known limitations
Files changed
Commands to reproduce
```

## Important constraints

1. Do not skip reading the source memos.
2. Do not assume the assignment page resolves the memo conflict.
3. Do not implement a single-process-only limiter.
4. Do not use per-process memory as the authoritative distributed state.
5. Do not merely test sequential requests; concurrency matters.
6. Do not merely claim three-node support; demonstrate it.
7. Do not make Northwind an undocumented special case.
8. Do not hide failing tests.
9. Do not overbuild the project.
10. Prefer a small, demonstrably correct implementation over a large feature-rich one.
Start with **Phase 1 only**: read the relevant files and give me the conflict analysis, requirements matrix, proposed policy decision, algorithm choice, architecture, and verification plan. Do not write implementation code yet.

GitHub Copilot: I’m reading the assignment and source memos first so I can resolve the conflict and propose the policy before any implementation.

Read [](file:///c%3A/Users/Risha/ti-assignment-promise-them-nothin/assignment.md)

Read [](file:///c%3A/Users/Risha/ti-assignment-promise-them-nothin/briefs/cto-memo.md)

Read [](file:///c%3A/Users/Risha/ti-assignment-promise-them-nothin/briefs/support-lead-memo.md)

Read [](file:///c%3A/Users/Risha/ti-assignment-promise-them-nothin/briefs/platform-context.md)

## Phase 1 — assignment read and policy analysis

I reviewed the source documents in assignment.md, cto-memo.md, support-lead-memo.md, and platform-context.md. No implementation has started yet; this is the design decision phase.

---

## 1) Conflict analysis

### CTO requirement
The CTO is clear that RelayAPI must enforce the contracted RPM as a hard limit:

- no over-limit traffic
- per-customer quotas are isolated
- fair treatment across customers
- auditable counting semantics
- rate limiting must work across three stateless app nodes
- under-limiting is acceptable; over-limiting is not

This is an SLA and billing requirement: the system must be explainable and legally defensible.

### Support Lead requirement
The Support Lead is making a commercial urgency argument:

- Northwind’s nightly batch window is business-critical
- they expect to operate above their contractual RPM
- they do not want 429s in the 02:00–04:00 UTC window
- they are asking for an invisible exception mechanism or operational workaround

This is not a technical requirement; it is an exception request driven by customer retention risk.

### Genuine conflict
The true conflict is:

- CTO: “never exceed quota; no special-case bypasses”
- Support: “Northwind must never see 429 during batch window; make it work even if it exceeds quota”

These cannot both be enforced in the same runtime algorithm without creating a customer-specific bypass or a non-contractual exception path.

---

## 2) Requirements matrix

| Requirement | CTO | Support | Resolution |
|---|---|---|---|
| Hard quota enforcement | Must never exceed quota | Wants exception for Northwind | Enforce quota in runtime; treat support ask as business exception outside the limiter |
| Per-customer isolation | Mandatory | Implied but not central | Keep per-customer state independent |
| Fairness | Mandatory | Not explicit, but desired for all customers | Enforce same algorithm for all customers |
| Auditable counting | Mandatory | Not prioritized | Use documented algorithm with explicit semantics |
| Three-node distributed enforcement | Mandatory | Implied | Shared Redis-backed atomic state |
| Northwind batch window | No special case | Must work | Not implemented as hidden override; handled as a separate commercial process |
| 429 semantics | Required when quota is exceeded | Must not happen for Northwind | Runtime remains strict; exception must be explicit and config-driven, not hidden |
| Load-balanced distributed traffic | Must work | Must work | Shared authoritative state, not local memory |

---

## 3) Proposed policy decision

I would prioritize the CTO’s requirement.

### Why
1. It is aligned with the contract, legal language, billing model, and GA success criteria.
2. It is the only requirement that is operationally testable, auditable, and non-ambiguous.
3. The Support Lead’s request is a business exception request, not a technical requirement the runtime can safely satisfy without violating the SLA.

### What I explicitly reject
- any runtime branch such as “if customer == northwind, bypass rate limit”
- hidden customer-specific exceptions in request paths
- per-node in-memory quota state as the authoritative source
- any “best effort” distributed limiter that is only correct when requests hit one node

### What I compromise on
I am not going to claim a runtime policy that lets Northwind exceed their contracted quota. Instead, I would treat the support ask as an operational or commercial exception:

- the system remains contractually honest
- if the business decides to grant Northwind a temporary exception, it must be explicit in config, reviewed, and auditable
- the code should not embed a hidden bypass

This resolves the conflict at the design level instead of masking it in a branch.

### Northwind treatment
Northwind is treated as a normal Enterprise customer with a configured quota (e.g. 300 RPM) and standard distributed enforcement. The system does not give Northwind a special runtime path. If the business later decides to grant an exception, that exception belongs in a documented operational policy, not in the core limiter.

---

## 4) Proposed algorithm

I would choose a token bucket.

### Why token bucket fits RelayAPI
It matches the actual business constraint better than a naive fixed-window counter:

- Customers have a contracted RPM budget, not a pure “counting at the minute boundary” policy
- A token bucket allows bounded bursts while still enforcing the long-run rate
- It is fair and easy to explain to enterprise prospects
- It handles short spikes better than rigid fixed windows
- It is straightforward to implement atomically in Redis without race-prone state transitions

### Precise semantics
For each customer:

- rate = 1 token per 1/60th of a minute, or equivalently 60 tokens per minute
- bucket capacity = the customer’s RPM quota
- one request consumes one token
- a full bucket means the customer can burst up to their total quota immediately
- refill is continuous over time
- when insufficient tokens are available, the request is rejected with 429 and Retry-After computed from the time until the next token is available

This means the effective semantics are:

- the customer may consume up to quota in a burst
- they cannot sustain above quota indefinitely
- they cannot exceed their contracted rate over time

This is a reasonable interpretation of RPM in a bursty B2B API environment.

### Why not a fixed window?
A fixed window is simpler, but it is worse at fairness and boundary semantics:
- it tends to create “thundering herd” behavior at window boundaries
- it punishes legitimate traffic around the transition to the next minute
- it is easier to get wrong under distributed concurrency

### The support conflict and burst semantics
The Support memo wants Northwind’s batch window to work without throttling. A token bucket does not solve that unless the customer has a higher configured quota or a separate approved exception. That is acceptable because the design chooses contract enforcement over hidden override.

---

## 5) Proposed distributed architecture

I would build a thin service with three app nodes and a shared Redis-backed rate-limit state.

### Why local memory is incorrect
Each node is stateless and has no shared memory. If quota is stored in local process memory:

- node 1 sees one customer’s requests
- node 2 sees another set
- each node makes independent decisions
- the total can exceed the contractual quota by a factor of the number of nodes

This is the exact failure mode the assignment warns about.

### How coordination works
Each request is evaluated against a shared Redis key per customer, such as:

- token bucket state
- last refill timestamp
- remaining tokens

The app node does not compute quota locally and then “write back” without synchronization.

Instead, the limiter should use an atomic Redis operation:
- read current bucket state
- compute next tokens and whether the request is allowed
- write the updated state in one atomic script or transaction

This ensures concurrent requests are serialized at the Redis layer.

### Race condition to avoid
A naive implementation looks like:

- GET current count
- compute new count
- SET new count

This is unsafe. Under concurrency, multiple requests can all read the same value before any write, and each one will “see” a stale allowance. The result is over-limit acceptance.

The fix is atomic update in Redis using a Lua script or Redis transaction.

### Time handling
To avoid clock skew between app nodes, the limiter should use Redis server time or a single authoritative time source for the refill calculation. That is materially better than trusting app-node clocks, which may drift or differ slightly.

---

## 6) Verification plan

The testing plan should intentionally target naive implementations and distributed bugs.

### Core scenarios
1. Exact quota boundary
   - send exactly N requests in the minute
   - confirm the Nth is accepted and the N+1th is rejected

2. One request beyond quota
   - send N+1 requests
   - confirm first N succeed, last one is rejected

3. Concurrent boundary
   - allow only a small number of tokens remaining
   - send many parallel requests
   - confirm no more than the quota are admitted

4. Multiple app instances
   - run three app nodes
   - distribute same customer traffic across them
   - verify the customer quota is enforced globally

5. Independent customers
   - customer A traffic must not consume customer B’s quota

6. Refill/recovery
   - after rejection, verify tokens refill after sufficient time and requests become allowed again

7. Boundary timing
   - requests immediately before and after the minute boundary
   - document exact semantics based on the token-bucket refill model

### What these tests are designed to catch
- stale reads and double-counting under concurrency
- per-node quota state instead of shared quota state
- incorrect off-by-one boundary logic
- incorrectly using wall-clock drift across nodes
- customer-isolation bugs

---

## Conclusion

The design decision is:

- prioritize the CTO’s contractual, auditable, globally enforced quota requirement
- reject hidden Northwind bypasses
- treat any business exception as a formal, explicit operational policy outside the runtime
- implement a token bucket backed by Redis with atomic updates across three nodes
- verify exact quota boundaries and distributed concurrency with explicit harness scenarios

This is the policy decision I will carry into implementation.

User: Your analysis is mostly good. Before implementing, I want you to perform one additional **design validation pass against the actual source memos**.

Do NOT modify any files yet.

## 1. Validate the token-bucket interpretation
You proposed:

- refill rate = quota / minute
- bucket capacity = quota
- 1 request = 1 token
- full bucket allows an immediate burst of N requests
I want you to go back to the actual:

- `briefs/cto-memo.md`
- `briefs/support-lead-memo.md`
- `briefs/platform-context.md`
and verify whether this interpretation is genuinely consistent with the source memos.

The CTO requirement says the contracted RPM is a hard limit. Carefully distinguish between:

- instantaneous burst capacity
- requests during a rolling minute
- long-run average rate
- contractual RPM
If a token bucket with capacity = RPM technically permits an instantaneous burst that could be interpreted as exceeding "N requests in any one-minute period", explicitly discuss that issue.

Do not silently assume that "RPM" means long-run average.

If the memos don't specify the exact mathematical interpretation, say so and explain why your chosen interpretation is the most defensible one.

## 2. Resolve the Northwind issue precisely
Your current proposal says:

> "If the business later decides to grant an exception, that exception belongs in a documented operational policy, not in the core limiter."
Check whether that is actually supported by the memos.

The assignment explicitly says:

> "Your job is not to make both memos literally true."
Therefore I want the final design to explicitly choose which stakeholder requirement wins.

Do NOT introduce an exception mechanism merely to make the two memos appear compatible.

The final implementation should have one clear policy.

## 3. Reconsider whether "Northwind = normal customer" is the strongest decision
You proposed treating Northwind as a normal Enterprise customer.

Evaluate whether that is actually the best resolution given that Northwind represents roughly 60% of recurring revenue and the Support Lead considers the nightly batch business-critical.

If the correct conclusion is still "Northwind is subject to the same hard quota", keep it.

If another interpretation is more strongly supported by the source memos, explain it.

Do not optimize for pleasing both stakeholders. Optimize for an explicit, defensible resolution.

## 4. Boundary semantics
Before implementation, define exactly what our tests mean by:

```
quota = 10 RPM
```
For example, clarify what should happen with:

```
10 requests at t = 0
1 request at t = 0
1 request at t = 1 second
1 request at t = 59 seconds
1 request at t = 60 seconds
```
Do not give me generic rate-limiting theory. Define the expected behavior of OUR chosen algorithm.

Also explain why a test saying:

> "send N requests in the minute, then N+1"
may not be a mathematically valid test for a token bucket unless the timing and bucket initialization are precisely controlled.

## 5. Improve the verification plan
I want the final tests to catch these specific naive implementations:

### Naive implementation A
Per-process in-memory limiter.

Expected: distributed test fails.

### Naive implementation B
Redis GET → calculate → SET.

Expected: concurrent test can expose over-admission.

### Naive implementation C
Fixed-window counter.

Expected: boundary test demonstrates its different semantics.

### Naive implementation D
Off-by-one limiter.

Expected: exact-quota test catches it.

### Naive implementation E
Application-node clocks used independently.

Expected: discuss/test the resulting refill inconsistency where practical.

For each test, explicitly state:

```
Test
Expected result
Bug it catches
Why the test is valid
```

## 6. Final design proposal
After this validation, give me the final:

1. Stakeholder decision.
2. Exact rate-limit semantics.
3. Algorithm.
4. Distributed state model.
5. Atomic Redis operation design.
6. Failure policy if Redis is unavailable.
7. HTTP API.
8. Customer configuration.
9. Test matrix.
10. Load-harness scenarios.
11. Final directory structure.
Still **DO NOT IMPLEMENT ANYTHING**.

Once I approve this final design, we will move to implementation.

GitHub Copilot: I'll add a short todo list to track this design-validation pass and next deliverable (final design document).

Created 5 todos

Progress: I created a TODO list tracking the validation steps and next design deliverable. Next I'll present the validated design decisions and the expanded verification plan.

**Validation & final design**

**1) Token-bucket interpretation vs source memos**
- Source review: cto-memo.md, support-lead-memo.md, platform-context.md.
- CTO language: “a customer must never exceed their contracted quota … Not ‘mostly,’ not ‘on average’ — never.” Also: prefers under-limiting over over-limiting ("I would rather reject a few extra legitimate requests than let someone blow past quota"). Requires auditable counting and correctness across three stateless nodes.
- Support language: demands Northwind see no 429s in nightly batch window (business exception).
- Token-bucket semantics (as proposed): rate = quota/60s, capacity = quota, 1 request = 1 token, full bucket allows immediate burst = quota requests.
- Key mismatch discovered: a token bucket with capacity = quota permits bursts that can lead to more than N requests inside some rolling 60-second windows. Concrete counterexample:
  - quota = 60 RPM, rate = 1 token/sec, capacity = 60.
  - If a client consumes 60 tokens at t=0, then 30 tokens are refilled by t=30s → the client can do 30 more at t=30s. In the 60s sliding window covering [-30, +30], that is 90 requests > 60.
- Conclusion: the memos do not define formally whether "RPM" = "no more than N requests in any rolling 60s window" or "long-run averaged rate ≈ N/min with bounded bursts". The CTO wording ("never exceed") strongly suggests the stricter interpretation (no more than N per minute window). Therefore a plain token-bucket with capacity = RPM is not guaranteed to meet the CTO’s literal demand.

**Decision from validation**
- To satisfy the CTO’s strict requirement and keep behavior auditable and unambiguous, I will adopt the strict rolling-window semantics (sliding-window) that enforces no more than N requests in any 60-second sliding window.
- Rationale: Sliding-window enforcement directly guarantees "never exceed N requests in any 60s interval", which is the strongest reading of the CTO's memo and is auditable. It also makes testing and proof easier (exact timestamps are stored and counted).
- Consequence: This is explicitly not the same as the token-bucket with capacity = RPM (that allows larger bursts). I choose correctness per the CTO over permissive bursts.

**2) Northwind resolution**
- The assignment instructions and memos force a choice. I will prioritize the CTO’s contract-first requirement: no hidden runtime bypasses. Therefore:
  - Stakeholder decision: Northwind is treated under the standard policy; no undocumented bypass.
  - Business exceptions (e.g., temporarily raising Northwind’s quota for the batch window) are permitted only as an explicit, auditable operational action (change their configured quota in system config / billing) — not a hidden if-customer hack in request path.
- Reason: Northwind’s business importance is real, but the CTO’s contract/audit requirement plus the rubric (we must demonstrate correct enforcement) makes the strict policy the defensible engineering choice. Operational exceptions can be made via config changes and must be recorded/audited.

**3) Exact boundary semantics (what we mean by `quota = 10 RPM`)**
- Chosen formal rule (sliding-window, 60s):
  - For an incoming request at time t (Redis server time), compute count = number of requests with timestamp s such that (t - 60s) < s ≤ t.
  - If count < quota, admit the request and insert a timestamp entry for t.
  - If count ≥ quota, reject with HTTP 429.
  - Inclusive/exclusive choice: lower bound exclusive, upper bound inclusive. This ensures that after exactly 60s a slot frees deterministically.
- Example for quota = 10:
  - 10 requests at t = 0 → all allowed (count becomes 10).
  - 1 request at t = 0 (the 11th at same instant) → rejected (window contains 11 if you attempted to add a request).
  - 1 request at t = 1s → rejected (window (t-60,t] includes the 10 at t=0 ⇒ would be 11).
  - 1 request at t = 59s → rejected.
  - 1 request at t = 60s → allowed (window (0,60] excludes events at t=0 due to exclusive lower bound; count = 0 before adding).
- Note: Tests that say "send N requests in the minute then N+1" must control timestamps and starting state: initialization must be known (empty history or bucket full) and inter-request timing must be precise to be meaningful under sliding-window semantics.

**4) Final algorithm choice**
- Algorithm: Sliding-window log implemented with Redis sorted sets (per-customer).
- Why:
  - Guarantees strict "≤ N requests in any rolling 60s interval".
  - Auditable: each admitted request corresponds to a stored timestamp.
  - Testable: boundary semantics are deterministic given server time.
  - Can be implemented atomically in Redis via a single Lua script that uses Redis server time.
- Tradeoffs:
  - Slightly more storage per request (timestamps in sorted sets), but acceptable for a prototype and simple to reason about.
  - Performance is adequate for the assignment; a production system could use approximate algorithms or sharded counters with careful analysis.

**5) Distributed state model**
- Authoritative state: Redis per-customer sorted set key, e.g., `rl:{customer_id}`.
- Stored members: unique value per request (e.g., combination of Redis TIME + random suffix) with the score = timestamp in milliseconds or microseconds.
- All operations happen in a single Redis atomic Lua script, executed by every app node.

**6) Atomic Redis operation design (Lua script outline)**
Operation (single atomic script, inputs: key, quota, window_seconds):
- Acquire authoritative time: use `redis.call('TIME')` to get server seconds + microseconds → compute `now_ms`.
- Remove expired entries: `ZREMRANGEBYSCORE(key, 0, now_ms - window_ms)` (clean older than window).
- Get current count: `local count = redis.call('ZCARD', key)`.
- If count < quota:
  - Add new member: `redis.call('ZADD', key, now_ms, memberId)` where `memberId` is a unique token passed or generated (e.g., client-random + now_ms).
  - Optionally set TTL on key to window_seconds to auto-expire empty keys.
  - Return allowed = 1, remaining = quota - (count + 1), limit = quota.
- Else (count >= quota):
  - Determine Retry-After: fetch the smallest score in the sorted set (oldest request) via `ZRANGE key 0 0 WITHSCORES` → its score `oldest_ms`. `retry_after_sec = ceil((window_ms - (now_ms - oldest_ms))/1000)` (≥1).
  - Return allowed = 0, remaining = 0, limit = quota, retry_after = retry_after_sec.
- This script avoids race conditions because remove/count/add are atomic.

**7) Time handling & clock skew**
- Use Redis server time (`TIME`) for all timestamping and refill boundaries — avoids app-node clock skew.
- App nodes do not use local clocks for decisions.

**8) Failure policy (Redis unavailable)**
- Default policy: fail-closed (deny traffic) — return `503 Service Unavailable` (not 429) with a short message indicating dependency failure.
- Rationale: CTO prioritized avoiding overuse; failing closed prevents unmetered consumption in face of Redis outage. Returning 503 is clearer operationally than pretending it is a rate-limit rejection.
- Operational alternative: make fail-open a configurable operational mode (dangerous for GA) but default must be fail-closed and auditable.

**9) HTTP API (spec)**
- GET /health
  - 200 OK when app up (may still respond 200 if Redis is down? Prefer 200 but with body indicating Redis status; but simpler: 200 if app up; include `X-Redis-OK: true|false`).
- GET /api/resource
  - Required header: `X-Customer-ID: <id>` (if missing → 400 Bad Request).
  - Allowed response:
    - HTTP 200
    - Headers:
      - `X-RateLimit-Limit`: quota (requests per minute)
      - `X-RateLimit-Remaining`: remaining requests in current 60s window after this request is accounted
  - Rejected response (exceeded):
    - HTTP 429
    - Headers:
      - `X-RateLimit-Limit`: quota
      - `X-RateLimit-Remaining`: 0
      - `Retry-After`: integer seconds until next slot (rounded up)
  - Redis-unavailable dependency failure:
    - HTTP 503 with body indicating dependency issue and header `X-Service-Dependency: redis`.

**10) Customer configuration**
- Simple config map (e.g., YAML/JSON in repo): `northwind: 300`, `acme: 10`, `test: 10`, etc.
- Operational exceptions change the configured quota for the customer explicitly (and must be recorded separately in audit logs). No hidden hardcoded customer bypass.

**11) Test matrix (explicit tests catching naive bugs)**

- Test 1 — Exact quota
  - Test: quota = 10; send 10 requests at t = 0 sequentially; assert all 10 return 200; next request at t = 0 → 429.
  - Expected result: 10 allowed, 1 rejected.
  - Bug it catches: off-by-one limiters and naive over-acceptance.
  - Why valid: deterministic timestamps and sliding-window semantics guarantee results.

- Test 2 — One beyond quota across time
  - Test: quota = 10; send 10 requests at t = 0; send 1 at t = 60s; assert the t=60s request is allowed.
  - Expected: last request allowed.
  - Bug it catches: fixed-window implementations that align windows differently might incorrectly reject/accept; also incorrect exclusive/inclusive boundary handling.
  - Why valid: sliding-window semantics exclude t=0 entries at t=60s.

- Test 3 — Concurrent boundary (concurrency correctness)
  - Test: quota = 10; ensure history has 0 or known state; send 50 concurrent requests across three nodes with same X-Customer-ID; assert exactly 10 allowed, 40 rejected.
  - Expected: 10 allowed total globally.
  - Bug it catches: Redis GET→calculate→SET race conditions and per-process limiters.
  - Why valid: race emerges under concurrency; atomic Lua script prevents over-admission.

- Test 4 — Distributed enforcement (three nodes)
  - Test: run three instances; use load balancer to randomly send 30 requests; quota = 10; assert only 10 total allowed across all nodes.
  - Expected: 10 allowed, 20 rejected.
  - Bug it catches: per-process memory limiters, non-shared state.
  - Why valid: demonstrates shared authoritative state required.

- Test 5 — Independent customers
  - Test: customers A and B each quota 10; send 10 requests for A and 30 for B; assert A unaffected by B.
  - Expected: A's requests unaffected; B limited to 10.
  - Bug it catches: shared-pool bugs or key-collision bugs.
  - Why valid: per-customer keys used.

- Test 6 — Refill/recovery (deterministic)
  - Test: quota = 10; consume 10 at t=0; wait 61s (or manipulate Redis time in test harness if possible); send 10 requests; assert allowed.
  - Expected: tokens freed, requests allowed.
  - Bug it catches: window-cleaning bugs and TTL miscalculations.
  - Why valid: uses server time and window logic.

- Test 7 — Boundary timing micro-test
  - Test: sequences at t = 0, t = 59.999s, t = 60.001s to ensure deterministic behavior around exclusivity.
  - Expected: behavior per exclusive lower bound rule.
  - Bug it catches: off-by-one and ms vs seconds rounding errors.
  - Why valid: ensures implementation uses ms-precision and server TIME.

- Naive implementations targeted explicitly:
  - Naive A — per-process in-memory limiter:
    - Test: distributed enforcement test (Test 4).
    - Expected fail: will allow quota × nodes.
  - Naive B — Redis GET → calculate → SET:
    - Test: concurrent boundary (Test 3).
    - Expected fail: permits >quota under concurrency.
  - Naive C — fixed-window counter:
    - Test: boundary timing and Test 2.
    - Expected behavior difference: fixed-window may allow or reject different requests at minute boundaries; test will reveal mismatch versus strict rolling-window.
  - Naive D — off-by-one limiter:
    - Test: Exact quota (Test 1).
    - Expected fail: admits 11 or rejects 10 depending on bug.
  - Naive E — independent node clocks:
    - Test: run nodes with artificially skewed clocks (or mock times) and concurrent workload; verify inconsistent admission or uneven refill.
    - Expected fail: window boundaries drift leading to transient over-admission; using Redis server time prevents this.

**12) Load-harness scenarios**
- Scenario A — Quota boundary (sequential)
  - quota = 10; requests = 11 sequential; expected: 10 allowed, 1 rejected; concise report.
- Scenario B — Concurrent boundary
  - quota = 10; concurrent requests = 50 across three nodes; expected: 10 allowed, 40 rejected.
- Scenario C — Distributed enforcement
  - nodes: node-1,node-2,node-3; total requests 30 randomly routed; quota=10; expected: 10 allowed, 20 rejected.
- Scenario D — Independent customers
  - customer A quota 10, B quota 20; stress B; assert A unchanged.
- Harness output format: plain table + PASS/FAIL exit code non-zero on failure.

**13) Directory structure (final plan, no files created yet)**
- solution/
  - app/
    - main service code
    - limiter/ (Lua script)
    - config/customers.json
  - tests/
    - unit/ (isolated Lua script/unit tests for script logic)
    - integration/ (three-node integration tests)
    - distributed/ (concurrency and multi-process tests)
  - harness/
    - run_scenarios.py (or .js) — drives HTTP requests across nodes
  - solution/README.md
  - DECISIONS.md
  - sessions/ (AI session exports)
- README at repo root will point to solution/README.md

---

If you approve this validated design (sliding-window + Redis Lua atomic script + fail-closed default + explicit operational exceptions via config), I will proceed to Phase 2 and implement the minimal vertical slice, starting with the Redis Lua script, the small HTTP service, config, tests, and the harness.

User: I approve this final design document. The decision to enforce a strict sliding window and treat the Northwind exception as an explicit configuration change perfectly satisfies the CTO's auditability requirement while providing a practical lever for Support.

Let's move to implementation (Phase 2), but we must do this iteratively. **Do not generate the entire repository at once.** We need to demonstrate structured decomposition.

### Step 1: Scaffolding and Core Limiter Logic
Please execute the following tasks:

1. **Language Choice:** Briefly state your chosen language/framework for the backend and testing (e.g., Go, Python/FastAPI, or Node.js) and why it's best for a thin, readable vertical slice.
2. **Project Setup:** Output the shell commands to create the initial directory structure under `solution/` as designed.
3. **Lua Script:** Write the exact Redis Lua script for the atomic sliding window. Ensure it uses `redis.call('TIME')` and returns the exact agreed-upon variables (allowed, remaining, limit, retry_after).
4. **Core Logic Tests:** Write an isolated test suite (using a local Redis instance or Testcontainers) that directly invokes and tests this Lua script. This test suite MUST explicitly implement and cover:

- Test 1: Exact quota (off-by-one check).
- Test 2: One beyond quota across time (inclusive/exclusive boundary check).
- Test 6: Refill/recovery.
- Test 7: Boundary timing micro-test (milliseconds precision).
Provide the code for this step and the commands to run these specific tests. Stop and wait for my approval. Do not build the HTTP API, the configuration layer, or the Load Harness until I verify that the core mathematical logic passes these boundary tests.

GitHub Copilot: I'll scaffold the `solution/` dirs and add the Redis Lua script plus Python tests (requires local Redis). Then I'll update the todo list.

Apply Patch

Now I'll create the Lua script, test suite, and requirements file under `solution/`. They require a local Redis at `localhost:6379` to run tests.

Created [](file:///c%3A/Users/Risha/ti-assignment-promise-them-nothin/solution/limiter/redis_scripts/sliding_window.lua)

Created [](file:///c%3A/Users/Risha/ti-assignment-promise-them-nothin/solution/tests/test_sliding_window.py)

Created [](file:///c%3A/Users/Risha/ti-assignment-promise-them-nothin/solution/requirements.txt)

Created [](file:///c%3A/Users/Risha/ti-assignment-promise-them-nothin/solution/README.md)

Starting: *Draft tests targeting naive implementations A–E* (4/5)

Progress: I scaffolded the limiter script and an isolated test suite that invokes the Redis Lua script. Next step: you can run the tests locally (requires Redis). I paused before building the HTTP API or harness as requested.

1) Language/framework choice
- Python 3 + pytest, using `redis` (redis-py).
- Why: minimal boilerplate, excellent test support, quick scripting, easy to call Redis and register Lua scripts; good for a small, readable vertical slice.

2) Project setup commands (run in repo root)
```bash
# create directories
mkdir -p solution/limiter/redis_scripts
mkdir -p solution/tests
# create virtualenv and install later:
python -m venv .venv
# Windows activation:
.venv\Scripts\activate
pip install -r solution/requirements.txt
# run tests
pytest -q solution/tests/test_sliding_window.py
```

3) Files added
- sliding_window.lua — atomic Redis Lua script (uses `redis.call('TIME')`). It returns: [allowed, remaining, limit, retry_after].
- test_sliding_window.py — pytest suite that loads and registers the Lua script and runs four core tests (Exact quota, One-beyond across time, Refill/recovery, Boundary timing micro-test). Tests use small window_ms values for speed and determinism.
- requirements.txt — `redis`, `pytest`.
- README.md — quick-run instructions.

4) Lua script summary
- Uses Redis `TIME` to compute `now_ms`.
- Cleans expired entries: `ZREMRANGEBYSCORE key 0 window_start`.
- Counts with `ZCARD`.
- If count < quota: `ZADD now_ms member`, `PEXPIRE key window_ms`. Returns allowed=1, remaining, limit, retry_after=0.
- Else: compute oldest via `ZRANGE ... WITHSCORES`, compute retry_ms and ceil to seconds, return allowed=0, remaining=0, limit, retry_after.

5) Tests
- Use `window_ms` small (1000ms, 200ms, 300ms) to keep tests fast.
- Rely on Redis server TIME for determinism.
- Each test flushes DB to start clean; tests will skip if Redis not available.

6) Next step (awaiting your approval)
- If you approve, I'll proceed to implement the HTTP API, configuration, integration tests, and distributed multi-node harness as the next iterative steps.

If you want any changes to the Lua script return format, boundary inclusivity, or test timings before I continue, tell me now.

Made changes.

User: This looks excellent. The Lua script correctly implements the strict sliding window semantics using Redis `TIME`, and the test coverage effectively targets the boundary conditions. I approve moving forward.

### Step 2: HTTP API and Configuration Layer

Let's build the thin HTTP layer. Since you chose Python, use a lightweight, async framework like FastAPI to keep the codebase minimal, readable, and performant.

Please execute the following tasks:

1. **Configuration Loader:** Implement a simple setup to load customer quotas (e.g., from `solution/app/config/customers.json`). Include Northwind with their explicit config-based exception (e.g., 300 RPM) and a few test customers with a standard quota (e.g., 10 RPM).
2. **HTTP Service:** Create the main application (e.g., `solution/app/main.py`) with:
   * A basic `GET /health` endpoint.
   * The `GET /api/resource` endpoint as specified in our design. It must require the `X-Customer-ID` header, return 200 or 429, and inject the standard `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `Retry-After` headers.
   * **Crucial Rule (Fail-Closed):** Implement the fail-closed policy. Catch Redis connection errors/timeouts and return a `503 Service Unavailable` with an `X-Service-Dependency: redis` header. Do not allow requests to pass unmetered.
3. **API Integration Tests:** Write a test suite (e.g., `solution/tests/test_api.py`) using the framework's test client. You must explicitly test:
   * Valid admission (200 OK) and correct headers.
   * Quota exhaustion (429 Too Many Requests) and correct `Retry-After` header.
   * Missing customer ID header (400 Bad Request).
   * Dependency failure (503 Service Unavailable) — use mocking (e.g., `unittest.mock.patch`) to simulate a Redis connection drop and verify the fail-closed behavior.

Provide the code for these components and the commands to run the API tests. Update `requirements.txt` as needed.

**Do NOT build the distributed load harness or the multi-node deployment setup yet.** We will do that in Step 3 after verifying the API layer works perfectly in isolation.

GitHub Copilot: Optimized tool selectionI'm going to add the API app, JSON config, and API tests; I'll update requirements. These changes let you run the API tests locally (they require Redis).

Generating patch (5 lines) in [](file:///c%3A/Users/Risha/ti-assignment-promise-them-nothin/solution/app/__init__.py)


```

```


Created [](file:///c%3A/Users/Risha/ti-assignment-promise-them-nothin/solution/app/config/customers.json)

Created [](file:///c%3A/Users/Risha/ti-assignment-promise-them-nothin/solution/app/main.py)

Generating patch (9 lines) in [](file:///c%3A/Users/Risha/ti-assignment-promise-them-nothin/solution/requirements.txt)


```

```


Created [](file:///c%3A/Users/Risha/ti-assignment-promise-them-nothin/solution/tests/test_api.py)

Updated todo list

Progress: I added the FastAPI app, customer config, and API tests, and updated requirements. Next I will run or help you run the API tests locally — they require Redis. Below are details and commands.

What I added
- customers.json — includes `northwind: 300`, `alpha:10`, `beta:10`, `test-customer:10`.
- main.py — FastAPI app:
  - `GET /health` returns JSON including Redis status.
  - `GET /api/resource` requires `X-Customer-ID`, calls the sliding-window Lua script via Redis server time, and returns 200 or 429 with headers `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `Retry-After`. On Redis errors returns 503 with `X-Service-Dependency: redis`.
- test_api.py — TestClient-based tests:
  - health check,
  - missing header -> 400,
  - valid admission -> 200 and headers,
  - quota exhaustion -> 429 with Retry-After,
  - dependency failure simulated via `unittest.mock.patch` -> 503.
- Updated requirements.txt with `fastapi`, `uvicorn`, `httpx`.

Commands to install and run API tests (PowerShell)
```powershell
# from repo root
python -m venv .venv
.venv\Scripts\Activate
pip install -r solution/requirements.txt

# Ensure Redis is running on localhost:6379

# Run the unit tests (Lua core tests + API tests)
pytest -q solution/tests/test_sliding_window.py::test_exact_quota solution/tests/test_sliding_window.py::test_one_beyond_across_time solution/tests/test_sliding_window.py::test_refill_recovery solution/tests/test_sliding_window.py::test_boundary_timing_precision solution/tests/test_api.py -q
```

Notes and caveats
- Tests require Redis at `localhost:6379`. If Redis is unavailable, tests will skip or fail; the core Lua tests will skip earlier if Redis absent.
- The FastAPI app loads the Lua script on startup, so TestClient triggers that startup automatically.
- I used `redis.asyncio` for the app redis client for clean async behavior; tests patch the `redis_client.evalsha` to simulate dependency failure.
- If you prefer sync redis usage for simpler mocking, I can change it — but current async approach is robust.

Next steps (after you run and confirm tests pass):
- Implement multi-node harness and distributed tests (Step 3).
- Add more tests targeting naive implementations A–E explicitly (some already covered; we'll add distributed concurrency tests next).

Run the tests and tell me the results or any issues; I will iterate as needed.

Made changes.

User: Excellent work. The API layer is perfectly thin, the dependency failure is handled correctly (fail-closed), and the tests are thorough. For the sake of our workflow, assume I ran the tests locally and they all passed beautifully.

Let's move to the final engineering phase: Step 3 - The Distributed Load Harness and Final Documentation. 

The rubric heavily weighs the load harness. It must clearly prove that our limiter works across multiple nodes and under concurrent load, catching the naive bugs we discussed.

Please execute the following tasks:

1. **Multi-Node Runner:** Create a simple script (e.g., `solution/run_cluster.py` or a shell script) that launches 3 instances of our FastAPI app on different local ports (e.g., 8001, 8002, 8003). This simulates our distributed environment without needing Docker.

2. **The Load Harness (`solution/harness/run_scenarios.py`):** Write an async Python script using `httpx` and `asyncio` that runs our defined scenarios against the cluster. It should round-robin requests across the 3 ports to simulate a load balancer. 
   Implement these exact scenarios:
   * **Scenario A (Exact Quota):** Send 11 sequential requests. Assert 10 allowed, 1 rejected.
   * **Scenario B (Concurrent Boundary):** Fire 50 requests concurrently at the cluster. Assert exactly 10 allowed, 40 rejected. (Proves atomicity/no race conditions).
   * **Scenario C (Distributed Enforcement):** Fire 30 requests across all 3 nodes randomly/round-robin. Assert exactly 10 allowed, 20 rejected. (Proves shared state; catches in-memory limiter bugs).
   * **Scenario D (Independent Customers):** Hit the cluster with 20 requests for customer `beta`, and concurrently 10 requests for customer `alpha`. Assert `alpha` gets 10 allowed, `beta` gets 10 allowed/10 rejected.
   
   The harness MUST output a clean ASCII table of the results to stdout (Scenario Name, Expected, Actual, Pass/Fail) and exit with a non-zero code if any scenario fails.

3. **DECISIONS.md:** Draft the final `solution/DECISIONS.md` file. Keep it under one page. As required by the assignment, it must explicitly cover:
   * The stakeholder conflict resolution (why we chose the strict sliding window and forced Support to use an auditable config change).
   * The algorithm and distributed-coordination choice (Redis Lua atomic script).
   * What the harness proves (shared state, race-condition immunity) and what it does not prove (e.g., Redis cluster failover, clock skew between Redis nodes).
   * What we would build next with another four hours.

Provide the code for these files and the exact commands to start the cluster and run the harness.

GitHub Copilot: I'll add the cluster runner, async harness, and DECISIONS.md files. These scripts will flush Redis before scenarios and print results; I'll update the todo list accordingly.

Created [](file:///c%3A/Users/Risha/ti-assignment-promise-them-nothin/solution/run_cluster.py)

Created [](file:///c%3A/Users/Risha/ti-assignment-promise-them-nothin/solution/harness/run_scenarios.py)

Created [](file:///c%3A/Users/Risha/ti-assignment-promise-them-nothin/solution/DECISIONS.md)

Added 1 todo

Progress: I added the cluster runner, the async load harness with the four scenarios, and `DECISIONS.md`. Next: start the cluster and run the harness locally.

Files added
- run_cluster.py — starts 3 uvicorn instances for `solution.app.main:app` on ports 8001,8002,8003.
- run_scenarios.py — async harness implementing Scenarios A–D, prints table and exits non-zero on failure. Flushes Redis between scenarios for deterministic runs.
- DECISIONS.md — one-page decision summary.

Commands to start the cluster and run the harness (PowerShell)
```powershell
# from repo root
# activate venv if not already:
.venv\Scripts\Activate

# start the cluster in one terminal
python solution/run_cluster.py

# in another terminal, run the harness
python solution/harness/run_scenarios.py
```

Single-line sequence (start cluster in background on Windows PowerShell; quieter alternative is to use separate terminals):
```powershell
Start-Process -NoNewWindow -FilePath python -ArgumentList 'solution/run_cluster.py'
python solution/harness/run_scenarios.py
```

Notes and caveats
- Ensure Redis is running at `localhost:6379` (or set `REDIS_URL` env var).
- The cluster runner sets `PYTHONPATH` so `solution.app.main` module path resolves.
- The harness flushes the Redis DB at start and between scenarios to isolate behavior.
- The harness expects exact counts; if you changed `customers.json` quotas, adjust the harness expected numbers accordingly.
- The cluster runner prints PIDs and must be terminated (Ctrl+C) to stop all uvicorn instances. If started via `Start-Process`, use Task Manager or `Stop-Process` with the PIDs.

If you want, I can:
- Run a smoke-check script that starts the cluster and runs the harness automatically (but I did not execute anything here — you will run locally).
- Add a makefile or PowerShell script to orchestrate start/run/stop.

Made changes.

User: This is fantastic. The cluster runner and the load harness perfectly simulate the distributed environment and rigorously test the boundary conditions. We have met all the core engineering requirements of the assignment.

Let's complete the final engineering step: polishing the documentation. 

Please update the `solution/README.md` to be a comprehensive guide for the reviewer. Remember, the reviewer needs to be able to get this running from scratch in under 15 minutes. The README must include:
1. **Prerequisites:** Python 3 (specify version if necessary) and Redis (must be running locally on the default port 6379).
2. **Setup:** Clear instructions on how to create the virtual environment and install `requirements.txt`.
3. **Running the Unit & API Tests:** The exact `pytest` commands to run the isolated tests.
4. **Running the Distributed Load Harness:** Step-by-step instructions on how to start the cluster (`solution/run_cluster.py`) in one terminal, run the harness (`solution/harness/run_scenarios.py`) in a second terminal, and how to safely shut down the cluster afterward.
5. **Project Structure Overview:** A brief explanation of what is in the `app/`, `tests/`, `limiter/`, and `harness/` directories so the reviewer knows where to look.

Output the full markdown for the updated `README.md`. Do not execute any scripts.

GitHub Copilot: I'm updating README.md with full setup, test, and run instructions for the reviewer. I'll replace the file contents.

Apply Patch

User: @agent Try Again

GitHub Copilot: I'll update README.md with step-by-step setup, test, and harness instructions for reviewers.

Apply Patch

I'm updating README.md with the full reviewer guide now.

Apply Patch

Generating patch (135 lines) in [](file:///c%3A/Users/Risha/ti-assignment-promise-them-nothin/solution/README.md)


```

```
Here is the updated README.md content I added:

```markdown
Solution core limiter tests

Prerequisites:
- Python 3.9+
- Redis running on localhost:6379

Quick start:

Create a venv and install deps:

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

Run tests:

```bash
pytest -q test_sliding_window.py
```

Notes:
- Tests use small windows (ms) to remain fast and deterministic. They rely on Redis server TIME for timestamping.
- If Redis is not available, pytest will skip the tests.

Full reviewer guide
===================

This README explains how to run the project end-to-end: unit tests, API tests, and the distributed load harness that demonstrates global rate-limit enforcement across three app instances.

Prerequisites
-------------
- Python 3.9+ (3.10 or 3.11 recommended)
- Redis running locally and reachable at `localhost:6379` (default port)

Setup
-----
1. From the repository root, create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

Running the unit & API tests
----------------------------
Run the Lua/core tests and API tests (requires Redis):

```powershell
# run the Lua core boundary tests
pytest -q solution/tests/test_sliding_window.py::test_exact_quota solution/tests/test_sliding_window.py::test_one_beyond_across_time solution/tests/test_sliding_window.py::test_refill_recovery solution/tests/test_sliding_window.py::test_boundary_timing_precision

# run the API tests
pytest -q test_api.py
```

Or run all tests together:

```powershell
pytest -q solution/tests
```

Running the distributed cluster and the harness
---------------------------------------------
We simulate three stateless app nodes locally. The cluster runner starts three Uvicorn processes bound to ports `8001`, `8002`, and `8003`.

1. Start the cluster in a terminal (this blocks; leave it running):

```powershell
python run_cluster.py
```

You should see three uvicorn instances start. Give them a second to warm up.

2. In a separate terminal (same venv), run the harness which executes the scenarios and prints a short summary table:

```powershell
python run_scenarios.py
```

The harness will:
- Flush Redis at start for deterministic runs
- Run Scenario A (Exact Quota), Scenario B (Concurrent Boundary), Scenario C (Distributed Enforcement), and Scenario D (Independent Customers)
- Print per-scenario results and a summary table and exit with a non-zero code on failure

3. Stop the cluster:

- If you started `solution/run_cluster.py` in a terminal, press `Ctrl+C` to stop the processes cleanly.
- If started with `Start-Process`, terminate the processes with Task Manager or:

```powershell
# replace <PID> with the actual PIDs printed by the runner
Stop-Process -Id <PID>
```

Project structure overview
--------------------------
- `solution/app/` — FastAPI application and configuration loader
  - `main.py` — HTTP app with `GET /health` and `GET /api/resource` endpoints
  - `config/customers.json` — per-customer quota config (including `northwind: 300`)
- `solution/limiter/redis_scripts/` — Redis Lua scripts
  - `sliding_window.lua` — atomic sliding-window script that uses `redis.call('TIME')`
- `solution/tests/` — tests
  - `test_sliding_window.py` — isolated Lua/script tests for boundary correctness
  - `test_api.py` — API integration tests using FastAPI TestClient
- `solution/harness/` — load-testing harness
  - `run_scenarios.py` — async harness that round-robins requests across three nodes and prints PASS/FAIL
- `solution/run_cluster.py` — local cluster runner launching three uvicorn workers for `solution.app.main:app`
- `solution/DECISIONS.md` — one-page decisions and conflict resolution summary

Notes and limitations
---------------------
- This prototype uses a single Redis instance as authoritative state. It demonstrates correct multi-node enforcement and atomicity but does not implement Redis cluster failover or multi-master replication. Those are out-of-scope for this exercise.
- The limiter implements strict sliding-window semantics (no more than N requests in any 60s interval). This choice was made to satisfy the explicit CTO requirement for auditable, never-exceed behavior. Operational exceptions must be applied by changing the customer's configured quota in `solution/app/config/customers.json` and are auditable.

If something fails
------------------
- Confirm Redis is running at `localhost:6379`.
- Ensure your venv is activated and dependencies are installed.
- Check logs in the terminal running `solution/run_cluster.py` for uvicorn errors.

Contact
-------
If you want me to run the harness automatically and collect the output, tell me and I will prepare an orchestration script that starts the cluster, waits for readiness, runs the harness, and tears down the cluster.
```

If you'd like, I can also add a convenience PowerShell script to start the cluster, run the harness, and stop the cluster automatically. Would you like that?

Made changes.