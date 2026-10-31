# Standard Operating Framework for Claude Code

> Derived from CS 180 (Introduction to Software Engineering, UC Riverside) and
> *Software Engineering at Google*, Ch. 1. This file is the contract for how Claude Code
> works in this repository. It applies to every task: writing, modifying, debugging,
> testing, reviewing, and documenting code.
>
> Rule IDs (`R-x`) are stable. The user may cite one to correct behavior mid-task
> ("you broke R-12"). Skill IDs (`S-x`) name the capability to apply.

---

## 0. Precedence

1. An explicit instruction from the user in the current conversation.
2. `CLAUDE.local.md` or a nested `CLAUDE.md` deeper in the tree (project-specific overrides).
3. This file.
4. Claude Code defaults.

If an instruction conflicts with a rule here, follow the instruction and say which rule
is being suspended and why. Never silently drop a rule.

---

## 1. Prime Directive

**Do not blindly implement requests.**

Cheap code generation moved the expensive work upstream (specifying the right behavior)
and downstream (verifying the change belongs in this repository). Producing plausible
code fast is not the job. The job is a **bounded, reviewable, correct change that leaves
the repository healthier than it was.**

Before any edit, four things must be true:

1. **Understood** — the existing code, its conventions, and what currently works.
2. **Bounded** — the files/modules in scope, and the ones explicitly out of scope.
3. **Specified** — acceptance criteria that can be checked, not vibes.
4. **Reversible** — a way to tell if this broke something that used to work.

If any of the four is missing, get it before editing. Ask, or read the code.

**Three jobs of code** (CS180 Lec 8). Every change must leave all three intact:
1. It implements the required behavior.
2. It supports future change.
3. It communicates clearly to whoever reads it next.
Failing any one means the code is broken, even if tests are green.

**The two failure modes that matter most:**
- *Functionally right, structurally wrong* — the test passes but the logic was pasted
  into the first matching caller instead of the module that owns it. (NITR)
- *Locally right, globally poisonous* — today's shortcut makes next month's change
  expensive. (EvoClaw milestone DAG)

Passing tests is necessary and **not sufficient**. Empirically, 90–93% of defects in
LLM-generated code are code smells rather than test failures, and unit-test success shows
no correlation with structural quality (Sonar/arXiv 2508.14727, 2025).

---

## 2. Skills

Capabilities to invoke deliberately. Each has a matching skill file under
`.claude/skills/` with the full procedure.

| ID | Skill | What it is |
|----|-------|-----------|
| **S-1** | **Spec-First Task Brief** | Convert a request into Task / Scope+Constraints / Acceptance Criteria before touching code. |
| **S-2** | **Context Packet Assembly** | Deliberately select the minimum set of files, tests, and docs that ground the change. Retrieval, not dumping. |
| **S-3** | **Modular Design** | Place behavior in the module that owns it. High cohesion, low coupling, SOLID, information hiding. |
| **S-4** | **Test-First Verification** | Define success as executable tests before implementation; cover the critical scenarios, not the happy path. |
| **S-5** | **Systematic Debugging** | Reproduce → minimize (delta debugging) → localize → hypothesize → fix root cause → regression test. |
| **S-6** | **Refactoring (Two Hats)** | Improve structure without changing behavior — never mixed with feature work in the same commit. |
| **S-7** | **Self-Review Against Structural Oracles** | Critique the diff for placement, coupling, API discipline, and unverified claims before declaring done. |
| **S-8** | **Static Analysis Gate** | Linters, type checkers, and security patterns as a hard gate — with AI-generated code held to the stricter config. |
| **S-9** | **Scaling & Performance Analysis** | Measure first. Identify the bottleneck. Change the design, not the constant factor. |

---

## 3. Use Cases — which skill, when

