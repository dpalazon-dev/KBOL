---
type: Reference
title: "Documentary system and knowledge base: core"
description: "KB-DPP contract preserved for the installation."
class: fixed
state: Draft
status: draft
---

# Documentary system and knowledge base: core

**Version:** 1.0 · **State:** design reference for the target system · **Date:** 3 Nov 2026 · **Companion document:** [Implementation 1.0](KB-DPP-implementation.md)

> KB-DPP core 1.0 is the English edition of KB-DPP core 0.7, with the field names of `docs/glossary-es-en.md`; it introduces no semantic change.

This document defines the overall system: purpose, concepts, invariants, contracts and limits. It includes behavior, concrete contracts, scenarios and acceptance. The companion guide develops the construction sequence. Neither describes the deployed state of a project. Adopting this revision requires an explicit migration; editing the design does not modify existing repositories, permissions or decisions.

The base preserves knowledge in readable, versioned text, with explicit provenance, authority and validity. Agents help to discover, interpret, propose and execute within an authorization; people govern decisions; code enforces the constraints that can be checked mechanically. The guarantees are limited to the declared scope and to the paths that are actually controlled.

## Reading and results contract

This document is a primary reference for the target system, not a review of background material or an inventory of recommendations. It contains the rules needed to understand and carry out its purpose without retrieving conversations, research reports or decisions of a specific installation. The design decisions it states are the starting point; the parameters specific to each installation are completed with real data.

**MUST** expresses a conformance condition; **MUST NOT**, a prohibition; **BY DEFAULT**, a choice that is changed only through a recorded and evaluated difference; **OPTIONAL**, a capability that is not required until it is announced. "Is preserved", "is validated", "requires" and the conditions in the tables are requirements, unless the text identifies them as an example or an alternative.

The core answers what system is wanted, how it behaves and what results it must produce. The implementation answers how to materialize that behavior, in what order and with what evidence. Each file contains the contract needed for its responsibility. The links between them ease navigation, but are not reading preconditions. The implementation incorporates a versioned reproduction of the normative rules it needs; it cannot redefine them. Every joint update compares those blocks to avoid divergence.

The design reference and the built state are different things. A requirement written here does not become an implemented capability until its test and its use demonstrate it. Conformance is declared by result and scope, never by the mere presence of these documents.

| Result | Observable behavior | Minimum evidence to declare it achieved |
| --- | --- | --- |
| RES-01. Know what is in force | A query distinguishes clauses in force, superseded and proposed, preserves conditions and shows authority. | Cases of total, partial, future and conflicting supersession with expected outputs. |
| RES-02. Change knowledge under control | Only content approved by the corresponding authority is integrated as accepted. | Rejection of a fictitious approval, changed content and self-extension of permissions; receipt of a valid acceptance. |
| RES-03. Resume work | A session reconstructs goal, authorization, constraints, pending items and next step without presenting proposals as facts. | Interruption and resumption of a real task with changes not yet integrated. |
| RES-04. Answer with evidence | An answer reaches the source and representation used, preserves conditions and declares insufficiency when decisive evidence is missing. | Reviewed questions, resolvable citations, comparison against sources and an ablation test. |
| RES-05. Maintain coherence | An update identifies affected consumers and preserves history without modifying old derivations. | Source change, impact resolution and comparison of current and historical queries. |
| RES-06. Operate and recover | A partial failure neither duplicates effects nor is declared a success; a restore recovers a consistent set. | Idempotent retry, reconciliation and restore with queries and citations checked. |
| RES-07. Save effort without losing correctness | Representative tasks require less total human time or justify their cost through an agreed correctness improvement. | Comparison with a baseline, maintenance included, review of late errors and quality limits satisfied. |

Results are the unit of prioritization and of acceptance. Each increment declares which RES it delivers, which scenarios it covers and which evidence is missing. Modules, documents and tests are means to produce those results. No speed improvement compensates for an unauthorized acceptance, an omitted decisive condition or an exposure of data outside the permitted scope.

**Complete initial walkthrough.** Capture a textual source → propose a decision supported by it → review and ratify its content → integrate → query what is in force → propose and accept a partial amendment → query the consolidated text and its history → interrupt and resume the work → record the human cost. This walkthrough makes it possible to check RES-01 to RES-05 without needing multimodal ingestion or several writers. RES-06 is checked before trusting the installation; RES-07 requires sustained use.

**Parameters that require information from the installation:** real people and scopes, identity channels, data classification, available tools, budget, volume, tasks and baseline. The absence of a critical parameter blocks only the capability that depends on it. It is not filled in with an assumption, nor is it required to decide the whole future evolution before starting.

**Policy on design contradictions.** Normative contracts take precedence over examples, tool recommendations and local parameters. If two normative requirements are incompatible, the conflict is recorded and the reference is corrected before that behavior is implemented. Code, an external source or a conversation do not silently replace the contract.


<a id="1-purpose-problem-and-scope"></a>
<a id="1-purpose-problem-and-scope-1"></a>
<a id="1-purpose-problem-and-scope-2"></a>
<a id="1-purpose-problem-and-scope-3"></a>
## 1. Purpose, problem and scope

**Goal.** Increase the work correctly resolved with AI and reduce the total human time needed to achieve it, including explanation, supervision, review, correction and maintenance of the system itself. Hiding problems in order to interrupt less is a regression.

The problem appears when a session does not know which part of a decision is still in force, confuses a proposal with an authorization, uses an outdated synthesis or loses the goal and the constraints when resuming. Having more documents or a larger context window does not by itself resolve those ambiguities.

The system offers two connected capabilities, with separable rollout and evaluation:

1. **Governance and operational continuity:** decisions, questions, plans and milestones; authority; validity queries; execution evidence; handoff between sessions.
2. **Ingestion and documentary knowledge:** source inventory, representations, locators, extraction and interpretation, quality limitations and evidence retrieval.

The first can start with textual sources already available. The second is extended when real tasks require documents or modalities that are not yet adequately retrieved. Resolving every modality is not required in order to improve continuity.

**Reference use cases:** query what is in force and why; resume a task with its limits; propose and ratify a change; detect what is affected by an update; answer a question with locatable evidence or declare what is missing. Each installation selects its priority cases and measures its baseline.

**Outside the scope of the guarantees:** proving the truth of any claim, eliminating hallucinations, discovering every implicit relation, replacing business judgment, guaranteeing maintainability with tests alone or certifying regulatory compliance. Nor does it aim to replace the source systems or to build, by default, a general project manager or a multi-agent platform.

It is a working method supported by software: it prescribes cycles of knowledge, review and retrieval. Its portability is a desirable property; its value is demonstrated in the tasks of those who use it.

<a id="2-glossary"></a>
## 2. Glossary

| Term | Meaning |
| --- | --- |
| Record | Identifiable unit of knowledge or governance, with type, provenance, state and relations. |
| Source | Preserved original, or identified derived representation linked to an original. |
| Representation / derivation | Result of processing a specific source; it has its own identity, fingerprint and limitations. |
| Locator | Address of evidence within a version: page, section, table, cell, region, interval or code symbol. |
| Decision | Normative choice adopted by an identified authority. It does not prove that its premises are true nor that it has been executed. |
| Clause / anchor | Stable part of a decision that can be amended without superseding the others. |
| Fact | Claim with source, date and evidence class; it may be uncertain, disputed or corrected. The name of the type does not imply certainty. |
| Evidence class | Observed, computed, declared, modeled, predicted or assumed; it describes the origin of a claim, not its normative force. |
| Ratification | Authenticated approval of specific content by whoever had the authority to give it. |
| Verification | Check of content against evidence, with scope and result; it is not by itself equivalent to ratification. |
| Delegated authority | Prior, limited and verifiable permission to execute a class of actions. It does not allow the agent to extend its own permissions. |
| Validity | Applicability of a record or clause at an instant, computed from events, dates and effective relations. |
| Valid time | When a claim or decision is considered applicable in the domain. |
| Knowledge time | When an event was recorded and accepted in the authorized base. |
| As-of | Historical query that declares both the validity date and up to when the history is considered known. |
| Fixed / synthesis | Maintained document that integrates records and declares its dependencies and checks. |
| View | Regenerable projection: index, consolidated text, agenda or dashboard. It adds no facts or authorizations of its own. |
| Checker | Deterministic core for validation and computation; it shares its model with the queries, without needing a single monolithic module. |
| Harness | Adapter for an agent client that implements the contracts for opening, reading, writing, stopping and resuming. |
| Handoff | Brief context reconstructed from records and session evidence, with goal, limits, state and next step. |
| Receipt | Evidence of an operation: proposal, previous state, observed result and revision in which it was incorporated. |
| Pending impact | Dependency that requires re-evaluation; it is not equivalent to proving that its content is false. |
| Integrity broken / unchecked | Content missing or altered, versus a check that could not be completed; their causes are distinguished. |
| Exception report | Deviation, evidence, relevant options, recommendation, decision required and consequence of waiting. |
| Attention budget | Available time and review capacity, including the pending queue and its age. |
| Reserve | Capability not activated, with cost, owner and observable trigger. |
| Question contract | Questions that a new structure must make answerable, and proof of the improvement it brings. |

<a id="3-principles-of-the-system"></a>
<a id="3-principles-of-the-system-1"></a>
## 3. Principles of the system

The identifiers P1–P25 make it possible to trace requirements, controls and results. The complete normative meaning is defined in this version.

<a id="P1"></a>**P1. Accumulate reusable knowledge.** Preserving useful results avoids rediscovering them; reusing them requires checking validity and conditions.

<a id="P2"></a>**P2. Separate original, representation and interpretation.** An interpretation does not silently replace the evidence it comes from.

<a id="P3"></a>**P3. AI proposes and operates; people govern.** The agent may execute within a verifiable delegation. It does not ratify decisions nor turn its output into observed evidence.

<a id="P4"></a>**P4. Maintain what is used.** Detect contradictions, outdated dependencies and knowledge without use; review without generating automatic bureaucracy for every finding.

<a id="P5"></a>**P5. Stable identity and single responsibility.** Every piece of data has an owner. Projections and modular separation do not create a second owner if their origin is explicit.

<a id="P6"></a>**P6. Readable text as the canonical record.** Normative records live in versioned files; originals and representations that require other formats are preserved as such. Indexes are rebuildable.

<a id="P7"></a>**P7. Provenance, validity and limits travel with the data.** A resolvable citation does not by itself prove that it supports the claim.

