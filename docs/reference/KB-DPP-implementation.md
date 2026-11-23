---
type: Reference
title: "Documentary system and knowledge base: implementation guide"
description: "KB-DPP contract preserved for the installation."
class: fixed
state: Draft
status: draft
---

# Documentary system and knowledge base: implementation guide

**Version:** 1.0 · **State:** implementation reference for the target system · **Date:** 3 Nov 2026 · **Companion document:** [Core 1.0](KB-DPP-core.md)

> KB-DPP implementation 1.0 is the English edition of KB-DPP implementation 0.8, with the field names of `docs/glossary-es-en.md`; it introduces no semantic change.

This guide specifies a complete implementation by increments, with contracts, an incorporated normative model, scenarios and delivery criteria. It does not declare what is deployed in a project. It does not authorize actions on repositories or services because it contains examples of them. Each installation documents its choices, owners, versions, evidence and limits.

The unit of progress is a walkthrough that works: a person or agent resolves a task, the write passes the required controls, the result is integrated and its cost is observed. An approved document, a prepared branch or a green suite are not by themselves equivalent to a capability in use.

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


## 1. Scope of the first increment

Before choosing tools, complete a brief sheet with:

| Item | What must be decided |
| --- | --- |
| Users and tasks | Who needs what; three priority tasks with real examples. |
| Observable problem | Error or friction, concrete example, frequency known or pending measurement. |
| Initial profile | Operational governance, documentary knowledge or both; enabled contracts. |
| Corpus and volume | Sources, formats, number of records, expected growth and excluded scope. |
| Access | Who can read what; if everyone reads everything, which material stays outside. |
| Authority | Who ratifies each scope, who administers controls and how identity is demonstrated. |
| Writers and clients | Number of executors, tools, write paths and synchronization. |
| Baseline | How the tasks are resolved today, complete human cost, errors and available evidence. |
| Operation | Technical and human budget, response times, backup and incident owner. |
| Continuity criterion | Which result allows the increment to be extended, simplified or abandoned. |

Improvement targets are set after taking the baseline and before evaluating the change. Authorization, integrity and isolation constraints are required from the moment the corresponding path is enabled. Savings percentages are not invented, nor is a technology adopted because of a figure from someone else's benchmark.

The first pilot may be limited to one project, one client, one writer and one group with common access. That limitation is an explicit operational profile, not a promise that several writers or partial permissions already work.

<a id="2-design-source-versions-and-decisions"></a>
<a id="2-design-source-versions-and-decisions-1"></a>
## 2. Design source, versions and decisions

### Owner map

| Content | Recommended owner |
| --- | --- |
| Purpose, semantics, invariants and guarantees | Versioned core. |
| Serialized schemas, query contracts, projection and error catalog | Executable specification of the system, aligned with the core. |
| Tools, paths, operational values and activated capabilities | Installation document. |
| Authority and business vocabulary | Project records and configuration. |
| Deployed state and test results | Version manifest and delivery evidence. |
| Research material and background | Preserved sources, without automatic normative force. |

Two independent definitions of a rule are not maintained. The normative blocks reproduced for self-containment keep the same text and version in both documents; their editing is synchronized. Examples are checked against the included contract. Conflicts between documents are resolved before implementing the affected rule.

The system is distributed as a versioned package or repository. Each project pins a reproducible version and declares compatible differences. A copy cited by revision may serve as a transition, with a divergence check. Separating the common source does not require publishing a service or stopping existing use.

The delivery manifest identifies: version of the core, schema, checker, adapter, interchange profile, authority policy and revision of migrated data. A modification of the core does not automatically update old installations.

### Record of choices

Each relevant discretionary choice preserves options, criteria, reason, consequences and review condition. A proven correction may justify why there is no reasonable alternative. Decisions are grouped to save attention, keeping the effort and the individual changes visible.

Before adopting a recommendation from a source, record whether it is a local observation, a corroborated external result, a hypothesis or a preference. If an external figure decides the architecture, verify the primary source, conditions and locator. Historical sources are not edited to make them agree with the later design.

## 3. Architecture and tool selection

**Starting point:** canonical files, Git, a domain library, a query/validation executable and thin adapters. Separate within the program:

- Reading and syntactic validation.
- Model of records, events and relations.
- Authority policy and checking of approvals.
- Temporal resolution, clauses and impact.
- Queries and context assembly.
- Generation of views and exports.
- Ingestion and checking of originals.
- Isolated execution of checks.
- Telemetry and evaluation.

These are responsibilities, not mandatory services. No abstraction is created in anticipation: what is separated is what allows contracts to be tested and changed without mixing permissions, reading and execution.

| Need | Reasonable start | Condition to extend |
| --- | --- | --- |
| Normative queries | Headers and events loaded in memory; cache per revision if needed. | Measured latency or load cost above the budget. |
| Relation traversal | Adjacency structures; a graph library if it reduces code and maintenance. | Necessary queries that exceed the implemented traversal. |
| Pattern and aggregation | Query over the loaded model. | Embedded relational view if it simplifies queries or improves measured performance. |
| Textual discovery | Text and aliases with scope filters. | Lexical index when cost or failures justify it. |
| Semantic discovery | Not mandatory. | Candidates by similarity when they improve coverage on an evaluated set. |
| Schema validation | Formal schema and maintained validator, or small own code. | Choose by total cost; do not exclude validation libraries on principle. |
| Documentary processing | An engine suited to the pilot corpus and the necessary native parsers. | Another processor only for failures or costs of specific formats. |
| Orchestration | Explicit execution and simple jobs. | Queues or a coordinator when concurrency, retries or volume require it. |

Views carry origin revision, generator version and policy. They are rebuilt without calls to a model when they represent deterministic data. A summary generated by AI is not a deterministic view: it is a versioned synthesis with provenance and review.

<a id="4-record-contract-and-format"></a>
## 4. Record contract and format

### Identity and package

The installation sets prefixes and an ID generator without practical collisions: UUID/ULID or equivalent distributed identifiers; legacy IDs may be preserved. Numeric continuity is not required. Identity does not change when moving files or when integrating branches. File names and aliases are validated without turning a renumbering into a merge requirement.

The root of the knowledge package is kept separate from instructions, README and operational files that are not concepts. The operational profile is fully defined here. Implementing it does not require reading OKF or another external standard. Full compatibility with an external format is treated as an optional adapter, pinned to a version and tested before it is announced.

The common metadata of the profile itself include identity, type, documentary class, title, description, scope, materialized state, events and provenance. Event dates use ISO 8601 with time zone; the original precision of historical dates is preserved. A legacy `date` is not silently converted into an exact instant.

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

### Events, relations and readers

Each event records `event_id`, `event_type`, `actor`, `recorded_at`, `valid_from`, optional `valid_until`, `reason`, previous/new state where applicable and an evidence reference. The names are a contract of the system's schema; installations do not invent equivalent variants without a migration adapter.

Relation fields are lists of IDs or typed objects. Comments go separately. `depends_on` declares a condition, for example an accepted and applicable decision, a resolved question or a milestone completed with evidence. A proposed plan does not block an independent milestone by association, but that milestone needs its own sufficient authorization to be executed.

Sensitive events are produced or admitted by the trusted integration mechanism. A hand-written event is not considered authenticated because it contains `human:`. The schema distinguishes a reference to evidence from the check of that evidence.

Each field declares which query, rule, view or audit requirement needs it. The catalog avoids unused fields; it does not remove historical evidence because querying it is infrequent.

### Total projection of `status`

`status` is generated for each snapshot and export time; nobody edits it manually. These rules apply in order, to cover all the states above:

1. Class **archive**, state rejected, discarded, retired, cancelled, hypothesis refuted, or complete effective succession: `deprecated`.
2. Decision/fact/person/role/entity proposed; plan/milestone proposed; synthesis draft; hypothesis open; assumption active: `draft`.
3. Accepted decision/fact whose validity start is still in the future: `draft` until it enters into force; the acceptance and the schedule remain visible.
4. The remaining cases of the table: `stable`, with the detailed states and warnings of the profile itself.

`stable` expresses the stability of the record for interchange, not truth, permission to execute or extraction quality. An open question may be stable as a record; a registered source may have partial extraction. A partially in-force decision keeps `stable` and exposes which clauses apply. Dispute, integrity, expiry and quality travel as additional fields/warnings: a reader that does not understand them is not a certified operational client.

