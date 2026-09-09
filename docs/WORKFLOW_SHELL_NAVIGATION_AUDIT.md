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