<a id="P8"></a>**P8. Progressive reading.** Serve first what is needed to decide what to open, without omitting conditions that change the answer.

<a id="P9"></a>**P9. Portability through contracts.** Pin versions, formats and conformance tests; do not promise tool independence without testing the adapters.

<a id="P10"></a>**P10. Written and authenticated authority.** Fields describe authority; verifiable evidence demonstrates who approved what content and under which policy.

<a id="P11"></a>**P11. Distinguish normative and factual knowledge.** Authority decides which policy is in force. Factual correctness requires evidence; both can coexist with uncertainty.

<a id="P12"></a>**P12. Typed relations and explicit semantics.** Every edge has an owner and a direction; inverses are computed. Cycle constraints depend on the relation.

<a id="P13"></a>**P13. Preserve history and correct through events.** Accepted clauses are not rewritten. Mutability is defined per field. There is an exceptional procedure to withdraw content that must not be preserved.

<a id="P14"></a>**P14. Mechanically validate what is verifiable.** Determinism means reproducibility with the same inputs, not semantic truth. Content checks are evaluated separately.

<a id="P15"></a>**P15. Separate data and control with effective barriers.** Sources neither grant permissions nor execute instructions. Integration and external actions have controls independent of the proposed text.

<a id="P16"></a>**P16. Sufficient context at the lowest useful cost.** Reduce reads and tokens without losing decisive evidence. Relevance selects candidates; authority, validity and permissions determine how to use them.

<a id="P17"></a>**P17. Reconstructible continuity.** The handoff is derived from persisted state and execution evidence. What was not recorded cannot be magically deduced: it is declared as missing.

<a id="P18"></a>**P18. Observable and verifiable evidence.** A milestone needs acceptance criteria and results linked to the tested revision. A successful command is partial evidence when the result requires human judgment.

<a id="P19"></a>**P19. Proportional autonomy and review by exception.** Combine authorization, scope, reversibility, impact, tolerance and the ability to intervene. Reversibility alone does not authorize an action.

<a id="P19bis"></a>**P19 bis. Alternatives where there is a real choice.** Relevant discretionary decisions preserve options, criteria and reasons. Alternatives are not invented to correct a proven error or to comply with a constraint already set; the justified absence is recorded.

<a id="P20"></a>**P20. Measure use and correctness.** Total human minutes per correct result, with quality and safety limits. Intermediate indicators do not replace the result.

<a id="P21"></a>**P21. Add structure for demonstrable usefulness.** Each new field declares its reader or audit requirement; each type or relation, its question contract. Maintenance counts as cost.

<a id="P22"></a>**P22. Evolve in reviewable increments.** Grouping decisions reduces interruptions; it must not hide their number, effort or impact. Fix failures in the piece responsible for them before adding general rules.

<a id="P23"></a>**P23. Proportional complexity.** Reuse tools and dependencies when their total cost is lower than building them. Modularity does not imply microservices or duplicated vocabulary.

<a id="P24"></a>**P24. Explicit documentary coverage and evaluated fidelity.** Every promise of knowledge is limited to checked sources, modalities and quality. Ingestion is essential for the cases that need it, without requiring universal support before delivering value.

<a id="P25"></a>**P25. Separate method, domain and installation.** The system defines general contracts; the project, the meaning and authority of the domain; the installation, tools and operation. They are related through explicit versions.

<a id="4-components-and-responsibilities"></a>
## 4. Components and responsibilities

| Component | Responsibility | Limit |
| --- | --- | --- |
| Sources and ingestion | Inventory, capture, process and record quality and provenance. | Does not ratify decisions nor declare completeness without evaluation. |
| Records | Represent decisions, claims, questions, identity and authorized work. | Does not turn a field written by the agent into an approval. |
| Fixed documents and views | Synthesize or project records for people and agents. | Does not hide conditions nor act as an independent authority. |
| Governance | Policies, roles, delegations and checking of approvals. | Changing permissions requires authority prior to the change. |
| Validation and queries | Apply schemas, transitions, validity, impact and retrieval. | Does not certify the correctness of the meaning of any text. |
| Adapters | Implement opening, tools, receipts and continuity per client. | Does not introduce hidden business rules. |
| Measurement and evaluation | Record use, results, cost and failures; test changes. | Does not evaluate quality only by counting citations, tokens or tests. |
| Evolution | Decide what to correct, withdraw or extend on the basis of evidence. | Does not turn every recurrence into a new structure. |

They may be implemented in a modular monolith. Validation, view generation, command execution and ingestion keep separate interfaces even if they share a library. Queries do not execute milestone commands to answer a read.

<a id="5-knowledge-model"></a>
<a id="5-knowledge-model-1"></a>
## 5. Knowledge model

### Types and classes

Fundamental types: **source, fact, decision, person and role**. Types activated according to the use cases: **question, hypothesis/assumption, entity, plan, milestone and synthesis**. An installation profile declares which ones it uses and their dependencies; it cannot offer verifiable authorization without identity and roles, nor governed execution without an object that records its authorization and acceptance.

| Type | Content and purpose |
| --- | --- |
| Source | Original or derivation, location, identity, fingerprint, provenance and applicable quality. |
| Fact | Claim, evidence, temporal scope and sources; corrections preserve the previous claim. |
| Decision | Clauses, rationale, authority, relevant alternatives, scope and temporal effects. |
| Person | Identity of a human or agent participant and role holdings with an interval. Only necessary data. |
| Role | Scope, ratification capability and delegation conditions. |
| Question | Unknown, incident or factual discrepancy, owner, deadline and closing condition. |
| Hypothesis/assumption | Claim put to the test or assumed without one; refutation criterion or review date and consequence of failing. |
| Entity | Identity, name, aliases and domain class. Its attributes with factual meaning are expressed through facts. |
| Plan | Goal and grouping of milestones; approval, constraints and dependencies. It does not implicitly authorize every future action. |
| Milestone | Expected result, scope, required authorization, tolerances, acceptance criteria and checks. |
| Synthesis | Derived text, content and validity dependencies, review and freshness. |

Documentary classes describe maintenance: **record**, **source**, **fixed**, **view** and **archive**. Archiving changes participation in working views; it does not erase the identity nor prevent historical queries. An archived source is still evidence of the preserved content; it is not presented as the current version for that reason.

A fact gets its own file when it is reused, concerns an entity or needs an independent review cycle. The others may be claims marked within a record, with anchor, date, class and citation. Two citations of the same fragment are a signal to review duplication, not proof that they express the same fact.

### State, evidence and verification

These are distinct axes:

- **Governance state:** proposed, accepted, rejected; or the enumeration corresponding to the type.
- **Validity and dependencies:** total, partial or not in force; disputed, expired, base invalidated, pending impact.
- **Evidence class:** observed, computed, declared, modeled, predicted or assumed.
- **Verification:** what was checked, on what content, by whom, when and with what result.
- **Representation quality:** coverage and fidelity per dimension, errors and pending elements.

A human review does not automatically turn an inference into an observation. A decision may be accepted and rest on assumptions. A computed fact may come from wrong inputs. Every output must preserve these distinctions.

State changes are represented as append-only events linked to the record: event identity, previous and new state, actor, reason, recording time, temporal effect and authorization evidence where applicable. `state` represents the last admitted transition and is checked against those events. Events are not another store: they are part of the canonical record. The Git history makes it possible to audit their incorporation.

The transition to accepted requires a valid ratification. Rejecting is not equivalent to repealing a previously accepted decision: its normative withdrawal requires a successor decision. Each type has a complete transition table; the installation does not invent states outside it. "Unresolved impact" is the reason for an open question, not a state added informally.

### Relations

Each relation is written on one side. Its inverse is computed. The relations of a proposal produce no normative effects. Edges that need dates or provenance use typed objects, not prose mixed with IDs.

| Relation | Origin → target | Semantics |
| --- | --- | --- |
| `resolved_by` | question → decision | Resolves a normative choice; requires an accepted decision. |
| `challenges` | question → clause | Opens a normative dispute, without automatically repealing. |
| `amends` | decision → clause or decision record | Replacement, repeal or addition with explicit scope. |
| `supersedes` | decision, fact or source → record of the same type | Complete succession, with applicable date and authority or provenance. |
| `depends_on` | question, decision, plan or milestone → record/clause | Typed dependency with a satisfaction condition; the target merely existing is not enough. |
| `tests` | hypothesis → clause | Tests a premise or consequence of a decision; failing triggers a review, not an automatic repeal. |
| `based_on` | decision, fact, hypothesis or question → source/fact | Evidence for a claim or for a factual resolution. |
| `derived_from` | derived source → source | Lineage of a process over a specific version; never presupposes perfect fidelity. |
| `affects` | decision, fact or question → entity/record/synthesis | Scope or impact; by itself it implies neither causal dependency nor blocking. |
| `authorized_by` | decision, plan or milestone → role | Required capability; accompanied by an authenticated approval or delegation. |
| `holds` | person → role | Holding with an interval, incorporated under prior authority. |
| `vetoes` | decision → pattern and scope | Defined terminological or usage restriction, with exclusions and exceptions. |

A factual question may be resolved through `based_on` evidence and a verified closing event; a normative decision is not invented to declare a measurement result. A discrepancy between sources is represented as a question that affects both and preserves their evidence. `challenges` does not replace a universal contradiction relation between facts.

Cycles are prohibited in chains of succession, derivation and executable dependency. Cycles between context relations may be legitimate: a question resolved by a decision that affects that question must not be rejected. Queries use visited sets and expansion limits.

Vetoes apply to prescribed use in operational content, not indiscriminately to originals, historical citations, explanations of the prohibition itself or identifiers. A lexical pattern is a limited control; it does not by itself determine semantic equivalence.

### Extending the schema

An extension proposes concrete questions, examples, readers, capture cost, rules and migration. A new type needs a life cycle or relations that cannot be adequately expressed with the existing ones. Projects define entity classes and domain vocabulary; changes to general contracts are versioned in the system. Declared differences cannot silently lower authority, integrity or permissions.

<a id="6-mutability-validity-and-history"></a>
<a id="6-mutability-validity-and-history-1"></a>
<a id="6-mutability-validity-and-history-2"></a>
<a id="6-mutability-validity-and-history-3"></a>
<a id="6-mutability-validity-and-history-4"></a>
<a id="6-mutability-validity-and-history-5"></a>
## 6. Mutability, validity and history

### Mutability matrix