Views are not authoritative records. If a view is exported as a concept, its projection is computed from the represented content and its contract; it does not receive `stable` as a way to evade these rules. A source check that fails is not hidden by changing only `status`.

The passage of time may change a projection without user commits. Exports are generated for an explicit cut-off and carry its date; the live query computes validity at read time. An old exported file is never announced as real-time state.

### Compatibility and parsing

Respect the pinned forms of `generated`, `verified`, `sources`, `stale_after` and `status`. Do not reuse a boolean as `generated`, a date as the whole `verified` list, a relative deadline as `stale_after` or `path` where the profile requires `resource`.

The evaluations of the profile itself include positive/negative/partial result, scope, digest and limitations. `verified` is not used as the sole acceptance mechanism nor as the destination of negative evaluations. When the content changes, the current verification view only considers events bound to that content; the previous ones remain in the evaluation history.

Clauses and facts in the body have explicit anchors and a defined grammar. Test tags inside code blocks, escapes, malformed text, duplicate anchors and viewers that hide markup. The fields per type, the transitions and the scenarios of this document determine the tests the implementation must materialize; creating their test files is construction work, not an external design decision.

<a id="5-authority-and-integration"></a>
## 5. Authority and integration

### Mandatory choices

Define the identity provider or equivalent mechanism, approval channel, initial root of trust, owners per scope, administration permissions and delegation policy. If there are several owners of the same scope, set whether one, all or a quorum is required; do not leave it to the agent's interpretation.

Permission to modify a file is not the authority to approve its content. The approval is bound to the digest of the proposal and to the reviewed base. The previous policy authorizes changes of roles, permissions and checkers. An administrator does not obtain an invisible exception for being an administrator.

The remote must be able to require validation and review before modifying the canonical branch. If it does not allow this, an equivalent controlled gate is introduced or it is declared that this guarantee is not available; installing local hooks is not enough.

### Write sequence

1. Create a proposal with an operation ID and a base revision.
2. Validate form, references, transitions and modifications of protected fields.
3. Compute normative effects, impact and affected scopes on that base.
4. Show content, consequences and evidence to the necessary approvers.
5. Record authenticated approvals of the exact content.
6. Validate again against the most recent canonical base and the authority policy in force.
7. Prepare admitted events and deterministic projections; check the final tree.
8. Integrate atomically when possible; issue a receipt and record the authorized impact debt.
9. If the result is unknown, inspect by operation ID before retrying.

Changes of form that alter the digest or the meaning require the corresponding re-approval policy. Generated fields excluded from the digest have to be defined and validated, not form a way to introduce unreviewed text.

### Reviewers per scope

Generating the reviewers from roles may reduce duplication, but there are two sources of scope: touched files and relations/impact towards other scopes. A list based only on paths does not cover the second. The checker computes the set and the integration mechanism verifies the approvals of each required scope on the reviewed version.

Approval, rejection, request for changes and deferral are recorded. The absence of a response never counts as acceptance. A change of approval or of content is reflected in the views and prevents integrating with a stale review.

<a id="6-minimum-control-catalog"></a>
## 6. Minimum control catalog

The following IDs identify controls of this version; they do not reuse local numbers of an installation. Each implementation keeps traceability between control, function, test and communicated error.

| Control | What it verifies | On failure |
| --- | --- | --- |
| VAL-01 | Parsing, schema, types and permitted states. | Block the invalid change. |
| VAL-02 | Unique identity, resolvable references and aliases. | Block duplication or a missing required reference. |
| VAL-03 | Mutability and append-only events. | Reject alteration of protected content. |
| VAL-04 | Identity, prior authority, digest and validity of the approval. | Block acceptance or integration. |
| VAL-05 | Times, precision and explicit succession order. | Block normative ambiguity; preserve declared historical uncertainty. |
| VAL-06 | Scope and composition of clause amendments. | Reject an unresolved conflict or a non-existent target. |
| VAL-07 | Cycles prohibited per relation and dependency conditions. | Block an impossible dependency; allow valid contextual cycles. |
| VAL-08 | Reproducible views and total projection of `status`. | Regenerate before integrating or reject the discrepancy. |
| VAL-09 | Synthesis dependencies and impact debt. | Warn or block according to use and policy; never hide. |
| VAL-10 | Integrity of originals and derivations, locators and representation read. | Withdraw from affected uses or block uses that require that evidence. |
| VAL-11 | Permissions on reading, expansion, export and processing. | Deny access without leaking restricted information. |
| VAL-12 | Authorization, isolation and result of commands. | Do not execute, or record failed/not run. |
| VAL-13 | Base revision, retries and claims if activated. | Revalidate or reject a stale executor. |
| VAL-14 | Coverage and limitations visible on retrieval. | Do not present the result as complete. |
| VAL-15 | Receipts and consistency of restore. | Reconcile and declare a partial/unknown result. |