| Situation | Skill chain |
|---|---|
| New feature request | S-1 → S-2 → S-3 → S-4 → implement → S-8 → S-7 |
| Bug report / "it's broken" | S-5 → S-4 (failing test first) → fix → S-7 |
| "Clean this up" / "this is messy" | S-4 (characterization tests) → S-6 → S-8 → S-7 |
| "It's too slow" | S-9 → S-2 → S-3 (if the design is the bottleneck) → S-4 |
| Adding a variant of something that exists (new format, new provider, new payment type) | S-3 (Open–Closed: extend, do not branch) → S-4 |
| Reviewing existing or generated code | S-7 → S-8 |
| Change spanning >3 modules, or an unfamiliar repo | S-1 → S-2 → plan and **stop for approval** before editing |
| Any change to auth, secrets, payments, user data, or migrations | S-1 → S-2 → S-4 → S-8 → **mandatory human review before merge** |
| Quick one-line typo / comment / constant rename | Just do it. Do not ceremony a two-character change. |

Proportionality is itself a rule (R-30). The framework scales with risk.

---

## 4. Rules (mandatory)

### Understanding before action
- **R-1** Read before you write. Never edit a file you have not read in this session.
- **R-2** Find the owner. Before adding behavior, identify which module *should* own it.
  If the natural owner is not where the code currently is, say so instead of pasting into
  the nearest caller.
- **R-3** Reuse before you invent. Search for an existing helper, interface, or test seam
  first (`grep`/`rg` for the domain nouns). Duplicated logic is a defect, not a shortcut.
- **R-4** Match the codebase. Existing naming, error handling, layering, and test style win
  over personal preference — even a worse convention, applied consistently, beats a local
  improvement that fragments the codebase. Propose the convention change separately.
- **R-5** State assumptions explicitly. If a requirement is ambiguous, write the
  interpretation into the task brief before coding. Most AI failures are unasked
  requirements, not model errors.

### Scope discipline
- **R-6** Smallest reliable change. The correct diff is the smallest one that fully
  satisfies the acceptance criteria and leaves the design sound. Not the smallest one that
  makes the test pass.
- **R-7** Stay in scope. Do not edit files outside the declared scope. If the fix genuinely
  requires an out-of-scope file, stop and say why before proceeding.
- **R-8** One concern per change. Feature work, refactoring, formatting, and dependency
  bumps are separate commits. Never wear two hats at once.
- **R-9** No drive-by changes. Do not reformat, rename, reorder imports, or "improve"
  untouched code. Note it as a follow-up instead.
- **R-10** No new dependency without asking. Verify the package exists and is maintained —
  hallucinated imports are a documented LLM failure mode.

### Correctness and honesty
- **R-11** Never claim something works without running it. "Should work" is not a result.
  If it cannot be run here, say exactly what was and was not verified.
- **R-12** Never fabricate. No invented APIs, config keys, file paths, metrics, benchmark
  numbers, or test results. If unknown, read the source or say it is unknown.
- **R-13** Report failures immediately. A failing test, a broken build, or an approach that
  did not work gets surfaced in the moment — not buried, not worked around silently.
- **R-14** Delete nothing you do not understand. Dead-looking code may be load-bearing
  (Hyrum's Law: with enough users, every observable behavior of a system is depended on by
  somebody). Confirm before removal.
- **R-15** No suppression to pass a gate. Never add `eslint-disable`, `# type: ignore`,
  `@ts-ignore`, `--no-verify`, skipped tests, or widened `any` to get green. Fix the cause
  or escalate. A gate the agent can disable is not a gate.

### Structure
- **R-16** One reason to change per module (SRP). If describing a module needs "and", split it.
- **R-17** Extend, do not branch (OCP). A new `if`/`switch` case added to central logic to
  support a new variant is a design smell — add an implementation behind the existing
  abstraction instead.
- **R-18** Depend on abstractions (DIP). High-level policy must not construct or import
  concrete low-level implementations directly; inject them.
- **R-19** Keep behavior changes local. A small behavior change must not widen a public
  API, add a flag to the signature, or leak into call sites. Fix it inside the owning module.
- **R-20** No layer tunneling. UI must not query the database. Business logic must not parse
  transport formats. Respect the seams that exist.

### Verification
- **R-21** Every behavior change ships with a test. Bug fix → a test that fails before the
  fix and passes after. Feature → tests for the acceptance criteria.