| Element | Permitted change |
| --- | --- |
| Non-accepted proposal | Editing through review; invalidates the checks of the previous content that no longer apply. |
| Accepted clause and its anchor | Not rewritten nor deleted; another decision amends or repeals it. |
| Consolidated factual claim | Correction through a new claim and explicit succession; preserve evidence of the error. |
| Approval, state and holding events | Append-only; corrections through later events, without fabricating historical activity. |
| Pointer to an original | May change with a check that it preserves the expected identity and fingerprint. |
| Original and derivation | Immutable content; a change of bytes or reprocessing produces another identified version. |
| Synthesis | Versioned editing and new verification of the changed content. |
| View / interoperability `status` | Deterministic regeneration from an explicit revision and instant. |
| Title, aliases and description | Versioned change; evaluate whether it alters meaning or references. Does not reopen an intact clause by default. |

The fingerprint policy distinguishes binary identity from normalization for comparisons. Originals are not normalized to check their integrity. Synthesis hashes include the semantically relevant dependencies: clause, state and policy version, not just their text. A repeal can invalidate a synthesis even though the original text remains identical.

### Two times and one revision

Each canonical event has `recorded_at`, an instant with time zone assigned by the integration mechanism, and a validity start `valid_from`; the end, when it exists, defines a half-open interval `[from, until)`. Dates declared by users or sources are kept separate from the evidence of incorporation. The author timestamps of a commit are not by themselves an authenticated clock.

A temporal query receives:

- `valid_at`: instant of the domain being asked about.
- `known_until`: cut-off of the admitted history.
- `revision`: canonical snapshot used to reconstruct the answer.

If only `valid_at` is provided, the default mode is "what we know today about that date" and the cut-off used is shown. "What was known then" also sets `known_until`. Differences within the day are not inferred when legacy data only have a date: the precision and the ambiguity are declared.

Example: a decision incorporated on day 10 enters into force on the 15th. A correction incorporated on the 20th and valid from the 12th affects the query for day 13 with knowledge up to the 20th, but not the same query with knowledge up to the 14th. The policy must expressly admit that retroactivity and the approval must cover it. `recorded_at` is never rewritten to simulate that it was already known.

### Amendment by clauses

`amends` carries `target`, `operation` and, when applicable, `by`:

- **Replacement (`replaces`):** target `ID#anchor`; `by` identifies the new clause of the amending record.
- **Repeal (`repeals`):** target `ID#anchor`; does not admit `by`.
- **Addition (`adds`):** decision target; `by` identifies a new clause and its explicit logical position.

The amendment applies only when it is accepted and valid at the queried cut-off. The consolidated text returns each clause with its provenance and effects. It does not summarize creatively nor hide pending proposals.

Two changes to the same clause with overlapping intervals are not ordered by file date or by reading order. The later one must declare the succession and dependency with respect to the earlier one, specify the resulting content and pass review against the current base. If ambiguity persists, integration is blocked. Withdrawing an amending decision does not automatically revive the previous clause: a decision is required that establishes what is in force from then on.

### Derived states and impact

They are computed, not edited: `in_force`, `disputed`, `base_invalidated`, `expired`, `outdated`, `impact_pending` and integrity states. An open question about a clause stops disputing it when it is resolved or the clause stops being in force; the question may still require explicit closing.

A new version of a source does not alter its historical derivations. Those that relied on the previous version require an impact review. The analysis identifies dependency, cause, origin revision, owner, deadline and resolution: updated, not affected with justification, or pending. The debt is recorded during the integration of the change; it does not depend on the agent remembering it in another session.

Impact propagates through declared dependencies, with traceability of the path and control of cascades. Detecting dependencies hidden in prose is not promised. A periodic or incident-driven semantic reading may propose the missing relations. Absence of an edge means absence of a declared relation, not proven independence.

<a id="7-authority-approval-and-writing"></a>
## 7. Authority, approval and writing

### Identity and approval

The minimum ratification evidence contains authenticated identity, capability exercised, approved content, base revision, approval date, scope and authorized temporal effect. It is bound to a canonical digest of the proposal: clauses, relations, dates and fields that change its meaning. Audit events and generated projections are excluded from that digest by an explicit rule to avoid self-reference.

`verified`, `author`, trailers or `authorized_by` written by an agent are declarations until they are checked against the trust mechanism. Approval may originate in an authenticated review, a controlled dashboard or another channel with verifiable identity. Copying a sentence from a conversation does not automatically turn it into an approval event.

The authority policy is evaluated from the base prior to the change and at the moment of approving. An operation cannot grant itself authority and use it to approve itself. The initial bootstrap declares a human root of trust and leaves evidence of its configuration. Revoking a role does not erase historical approvals; its effect on approvals not yet integrated is applied according to the explicit policy and revalidated at integration.

A later substantive change requires a new approval. A change of the base requires revalidating the impact; if the approved meaning or scope changes, the approval too. An agent does not hold a ratifying role. Actions under delegation are recorded as executions of that delegation, not as new human decisions.

### Integration gate

Git preserves snapshots and diffs; the server or integration mechanism applies the effective gate. A local hook helps, but it is not the security boundary. The canonical branch, the mandatory controls, the checker, the schemas and the authority policy are protected. Administrative exceptions are explicit, limited and audited; no guarantees are announced over paths that allow them to be bypassed.

Flow: proposal in an isolated branch → validation → review of content and impact → authenticated approval → revalidation against the current base → integration → receipt. The user sees understandable differences and relevant evidence; a YAML diff is not presumed to be a sufficient interface.

Every writer goes through the same gate. Temporarily restricting to a single writer may reduce coordination, but does not replace the controls. An authorized read uses a canonical snapshot; what is proposed and what is unconfirmed are shown separately.

### Receipts and partial failures

An operation records an idempotent ID, expected base, proposal, observed result and integrated revision, if any. A distinction is made between prepared proposal, local write, canonical integration and confirmed external effect. The receipt is built from re-reading the real state and the evidence of the system that performed the operation.

If there is a discrepancy or a lost response, the state is **unknown or partial result**, not "did not happen". It is inspected before retrying, and what did happen is reconciled or compensated. A commit does not by itself demonstrate that an email was sent, a deployment finished or an external file was saved.

<a id="8-retrieval-and-context"></a>
<a id="8-retrieval-and-context-1"></a>
<a id="8-retrieval-and-context-2"></a>
<a id="8-retrieval-and-context-3"></a>
<a id="8-retrieval-and-context-4"></a>
<a id="8-retrieval-and-context-5"></a>
<a id="8-retrieval-and-context-6"></a>
<a id="8-retrieval-and-context-7"></a>
<a id="8-retrieval-and-context-8"></a>
## 8. Retrieval and context

### Query contract

Deterministic queries operate on an explicit revision, clock and policy. They return IDs, content at the requested level, authority, validity, evidence, quality, provenance and warnings. Their output includes the coverage examined, truncations and options to expand; a budget limit is not presented as an exhaustive result.

| Query | Result |
| --- | --- |
| Handoff | Goal, authorization, scope, integrated and pending work, check results, next step and relevant questions. |
| By ID | L0: identity and description; L1: operational content and conditions; L2: complete record. |
| Consolidated | Text of the applicable clauses with their provenance, and proposed amendments shown separately. |
| As-of | State reconstructed under the two temporal cut-offs. |
| Entity | Related facts, decisions and questions, without turning a lack of results into an absence of knowledge. |
| Ready | Milestones with authorization, dependencies satisfied and, where applicable, a valid claim. |
| Agenda | Reviews and decisions by deadline, consequences and owner. |
| Impact | Affected dependencies, cause and resolution state. |
| Integrity and synthesis | Evidence of the last check, incidents and outdated dependencies. |
| Exploration | Candidates by text, alias, structure, relations or similarity, subject to the same permission and validity filter. |

The next step of the handoff is a recommendation derived from recorded data. The first failed test does not always indicate what to do: it may be an environment failure, an omitted check or an authorization constraint. Check results carry revision, environment and age; querying the handoff does not re-run them automatically.

### Relevance and authority

Lexical or semantic search finds candidates; it does not determine what is true nor what is in force. Retrieval by ID, relations and states is preferred for normative questions. Open questions may need full text, hybrid search or exploration. The choice is made with the installation's evaluations, not by excluding entire categories of tools.

Practical order: handoff and identity when known; scope and entity filters; bounded exploration; expansion and reading of evidence. Permissions are applied before exposing candidates and during their expansion. A fragment always travels with the identity and conditions of its record.

The following are distinguished: no matches, source not inventoried, source not processed, partial extraction, access restriction and insufficient evidence. Messages do not reveal the existence of restricted material to whoever is not allowed to know it. The ignorance map contains known questions; it does not demonstrate that every unknown has been discovered.

### Bottlenecks and budget

Priority combines work actually blocked, useful time to intervene, consequences, fragility of premises and observed signals. The number of edges is not by itself equivalent to business value. The installation publishes its criterion and makes it possible to explain why one matter appears before another.

Context has an adjustable budget. If the decisive evidence does not fit, the reading is expanded, a limited answer is offered or the necessary information is requested. A safety or authorization condition is not removed to meet a number of lines.

<a id="9-ingestion-and-documentary-understanding"></a>
<a id="9-ingestion-and-documentary-understanding-1"></a>
<a id="9-ingestion-and-documentary-understanding-2"></a>
<a id="9-ingestion-and-documentary-understanding-3"></a>
<a id="9-ingestion-and-documentary-understanding-4"></a>
<a id="9-ingestion-and-documentary-understanding-5"></a>
<a id="9-ingestion-and-documentary-understanding-6"></a>
<a id="9-ingestion-and-documentary-understanding-7"></a>
<a id="9-ingestion-and-documentary-understanding-8"></a>
<a id="9-ingestion-and-documentary-understanding-9"></a>
<a id="9-ingestion-and-documentary-understanding-10"></a>
<a id="9-ingestion-and-documentary-understanding-11"></a>
<a id="9-ingestion-and-documentary-understanding-12"></a>
<a id="9-ingestion-and-documentary-understanding-13"></a>
<a id="9-ingestion-and-documentary-understanding-14"></a>
## 9. Ingestion and documentary understanding

### Scope and flow

Inventory → capture version → extract structure → evaluate quality → propose interpretation → integrate under the record rules → retrieve evidence. The input distinguishes known, accessible, processed and evaluated sources. "Available" does not mean that all of its meaning is represented.