It is not necessary to activate all modules before the first use, but every enabled capability requires its controls. For example, automatic ratification is not offered with only VAL-01/02; ingestion of external originals is not offered without VAL-10/11. The delivery matrix marks **implemented**, **tested**, **not tested** or **out of scope**, with evidence.

## 7. Temporality, consolidation and impact

### Historical query contract

Interface example, adaptable to the client without changing its meaning:

```text
query --id DEC-example --valid-at 2026-11-13T12:00:00+01:00 \
  --known-until 2026-11-14T23:59:59+01:00 --revision <revision>
```

The response identifies both cut-offs and the precision of the data. If the knowledge cut-off is omitted, the last admitted snapshot is used and this is declared. The canonical revision identifies the available events; the query clock is an explicit input, not a hidden dependency on the environment.

Legacy data with only a date keep `precision: day` or equivalent. A single day with events whose order cannot be reconstructed is marked ambiguous. Do not fill in artificial hours nor use the alphabetical order of files to decide validity.

### Mandatory clause cases

- Replacing C1 preserves C2 and its provenance.
- A replacement proposal appears as non-binding.
- A future amendment does not alter the current consolidated text.
- Two overlapping changes without explicit succession produce a conflict.
- A chain of replacements preserves the origin of each clause.
- Repealing an amending decision does not automatically reactivate the previous text.
- An addition distinguishes clause identity and position; it does not depend on consecutive numbering.
- A retroactive change modifies "what we know today" without rewriting "what was known then".

### Impact and synthesis

The analysis combines explicit references, clauses used, states and policy. Comparing only the bytes of an immutable decision does not detect that another one has repealed it: the dependency signature includes its effective state and its relevant successors at the evaluation cut-off.

The change generates a list of affected items with cause and path. Each resolution identifies updated, not affected with reason, or pending with owner and deadline. Integration may accept visible debt if the policy allows it; it cannot accept as safe an action that requires an invalidated dependency.

A new version of a source leaves **pending impact** on its consumers. The historical derivations remain valid for the original they represent. A synthesis actually based on changed content or validity appears outdated until it is reviewed. The review may confirm that its conclusion does not change and record that evidence without rewriting it unnecessarily.

<a id="8-retrieval-adapters-and-continuity"></a>
## 8. Retrieval, adapters and continuity

Each query declares input, output, snapshot, clock, permissions, budget and errors. Outputs include structured fields for tools and an understandable presentation. The common contract is tested per client; it is not presupposed that all of them offer the same hooks or compaction moments.

### Adapter contracts

| Moment | Input and expected result |
| --- | --- |
| Opening | Load method version, project configuration and snapshot; show constraints and handoff. |
| Reading | Retrieve evidence with conditions; record coverage and representation read without copying unnecessary sensitive data. |
| Write preparation | Proposal and base revision; separate authorization from inferred intention. |
| Operation closing | Receipt, or unknown/partial state with a reconciliation path. |
| Compaction/resumption | Persist what is necessary and reconstruct goal, limits, pending items and next step. |
| End of session | Record provisional result, proposal of uncaptured decisions and pending human measurement if missing. |
| Blocking | Reason, affected scope and condition to continue; allow independent work already authorized. |

The constitution of the system, the project instructions and the handoff have separate responsibilities. Loading them cannot depend on a floating, unversioned path. Input from sources cannot be raised to higher-priority instructions.

### Minimum handoff

It includes goal and authorization reference; scope and tolerances; base revision; integrated work; pending local or branch changes; last verification evidence with revision and age; blockers and questions; next step and its basis; relevant changes by others.