- **R-22** Cover the critical scenarios, not the happy path: normal case, edge case, invalid
  input, empty input, duplicate/repeat action, and the explicit "must not happen" case.
- **R-23** Run the existing suite before and after. A change is not done until previously
  passing tests still pass. Report the before/after counts.
- **R-24** Lint and type-check before declaring done, and treat errors as blocking (R-15).
- **R-25** Never weaken a test to make code pass. If a test is genuinely wrong, say so and
  fix it as its own change with justification.

### Communication
- **R-26** Explain the *why*, not the *what*. The diff shows what changed; the summary must
  say why this approach, what was rejected, and what remains unverified.
- **R-27** Flag debt you create. If the change takes a shortcut under time pressure, name it
  explicitly and where it will hurt.
- **R-28** Escalate rather than guess on: irreversible operations, security-sensitive paths,
  ambiguous requirements with materially different valid readings, or three consecutive
  failed attempts at the same fix.
- **R-29** Stop after 3 failed attempts on the same approach. Re-diagnose, do not retry.
  Looping is a failure mode; report what was tried and what was learned.
- **R-30** Be proportional. A typo fix does not need a task brief. A cross-cutting refactor
  does. Match ceremony to risk, and say which level is being applied.

---

## 5. Workflow

The agentic loop, with explicit gates. Do not skip forward; each stage's output is the
next stage's input.

```
BRIEF ──> RETRIEVE ──> PLAN ──> [GATE 1] ──> EDIT ──> VALIDATE ──> [GATE 2] ──> REVIEW ──> REPORT
                ^                                        |
                └──────────── RECOVER (max 3) ───────────┘
                                                         |
                                                    ESCALATE
```

### 1. BRIEF (S-1)
Restate the request as:
- **Task** — one or two sentences of intended behavior.
- **Scope** — files/modules that may be edited; files that must not be.
- **Constraints** — invariants, conventions, performance or compatibility limits.
- **Acceptance criteria** — checkable statements, each mappable to a test.
- **Out of scope** — what is deliberately not being done.

Ambiguity is resolved here, not during implementation. If two readings would produce
materially different systems, ask (R-5, R-28).

### 2. RETRIEVE (S-2)
Assemble the context packet — small, relevant, and explicit about why each item is present:
- the module that owns the behavior, and its interface;
- existing tests covering the area;
- the schema / persistence contract if data is touched;
- the architecture note or README section that governs placement;
- one or two call sites to see how it is actually used.

Retrieval quality beats prompt polish. Dumping the repo is not context engineering.
Stopping condition: you can name the owning module and predict which tests will break.

### 3. PLAN
Write, before editing:
- files to change and the change in each, in one line apiece;
- the design choice and the alternative rejected, with the reason;
- which acceptance criterion each edit serves;
- expected blast radius — what could regress.

### GATE 1 — approval
Stop and get approval when the change: touches more than three modules, alters a public
interface or schema, introduces a dependency, is irreversible (migration, deletion,
deploy), or touches auth/secrets/payments/user data. Otherwise proceed.

### 4. EDIT
- Smallest reliable change (R-6). In-scope files only (R-7).
- One concern per commit (R-8).
- Work in executable increments — edit, run, read the result, then continue. Do not write
  six files and run nothing.

### 5. VALIDATE
In order, and report actual output:
1. Targeted tests for the new behavior.
2. The module's existing test suite.
3. Full suite (or the affected package, if the full suite is impractical — say which).
4. Linter and type checker (S-8).
5. Manual check of anything not covered by automation, named explicitly.

### GATE 2 — evidence
Do not proceed on a claim. If it was not run, it is unverified and must be labeled so.

### 6. REVIEW (S-7)
Self-review the diff against the structural oracles in §7 and the checklist in
`templates/REVIEW_CHECKLIST.md`. Self-review improves drafts; it is not proof. On
security-sensitive paths, human review is mandatory (R-28).

### 7. REPORT
- What changed and why (R-26).
- Evidence: commands run, results, before/after test counts.
- What is **not** verified.
- Debt created or follow-ups deferred (R-27).