Each source receives the cheapest treatment that preserves what is needed for its tasks. It is escalated to another processor or modality when quality or a real question requires it. Running OCR, vision and semantic extraction on every document is not mandatory.

| Content | Treatment and limits to declare |
| --- | --- |
| Text and email | Native extraction, authorship, date and thread; distinguish quotation from instruction. |
| Native or scanned PDF | Reading order, pages, tables, figures and OCR where applicable. |
| Spreadsheet | Cells, formulas, available values, units and dependencies; distinguish stored value from recalculation. |
| XML and data | Schema parser; preserve types and structure. Do not flatten series or massive tables into prose. |
| Image, diagram or chart | Region, context, legends and limits of visual interpretation. |
| Audio and video | Intervals, participants when known, transcription uncertainty and relation between image and voice. |
| Code | Revision, file and symbol; the code graph does not replace the decision graph. |
| Web | Dated and fingerprinted capture; the URL is an origin, not an immutable version. |

### Identity, representations and citations

Original, structured representation and semantic interpretation have separate identities and cycles. The identity of a source is a stable ID, not the path nor the hash. Identical binary content, visual similarity and reference to the same concept are different equivalences; they are not merged automatically.

The record of the original preserves ID, provenance, intake date, location, format, access policy and fingerprint. The derivation adds `derived_from`, processor, version, identifiable configuration, date, its own fingerprint, coverage and quality. A sensitive configuration is referenced safely, without storing secrets.

The canonical citation points to the original and its locator. The reading evidence also preserves the identity and fingerprint of the representation used. If the locator depends on the processor, it is bound to that representation; a new derivation does not silently change the resolution of previous citations. A map between locators of versions must be checked; if it cannot be, the citation requires review.

A derivation does not ratify a decision. It may be the artifact read, and that fact must be reconstructible. Records are grounded in the original source, declaring the transformations used. A computed fact cites inputs, code/configuration and execution; the computed result is new information, not a mere copy.

A fragment does not need its own file merely because it is citable. It receives independent identity when it is reused or needs its own maintenance, preserving context, hierarchy and the link to its origin.

### Quality and corrections

Coverage, textual fidelity, structure, tables/units, visual elements, traceability and semantic quality are evaluated. A global percentage does not compensate for the loss of a negation, a unit or a decisive figure.

The processing state (pending, processed, partial or failed) is kept separate from quality and from review. The processor may report metrics; it does not certify itself as correct for having finished. The evaluation records method, sample, dimensions, result and unchecked elements.

A person who detects an error adds a negative evaluation or incident linked to the derivation. The derivation is excluded from the affected uses, and the original is consulted or the source is reprocessed. The historical output is not altered to make it match, nor is only a positive "reviewed" mark added.

### Integrity and update

Originals and derivations carry their own cryptographic fingerprints. Moving a resource preserves its ID if the fingerprint is verified. Reprocessing creates a new derivation. A new documentary version is another source, linked by succession; the previous derivations still represent their original and are not rewritten.

The periodic check detects alterations, disappearances and access failures. A timeout or an expired credential produces integrity unchecked, not proof of tampering. The output includes when it was last verified; the policy sets when evidence that is too old prevents a sensitive use. For operations that require it, verification happens at read time or a verified immutable copy is used.

A change of source triggers impact on those that cite it. Propagation does not invalidate the whole corpus by default nor interpret any editorial revision as a change to all its conclusions.

<a id="10-human-interaction-and-autonomy"></a>
<a id="10-human-interaction-and-autonomy-1"></a>
<a id="10-human-interaction-and-autonomy-2"></a>
<a id="10-human-interaction-and-autonomy-3"></a>
## 10. Human interaction and autonomy

The review interface shows what changes, why, evidence, impact, uncertainty and the effect of waiting. It allows accepting, rejecting, requesting changes and deferring. Actions are bound to the reviewed content. A dashboard is a view; its input events are recorded through the authority gate.

Capture must fit the channels people use. Little use of a dashboard is a signal to investigate the flow, not proof of a lack of discipline. Proposals from conversations are grouped and shown as such; an ambiguous sentence is not transformed into a ratification.

The sensor for unrecorded decisions may propose, at closing, detected decisions, commitments and assumptions. Its effectiveness is measured by useful proposals, omissions in a reviewed sample and review cost, not only by acceptance rate. It does not see conversations it has no access to.

An autonomous action needs a delegation in force and limits on operation type, target, resources, cost, deadline and external effects. Escalation considers impact and the possibility of correction, in addition to reversibility. Intervention happens with a real margin; it does not always wait until the last theoretical instant.

Exceptions with a common cause are grouped and duplicates are removed. Critical alerts are not suppressed by quota: when capacity is exhausted, the affected work is paused and the overflow is made visible. The queue has an owner, an age and an escalation policy; silence is not equivalent to approval.

Alternatives are required in decisions with real options. Proven corrections, delegated execution and compliance with a constraint can be justified without fabricating them. Preserving discarded alternatives serves to reopen a choice if its conditions change.

The calibration sample reviews autonomous actions and decisions not to escalate, combining random selection and higher-impact cases. More approvals and fewer comments are signals to investigate, not automatic proof of habituation. The review asks to check something concrete, not to read an extensive explanation from the agent as a substitute for evidence.

## 11. Security, privacy and execution limits

The threat model includes errors, malicious instructions in documents, approval impersonation, modification of controls, leakage between scopes and execution of unsafe commands. Defenses are tested on the enabled paths.

- Sources, conversions and tool responses are data with no capacity to change policies.
- Agents and processors receive minimum permissions; approval and integration credentials are not available without restriction to the proposer.
- Check commands are treated as code: review, isolated environment, resource and network limits, no unnecessary secrets. Queries read results; they do not execute commands embedded in sources.
- Paths, linked files, network access and potentially active formats are controlled during ingestion.
- Derivations, facts, indexes, caches, logs and exports inherit the restrictions of their sources. Aggregation does not remove confidentiality.
- An external service processes only authorized data classes under an explicit processing and retention policy.

The initial profile may assume that all authorized members read the whole repository. In that case, material that requires partial permissions is not ingested. Separating repositories is an option; a future permission layer requires tests that include searches, relations, indexes and errors.

The retention policy provides for the exceptional withdrawal of secrets, data exposed by mistake or content that must not be retained. It covers originals, derivations, history, clones, indexes and backups, with limits on verifiable deletion. The minimum permitted record of the incident is preserved without copying the withdrawn content again. P13 does not prevent this response.

<a id="12-concurrency-failures-and-operation"></a>
## 12. Concurrency, failures and operation

Canonical IDs are stable and do not require gapless sequences. A numeric display label is optional. Published identities are not renumbered to resolve collisions; legacy installations keep aliases and explicit migrations.

Each session uses an identified base and an isolated workspace. Before integrating, it is revalidated against the current canonical state: permissions, approvals, references, validity and semantic conflicts. A clean textual merge does not prove normative compatibility.

Claims are activated only when several executors need coordination. They are acquired atomically through the integration gate or a coordinator whose state and authority are declared. They include owner, expiry, renewal and a generation number that invalidates old executors. An informational notice is not enough to promise mutual exclusion. External actions also check that the claim is still valid when they depend on it.

| Failure | Behavior |
| --- | --- |
| Required authorization or integrity cannot be checked | Block the affected write or action and explain the condition. |
| Query or index unavailable | Read a validated snapshot if the policy and permissions allow it, declaring age and limits. |
| Telemetry unavailable | Record the gap; allow non-critical work if the policy admits it. Do not invent measurements. |
| Original inaccessible | Distinguish non-existence, permission and transient failure; use only evidence whose policy allows the observed state. |
| Unknown write result | Reconcile before retrying; avoid duplicates and declare partial effects. |
| Synchronization of a stale copy | Show revision and cut-off; do not ratify changes against a copy whose base cannot be verified. |

The installation sets volume, concurrency, budget, response times, availability and tolerance to data loss. Performance claims are measured. Backups include external originals, policies and approval evidence, not just Git; restoring a consistent set is tested. Views can be deleted and rebuilt from that set.

<a id="13-format-git-and-interoperability"></a>
<a id="13-format-git-and-interoperability-1"></a>
<a id="13-format-git-and-interoperability-2"></a>
<a id="13-format-git-and-interoperability-3"></a>
<a id="13-format-git-and-interoperability-4"></a>
## 13. Format, Git and interoperability

Markdown with a YAML header and Git are the choices for the normative record of this design. Their justification is the scale of teams and of reviewable corpora, the availability of tools and the value of diffs. It is not claimed that other stores are incapable of auditing or that any database is a second owner.

A relational database, lexical index, in-memory graph or vector index may be a rebuildable view. It is incorporated on measured need, including query cost, concurrency and operation. If the premises of the canonical store stop holding, an architectural decision is opened; the cost is not hidden to protect a preference.

The operational format is fully defined in this document: Markdown, YAML and the profile of fields, states and events described here. It uses interchange conventions inspired by OKF 0.2. It is not necessary to consult that standard to implement the profile itself. Declaring full external compatibility is an optional capability that requires testing the adapter against the corresponding external version. A generic reader need not execute the normative semantics of the system.

- One concept per file, with `type`, `title`, `description` and its own stable `id`. The path-based identifier of the external format is kept separate; moving files may break links of external readers and requires aliases or a checked update.
- `generated: {by, at}` identifies the producer; it grants neither trust nor privileges. `process:` does not mean that the content is deterministic or true.
- `verified` preserves positive events compatible with the format; they are bound to the digest of the verified content. Negative, partial and expired results live in explicit evaluations of the profile itself, without forcing meaning into `verified`.
- `sources` uses `resource` and a citation identifier, with extensions for locator, representation and fingerprint when needed.
- `stale_after` is an instant with time zone; it is computed with a declared policy. Elapsed time and repeal are different causes of review.
- `status` is a generated interoperability projection, not an authority of its own. The total projection table appears in the state contract of this document. Operational readers use the detailed state and the warnings.
- `index.md` is generated under the pinned format. The root of the package contains the concepts; instructions foreign to that format stay outside. If the reserved format of `log.md` is not used, the log carries another name.

Clause and claim markup follows the grammar of the concrete contract and the scenarios included in this document. The parser must distinguish text, code, escaped tags and quotations; it is not taken as trivial. The viewers used are tested to avoid hiding conditions or anchors.

Automatic modifications of projections happen before closing the final revision of the integrated tree, or through a controlled and reproducible operation. CI validates the result; it does not silently modify the content the person approved.