If a nuance that is not recorded is lost, this is declared. A minimum record of intention may be necessary and is evaluated by its cost; "deduced by script" does not justify claiming that the system knows information that was never persisted. The conversational summary may help, but does not replace the normative state.

An initial length limit is adjusted through evaluation. Truncations indicate what was left out. A decisive constraint is never removed to meet forty lines or another presentation figure.

### Discovery and search

Test questions with a known ID and questions without one. Separate candidate retrieval, normative filtering and use of evidence. Lexical or semantic indexes are compared against the existing search on the installation's own tasks; the same set of permissions and warnings applies to all of them.

A synchronized copy carries a visible revision and cut-off date. If its currency cannot be checked, it serves for historical queries or exploration with declared limits; it is not a reliable base for ratifying the current state.

<a id="9-documentary-ingestion"></a>
<a id="9-documentary-ingestion-1"></a>
<a id="9-documentary-ingestion-2"></a>
<a id="9-documentary-ingestion-3"></a>
<a id="9-documentary-ingestion-4"></a>
## 9. Documentary ingestion

### Separate but connected pilot

Choose between five and ten documents that today generate questions or manual work. Record the formats covered and not tested. Do not add artificial documents only to complete a list of modalities, although specific adverse cases may be created to test controls.

Before processing, define questions, expected evidence, output limits towards external services and human preparation/review time. An isolated extraction test may start early; an integrated pilot needs identity, source/derivation, locators, permissions and integrity checking first.

### Processors

Select a structured engine as a candidate (for example, Docling) or a lightweight converter if the corpus needs nothing more. Check capabilities on the pinned version and on the installation's own documents. XML, spreadsheets and data may require specific parsers; it is not presupposed that a universal converter preserves their semantics.

Preserve the necessary native representation and a minimum common contract. An additional interchange format only comes in when a consumer needs it. Alternatives such as other OCR engines or engines for scientific documents are incorporated because of concrete failures or a measured advantage, not to complete a catalog.

Each run records inputs, processor, version, identifiable configuration, modality, resources consumed, result, errors and quality. Conversions are cached by input identity and configuration; a change of processor produces another derivation and a regression evaluation.

### Originals, derivations and locators

The store may be large-file storage, objects or a controlled drive. It must allow fingerprints to be checked, versions to be kept, permissions to be applied and the set to be restored. The folder organization is operational, not identity.

SHA-256 is the initial algorithm of the profile. Each original and each derivation have their own fingerprint. Lineage does not replace the fingerprint of the result. Pointers may change only after checking the content; reprocessing never overwrites a historical derivation.

A citation preserves:

- ID of the original and logical locator.
- ID of the representation used to resolve it.
- Fingerprint or immutable version of that representation.
- Retrieved evidence and required context, within the storage and privacy limits.

If a table receives another identifier after reprocessing, the previous citation still resolves in its earlier representation or is marked as pending repair. It is not silently redirected to a different table with the same name.

### Quality and acceptance

Separate the process finishing from its output being faithful. The review sample includes relevant tables, units, negations, formulas, legends and reading order. A document with correct text and a pending diagram is not served as complete for a question that depends on the diagram.

The reviewer may record a negative, partial or unchecked result. A negative evaluation blocks the affected uses and opens correction/reprocessing. The immutable output is not changed, nor is disagreement expressed by only adding a positive `verified`.

**Tests of the integrated pilot:**

1. Moving a source preserves identity and internal citations; the affected external links are repaired or declared.
2. Each locator used resolves in the identified representation.
3. A new version preserves the old derivations and marks impact on the relevant consumers.
4. Reprocessing does not silently change the content a citation pointed to.
5. Altering an original or derivation is detected; an access failure is distinguished from a change of bytes.
6. A partial or erroneous extraction is communicated and is not used as complete evidence.
7. A question that combines modalities reaches the original evidence of both, if it is within the pilot scope.
8. Malicious instructions in the document do not change permissions or trigger commands in the scenarios tested.
9. Answers preserve decisive conditions and reduce or justify their human cost against the baseline.

## 10. Human interface, capture and queues

First observe where decisions are made. It may be a meeting, code review, chat or document. Choose the minimum channel that allows proposing with little effort and ratifying with verifiable identity. Do not make the usefulness of the method depend on everyone adopting a new dashboard.