### RECOVER / ESCALATE
Each failure is one hypothesis eliminated — record it. After three failed attempts on the
same approach, stop and re-diagnose from evidence (R-29). Do not thrash.

---

## 6. Code Quality

**Readability.** Names are the primary documentation. Reveal intent; no `data`, `tmp`,
`handle`, `manager` without a qualifier. Extract a named constant instead of a magic
number. Extract a named function instead of a comment explaining a block. Keep the happy
path unindented; use early returns.

**Modularity.** High cohesion within a module (one reason to change), low coupling between
modules (narrow, explicit interfaces). Prefer composition to inheritance; when inheriting,
subtypes must be substitutable for their base (LSP) — no strengthened preconditions, no
weakened postconditions.

**Interfaces.** Lean, not fat (ISP). A client should not be forced to depend on methods it
does not use. Public surface is a liability: everything not required by a consumer is
private.

**Complexity budget.** A function doing more than one job, a parameter list past four, a
nesting depth past three, or a file past a few hundred lines is a signal to decompose. Not
a hard failure — a prompt to justify.

**Error handling.** Fail loudly and early. No empty catch blocks, no swallowed errors, no
returning `null` where the caller cannot distinguish it from a valid value. Error messages
name what failed, what was expected, and what to do about it.

**Security defaults** (documented LLM failure modes — Fu et al., ACM TOSEM 2024; ~30% of
Copilot snippets in production repos carried weaknesses):
- Never hardcode secrets, keys, tokens, or credentials. Environment or secret store only.
- Use cryptographically secure randomness for anything security-relevant (CWE-330 was the
  most common finding).
- Never build SQL, shell commands, or HTML by string concatenation with untrusted input —
  parameterize (CWE-89 / CWE-94).
- Validate at the boundary; trust nothing crossing a process or network edge.
- Least privilege for anything the agent runs. No broad destructive operations.

**Performance.** Correct and clear first. Optimize only after measurement (S-9). Premature
optimization that costs readability is rejected by default.

---

## 7. Testing & Verification

**Test-first.** Define success before implementation. For a bug: write the failing test
that reproduces it first. For a feature: turn each acceptance criterion into a test name
before writing the implementation. The later a defect is found, the more it costs.

**Levels.** Know which one is being written:
- *Unit* — one function/method, isolated.
- *Module* — one class/file/component and its internal collaboration.
- *Integration* — how modules interact across a boundary (this is where AI-generated code
  most often fails, and where it is most often under-tested).
- *System* — end-to-end behavior.
- *Acceptance* — does it satisfy the stated criteria.

**Selecting inputs.** The input space is effectively infinite; the goal is the fewest
inputs that find the most problems, with little overlap. Use both:
- *Black box* — derived from the spec: valid, boundary, invalid, empty, duplicate.
- *White box* — derived from the code: every statement executed, every branch taken both
  ways. Branch coverage is the practical target; a branch never taken cannot be shown correct.

**A test suite must cover, at minimum:** the normal case; each boundary; invalid input;
empty/null input; the repeat or duplicate action; and each explicit "must not happen" rule
from the brief. One happy-path test is a weak harness, not verification.

**Regression.** Modifications must not break what worked. Run the affected suite before
and after; when the full suite is too slow, select tests that cover the changed code paths
and say which selection was used and why.

**Test quality.** Tests are code and follow the same standards. One behavior per test; the
name states the behavior; arrange–act–assert; no logic in tests; deterministic (no real
clock, network, or randomness — inject them). Assert on behavior, not on implementation
details, or the test blocks future refactoring.

**Honest limits.** Testing shows the presence of defects, not their absence. State what
the tests do not cover.

---

## 8. Architecture

**Architecture vs design.** Architecture = what the components are, what each owns, and
how they talk. Design = how each component is built internally. Answer the architecture
question before the design question, and both before naming a framework.

**Decompose by responsibility.** For any non-trivial system: identify the actors → list
the core actions → group actions into modules with one main responsibility each → describe
one important data flow end to end. "One giant backend box" and "just use MVC" are both
non-answers.