<a id="14-measurement-and-evaluation"></a>
<a id="14-measurement-and-evaluation-1"></a>
## 14. Measurement and evaluation

### Main metric

**Human minutes per correct result = all attributable human time / number of results that meet the agreed rubric.** The numerator includes failed attempts, review, capture, learning and maintenance; shared costs are allocated by a published criterion. If there are no correct results, the time and the failure are reported, not a favorable ratio.

Results are grouped by type and complexity to avoid apparent improvements due to easier tasks. The installation cost is shown separately from the recurring cost, but it does not disappear. Late errors are attributed to the original result with a declared follow-up window.

The HUMAN line may be a lightweight log of minutes, legitimate/avoidable interruptions, provisional result and corrections. The agent does not invent minutes or correctness. Time between messages is not equivalent to active attention; it is used only as an identified approximation and is contrasted with samples.

### Indicators and limits

| Indicator | Use and caution |
| --- | --- |
| Interruptions and queue | Count the avoidable ones, but watch for escalation omissions, age and overflow. |
| Rework and errors | Severity, cause, detection and repair time; not just quantity. |
| Tokens, latency and cost | Complete chain: ingestion, extraction, retries, navigation, generation and automatic review. |
| Retrieval | Coverage of decisive evidence, obsolete items served as current and failed searches. |
| Useful signal and support | Citations are a proxy; a sample evaluates whether they support the claim and whether conditions are missing. |
| Adoption and readability | Tasks completed, understanding, abandonment and effort per role/channel. |
| Maintenance | Time spent on the system versus the business; grouping decisions must not hide it. |
| Documentary quality | Fidelity per format and element; distinguish evaluated, not evaluated and failed. |

### Three levels of testing

1. **Deterministic invariants:** schemas, states, authority, temporality, clauses, impact, idempotency and restore. Positive, negative and property tests.
2. **AI evaluation:** reviewed sources and answers, full context, served context and ablation of decisive evidence; check conclusion, conditions, citations and abstention. The model's answer with the full context is not automatically the correct reference.
3. **Validation in use:** real tasks, total human cost, adoption and late errors. It complements the previous tests; it does not replace them.

The minimum regression set is run before changing retrieval or governance, even if the savings look good. The extensive evaluation may be activated by scale or uncertainty. Versions of model, prompts, tools, corpus and results are preserved; an independent set is held out to avoid tuning and evaluating on the same examples.

Improvement thresholds are set after the baseline and before evaluating the increment. The authorization and isolation invariants do not wait for it. Causality is not attributed from a single short series: equivalent tasks, isolated changes when possible and causes of regression are compared. A mechanism is simplified or withdrawn if its net cost does not pay off, preserving the necessary protections.

<a id="15-results-oriented-evolution"></a>
<a id="15-results-oriented-evolution-1"></a>
<a id="15-results-oriented-evolution-2"></a>
## 15. Results-oriented evolution

The system evolves through a cycle: observed problem → chosen RES result → scenario and contract → implementation → test → integration → use → measurement. Each increment must produce a complete walkthrough and evidence that allows it to be kept, corrected or withdrawn.

Optional capabilities (sleep phase, semantic lint, procedure capture, other indexes or multiple writers) propose improvements and are activated by an observed need. They do not ratify knowledge nor promote a claim by frequency. A known error is corrected without waiting for the schedule of an optional capability.

Performance or savings hypotheses are recorded as such until they are measured. Comparisons with other tools do not replace the system's own scenarios. The architecture is judged by results, correctness and maintenance cost, not by the number of components or documents.

The next development decision must identify the result sought, the failing case, the minimal change and the test that would demonstrate it. If that relationship cannot be formulated, the proposal requires clarification before becoming work.

## Persistent instructions, procedures and resolvable references

### Distribution of responsibilities

The agent's persistent instructions describe its behavior across all sessions: judgment, initiative within the assignment, relationship with the person, communication, treatment of evidence and uncertainty, and respect for the authorization in force. The entry files of each client load that profile through a tested mechanism. They are neither the definition of the system nor a copy of its operating manual.

Concepts, contracts and results belong to the design references. Owners, scopes, permissions and parameters belong to versioned policies and configuration. The steps to investigate, record, verify or deliver belong to procedures and skills loaded when appropriate. Verifiable constraints are enforced in the core and at the effect and integration gates. The task context gathers goal, constraints, evidence and relevant state. Extracting a protocol from the permanent instructions requires keeping an entry point that discovers it and an owner who applies it.

The permanent behavior must be brief and stable; it does not include catalogs of commands, schemas, lists of validations or complete tables of tools. An essential constraint may also be expressed as expected behavior, but its mechanical enforcement does not depend only on the model remembering a sentence. Code demonstrates implemented behavior; the accepted policy or decision demonstrates what is authorized or desired. A discrepancy between them is identified and resolved without automatically turning one into a substitute for the other.

### Navigable references local to the repository

Every reference intended to take the reader to another document or section uses a Markdown link with a resolvable target. Internal references use paths relative to the file that contains the link; sections use stable fragments. File names in code quotes serve to name artifacts; they do not replace a link when the reader is asked to consult them. Depending on section numbering, abbreviated titles or locations described only in prose is avoided.

Syntax example from a file at the root, with a fictitious target that the installation must create and validate:

```markdown
See [the integration contract](docs/system/integration.md#integration-gate).
```

An explicit anchor such as `<a id="integration-gate"></a>` preserves identity even if the visible title changes, provided the viewer used supports it. The installation tests its viewers; if it requires another fragment convention, it declares and validates it. Changing or moving a target requires updating references or keeping a resolvable alias. Citations of external evidence pin a version or revision and a locator when reproduction requires it; operational references to documentation in force are resolved within the project's revision.

The same criterion applies to documentation, skills, agent descriptions and comments that refer to documentation. In Python, JavaScript or shell comments, the link remains commented text. The structured relations of knowledge keep the IDs and types of the contract; the renderer generates their links. Markdown is not introduced inside an ID field to make it navigable.

### Linking, importing and retrieving are different operations

A link identifies a target; it does not prove that the agent has read its content. An import incorporates content into the context. An import syntax is used only in files and clients whose adapter supports it and where it has been tested; `@path` is not presumed to be a universal convention nor a permission to execute the imported content. Support for fragment imports is not presumed either. The core, the procedures manual or chains that end up loading them in full are not imported from the permanent entry.

The adapter discovers the declared targets, checks access and retrieves what is needed for the task. Transitive loading has limits on scope, depth and budget; it reports cycles, absences and omitted content. Reading a linked file does not raise the instructions contained in a source to system policy.

`rg` or `git grep` serve to locate references and to search for the fragment of interest in already identified files. They do not replace the link parser nor guarantee complete coverage. Reading may be bounded by anchor or section through a tool that preserves the relevant limits and conditions; an isolated match is not extracted if its meaning depends on the rest of the section.

### Validation and migration

The reference validator checks the existence and capitalization of paths, the resolution and uniqueness of fragments, links after moves and the imports actually enabled. It respects code blocks, escapes and literal examples so as not to treat them as active references. Imports have client-specific validation and are tested when their version changes. External checks distinguish an inaccessible link, access denied and a missing resource; a check not performed is not declared valid.

The migration inventories informal references, resolves their target and proposes links. It does not automatically turn a section number into an assumed anchor. It prioritizes documents in force and operational paths; accepted or historical records keep their protection and go through the authorized correction procedure or through a derived navigable view. The inventory keeps pending historical cases visible until the whole scope of the repository is covered. CI blocks new unresolvable operational references; the previous debt is recorded explicitly without imposing a silent historical rewrite.

**Acceptance:** moving a target preserves or repairs the incoming links; renaming a title preserves its stable anchor; a non-existent fragment fails; literal examples do not trigger loads; the permanent import does not drag in complete procedures; a task discovers and loads its procedure through the intended entry point. This control extends VAL-02 and VAL-14 and accompanies ESC-05 and ESC-09 when their adapters are enabled.

## Operation layer, access and harness improvement

### Responsibility and limits

The knowledge operation layer delivers to each task evidence, rules in force, applicable procedures and execution state; it receives proposals and results through controlled operations. "KOL" is here a descriptive name for this responsibility, not a conformance standard nor a new record class. Its success is measured by RES-01 to RES-07. A graph, a repository or a server accessible to agents do not by themselves demonstrate that result.

Three objects are distinguished: **domain knowledge** (what is known and what is in force), **procedural knowledge** (how to approach a class of work) and **execution state** (what happened in a specific task). A trace is not automatically transformed into a procedure; a procedure does not grant permission; a historical decision is not generalized outside its scope and conditions. Frequency of use, positive rating and confidence declared by a model are signals to investigate, not proofs of truth or authority.

A reusable procedure is represented through the existing types: `synthesis` for a derived guide; `decision` for ratified rules; `plan` and `milestone` for concrete work and its acceptance. Its body must identify scope, inputs, preconditions, steps, observable outputs, checks, external effects, stop conditions, recovery and sources. These are sections of the content, not new mandatory YAML fields nor executable code. An adapter that automates steps also needs a validated executable contract. A derived guide does not replace the decisions it cites nor inherit their authority over added content.

### One core, several channels and stores with an explicit owner

Git is the versioned store chosen for the canonical records. GitHub may host it and ease review and integration; it is neither mandatory nor a replacement for the core's controls. MCP is a protocol for accessing capabilities, not the knowledge store, the business authorization system or the agent's life cycle. The harness coordinates when those capabilities are queried and how their results are applied during the task.

Initial architecture: **agent or person → CLI/library/MCP adapter → domain core → canonical records and authorized sources**. The core gathers query, temporality, authority, validation and integration. Adapters translate inputs and outputs without duplicating those rules. Deploying microservices is not required: library and adapters may run in a single process or machine.

A single owner is kept per data class: accepted records and their normative events in the canonical store; originals in the authorized evidence repository; indexes as rebuildable views; traces, queues and operational receipts in the execution log defined by the installation. The latter may initially be a set of files. Its results are incorporated into knowledge through explicit references and proposals. Not all logs are copied to Git, nor is a second normative truth created. Changes between stores use an idempotent identifier and reconciliation; a distributed transaction is not presupposed.

The first delivery needs one complete operational channel. The MCP adapter is incorporated when a specific client is going to use it and it can pass the same acceptance as the CLI. A local MCP server does not require building a hosted platform. The remote service is justified when there is a need for shared access, clients without a local copy, central availability, review accessible to other profiles or permissions incompatible with distributing the complete repository. Before activating it, identity, isolation, concurrency, recovery and operation of the service are tested.