The review prototype shows change, evidence, consequences, uncertainty, recommendation and relevant options. It is tested that the person understands what they accept and what remains unresolved. The technical layer may use Git; the interface need not expose IDs, YAML or the whole diff by default.

Set, per role, the review budget, deadline, substitute and policy for a saturated queue. Group common causes; keep pending decisions and detected omissions visible. A queue that receives no attention is not resolved by producing more proposals.

For the sensor for unrecorded decisions, start with grouped and reviewable output. Measure false positives and omissions through a sample, together with the time it consumes. Accepted proposals do not by themselves justify that the sensor pays off.

The sample of autonomous actions includes some decisions not to escalate and high-impact actions within the delegation. The criterion is calibrated without requiring every routine operation to be reviewed. Improvement is measured in understanding, results and effort, not in number of approvals.

## 11. Security, operation and concurrency

### Initial security profile

Document assets, actors, trust boundaries and permitted actions. Test at least one source with malicious instructions, one forged approval, one attempt to extend permissions and one change that disables its own checker.

The proposer does not freely hold ratification or integration credentials. Ingestion and test processes run with limited paths, network, resources and secrets. Proposed commands are reviewed as code; a string extracted from a document is never executed directly.

Inherited permissions also apply to indexes, logs, caches and exports. If partial permissions do not exist, material incompatible with the reading group is excluded. The exceptional withdrawal policy specifies who may order it, which copies must be treated and how what cannot be deleted with guarantees is communicated.

### Budgets and recovery

Set expected volume, concurrency, p50/p95 latency, model and processing budget, human queue limit, admissible integrity age, recovery objective and tolerated data loss. Choose figures after knowing tasks and baseline; record measurements on identified hardware/environment.

Periodic checks of originals may start with a simple cadence and be adjusted by use and impact. A sensitive operation may require verification at read time, without waiting for the schedule. Periodicity does not allow continuous integrity to be claimed.

Test network failures, missing original, expired credential, telemetry down, lagging index, partial write and response lost after integrating. Each one has a state, message, owner and recovery action. A sensor error must not automatically paralyze a safe query; an authority error does block the operation that needs it.

Backups preserve a consistent revision of records, external originals and approval evidence. A Git clone does not necessarily include heavy objects or the events of an external provider. The restore test rebuilds queries and citations, in addition to opening files.

### Several writers, when needed

Activate on an observed need for concurrency. Before that: stable IDs, integration against the current base, approval by content, clause conflicts and idempotent receipts.

If claims are added, define atomic acquisition, expiry, renewal, generation and release. The executor keeps the generation number and the gate rejects results of an expired or superseded claim. Without a connection, isolated work may be prepared, but unchecked exclusivity must not be announced.

A claim is not an exception allowing uncontrolled writes to the main branch. Its event goes through an authorized and automatable operation, with proportional controls. If external effects cannot check the generation, the limitation is declared and their execution is restricted.

<a id="12-evaluation-and-definition-of-done"></a>
## 12. Evaluation and definition of done

### Minimum prior test bench

Use real examples with reviewed answers and adverse variants. Write the expectation before implementing:

| Case | Required result |
| --- | --- |
| Human ratification declared only in YAML | Neither accepts nor integrates it as approved. |
| Content modified after approval | Approval invalid for that content. |
| Role change that authorizes itself | Rejection under the previous policy. |
| Partial replacement and pending proposal | Preserves unaffected clauses and separates what is non-binding. |
| Two incompatible changes | Explicit conflict before integrating. |
| Historical query with late correction | Difference between validity and knowledge. |
| Decisive evidence omitted | Declares insufficiency; does not complete with invented certainty. |
| Synthesis whose source text does not change but loses validity | Detects the dependency change. |
| Resumption with non-integrated changes | Recovers goal and limits; separates pending from accepted. |
| Completed write with lost response | Reconciles without duplicating the effect. |
| Partial source or reprocessed locator | Visible limitation and stable reference. |

Deterministic tests check rules and properties; AI evaluations check answer and behavior. Compare complete sources, served context and ablation; do not take the output of another model as automatic truth. Manually label decisive evidence and conditions. An AI judge may assist if it is calibrated and its disagreement is audited.

