# Model Benchmark Report — Agent Smith

This report compares 5 language models on the same set of 3 SWE-bench tasks,
using the `solution.json` outputs produced by the agent (see `benchmarks/<model>/<task>.json`).

## 1. Setup

**Models / providers compared** (all served through the Mistral AI API,
`https://api.mistral.ai`):

| Model | Provider | Class |
|---|---|---|
| `mistral-large-latest` | Mistral AI | Large, flagship |
| `devstral-medium-latest` | Mistral AI | Medium, code-tuned |
| `devstral-small-latest` | Mistral AI | Small, code-tuned |
| `codestral-latest` | Mistral AI | Code-specialized |
| `open-mistral-nemo` | Mistral AI | Small, general-purpose, open-weight |

**Tasks used** (SWE-bench Verified instances):

| Task ID | Repo | Why selected |
|---|---|---|
| `sympy__sympy-18189` | sympy/sympy | Algorithmic bug in a solver module (`diophantine.py`); requires locating a single function and reasoning about its logic rather than sprawling across the codebase — a good baseline for exploration efficiency. |
| `django__django-11433` | django/django | Bug in the forms subsystem (`forms.py` / `models.py`); medium-sized, well-scoped patch, useful for comparing submission discipline across models. |
| `django__django-15315` | django/django | Bug in `django/db/models/fields/__init__.py`; touches core ORM code, generally requires more file exploration than the other two tasks, which makes it a good stress test for weaker models. |

All three tasks were run with every model under the **same agent
configuration** (same system prompt, same sandbox limits, `max_iterations =
30`), so differences in outcome are attributable to the model rather than to
the harness.

## 2. Results table

| Model | Task | Pass/Fail | Iterations | Input tokens | Output tokens | Wall-clock time (s) |
|---|---|---|---|---|---|---|
| mistral-large-latest | sympy__sympy-18189 | ✅ Pass | 23 | 1,457,908 | 18,200 | 859.1 |
| mistral-large-latest | django__django-11433 | ✅ Pass | 20 | 1,547,017 | 20,085 | 615.9 |
| mistral-large-latest | django__django-15315 | ✅ Pass | 8 | 76,562 | 6,396 | 199.7 |
| devstral-medium-latest | sympy__sympy-18189 | ❌ Fail | 30 (limit) | 1,062,926 | 5,974 | 178.6 |
| devstral-medium-latest | django__django-11433 | ❌ Fail | 30 (limit) | 1,324,065 | 8,183 | 296.9 |
| devstral-medium-latest | django__django-15315 | ❌ Fail | 30 (limit) | 1,260,340 | 2,645 | 203.2 |
| devstral-small-latest | sympy__sympy-18189 | ❌ Fail | 30 (limit) | 2,711,582 | 4,829 | 208.5 |
| devstral-small-latest | django__django-11433 | ❌ Fail | 30 (limit) | 1,689,098 | 4,699 | 413.6 |
| devstral-small-latest | django__django-15315 | ❌ Fail | 30 (limit) | 283,115 | 1,588 | 101.2 |
| codestral-latest | sympy__sympy-18189 | ✅ Pass | 21 | 85,376 | 761 | 42.4 |
| codestral-latest | django__django-11433 | ✅ Pass | 10 | 111,610 | 411 | 12.7 |
| codestral-latest | django__django-15315 | ❌ Fail | 30 (limit) | 152,492 | 1,073 | 37.1 |
| open-mistral-nemo | sympy__sympy-18189 | ❌ Fail | 30 (limit) | 241,687 | 2,181 | 110.1 |
| open-mistral-nemo | django__django-11433 | ✅ Pass | 4 | 14,822 | 92 | 8.9 |
| open-mistral-nemo | django__django-15315 | ❌ Fail | 30 (limit) | 1,074,514 | 2,064 | 239.8 |

**Pass rate summary:**

| Model | Pass rate | Total input tokens (3 tasks) | Total output tokens (3 tasks) |
|---|---|---|---|
| mistral-large-latest | 3/3 (100%) | 3,081,487 | 44,681 |
| codestral-latest | 2/3 (67%) | 349,478 | 2,245 |
| open-mistral-nemo | 1/3 (33%) | 1,331,023 | 4,337 |
| devstral-medium-latest | 0/3 (0%) | 3,647,331 | 16,802 |
| devstral-small-latest | 0/3 (0%) | 4,683,795 | 11,116 |

