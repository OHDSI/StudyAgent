# Shell Navigation and Input-Recovery Audit

This maintained audit records the user-visible branch points in the Strategus
incidence and CohortMethod shells. It is a design checklist, not a claim that
every branch can yet rewind arbitrarily.

| Branch point | Current destination for `/back` | Intended policy | Invalid input policy |
|---|---|---|---|
| Role statements / intent confirmation | Previous supported statement boundary | Functional back | Re-prompt the field |
| Cohort-source menu after a prior choice | Prior role-selection boundary where state exists | Functional back | Re-prompt with valid sources |
| Initial target cohort-source menu | No earlier source choice | Graceful: explain that restart is needed to revise study statements | Re-prompt with valid sources |
| ACP candidate list / preview | Cohort-source menu | Functional back | Return safely to source menu |
| Empty recommendation or declined advice | Cohort-source menu | Functional back | Never fall through to manual database-ID entry |
| File/directory/database import prompt | Cohort-source menu | Functional back | Explain error and re-prompt |
| Review CSV / Atlas JSON path | Cohort-source menu | Functional back | Explain path or schema error and re-prompt |
| Scope confirmation and concept-set approval | Cohort-source menu | Functional back | Re-prompt validation errors; preserve artifacts |
| Post-role improvement / next-role boundary | Previous role-selection boundary | Functional back | Re-prompt valid choices |
| Study-configuration boundary | Outcome role-selection boundary | Functional back | Re-prompt valid choices |

## Error handling inventory

Inputs that should never end a shell session include source-mode tokens, cohort
file paths, directory paths, database cohort identifiers, reviewed CSV paths,
Atlas/Capr-Circe JSON paths, scope numeric values, confirmation tokens, and
menu commands. They should either re-prompt locally or return to a documented
safe boundary with durable review artifacts retained.

## Rendering note

CirceR print-friendly output is Markdown. Terminal shells should either render
the concept-set tables as fixed-width text or offer a saved Markdown artifact;
raw Markdown tables are not reliably readable in all R consoles.

## Deterministic shell-test harness

Both shells accept optional `inputProvider` and `acpFlowCaller` arguments for
scripted tests. Their production defaults continue to use `readline()` and the
ACP client. A test supplies an input-provider function that returns one
response per prompt and an ACP fixture function that returns a response for a
given flow name and request body. The reusable `new_shell_transcript()` helper
under `tests/testthat/` records prompts, fails on exhausted input, and verifies
that a scenario consumed its complete transcript.

Use this seam for branch, recovery, and artifact assertions. Keep live
ACP/MCP/OMOP smoke tests separate because they validate integration rather than
deterministic shell control flow.

## Current automated coverage

The deterministic suite now covers the following audit scenarios:

| Scenario | Coverage | Shells |
|---|---|---|
| Empty ACP recommendation response returns to source selection | Full scripted transcript | Incidence and CohortMethod |
| Role-statement /back returns to target-entry boundary | Full scripted transcript | Incidence and CohortMethod |
| Multiple outcomes retain separate imported definitions; first outcome offers an improvement and the next has none | Full scripted transcript with local Circe fixtures | Incidence and CohortMethod |
| Free-text analytic settings use a confirmed ACP recommendation and persist its artifact | Full scripted transcript with ACP fixture | CohortMethod |
| Incidence time-at-risk/strata wizard re-prompts an invalid integer and persists customized settings | Full scripted transcript with local Circe fixtures | Incidence |
| Accepted improvement action patches only the accepted outcome cohort | Full scripted transcript with ACP fixture | Incidence |
| Step-by-step analytic-settings wizard re-prompts an invalid risk-window value | Deterministic wizard fixture | CohortMethod |
| Invalid source-mode token re-prompts; /back is preserved | Shared acquisition helper | Both shells |
| Invalid Atlas/ACP concept-set JSON path re-prompts; /back returns safely | Focused review-handoff transcript | Both shells |
| Dialogue command handling returns an explicit navigation signal | Focused dialogue transcript | Both shells |

The remaining boundaries will be added as fixtures are introduced for direct Circe imports, CIPHER preparation/conversion, saved-review resume, scope confirmation, concept-set approval, and post-role configuration. Those flows currently call ACP preparation or R-package integrations directly; their tests need narrowly injected fixtures rather than live service dependencies.