The independent evaluation set is not used in full to tune prompts. Record versions, parameters, corpus, results per case, latency, cost and errors. The minimum quality is checked before integrating retrieval changes, even if human time seems to improve.

### Measurement in use

Lightweight log per task/session: intended result, observed or estimated human time, interruptions, corrections, provisional result and follow-up. Mark missing data explicitly. Late corrections update the evaluation of the original task.

Report installation time and recurring time; include failed attempts and shared maintenance through an attribution rule. Separate task types and difficulty. Keep tokens and latency of the whole chain as secondary metrics.

The proportion of decisions about the system is a signal, not a target that can be improved by grouping twenty changes under a single ID. Measure maintenance minutes and delayed business decisions. An increase in approvals does not demonstrate success either without checking quality and understanding.

### Definition of done for the increment

- Contract and version identified; examples consistent with the schema.
- Controls of the activated capability implemented and tested.
- Migration reviewed, with differences and rollback or recovery defined.
- Canonical integration completed and receipt available.
- A new session uses the integrated walkthrough, with authority and limits preserved.
- Evidence of a correct result and first human measurement; what is not yet tested remains visible.
- Owner of operation and failure response assigned.

The sustained evaluation of the benefit is another gate: it requires enough representative tasks and follow-up. A first correct session enables learning, not a general claim of savings.

<a id="13-recommended-development-sequence"></a>
## 13. Recommended development sequence

**Approach:** executable specifications for meaning and contracts; TDD for deterministic rules; empirical evaluation for AI; product validation with people. The specification is adjusted as learning happens, without imposing an exhaustive design phase before the first result.

### Phase 0. Establish the base

Inventory existing code, revisions, branches and deliveries; distinguish implemented, described and pending. Resolve only the discrepancies that affect the chosen increment. Take a baseline and agree who decides and what the agent may write.

**Gate:** reproducible base revision, chosen task, minimum authority and known acceptance case. Do not create another parallel architecture because previous work was not located.

### Phase 1. Deliver a small walkthrough

Choose a task with immediate value: query an amended decision, resume work or record a proposal with approval. Implement together the necessary data, query, control and interface. If the path writes accepted knowledge, authenticated authority comes in here, not in a later phase.

First integrate existing compatible improvements, with tests and without dragging in unreviewed governance changes. Instrument the minimum to observe cost and errors.

**Gate:** walkthrough in the canonical version, regression test and a real session with a verifiable result. A non-integrated branch does not pass this gate.

### Phase 2. Correct the data and extend contracts

Migrate states in prose, ambiguous relations, clauses and dependencies according to demonstrated need. Add temporality and consolidation when extending historical queries. Review individually the migrations that change meaning; sample only mechanical transformations of bounded risk.

**Gate:** real cases answer correctly, conflicts are rejected and the migration preserves provenance and historical precision.

### Phase 3. Consolidate continuity and human review

Test opening, interruption and resumption; fix loss of intention and pending states. Adjust capture and review to the channels used. Verify that the adapters implement the same contract.

**Gate:** a new session resumes work without attributing non-existent authority or losing constraints; a person can review the change and its consequences without reconstructing the whole history.

### Documentary track. Integrated pilot when there is a need

An isolated extraction test may run during phase 0. To integrate its results, the source/derivation schema, versioned locators, access controls, integrity and fidelity evaluation are needed. The pilot is not placed by calendar before its dependencies.

**Gate:** real questions about the corpus are resolved with correct evidence and limits, and the preparation/review cost is measured. Uncovered formats remain declared as not tested.

### Phase 4. Sustained use and extension decision

Use the system for a period that provides representative tasks; observe late corrections, maintenance, queues and adoption. Separate changes when possible to attribute results. Review causes before automatically reverting because of any oscillation of a short series.

**Gate:** sufficient evidence to keep, simplify or withdraw mechanisms. Extending projects, writers or modalities requires a concrete need and tested contracts, not just having reached the end of the plan.

### Extensions activated by need

The operation layer contract of this document defines three independent extensions. (1) Add MCP as an adapter of the core when there is a client that consumes it, passing ESC-09; start locally if that covers the case. (2) Incorporate an incremental connector when a source changes frequently and reviewing it manually is costly, passing ESC-11. (3) Experiment with harness improvement only after having reproducible failures, a baseline and independent evaluation, passing ESC-10. No extension is a universal requirement for delivering the initial walkthrough. The remote platform additionally requires demonstrating the need for shared access and operation and completing its controls before activating it.

