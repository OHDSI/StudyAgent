# Phenotype Recommendation Sparse Index Evaluation

## Objective
This evaluation assessed two related questions for the phenotype recommendation workflow. First, we wanted to confirm that recent cleanup and refactoring work did not introduce regressions in phenotype recommendation behavior. Second, we wanted to estimate whether the sparse retrieval index is contributing enough value to justify its build cost, especially for VA/CIPHER-oriented phenotypes and long-tail phenotype titles.

The comparison was motivated by the current implementation state of the phenotype recommendation flow after a series of ranking, shortlist-enforcement, prompt, and refactor changes. The practical decision point for this sprint was whether the team could simplify retrieval by reducing or removing sparse weighting without materially degrading shortlist quality.

## Methods
A fixed multi-case phenotype recommendation batch was executed repeatedly through the ACP flow using the local `phenotype_recommendation` endpoint. The test set included mixed OHDSI and CIPHER titles, including diagnosis phenotypes, procedure phenotypes, medication exposure phenotypes, shorthand and acronym cases, VA/CIPHER-skewed phenotypes, and previously identified control cases such as AAA, COPD, ADRD, GI bleed, heart failure hospitalization, and COVID outpatient diagnosis. The titles were sampled randomly from the titles of the phenotype definitions which then converted to study intent statements automatically with human review.

The same batch was run under three retrieval weighting configurations: dense/sparse `0.7 / 0.3` as the working baseline, dense/sparse `1.0 / 0.0` as the dense-only condition, and dense/sparse `0.8 / 0.2` as an intermediate condition. For each run, heredoc summaries were reviewed with attention to `planning.shortlist_ids`, final recommendation ids, and visible rerank evidence. Evaluation artifacts were preserved in this folder, including the shell script used to execute the batch and the full text outputs from each weighting condition.

## Results
The dense-only condition (`1.0 / 0.0`) produced large behavioral changes relative to the baseline. Across 71 evaluated cases, 49 cases changed in shortlist and/or final recommendation ids. Several of those changes were clear regressions, including loss of strong CIPHER-heavy results for abdominal aortic aneurysm in veterans, degradation of multiple VA/CIPHER-oriented chronic disease phenotypes, and drift toward weaker generic OHDSI neighbors in reviewer-facing cases such as cardiac complications, renal sclerosis, developmental disorders, and aortic valve disease. Dense-only also caused some known-risk cases to improve, notably rifamycin exposure and some GI bleed outputs, but the regressions were broader and more consequential than the gains.

The intermediate condition (`0.8 / 0.2`) behaved as a partial compromise but still changed 39 of 71 cases relative to the `0.7 / 0.3` baseline. It preserved some sparse-dependent wins that dense-only had lost, including stable outputs for fasciitis, keloid scars, COPD, and developmental disorders, and it retained the improvement on rifamycin exposure. However, it still regressed several important VA/CIPHER-facing cases relative to baseline, including renal sclerosis, veteran cardiac complications, and some reviewer-oriented long-tail phenotypes. It also did not fully resolve medication-exposure precision problems.

## Discussion
The main conclusion from this evaluation is that the sparse index is currently contributing meaningful retrieval value and should be retained for the phenotype recommendation workflow. The evidence is not merely that some individual recommendations changed, but that removing sparse weighting altered a large fraction of the batch and materially weakened several cases that are important for CIPHER-oriented human review. In particular, the long-tail VA/CIPHER slice appears sensitive to sparse support in a way that dense-only retrieval does not currently reproduce.

For the current sprint, the baseline weighting of dense/sparse `0.7 / 0.3` remains the best operational choice. The `0.8 / 0.2` condition is informative and may be worth revisiting in a future tuning pass, but it does not yet offer a clear enough improvement to justify changing the default immediately before human evaluation. The dense-only condition should not be adopted at present. Future follow-up work, if needed, should focus on targeted holdout cases such as medication exposure precision and selected context-heavy phenotypes rather than broad retrieval simplification before review.

### Next steps

We have listed below a set of student intent statements that should be helpful for a first round human review.

(TODO: revise to ensure variability of incidence, diagnostic difficulty (e.g., length of differential diagnoses with less than negligable incidence), ...)  

**Human test cases**
1. `Veteran patients with renal sclerosis`
2. `Veteran patients with polymyalgia rheumatica`
3. `Veteran patients with autoimmune hemolytic anemia`
4. `Patients diagnosed with fasciitis`
5. `Patients with stomatitis or mucositis`
6. `Patients with Barretts esophagus`
7. `Patients with regional enteritis`
8. `Patients with chronic periodontitis`
9. `Patients with scleritis or episcleritis`
10. `veterans who experienced an abdominal aortic aneurysm`
11. `patients with COPD according to diagnostic codes in the EHR`
12. `patients who experienced a GI bleed adverse event`
13. `older adults with a likely diagnosis of ADRD or late-stage dementia`
14. `patients hospitalized at least once for heart failure`

**Holdout Cases**
Keep these out of the main reviewer round and track them separately for internal analysis.
- `patients who received a COVID-19 diagnosis in the outpatient setting`
- `Patients with MSI-low rectal adenocarcinoma`
- `patients with a drug exposure to acetaminophen in the hospital setting`
- `patients exposed to rifamycin antibiotics`
- `Patients with a urinary tract infection who are new users of cephalosporins`
- `Patients hospitalized with preinfarction syndrome`

**Compact Scoring Sheet**
Have each reviewer score each case on 3 axes.

- `Top recommendation quality`
  - `2` = clearly appropriate
  - `1` = plausible but not ideal
  - `0` = inappropriate

- `Overall shortlist quality`
  - `2` = all returned recommendations are defensible
  - `1` = one weaker but acceptable extra result
  - `0` = one or more clearly off-target results

- `Usefulness for study planning`
  - `2` = would confidently use as a starting point
  - `1` = useful with manual review
  - `0` = not useful

Optional binary flags:
- `Too broad`
- `Too narrow`
- `Wrong role`
- `Wrong care setting`
- `Duplicate/near-duplicate`
- `Missing obvious better phenotype`

**Simple Reviewer Table**
Use one row per case:

```text
Case | Query | Top quality (0-2) | Shortlist quality (0-2) | Usefulness (0-2) | Flags | Notes
```

**Suggested Success Threshold**
For the main reviewer batch, I’d treat this as ready if:
- most cases score `2` on top recommendation quality
- few or no cases score `0` on overall shortlist quality
- average usefulness is at least `1.5`
