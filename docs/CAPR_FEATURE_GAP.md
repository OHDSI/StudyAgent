# Capr Capability Gap for Phenotype Make Computable

This document tracks the difference between the Capr surface documented in the repository-owned [Capr reference](../mcp_server/prompts/phenotype_make_computable/CAPR_REFERENCE.md) and the deterministic `phenotype_make_computable` emitter. It is a planning and implementation inventory, not a promise that every Capr feature is available through the ACP flow.

## Implemented and regression-tested in the ACP emitter

- Condition-occurrence entry from reviewed concept sets, including descendant, mapped, and exclusion policy.
- First/all entry selection; prior continuous observation for single-condition and visit-overlap paths.
- Observation-period or fixed exits, with supported start/end anchors.
- Era collapse settings.
- Condition entry constrained by overlapping Visit events, either as an entry condition or attrition rule.
- The explicit condition-to-condition temporal-followup pattern used by the corrected cohort-63 development variant.
- Pure function-form Capr source and Capr/CirceR technical validation.

## High-value Capr features not yet implemented

| Capability | Capr surface | Why it needs an explicit scope variant |
|---|---|---|
| Drug exposure entry/criteria | `drugExposure()` | A Drug concept set is not enough: callers must specify event date, exposure versus era semantics, temporal anchors, and any quantity/days-supply logic. |
| Drug, condition, and dose eras | `drugEra()`, `conditionEra()`, `doseEra()` | Eras are derived intervals. The scope must state persistence-gap assumptions and whether start or end defines index/exit. |
| Observation entry/criteria | `observation()` | Mixed Condition/Observation evidence requires an explicit domain-combination policy; cohort 858 is the development clarification case. |
| Measurement logic | `measurement()`, numeric/value/unit attributes | Requires value operator, units, source/standard concept policy, timing, and missing-value semantics. |
| Procedure, device, specimen, death, and observation-period events | domain query constructors | Each requires clear event-domain and date semantics before deterministic emission. |
| Nested boolean and count logic | `nestedWithAll()`, `nestedWithAny()`, `atLeast()`, `exactly()`, `atMost()` | Needs a typed representation of event relationships, apertures, distinctness, and index anchors. |
| Advanced windows and date adjustment | `duringInterval()`, `eventStarts()`, `eventEnds()`, `dateAdjustment()` | The current flow intentionally fails closed for free-form windows outside explicit supported modes. |
| Censoring, demographics, provider, provenance, and source restrictions | `censoringEvents()`, demographic and attribute helpers | These must be represented in the cohort-plan model and reviewed against vocabulary/CDM semantics. |
| Database-backed hydration | `getConceptSetDetails()` and attribute hydration | Optional usability enhancement for Atlas-readable concept metadata; it must not become a runtime requirement for generated definitions. |

## Implementation rule

Add a Capr capability only when all of the following are delivered together:

1. a typed scope/cohort-plan variant;
2. declarative prompt instructions and output-schema support;
3. deterministic Capr emission;
4. controlled Capr/CirceR validation;
5. focused semantic and regression tests; and
6. documentation of any ambiguity or clinical-review decision required from callers.

Until then, the flow must return an explicit unsupported or clarification response rather than approximate the requested logic.