Identity comes from the authenticated channel and its authorized mapping, never from an `actor` sent freely by the model. Querying, proposing and integrating are separate capabilities. If the profile does not enable an operation, the adapter does not expose it or rejects it. Every operation with effects revalidates permissions in the core. An MCP interface does not protect against direct writes to the store: credentials, write paths and integration must close the paths outside the declared control. In profiles with readers of different scope, a Git copy with the whole history is not distributed to all of them; answers, indexes and caches must respect the effective scope.

The harness requests context when starting or resuming and on material changes of goal, source, authorization or revision. It verifies preconditions before effects and records the result when closing. Exposing a tool does not guarantee that the agent calls it. Where the query is mandatory, the controlled entry point verifies that it was made and blocks the effect if it is missing; a reminder in the prompt offers only a best-effort guarantee.

### Context package for a task

The read-only operation `context` is incorporated. It receives `task`, `goal`, `scope`, `revision`, the temporal cut-offs and `context_budget`; the core obtains the principal from the channel. It returns the common operation envelope and a package with:

- Package identifier, task, revision and policy applied, preparation instant and authorized scope.
- Relevant goal and constraints; effective decisions and clauses; applicable procedures and their preconditions.
- Evidence with versions and locators; pending items, conflicts, uncertainties and stop conditions.
- Persisted state of the task, proposals not yet integrated and justified next step, kept distinct.
- Included and omitted elements, reason, coverage and dependencies whose modification requires refreshing the package.

The budget declares quantity and unit; if it uses tokens, it identifies the counter or the estimate applied. It limits the context; it does not allow a decisive condition to be silently omitted. If the mandatory conditions do not fit, the result is partial or blocked and allows the scope to be reduced or the budget to be expanded. A package may reference evidence retrievable on demand; it does not load the whole base. It does not grant a portable authorization nor allow execution with revoked permissions: each effect revalidates authority and preconditions. The cache includes revision, temporal parameters, access scope, policy version and generator; on a revocation it is invalidated before serving again. An open session does not extend access by itself. Revocation prevents new deliveries and effects; it does not erase information already received by a client, whose treatment requires its own retention and session controls.

### Federated sources and external changes

The operational source keeps responsibility for its facts; the base keeps its interpretations, decisions and permitted evidence versions. Connecting an external system does not require moving all its content nor turn its messages into instructions. Events trigger review or proposed ingestion; they do not ratify decisions. For each connector, the following are declared: source system, access scope, copy/retention policy, change mechanism, last check and admissible delay for the intended use.

Each observation records object identity, version or fingerprint, event identifier if any, instant at the origin when available, reception instant and access check. If there is no event identifier, the connector derives a stable key from the origin, object and version; if it cannot distinguish versions, it does not declare guaranteed single delivery. Retries do not duplicate proposals; out-of-order events do not revert the version in force. The checkpoint is advanced only after persisting the receipt and the corresponding recoverable state.

Webhooks and polling may lose changes. Periodic reconciliation with the origin is declared and tested; real time is not promised without measuring it. A disconnection reports coverage and age; if the required freshness cannot be demonstrated, the conclusion or action that depends on it is blocked. A change marks consumers for review, preserving history. A removal or access revocation withdraws the content from answers and invalidates affected indexes and caches; the restricted retention of evidence depends on the authorized policy, not on Git allowing history to be kept. If the store cannot meet the required deletion or isolation, that data class is not incorporated there.

### Harness improvement with controlled promotion

Knowledge can help improve a harness and the harness can propose knowledge improvements. Both cycles are kept separate: **capture → interpret → validate → accept knowledge** and **observe failures → propose an operational change → experiment → evaluate → promote a version of the harness**. A task success does not prove that its strategy is generalizable; nor does the result of an execution ratify the facts the model assumed.

The profile declares an adjustable surface: selection and order of context, task instructions, procedures, tool strategies or scripts of bounded scope. Outside the optimizer's permission are the roots of trust, authorizations, isolation, integration controls, held-out data and evaluators, and the acceptance criteria of its own experiment. Changing those elements requires a separate governance procedure. An optimizer does not obtain new rights by modifying a prompt, a skill or a plugin. Candidate code and plugins are tested in isolation and are not installed in production as a consequence of a reflection.

Each candidate preserves observed failure, hypothesis, base version, exact difference, scope, budget, experiments and favorable and negative results. The experiment pins versions of model, client, harness, tools, corpus and evaluator. It uses development tasks to tune and independent tasks to accept; the optimizer does not access held-out answers nor alter its evaluator. Network access is controlled when it could contaminate the evaluation. The judgment of another model is a complementary signal, not sufficient independent proof of correctness or authorization.

Promotion requires invariants without regression, a quality criterion set beforehand and total cost within the budget, including discarded attempts and human time. The aggregate improvement does not hide a critical regression by task type. The evidence and its limits remain reviewable. Automatic promotion can operate only within a prior, bounded delegation for operational changes; normative changes follow their ratification. The previous version is preserved and harness rollback is tested; rolling it back does not undo external effects already produced, which require their own reconciliation or compensation.

The experience library preserves applicability conditions, evidence, counterexamples and expiry. Retrieving an old lesson requires checking current preconditions; textual similarity is not enough. Obsolete lessons are withdrawn from current use without losing traceability. Each cycle has limits on cost, time and iterations and stops if there is no evidence of improvement. This capability is optional: the first useful walkthrough is delivered with a stable harness, and experimentation starts when there are repeated failures, traces and an evaluable baseline.

### Acceptance of these capabilities

**ESC-09 — Equivalent access and restricted context (RES-01, RES-03, RES-04).** With the same principal, revision and query, CLI and MCP return the same clauses, citations, warnings and access decision, even if the presentation changes. A user without access receives neither the content nor sensitive hints in errors. An insufficient budget does not remove the decisive constraint. Revoking access after preparing the package prevents reusing it to read again or to execute. The scenario for the second adapter is required when that adapter is announced; it does not oblige building it in the first delivery.

**ESC-10 — Optimization without self-authorization (RES-02, RES-06, RES-07).** A candidate reduces latency by removing a mandatory check: it is rejected even if it improves the average. Another improves retrieval without changing permissions: it is promoted only after independent evaluation and a valid approval or delegation. Its version and receipt allow the previous harness to be restored. If the candidate fails, its cost remains included in the measurement. The optimizer cannot edit the test that rejected it.

**ESC-11 — Changes, duplicates and loss of access (RES-04, RES-05, RES-06).** A source emits version 2, repeats the event and then version 1 arrives: a single proposal for version 2 is preserved, without going back. A failure before persisting the receipt allows retrying without losing the change. Reconciliation detects a version omitted by the webhook. A revocation withdraws affected answers and caches; a historical query reports the access limit without revealing the text. The detection delay is measured against the declared budget.

## Concrete reference contracts

This section sets conventions sufficient to produce the first implementation without resorting to another specification. Extensions are versioned. The examples use fictitious identities and do not configure a real authority.

### Record and events

The canonical container is a UTF-8 file with a YAML header delimited by `---` and a Markdown body. The header is a map; repeated keys, object construction tags and values whose type does not match the contract are rejected. A safe parser is used. Unknown fields are preserved in interchanges and rejected in canonical writing until the schema declares their reader. No content of the header or the body is executed.

Mandatory common fields: `id` (stable string), `type` (type), `class` (documentary class), `title` (string), `description` (one-line string), `scope` (scope ID), `state` (enumeration of the type), `author` (actor ID), `events` (list) and `sources` (list, empty if there are no sources). New IDs are a type prefix plus a UUID; unique legacy ones are preserved. The reference prefixes are SRC, FACT, DEC, PER, ROLE, Q, HYP, ASM, ENT, PLAN, MS and SYN. The documentary class is record, source, fixed, view or archive.

Each admitted event contains `event_id`, `event_type`, `actor`, `recorded_at`, `valid_from`, `reason` and `event_evidence`. `valid_until` is optional. A transition also contains `previous_state` and `new_state`; in the initial event, the previous one is null. Timestamps carry a time zone. The event evidence identifies the mechanism and the proof with which its incorporation was verified. Non-admitted local events remain in the proposal; they do not invent a canonical date or authentication.

The materialized state must match the admitted history. An acceptance transition that has not yet entered into force may be accepted as an act, but the validity query shows it as future. Historical queries reconstruct the state from the admitted events up to the knowledge cut-off; they never filter only the current header.

| Type | Minimum additional fields |
| --- | --- |
| Original source | `subtype: original`, `origin`, `location`, `format`, `sha256`, `access`. |
| Derived source | `subtype: derived`, `derived_from`, `location`, `format`, `sha256`, `processor`, `processor_version`, `configuration_ref`, `processed_at`, `processing`, `quality`, `access`. |
| Fact | `claim`, `evidence_class`, `based_on`; date or interval of the claim, with its precision. |
| Decision | `authorized_by`, `alternatives`, `criteria`, `rationale`; clauses in the body; temporal effects in its events. |
| Person | `nature: human` or `agent`, `identity_ref`, `holds`. |
| Role | `scopes`, `capabilities`, `approval_rule`; changing these fields requires prior authority. |
| Entity | `name`, `aliases` and `entity_class`. |
| Question | `subtype: unknown`, `incident` or `discrepancy`, `owner`, `closing_condition`; deadline when there is one. |
| Hypothesis | `claim`, `test_plan`, `refutation_criterion`, `consequence_if_fails`. |
| Assumption | `claim`, `review_at`, `consequence_if_fails`. |
| Plan | `goal`, `milestones`, `authorized_by`, `constraints`. |
| Milestone | `goal`, `work_scope`, `authorized_by`, `acceptance`, `tolerances`, `checks`. |
| Synthesis | `dependencies`, `evaluations`; content in the body. |

`authorized_by` is a non-empty list of roles when acceptance/authorization is requested. `approval_rule` admits `one`, `all` or `quorum` with an explicit integer. By default, one valid human holder is required for each required role; if a role requires all or a quorum, that requirement applies as well. No relevant role can be satisfied by agent actors alone. The same human may satisfy several roles they hold unless the policy requires separation of duties.

Alternatives are stored as objects with identity, description and reason for selection/discarding. When there is no real choice, an empty list and a mandatory `no_alternatives_reason` are used. A fictitious option is not added to satisfy the form.

