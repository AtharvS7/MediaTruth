# Production accuracy target and current completion estimate

User target (revised 3 October 2026): strictly above 90% accuracy. This is a measurable target for specified
input distributions, not a guarantee for every image, unseen generator or attack.
The initial scope is **fully AI-generated still images versus non-generated
photos**. AI edits, traditional edits, mixed workflows and video require separate
validation and cannot inherit a still-image result.

## Iteration contract

- Decision: assess whether FSD can reduce false flags after calibration on new data.
- Primary target: held-out balanced accuracy >90%; each class precision and recall >90%.
- Guardrails: original false-positive rate <=5%; abstentions count as unsuccessful
  classifications, not correct answers; report coverage and confidence intervals.
- A claim of above 90% population accuracy also requires the lower 95%
  confidence bound >90%, not merely a point estimate over that value.
- Minimum release support: 200 independently verified examples per enabled class,
  with unseen-source/generator and recompression/crop/resize slices reported.
- No public promotion without provenance, licensing, resource and serving checks.
- Baseline FSD diagnostic set: 32/35 correct (91.4%), balanced accuracy 87.0%,
  25/26 AI detected, two of nine real images falsely flagged. This is not a
  representative or independent validation score.
- First adjustment: fit a threshold on a new calibration partition under a 1%
  empirical false-positive budget. Preserve a separate holdout and all prior
  diagnostic samples. Never tune on the holdout or claim fitted scores as accuracy.
- CPU budget: at most four inference threads, serial scoring, no paid services.
  New public dataset subsets are exploratory until independence/rights are verified.
- Fall back to inconclusive; a failed target remains a failed target.

## Project completion estimate

This is a planning estimate, not detection accuracy or a certification. Scores
reflect both implemented behavior and verification, using equal ten-point weights.

| Workstream | Earned / 10 | Main remaining gap |
|---|---:|---|
| Upload and report interface | 9 | Continued usability/regression coverage |
| Authentication | 8 | Real confirmation/recovery delivery |
| Private data and report persistence | 9 | Backup/restore rehearsal |
| Durable jobs and resource control | 9 | Capacity/operational validation |
| Metadata export | 9 | Format coverage; no universal trace-removal claim |
| Provenance | 8 | Broader credential/provider coverage |
| AI-generation accuracy | 2 | Independent calibration and >90% validation |
| Edit attribution and localization | 1 | Validated models and labeled pairs/masks |
| Advanced video forensics | 3 | Temporal/face models and video validation |
| Production operations | 6 | Monitoring, recovery, load evidence and cloud worker |
| **Total** | **64 / 100** | **Approximately 65% overall** |

Evidence: `IMPLEMENTATION_STATUS.md`, `ACCURACY_ITERATION.md`, recorded hosted
journey checks, 166 passing backend tests and successful CI at aed4af3. Earlier
documents saying the project is complete refer to narrower audit-fix scopes.
