# Autonomous Research Loop

ForgeGuard Nexus v0.10 adds controlled scientific autonomy above the v0.9 research scheduler, evidence DAG, adversarial council, and knowledge-evolution layers.

The loop is:

```text
Literature retrieval / controlled experiments
                 |
                 v
             Evidence DAG
                 |
                 v
        Branch resource budget
                 |
                 v
        Research lineage scoring
                 |
                 v
   Contradiction propagation / revalidation
```

## 1. Controlled automatic experiments

Automatic experiments are deliberately **not arbitrary code execution**. API clients select one of the registered deterministic experiment types:

- `numeric_threshold`
- `graph_integrity`
- `evidence_replay`
- `branch_consistency`

Every run:

1. charges the branch resource budget before execution;
2. creates a normal `ExperimentRecord` in the research branch;
3. executes a registered deterministic handler;
4. writes the result through the normal research service;
5. therefore creates/updates the corresponding Evidence Graph node;
6. records a stable `forgeguard://autonomy/experiments/...` artifact URI.

The public API never accepts shell commands, Python source, or executable paths as an experiment definition.

## 2. Literature retrieval into the Evidence Graph

ForgeGuard reuses the existing policy-controlled `SearchBroker` rather than creating a second retrieval stack.

Depending on configuration, the broker can use:

- controlled local knowledge;
- OpenAlex;
- Crossref;
- SearXNG.

External retrieval remains controlled by `FORGEGUARD_ALLOW_EXTERNAL_SEARCH` and the existing provider policies.

A literature run stores source URL, provider, publication date, query, and relation. Results can be ingested as:

- `context`: literature evidence;
- `support`: literature evidence linked to the claim;
- `challenge`: a counterexample/negative-evidence record.

Because ingestion goes through the normal research service, the records immediately become nodes and edges in the persistent Evidence DAG.

## 3. Branch resource budget

Every research branch has a persistent budget with limits for:

- automatic experiment runs;
- literature queries;
- citations ingested;
- compute units.

The default budget is intentionally finite. Operations that would exceed a limit are rejected before the expensive action is started.

Budget accounting is not a billing system. It is a governance primitive used to prevent one branch from consuming unbounded research resources merely because an agent keeps generating plausible next steps.

## 4. Research lineage scoring

Each branch receives a reproducible 0-100 lineage score based on recorded state rather than model self-confidence.

Current factors are:

- evidence accumulation;
- experiment accumulation;
- negative-result resolution;
- verified status;
- lineage fertility (useful descendants);
- remaining budget efficiency.

Rejected/archived branches and branches with unresolved counterexamples receive penalties.

The score is intended for scheduling and triage, not as a scientific truth probability. A high score means the branch has a stronger recorded research process, not that nature owes it an apology if the hypothesis is wrong.

## 5. Knowledge contradiction propagation

Negative evidence is propagated through research lineage rather than being trapped in the branch where it was discovered.

When a non-propagated counterexample is added to an ancestor branch:

1. ForgeGuard finds all descendants;
2. each descendant receives one inherited counterexample with a `propagated:` provenance marker;
3. descendant branch state becomes blocked until the inherited contradiction is resolved;
4. accepted knowledge derived from the affected lineage is listed as affected;
5. the propagation event is persisted for audit.

The provenance marker prevents recursive propagation storms.

When Accepted Knowledge is challenged, the same mechanism pushes a revalidation obligation into descendant branches and records the affected knowledge IDs.

## API

```text
GET  /api/v1/research/autonomy/overview
GET  /api/v1/research/budgets
GET  /api/v1/research/branches/{branch_id}/budget
POST /api/v1/research/branches/{branch_id}/budget
POST /api/v1/research/branches/{branch_id}/auto-experiments
GET  /api/v1/research/auto-experiments
POST /api/v1/research/branches/{branch_id}/literature
GET  /api/v1/research/literature-runs
GET  /api/v1/research/lineage-scores
POST /api/v1/research/branches/{branch_id}/counterexamples/{counterexample_id}/propagate
GET  /api/v1/research/contradictions
```

## Persistent state

Autonomy state is stored atomically in:

```text
runtime-data/research-autonomy.json
```

The original branch, Evidence Graph, Council, Scheduler, and Knowledge Evolution stores remain separate so a corrupted autonomy ledger does not silently rewrite primary scientific records.

## Scope boundary

"Autonomous research" in ForgeGuard means controlled orchestration of registered experiments, evidence retrieval, budgeting, lineage evaluation, and contradiction propagation. It does not mean unrestricted code execution, autonomous laboratory control, or automatic scientific truth.