**Fit the existing structure.** New code adopts the architecture that is already there.
Introducing a second pattern for the same concern is worse than an imperfect consistent
one. If the existing architecture genuinely cannot carry the requirement, say so and
propose the change explicitly — do not smuggle it in inside a feature.

**Known patterns, used on purpose:** layered (presentation / logic / persistence / data),
client–server, pipe-and-filter, MVC and variants. For AI-backed systems, the same
separation applies: **logic ("brain") / persistence ("brawn") / interface ("skin")** stay
in separate modules with explicit contracts between them. Model calls, prompts, and tool
definitions belong in the logic layer behind an interface — never inline in UI or storage code.

**Anticipate change.** Where a variation point is likely (a new export format, a second
provider, another storage backend), put an interface there now. Where it is not, do not —
unnecessary generality is its own smell.

**Complexity is the cost.** Every abstraction, layer, and indirection has to earn itself.
The default answer to "should I add an abstraction layer?" is no, unless there are at least
two real consumers or a named, likely change.

---

## 9. Debugging

Debugging is fault localization: finding the root cause, not the symptom. It is a
hypothesis–act–observe loop, run on evidence rather than guesses.

**Procedure (S-5):**
1. **Reproduce.** A deterministic reproduction comes before any fix. Cannot reproduce →
   cannot verify a fix. Capture the exact input, environment, and expected vs actual.
2. **Minimize.** Shrink the failing case by delta debugging: remove half the input; if it
   still fails, keep going; if it passes, take the other half; increase granularity and
   test complements when both halves pass. Stop at a 1-minimal case. A small failing case
   usually names the cause by itself.
3. **Localize.** Narrow to the responsible module using evidence — stack trace, bisect on
   history (`git bisect`), logging at boundaries, differential comparison against a
   passing input. Do not read the whole codebase hoping to spot it.
4. **Hypothesize.** State the suspected cause as a falsifiable sentence: "X fails because Y
   is Z when W."
5. **Test one hypothesis at a time.** One change, one observation. Changing several things
   at once destroys the signal.
6. **Fix the cause.** Not the symptom. `if (x == null) return;` at the crash site is a
   symptom patch unless the null is genuinely valid there — then it needs a comment saying
   why. Ask: why did this value get here, and what else can reach the same state?
7. **Regression test.** The reproduction becomes a permanent test (R-21).
8. **Look for siblings.** The same mistake usually exists elsewhere. Search for the pattern.

**Banned:** guess-and-check edits, adding `try/catch` to make an error disappear, changing
a test to match broken behavior, "fixed it" without knowing why it was broken. If the cause
is genuinely unknown after a fix appears to work, say so explicitly (R-11).

---

## 10. Documentation

Document decisions and contracts. Do not narrate code.

**In code:** every public function/class gets a docstring stating purpose, parameters,
return, and errors raised. Comments explain *why* — a constraint, a trade-off, a
non-obvious reason. A comment restating the line above it is noise; delete it.

**Architecture Decision Records** (`docs/decisions/NNN-title.md`, template provided) for
any decision that is expensive to reverse: a dependency choice, a schema or interface
change, a pattern adopted, an approach rejected. Format: Context / Decision /
Alternatives considered / Consequences. Short — half a page.

**README** stays current: what it is, how to run it, how to test it, and the module map.
If a change makes the README wrong, fix the README in the same commit.

**Task record.** For any multi-step task, leave the brief and the report in the PR or the
commit body so the reasoning survives the session. Agent context resets; the repository
is the memory.

**Do not** create documentation files nobody asked for. Update what exists.

---

## 11. Git & Changes

- **R-31** Never commit or push unless asked. Show the diff and let the user decide.
- **R-32** Never force-push, rewrite shared history, `reset --hard` on shared branches,
  amend a pushed commit, or discard uncommitted work without explicit instruction.
- **R-33** Branch off the default branch for any non-trivial change; never commit directly
  to `main`/`master`.
- **R-34** Atomic commits. One logical change each. Refactor commit and feature commit are
  separate, in that order (structure first, then behavior — a reviewer can then read the
  behavior diff on its own).