`sources` contains objects `{id, resource}` and optionally `anchor`, `representation_id`, `hash` and `context`. `resource` identifies the source record or artifact, not an instruction. A citation of transformed content includes `representation_id`; the hash of the representation can be resolved from its immutable record. A reference to an external mutable artifact needs an explicit version or hash.

`quality` contains evaluated dimensions with method, result and limits. Not evaluating a dimension is represented as `not_evaluated`, not as zero errors. `processing` admits pending, processed, partial or failed. The admission of a source and the result of its extraction are evaluated separately.

### Serialized relations

`resolved_by`, `challenges`, `supersedes`, `tests`, `based_on`, `derived_from`, `affects` and `authorized_by` are lists of IDs or of `ID#anchor` where the semantics admits clauses. A derived source has one main original identified in `derived_from`; a result of multiple inputs preserves the complete list and describes the role of each input in provenance.

`amends` is a list of `{target, operation, by?}`: replacement and addition require `by`; repeal prohibits it. `depends_on` is a list of `{target, condition}`; the initial conditions are `accepted_and_in_force`, `resolved`, `completed_with_evidence` and `available_with_integrity`. Another condition requires an explicit extension. `holds` contains `{role, from, until?}` plus the evidence of its events. `vetoes` contains `{pattern, scope, use, exclusions}`; the pattern engine and its limits are pinned in the schema version and do not execute arbitrary code.

By default, an invalid normative dependency blocks the work that needs it; a mere `affects` relation generates context or impact, not automatic blocking. Explanatory comments are stored apart from the references. The plan's `milestones` field groups work, but does not by itself create an authorization or a dependency.

### Clauses and claims in Markdown

A clause starts with `<clause id="C1">` on a line of its own and ends with `</clause>` on another. Its identifier is `C` followed by letters, digits, hyphen or underscore; it is unique within the decision and does not depend on position. Clauses are not nested. The text inside may be Markdown. Markup inside code blocks delimited by three or more backticks or tildes is not interpreted. An escaped tag does not open a clause either. An opening without a closing, a closing without an opening or a repeated ID are errors.

An inline factual claim uses `<fact id="H1" evidence="declared" source="s1">…</fact>`, with a unique ID, a class from the enumeration and a source that exists in `sources`; its date is recorded in the marked content or in the linked fact record. If it has its own life cycle, a fact record is created and cited through `<fact ref="FACT-id">…</fact>`. The visible text preserves conditions and units even if the viewer hides the markup.

### Digest and approval

The approvable content is converted into a JSON object with `id`, `type`, `class`, `title`, `description`, `scope`, `author`, `body`, `fields` and `requested_effects`. `fields` contains all the content and relation fields of the record except events, projections, caches, receipts, `verified`, evaluations and references to the approval. `requested_effects` contains transitions and their validity dates, without the incorporation timestamps that are still unknown. Therefore, changing an effective date or a relation changes the digest.

Profile serialization: keys sorted by Unicode code point; arrays in the declared order; no whitespace; UTF-8 without BOM; Unicode characters without normalization; mandatory JSON escaping of quotes, backslash and control characters; body line breaks normalized to LF. The numeric values of the object are exact integers; decimals are serialized as strings in the schema. Volatile fields are not removed heuristically. Digest = SHA-256 of those bytes. Test vectors are published when the serializer is implemented and all adapters must produce the same digest.

The admitted approval records `{approval_id, actor, identity_ref, roles, digest, base_revision, approved_at, policy_revision, proof}`. The proof must be verifiable through a trusted identity/service; storing that object without verifying it demonstrates nothing. Rejections and revocations are separate events. Changing content covered by the digest invalidates the approval for the new proposal. A change of base requires recomputing scope and validity before reusing an approval; a semantic change requires renewing it.

### Canonical types, execution and evaluation

The values of `type` are exactly `source`, `fact`, `decision`, `person`, `role`, `question`, `hypothesis`, `assumption`, `entity`, `plan`, `milestone` and `synthesis`. Names used in prose are presentation labels. The serialized states are the literals of the state table of this document. Actors use `human:<id>`, `process:<id>` or `<producer>/<version>`; their string identifies, but does not authenticate.

Initial admitted events: `creation`, `transition`, `ratification`, `approval_revocation`, `evaluation`, `holding_change`, `impact_resolution` and `import`. Events contain only the fields relevant to their class. The policy validates the actor and the evidence for each one. Incorporating a new proposal creates its creation event; in a proposal not yet incorporated the list may be empty and has no canonical time.

By default, an accepted decision or fact is not reopened: its successor is created. A resolved or discarded question and a completed milestone may be reopened through a reasoned transition at the same level of authority that authorized their closing, preserving the previous closing and indicating which evidence invalidates it. The target is `open` for questions and `authorized` for milestones, provided that the authorization is still in force. A validated/refuted hypothesis is revised through a new linked hypothesis; its previous experimental result is not erased.

`tolerances` is an object with declared limits of time, cost, resources and work scope. An absent limit does not mean unlimited: it is inherited from the delegation when the delegation defines it, or the action that needs it remains pending authorization. `acceptance` is a list of `{criterion_id, description, method, required}`; `method` is `command`, `human_review` or `ai_assisted_evaluation`. The latter requires a rubric and a human criterion for disagreement resolution.

`checks` contains `{check_id, criterion_id, executor, input, environment_ref, timeout, permitted_effects}`. The executor resolves an approved command or function from controlled configuration; the text of a source is not interpolated into a shell. The input cannot introduce paths or arguments outside the authorized scope. A command requires an expected exit code and captured evidence; a semantic criterion also requires the check declared by its method.

Each check result contains `{check_id, tested_revision, environment_ref, started_at, finished_at, result, evidence_ref, observations}`. `result` is `passed`, `failed`, `not_run` or `requires_review`. Completing a milestone requires all required criteria passed on the applicable revision and human acceptance when the method requires it. A skipped test is never equivalent to passed. The policy determines whether a later modification invalidates evidence through dependency; a result from another revision is not reused without justifying that equivalence.

An evaluation of content or representation contains `{evaluation_id, subject_id, digest_or_fingerprint, dimensions, method, actor, performed_at, result, evidence_ref, limitations}`. `result` admits `conforming`, `non_conforming`, `partial` and `not_evaluated`. A human evaluation may be negative. A new evaluation does not erase the previous one; the query shows the one applicable to the content and the unresolved discrepancies.

A delegation contains `{delegation_id, grantor, grantee, scopes, operations, resources, limits, valid_from, valid_until, revoked, approval_ref}`. The gate verifies the identity and authority of the grantor, validity, non-revocation and correspondence of the action with all the limits. The grantee cannot edit that delegation to extend its scope.

### Complete example of a decision proposal

This fictitious proposal is not yet integrated and has no ratification. `DEC-EXAMPLE` and `ROLE-EXAMPLE` are identities of the test corpus. The reference test creates the role first; resolving it by a person's visible name is not allowed.

```yaml
---
id: DEC-EXAMPLE
type: decision
class: record
title: Report delivery schedule
description: Deliver the report on Tuesdays using only verified data.
scope: operations
state: proposed
author: example-agent/1
events: []
sources: []
authorized_by: [ROLE-EXAMPLE]
alternatives:
  - id: A
    description: Delivery on Mondays.
    selected: false
    reason: It leaves no day to verify the data of the weekly close.
  - id: B
    description: Delivery on Tuesdays.
    selected: true
    reason: It reserves Monday to verify the data.
criteria: [Availability of verified data, Delivery deadline]
rationale: It is proposed to reserve one day for verification.
---
```

Markdown body of that same proposal:

```markdown
<clause id="C1">
The report is delivered on Tuesdays.
</clause>

<clause id="C2">
The report only includes verified data.
</clause>
```

The proposal can be validated as a proposal if the role and the scope exist. It does not authorize delivering the report nor demonstrate the acceptance of the policy. To accept it, the operation requests a transition with a validity date, computes the digest that includes it, obtains the authenticated proof and generates the admitted events at integration. Changing Tuesday to Wednesday after approving requires another digest and a new approval.

### From result to implementable work

Each development unit contains these fields, filled in with concrete information: `res_result`, `esc_scenario`, `current_behavior`, `expected_behavior`, `minimal_change`, `dependencies`, `test`, `integration_criterion`, `delivery_evidence` and `limits`. "Create module" or "write document" is not accepted as a finished task without linking it to a verifiable behavior.

Example: RES-01 / ESC-01; the query returns the complete old decision; it must return C1 of DEC-B and C2 of DEC-A; minimal change in clause resolution and presentation; test with the three records of the scenario; integration without conflicts; evidence of the query in a new session. It does not require incorporating a vector index or a second client to finish.


### Minimum interfaces

Interfaces may be CLI, library or API; their semantics are the same. Every response includes `operation_id`, `revision`, `valid_at`, `known_until`, `result`, `warnings` and `coverage`. If a temporal field does not apply, null is returned, not an invented date. `coverage` identifies the scope examined, truncation and elements not evaluated.

| Operation | Minimum input | Output and effect |
| --- | --- | --- |
| `validate` | Proposal, base revision, policy. | Errors and derived changes; does not integrate. |
| `query` | ID or criterion, level, revision and temporal cut-offs. | Content, provenance, authority, validity and limits; neither writes nor executes checks. |
| `context` | Task, goal, scope, revision, cut-offs and budget. | Authorized context package with constraints, evidence, omissions and refresh conditions; read-only. |
| `consolidate` | Decision, revision and cut-offs. | Effective clauses with origin; proposals kept separate. |
| `impact` | Proposal/change and base revision. | Affected items, paths, owners and pending resolutions. |
| `integrate` | Idempotent ID, proposal, base and approvals. | Integrated revision and receipt, conflict or result to reconcile. |
| `handoff` | Session/task and revision. | Goal, authorization, limits, persisted state and justified next steps. |
| `verify` | Milestone, revision, executor and authorization. | Result per criterion, environment, times, evidence and effects; requires isolation. |
| `ingest` | Source, access policy and processing profile. | Proposed source/derivation, provenance and quality; does not ratify interpretation. |
| `integrity` | Sources and check policy. | Matches, altered, missing or unchecked, with cause and last valid check. |