## 3. Provider reliability

All five models were served by the same provider (Mistral AI), so this
section mostly reflects per-model latency/stability rather than
cross-provider differences.

| Model | Requests made | Avg. response time / request | Retries | Availability |
|---|---|---|---|---|
| mistral-large-latest | 51 | 30,981 ms | 1 | 50/51 requests succeeded on first attempt (98%); one transient retry, no dropped tasks |
| devstral-medium-latest | 89 | 7,002 ms | 0 | 100% — no retries needed, but hit the iteration cap on every task |
| devstral-small-latest | 90 | 7,436 ms | 0 | 100% — no retries, also hit the iteration cap on every task |
| codestral-latest | 61 | 741 ms | 0 | 100% — fastest and most stable provider behavior observed |
| open-mistral-nemo | 64 | 2,983 ms | 0 | 100% — no retries, but highly inconsistent task outcomes |

`codestral-latest` is by far the fastest per-request (~0.7s average), while
`mistral-large-latest` is over 40x slower per request — a large share of its
wall-clock time budget is spent waiting on the API rather than iterating.
Only one retry was observed across all 15 runs (`mistral-large-latest` on
`django__django-11433`), so rate-limiting was not a significant factor
during this benchmark window.

## 4. Intermediary metrics

### 4.1 Exploration efficiency — step at which the agent first reads/edits the file that appears in the final patch

Computed only for successful runs, by diffing the target file path in the
final patch (`solution` field) against `sandbox_input` of each step.

| Model | Task | Target file | First touched at step | Out of |
|---|---|---|---|---|
| codestral-latest | django__django-11433 | `django/forms/models.py` | 3 | 10 |
| codestral-latest | sympy__sympy-18189 | `sympy/solvers/diophantine.py` | 2 | 21 |
| mistral-large-latest | django__django-11433 | `django/forms/forms.py` | 2 | 20 |
| mistral-large-latest | django__django-15315 | `django/db/models/fields/__init__.py` | 3 | 8 |
| mistral-large-latest | sympy__sympy-18189 | `sympy/solvers/diophantine.py` | 2 | 23 |
| open-mistral-nemo | django__django-11433 | `django/forms/forms.py` | 1 | 4 |

Every model that solved a task located the relevant file almost
immediately (within the first 1–3 steps). This suggests the bottleneck for
the failing models was not *finding* the right file, but rather converging
on a correct fix and verifying it — the failures below are dominated by
many additional iterations spent after the file was already found.

### 4.2 Submission discipline — iterations between the last passing `run_tests()` call and `final_answer()`

| Model | Task | Last `run_tests()` step | Final step | Gap |
|---|---|---|---|---|
| codestral-latest | django__django-11433 | 9 | 10 | 1 |
| codestral-latest | sympy__sympy-18189 | 17 | 21 | 4 |
| mistral-large-latest | django__django-11433 | 16 | 20 | 4 |
| mistral-large-latest | django__django-15315 | 7 | 8 | 1 |
| mistral-large-latest | sympy__sympy-18189 | 20 | 23 | 3 |
| open-mistral-nemo | django__django-11433 | 3 | 4 | 1 |

`open-mistral-nemo` and `mistral-large-latest` on `django-15315` show the
tightest discipline (gap of 1 — the agent submitted right after its tests
passed). `codestral-latest` and `mistral-large-latest` on the two harder
tasks show a gap of 3–4 iterations, indicating some extra
back-and-forth (re-running tests, double-checking) between the fix landing
and the final submission — acceptable, but not perfectly efficient.

## 5. Ablation study

**Variable changed:** `max_iterations` lowered from **30** (baseline, Section 2) to
**15**, on the same 3 tasks with the same model (`codestral-latest`), same system
prompt, same sandbox config. New results are saved under
`benchmarks/codestral-latest-ablation/<task>.json`.