- **R-35** Commit messages: imperative subject under ~70 chars, then a body saying *why*.
  Reference the issue. No "fix stuff", no "updates".
- **R-36** Never commit secrets, `.env` files, credentials, large binaries, or generated
  artifacts. Check the diff before staging.
- **R-37** Review your own diff line by line before proposing it — the first reviewer is
  the author (§7 oracles).
- **R-38** Keep changes reviewable. If a diff exceeds a few hundred lines, split it. A PR
  too large to review carefully will not be reviewed carefully.
- **R-39** PR description states: what, why, how verified, and what is not covered.
- **R-40** Leave the tree clean — no stray debug prints, commented-out code, scratch files,
  or `TODO: remove this`.

---

## 12. Structural oracles — the self-review gate (S-7)

Functional tests ask *does the visible behavior match?* Structural oracles ask *was this
solved in the right place?* Both must pass. Run this against the diff before reporting done:

**Placement** — Is the new logic in the module that owns that responsibility, or in the
first convenient caller?
**Duplication** — Does this logic already exist elsewhere? Will a future policy change now
require editing several places?
**Coupling** — Did this add a dependency between modules that previously did not know about
each other? Is it justified?
**API discipline** — Did a small behavior change widen a public interface, add a boolean
flag, or bypass an existing interface with ad-hoc branching?
**Extensibility** — When the analogous next requirement arrives (the next format, the next
provider), does the core logic change again? If yes, it was solved with a branch instead of
an abstraction.
**Testability** — Can the new code be tested without heavy mocking? Heavy mocks mean tight
coupling.
**Scope** — Is every line in the diff traceable to an acceptance criterion?
**Evidence** — Which claims in the report are backed by a command that was actually run,
and which are assumptions?

Answer these explicitly. "Looks good" is not a review.

---

## 13. Definition of Done

A task is done only when all of these are true:

- [ ] Every acceptance criterion is satisfied and demonstrated by a test.
- [ ] New and existing tests pass; before/after results reported (R-23).
- [ ] Linter and type checker are clean, with nothing suppressed (R-15, R-24).
- [ ] The diff stayed inside the declared scope (R-7).
- [ ] Structural oracles (§12) answered explicitly.
- [ ] Behavior lives in the module that owns it (R-2).
- [ ] Public interfaces unchanged, or the change was called out and justified (R-19).
- [ ] No secrets, no debug leftovers, no commented-out code (R-36, R-40).
- [ ] Documentation and README updated where the change made them wrong.
- [ ] The report states what was verified, what was not, and any debt created (R-26, R-27).

Anything unchecked is reported as unfinished, not rounded up to done.

---

## 14. Project-specific: AI Soccer Outcome Predictor

> Carried over from this repo's original CLAUDE.md. Module map, commands and
> invariants are in `CLAUDE.local.md`.

### Data sources

- **football-data.org v4** — the only live football data source (fixtures, standings,
  form, scorers). Free tier: 10 requests/minute, so every call is cached AND
  self-throttled: `storage/_fdorg.py` reads the `X-RequestsAvailable` /
  `X-RequestCounter-Reset` response headers and will not send a request while the
  budget is spent (the provider asks clients to do this). Never bypass `_fdorg.get()`.
  Docs: https://www.football-data.org/documentation/quickstart
  Client: `storage/league_data_client.py` (HTTP layer in `storage/_fdorg.py`).
  Not on the free tier: xG, lineups, injuries — those helpers return empty payloads
  on purpose and the prompt omits the section.
- **Gemini** (`google-genai`, model `gemini-2.5-flash`) — reasoning only, never the
  probabilities. Called from `engine/prediction_engine.py`.

### Rules

- Only `POST /api/fixtures/{id}/prediction` may spend Gemini credit, and it must stay
  behind `backend/access.py` (Firebase auth + allowlist + daily quota).
- Probabilities come from Dixon-Coles; Gemini's winner/confidence is overridden by the
  model output, never the other way round.
- Any accuracy figure quoted must be the point-in-time backtest number
  (`python scripts/backtest.py`), never the `--leaky` contrast run.
