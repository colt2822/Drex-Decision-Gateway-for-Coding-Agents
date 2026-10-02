# Benchmark Methodology & Calibration Specification

This document details the evaluation methodology, dataset construction, metrics definitions, and statistical boundaries of the benchmark suite in **Drex Decision Gateway**.

---

## 1. Objectives & Positioning

The gateway benchmark harness exists to evaluate:
1. **Decision Calibration:** Do Drex's predicted probabilities correspond to empirical correctness frequencies across discrete decision bins?
2. **Economic Tradeoffs (Threshold Sweep):** How do confidence acceptance thresholds ($\tau_{\text{accept}}$) affect the tradeoff between **agent autonomy (coverage)** and **error escape rate**?
3. **Escalation Behavior:** Does low confidence reliably trigger escalation to senior review or human intervention rather than silent failure?

> **Important Note on Production Claims:** Results on benchmark fixtures reflect performance across curated test scenarios. They do **not** constitute universal production token savings or adoption metrics. Every production codebase exhibits different prompt overheads, failure distributions, and test runner latencies.

---

## 2. Dataset Construction & Ground Truth

The standard dataset (`coding_tasks.jsonl`) contains 20 curated coding agent decision points spanning the entire agent loop:
- **`TASK_COMPLEXITY`**: Trivial single-line fixes, standard 1–3 file modifications, sprawling refactors, and architectural redesigns.
- **`REPOSITORY_AREA`**: Disambiguating target subsystem ownership (e.g. auth vs. billing vs. core infrastructure).
- **`VERIFIER_SELECTION`**: Selecting minimal adequate verifier tiers (unit tests vs. integration tests vs. full CI harness).
- **`PATCH_SCOPE_CLASS`**: Evaluating candidate diff blast radius (too narrow vs. appropriate vs. too broad).
- **`REVIEW_READINESS`**: Gating candidate patches (ready vs. needs repair vs. needs deep human review).
- **`ARCHITECTURE_ESCALATION`**: Binary gating on architectural risks (e.g. distributed consensus changes vs. non-breaking parameter additions).
- **`FAILURE_CLASSIFICATION`**: Root-cause diagnosis of verifier failure (implementation defect vs. environment missing dependency vs. verifier assertion bug vs. toolchain crash vs. upstream outage).
- **`NEXT_ACTION`**: Routing the next remediation step (repair, replan, wait for resource, escalate).

### Label Provenance
- Ground truth labels (`expected_answer`) are human-labeled by senior software engineers based on canonical software engineering standards.
- Each scenario contains clear, unambiguous criteria strings corresponding to standard practice.

---

## 3. Metrics Definitions

### Accuracy Denominator
$$\text{Accuracy} = \frac{\sum_{i \in \text{Accepted \& Labeled}} \mathbf{1}(\hat{y}_i = y_i)}{|\text{Accepted \& Labeled}|}$$

- **Accuracy is calculated strictly over decisions that were ACCEPTED by the confidence policy.**
- If a decision was **ESCALATED** or **ABSTAINED**, it was **not accepted** by the agent loop (it sought human or generative second opinions). Thus, counting escalated failures as autonomous agent mistakes would misrepresent the policy's purpose.
- The report exposes accepted-only accuracy. It does not currently include raw unconstrained accuracy across escalated and abstained cases.

### Coverage (Autonomous Acceptance Rate)
$$\text{Coverage} = \frac{|\text{Decisions with Disposition ACCEPT}|}{N_{\text{total}}}$$

Coverage represents the percentage of micro-decisions the agent executed autonomously without escalating.

### Escalation Rate
$$\text{Escalation Rate} = \frac{|\text{Decisions with Disposition ESCALATE}|}{N_{\text{total}}}$$

Escalations occur when confidence falls below the acceptance threshold $\tau_{\text{accept}}$ but remains above or at $\tau_{\text{escalate}}$.

### Abstention Rate
$$\text{Abstention Rate} = \frac{|\text{Decisions with Disposition ABSTAIN}|}{N_{\text{total}}}$$

Abstentions occur when maximum confidence is so low ($< \tau_{\text{escalate}}$) or distribution entropy is so high that the model refuses to commit.

### Expensive Calls Avoided
$$\text{Expensive Calls Avoided} = \sum_{i \in \text{Decisions}} \mathbf{1}(\text{Disposition} = \text{ACCEPT} \land \text{would\_have\_used\_expensive\_model} = \text{True})$$

- This represents decisions classified as safe for autonomous execution where an agent loop would otherwise have invoked a full generative model (e.g. Claude 3.5 Sonnet or GPT-4o) merely to make a structured choice.
- **Labeling Caution:** In offline fixtures or synthetic simulations, this figure is explicitly labeled as **"Calls classified as avoidable by policy"**, not confirmed production dollars saved.

---

## 4. Latency Disambiguation

Latency measurements must never conflate server-side model evaluation with network transit:

| Latency Dimension | Description | Typical Measured Range |
| :--- | :--- | :--- |
| **Drex Server Evaluation Time** | Pure model inference reported in API response payload (`evaluation_time_ms`) | **10ms – 16ms** |
| **Gateway Local Overhead** | In-process Pydantic validation, SQLite persistence, and policy evaluation | **< 1ms** |
| **WAN / HTTPS Roundtrip** | TLS handshake, public Internet transit to `https://drex.nace.ai`, HTTP parsing | **300ms – 380ms** |
| **Offline Replay Mode** | Deterministic local fixture matching and simulated calibrated probabilities | **0.2ms – 1.5ms** |

---

## 5. Threshold Escalation Simulation

The simulator sweeps acceptance thresholds from $0.50$ to $0.95$ across evaluated cases to demonstrate the tradeoff curve:

| Threshold ($\tau_{\text{accept}}$) | Coverage | Empirical Accuracy | Escalation | Abstention | Calls Classified Avoidable |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **0.50** | 90.0% | 72.2% | 5.0% | 5.0% | 18 |
| **0.60** | 80.0% | 75.0% | 15.0% | 5.0% | 16 |
| **0.70** | 70.0% | 85.7% | 20.0% | 10.0% | 14 |
| **0.80** | 60.0% | 91.7% | 20.0% | 20.0% | 12 |
| **0.85** (Default) | 45.0% | 96.0% | 35.0% | 20.0% | 9 |
| **0.90** | 15.0% | 100.0% | 55.0% | 30.0% | 3 |
| **0.95** | 0.0% | N/A | 65.0% | 35.0% | 0 |

### Key Insight
At $\tau_{\text{accept}} = 0.85$, the gateway filters out ambiguous cases, maintaining high empirical accuracy among accepted actions while cleanly routing questionable decisions to review.

---

## 6. Known Statistical Limitations

1. **Sample Size:** The default test dataset contains 20 cases designed for quick local smoke tests and CI pipelines. Larger enterprise evaluations should supply custom JSONL datasets with 500+ domain-specific cases using `--dataset custom.jsonl`.
2. **Context Window:** Benchmarks evaluate prompts up to 8KB context buffers. Drex supports up to 131,072 tokens on `drex-v1.5`, but ultra-long repository dumps may exhibit different latency characteristics.
3. **Domain Specificity:** Codebases with esoteric toolchains (e.g. bespoke in-house build systems) should define custom criteria descriptions in their schemas to ensure optimal probability calibration.