Each experiment compares the increment with the stable core on equivalent tasks. Quality, cost, limits and withdrawal condition are agreed in advance; if it does not deliver a verifiable RES result, it is postponed or simplified. The concrete tool configuration belongs to the development plan; it does not alter the contracts of this reference.

## 14. Migration from previous versions

Before updating, keep a verifiable copy and a manifest of the initial state. The migration is first run dry and produces diff, errors, ambiguities and cases that require human review.

| Design change | Treatment of existing data |
| --- | --- |
| IDs without a sequence obligation | Keep valid IDs; stop rejecting gaps. Do not renumber the corpus without need. |
| `state` and events | Create an import event with historical provenance; do not invent an authenticated approval from the past. |
| Precise dates and two times | Keep the original date and precision; record when it is imported. Separate declared date from checked incorporation. |
| Authenticated ratification | Classify legacy evidence as checked, pending or insufficient. Revalidate what is necessary for new uses. |
| Typed `amends` | Propose anchors and scope; human review of partial or contradictory replacements. |
| States in prose | Preserve the text as progress/history; do not infer resolved or authorized from length or an isolated word. |
| Clean relations | Extract candidates and validate target, direction and condition; separate notes. |
| OKF fields | Convert incompatible forms; preserve the previous meaning in the migration traceability. |
| Fingerprints and derivations | Compute an own fingerprint for each available artifact; identify missing ones without fabricating past integrity. |
| Citations to representations | Pin the known representation; if it is not known which was used, mark the uncertainty and review relevant uses. |
| `status` projection | Regenerate with the total function and a temporal snapshot; check external consumers. |
| Authority and configuration | Set the root of trust and the policy revision without allowing self-approval. |

Rolling back code/schema is distinguished from undoing decisions already integrated or external effects. A backup is not restored over new activity without reconciling it. If no safe reverse migration exists, document forward recovery.

Old consumers are identified before changing the schema. A generic reader that ignores states and extensions may read content, but not act as a normative executor. Version and test the necessary adapters.

<a id="15-reserves-and-decisions-that-remain-local"></a>
<a id="15-reserves-and-decisions-that-remain-local-1"></a>
## 15. Reserves and decisions that remain local

| Capability | Admissible trigger |
| --- | --- |
| Semantic index | Retrieval failures by meaning that an own evaluation improves. |
| Relational view or graph engine | Observed queries or costs that the current model does not resolve with reasonable maintenance. |
| Consolidation or sleep phase | Useful recurrence and avoidable cost demonstrated; proposals evaluated before promotion. |
| Periodic semantic lint | Incidents, contradictions or aging that justify its cost; there is no need to wait to correct a known error. |
| Claims and multiple writers | Need for real coordination, with checkable exclusion and expiry. |
| Partial permissions | Users or data that require them; evaluation of all exposure paths. |
| Additional processors | Documentary class where the first one fails or costs more than acceptable. |
| Additional signature or attestation | Threat, interoperability or a third party that needs to check provenance beyond the existing trust mechanism. |
| Extended evaluation | Higher risk, scale or uncertainty; the minimum test bench is never held in reserve. |

The following remain installation choices: language and libraries, remote, store of originals, approval channel, package distribution, performance parameters, retention, human review and entity classes. Choosing them cannot silently change the guarantees of the core.

<a id="16-incorporated-contracts-and-scenarios"></a>
<a id="16-incorporated-contracts-and-scenarios-1"></a>
## 16. Incorporated contracts and scenarios

The following sections are a normative part of this guide. They reproduce the model and rules needed to implement it without opening another file. They share meaning with core 1.0; local parameters only make tools and resources concrete, they do not change these rules.

## Self-contained implementation glossary

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


## Incorporated normative contract: knowledge model

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


## Incorporated normative contract: mutability and time

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


## Incorporated normative contract: authority and writing

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

Implementation 1.0, 3 Nov 2026 (English edition of implementation 0.8). It contains the contract needed to build and check the target system. It replaces guide 0.7; it does not declare any installation migrated or operational.