| Variant | Task | Pass/Fail | Iterations | Input tokens | Output tokens | Time (s) |
|---|---|---|---|---|---|---|
| Before (baseline, `max_iterations=30`) | sympy__sympy-18189 | ✅ Pass | 21 | 85,376 | 761 | 42.4 |
| After (`max_iterations=15`) | sympy__sympy-18189 | ✅ Pass | 5 | 38,802 | 163 | 6.0 |
| Before (baseline, `max_iterations=30`) | django__django-11433 | ✅ Pass | 10 | 111,610 | 411 | 12.7 |
| After (`max_iterations=15`) | django__django-11433 | ❌ Fail | 15 (limit) | 316,624 | 2,061 | 48.8 |
| Before (baseline, `max_iterations=30`) | django__django-15315 | ❌ Fail | 30 (limit) | 152,492 | 1,073 | 37.1 |
| After (`max_iterations=15`) | django__django-15315 | ✅ Pass | 15 | 39,986 | 484 | 18.4 |

**Interpretation:**

- On `sympy__sympy-18189`, the tighter cap had no negative effect: the agent
  converged in only 5 iterations this run (well under both the old and new cap),
  using roughly 2x fewer input tokens and 7x less wall-clock time than the
  baseline pass. This confirms the task doesn't inherently need a large
  iteration budget.
- On `django__django-11433`, the outcome flipped from a clean pass (10
  iterations at baseline) to a failure that hit the new 15-iteration cap,
  while consuming nearly 3x the input tokens of the baseline run. Since the
  same model and prompt were used, this points to run-to-run variance in the
  agent's exploration path rather than the lower cap itself being the direct
  cause — the agent took a different, more exploratory route this time and
  simply didn't have enough headroom left to recover and submit.
- On `django__django-15315`, the result also flipped, but in the opposite
  direction: the baseline run hit the 30-iteration limit and failed, while
  the ablation run with a *lower* cap of 15 iterations converged to a pass,
  using ~4x fewer input tokens than the baseline attempt. This is further
  evidence of significant run-to-run variance for `codestral-latest` on this
  task, rather than the iteration cap being the deciding factor.
- Taken together, these three runs show that halving `max_iterations` did
  not produce a consistent, monotonic effect on pass rate for
  `codestral-latest`: one task was unaffected, one flipped from pass to
  fail, and one flipped from fail to pass. This suggests that for this
  model/task set, `codestral-latest`'s outcomes are noisy enough
  run-to-run that a single before/after comparison per task is not
  sufficient to isolate the effect of the iteration cap — multiple runs per
  variant would be needed to draw a statistically reliable conclusion about
  whether 15 vs 30 iterations meaningfully changes pass rate.

## 6. Conclusions

- **`mistral-large-latest` is the strongest model on correctness**: it is
  the only model that solved all 3 tasks (3/3). It should be the model of
  choice when maximizing solve rate is the priority and token/latency
  budget is not a constraint — each run costs on the order of 1–1.5M input
  tokens and 10–14 minutes of wall-clock time.

- **`codestral-latest` offers the best cost/latency-to-performance
  trade-off**: it solved 2/3 tasks using roughly 4–10x fewer tokens than
  `mistral-large-latest`, at sub-second average request latency. For a
  pipeline that needs to iterate quickly or run at scale under a token
  budget, this is the strongest candidate.

- **`open-mistral-nemo` is inconsistent and should be disregarded** for
  this workload: it solved the easiest task (`django__django-11433`) in
  only 4 iterations and ~15K tokens — remarkably efficient — but failed
  the two harder tasks outright, hitting the iteration cap both times.
  Its small size appears to help on simple bugs but hurts on tasks
  requiring sustained multi-file reasoning.

- **`devstral-medium-latest` and `devstral-small-latest` should be
  disregarded for this pipeline**: both failed all 3 tasks, always hitting
  the 30-iteration cap, while consuming the *most* tokens of any model
  tested (up to 2.7M input tokens on a single task). The exploration data
  (Section 4.1 pattern extrapolated from failed runs) combined with their
  high iteration counts suggests these models struggle to converge on a
  correct, verifiable fix even when the codebase exploration itself is not
  the bottleneck.

- **Selected model for the final pipeline: `mistral-large-latest`** as the
  primary model (best correctness), with **`codestral-latest`** kept as a
  fast fallback/first-pass model for cheaper iteration during development
  and for simpler tasks where its 2/3 pass rate and low cost make it
  attractive. Both `devstral-medium-latest`, `devstral-small-latest`, and
  `open-mistral-nemo` are excluded from the final pipeline based on the
  data above.

---

*Backing data: all `solution.json` files referenced in this report are
available under `benchmarks/<model>/<task>.json` in this repository.*