Minimum errors: `INVALID_SCHEMA`, `MISSING_REFERENCE`, `INSUFFICIENT_AUTHORITY`, `STALE_APPROVAL`, `BASE_CHANGED`, `NORMATIVE_CONFLICT`, `AMBIGUOUS_TIME`, `INTEGRITY_BROKEN`, `INTEGRITY_UNCHECKED`, `INSUFFICIENT_EVIDENCE`, `ACCESS_DENIED` and `UNKNOWN_RESULT`. A code describes a cause; `blocked`, `partial` or `failed` describe the operational result. They are not confused.

Integration revalidates the base before writing. A change of base returns `BASE_CHANGED` and does not silently retry a new decision. Repeating the same ID with the same content returns the previous receipt; with different content it is rejected. External actions also use their own idempotent evidence or require reconciliation when the provider does not allow it.

### Initial parameters and absence of data

Initial profile: one project, one writer, members with common read access, queries over files, controlled integration and textual sources. External actions are disabled until their delegation is declared. Checks are not executed automatically when a session is opened. Critical exceptions pause the affected work when they cannot be reviewed; ordinary ones are grouped for the owner's next review.

Accepted writing cannot be activated without identity, a root of trust and owners. External processing cannot be activated without data classes and authorized destinations. Savings cannot be claimed without a baseline, nor correctness without a rubric. Performance, attention and retention budgets are real installation parameters; the implementer must obtain them or explicitly declare the capability as not enabled, without creating fictitious numbers.


## State and interoperability contract

### Minimum states and transitions

This table defines the reference contract. The schema distinguishes initial states, transitions and authorized actor; it is not limited to validating a list of words.

| Type | Admitted written states | Relevant condition |
| --- | --- | --- |
| Decision | proposed, accepted, rejected | Accepting requires approval; once accepted, normative changes through succession. |
| Fact | proposed, accepted, rejected | Accepted means admitted under an evidence policy, not factual certainty. |
| Question | open, resolved, discarded | Normative closing by decision; factual closing with evidence and review; reasoned discarding. |
| Hypothesis | open, validated, refuted, retired | Result with protocol and evidence; "validated" is limited to the tested conditions. |
| Assumption | active, retired | Carries a review; its expiry is derived. Turning it into a hypothesis or fact requires a traceable record. |
| Plan | proposed, authorized, closed, cancelled | Authorization with scope; closing does not automatically demonstrate all the results. |
| Milestone | proposed, authorized, in_progress, completed, cancelled | Completing requires acceptance and evidence; blocking and claim are separate dimensions. |
| Source | registered, retired | Processing quality, version currency and integrity are separate dimensions. |
| Person, role, entity | proposed, active, retired | Activating identity or authority goes through its policy; an agent does not ratify. |
| Synthesis | draft, current, retired | Current requires verification of the content and the required dependencies. |

Initial reference transitions: proposed→accepted/rejected; open→resolved/discarded; hypothesis open→validated/refuted/retired; assumption active→retired; plan proposed→authorized/cancelled and authorized→closed/cancelled; milestone proposed→authorized/cancelled, authorized→in_progress/cancelled and in_progress→completed/cancelled; source registered→retired; person/role/entity proposed→active/retired and active→retired; synthesis draft→current/retired and current→draft/retired when its content is revised.

Reopenings and corrections of a closing require a reasoned event with an explicit policy and re-evaluation of the impact. A reverse transition by simply editing `state` is not admitted. The revision of a consolidated fact or hypothesis preserves the previous version and its evidence.

### Total projection of `status`

`status` is generated for each snapshot and export time; nobody edits it manually. These rules apply in order, to cover all the states above:

1. Class **archive**, state rejected, discarded, retired, cancelled, hypothesis refuted, or complete effective succession: `deprecated`.
2. Decision/fact/person/role/entity proposed; plan/milestone proposed; synthesis draft; hypothesis open; assumption active: `draft`.
3. Accepted decision/fact whose validity start is still in the future: `draft` until it enters into force; the acceptance and the schedule remain visible.
4. The remaining cases of the table: `stable`, with the detailed states and warnings of the profile itself.

`stable` expresses the stability of the record for interchange, not truth, permission to execute or extraction quality. An open question may be stable as a record; a registered source may have partial extraction. A partially in-force decision keeps `stable` and exposes which clauses apply. Dispute, integrity, expiry and quality travel as additional fields/warnings: a reader that does not understand them is not a certified operational client.

Views are not authoritative records. If a view is exported as a concept, its projection is computed from the represented content and its contract; it does not receive `stable` as a way to evade these rules. A source check that fails is not hidden by changing only `status`.

The passage of time may change a projection without user commits. Exports are generated for an explicit cut-off and carry its date; the live query computes validity at read time. An old exported file is never announced as real-time state.


## Self-contained acceptance scenarios

The following scenarios set expected results. They are fictitious test data and not decisions of a project. The implementation turns them into reproducible tests; their short IDs are admitted as legacy IDs of the test corpus. They are run with a pinned clock and an identified snapshot.

### ESC-01. Partial replacement without loss of conditions

Base known up to 3 November 2026 at 12:00 UTC:

- DEC-A, accepted on 1 November and valid from that instant: C1 "The report is delivered on Mondays"; C2 "The report only includes verified data".
- DEC-B, accepted on 2 November and valid from that instant: C1 "The report is delivered on Tuesdays". It declares `amends: [{target: DEC-A#C1, operation: replaces, by: DEC-B#C1}]`.
- DEC-C, proposed: C1 "The report also includes estimated data". It proposes replacing DEC-A#C2, without approval.

**Expected result:** consolidating DEC-A returns delivery on Tuesdays with origin DEC-B#C1 and the verified-data restriction with origin DEC-A#C2. DEC-A is partially in force. DEC-C appears as a non-binding proposal. Answering that estimates are admitted, that DEC-A died entirely or that delivery is still on Mondays is a failure.

**Conflict variant:** another accepted decision attempts to replace DEC-A#C1 in the same interval without declaring succession with respect to DEC-B. Integration returns `NORMATIVE_CONFLICT`; the canonical state keeps the previous result.

### ESC-02. Two temporal cut-offs

DEC-T is recorded on 10 November at 09:00 UTC, valid from the 15th: C1 "The deadline is five days". On the 20th at 09:00 UTC, DEC-U is admitted, under an approval that expressly authorizes retroactivity from the 12th: C1 "The deadline is seven days". DEC-U adds that rule from the 12th and expressly replaces DEC-T#C1 during the interval in which the latter would have applied. There is no other previous rule.

**Query A:** valid on the 13th at 12:00, known until the 14th at 12:00. Result: no applicable rule is recorded; DEC-T is future and DEC-U is not yet known.

**Query B:** valid on the 13th at 12:00, known until the 21st at 12:00. Result: seven days, with a notice of later incorporation and retroactive effect.

**Query C:** valid on the 16th at 12:00, known until the 17th at 12:00. Result: five days. The same validity date with knowledge until the 21st returns seven days. The real instant of incorporation of DEC-U is never changed.

### ESC-03. Authority bound to content

A human person holds ROLE-OPERATIONS and may ratify a decision in that scope. An agent may propose it. The proposal has digest D1 and base R1.

1. The agent adds by itself `verified: [{by: human:person, at: ...}]`: there is no authenticated approval; it is not accepted.
2. The person approves D1 through the trusted channel: the proposal may be integrated if the other rules pass.
3. The agent changes a clause and obtains D2: the approval of D1 does not authorize D2.
4. The agent proposes assigning itself the role and accepting its own decision in one operation: the prior authority is evaluated and it is rejected.
5. The response is lost after integrating D1: repeating its operation ID returns the existing revision and receipt, without a second acceptance.

### ESC-04. Source, representation and impact

SRC-A is an original; SRC-AR is its derivation and contains a table cited by FACT-A. FACT-A preserves original, locator and representation SRC-AR. SRC-B is ingested as a new documentary version and processed as SRC-BR.

**Expected result:** SRC-A and SRC-AR keep content and fingerprints; the historical query resolves the citation of FACT-A in SRC-AR. FACT-A requires an impact review, but it is not automatically declared false. Reprocessing SRC-A produces SRC-AR2; it does not silently replace the table of a previous citation. Changing only the path with the same fingerprint does not invalidate the content.

**Quality variant:** SRC-AR omits a column that changes the answer. A negative evaluation prevents using it as a sufficient representation for that question; the system consults the original or declares insufficiency. A store timeout produces `INTEGRITY_UNCHECKED`, not an accusation of tampering.

### ESC-05. Continuity without invented authorization

MS-A is authorized to prepare a report, with a prohibition on sending it. The session drafted a proposal in its branch, not yet integrated, and a check was not run for lack of access. The session is interrupted.

**Expected result:** the handoff preserves goal, the limit of not sending, base, location of the proposal, non-integrated state and the check not run. The next step may be to complete the verification or to request the missing access. It does not announce a delivered report, does not take the check as passed and does not execute commands to build the handoff.

### ESC-06. Decisive evidence missing and use of AI

The question is "Can the report include estimated data?". The reviewed reference is ESC-01. It is tested with the complete sources, with the sufficient consolidated text and with a package from which the decisive clause has been removed but which declares incomplete coverage.

**Expected result:** the first two answers preserve the verified-data restriction and the non-binding condition of DEC-C. In the ablation, the agent declares that evidence is missing to determine the policy, or queries the missing clause if it has permission. It does not take the proposal as an authorization. The evaluation checks behavior and meaning, not literal matching of sentences.

### ESC-07. Measuring the result

In a window, two tasks meet their rubric and one fails. Between execution, review, failed attempt and attributable maintenance, thirty human minutes are consumed.

**Expected result:** three attempts, two correct results, one failure and fifteen human minutes per correct result are reported, in addition to the breakdown. If a correct task later requires ten minutes of correction, they are added to the cost and its classification is updated according to the rubric. The failed attempt is not removed to improve the ratio.

### ESC-08. Conformance and delivery

A delivery passes tests and has a prepared branch, but it has not been integrated nor used in a new session. Its state is **prepared**, not **operational**. After integration, receipt and a correct real walkthrough, it is declared **operational within the tested scope**. The sustained benefit remains pending until representative tasks and late errors are measured.

The final matrix contains, per RES: scenarios executed, revision, environment, result, evidence, limits and owner. Critical failures of authority, normative conditions, required integrity or permissions prevent declaring the affected result conforming. The other independent results may advance within their authorized scope.


## Identification of this reference

Core 1.0, 3 Nov 2026 (English edition of core 0.7). It defines the target system and its acceptance. It replaces revision 0.6 as the design reference; it does not demonstrate deployed capabilities. The background and the bibliography are not dependencies for understanding or executing this contract.


