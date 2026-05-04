#!/bin/bash

## After this runs, you can inspect a compact summary of the results using this:

OUTPUT_FILE="/tmp/phenotype_recommendation_tests.json"

echo "INFO: creating output file " ${OUTPUT_FILE}
echo '{"results":[' > ${OUTPUT_FILE}

echo "INFO: running COVID outpatient diagnosis cohort"
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"patients who received a COVID-19 diagnosis in the outpatient setting", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool > /tmp/result.json >> ${OUTPUT_FILE}

echo ","  >> ${OUTPUT_FILE}

echo "INFO: running abdominal aortic aneurysm in veterans"
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"veterans who experienced an abdominal aortic aneurysm ", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool > /tmp/result.json >> ${OUTPUT_FILE}

echo "," >> ${OUTPUT_FILE}

echo "INFO: COPD phenotype using diagnosis codes"
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"patients with COPD according to diagnostic codes in the EHR", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}

echo "," >> ${OUTPUT_FILE}

echo "INFO: heart failure hospitalization cohort"
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"patients hospitalized at least once for heart failure", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}

echo ","  >> ${OUTPUT_FILE}

echo "INFO: dementia in older adults"
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"older adults with a likely diagnosis of ADRD or late-stage dementia", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}

echo ","  >> ${OUTPUT_FILE}

echo "INFO:  GI bleeding adverse event outcome"
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"patients who experienced a GI bleed adverse event", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}

echo "," >> ${OUTPUT_FILE}

echo "INFO: diabetes medication-based phenotype"
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"patients who appear to have diabetes based on a medication-based phenotype", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}


echo ']}' >> ${OUTPUT_FILE}
echo "INFO: Tests completed. File written."


echo "RESULTS SUMMARY:"

/bin/sh -lc "python - <<'PY'
import json
from pathlib import Path
p = Path(\"$OUTPUT_FILE\")
obj = json.loads(p.read_text())
results = obj['results'] if isinstance(obj, dict) and 'results' in obj else obj
print('count', len(results))
for i, item in enumerate(results, 1):
    query = item.get('search', {}).get('query') or item.get('study_intent') or ''
    recs = item.get('recommendations', {}).get('phenotype_recommendations') or []
    rec_ids = [r.get('phenotype_id') for r in recs]
    shortlist = item.get('planning', {}).get('shortlist_ids') or []
    se = item.get('diagnostics', {}).get('planning_rerank', {}).get('shortlist_enforcement', {})
    print(f'CASE {i}: {query}')
    print('  shortlist:', shortlist)
    print('  rec_ids:', rec_ids)
    print('  replaced_ids:', se.get('replaced_ids'))
    print('  blocked_pool_ids:', se.get('blocked_pool_ids'))
    print('  blocked_candidate_reasons:', se.get('blocked_candidate_reasons'))
    print('  duplicate_topic_ids:', se.get('duplicate_topic_ids'))
    print('  dedupe_backfilled_ids:', se.get('dedupe_backfilled_ids'))
    print('  dedupe_applied:', se.get('dedupe_applied'))
    print('  enforced_shortlist_ids:', se.get('enforced_shortlist_ids'))
    print('  final_deterministic:', item.get('diagnostics', {}).get('final_deterministic'))
    print()
PY"

/bin/sh -lc "python - <<'PY'
import json
from pathlib import Path
p = Path(\"$OUTPUT_FILE\")
obj = json.loads(p.read_text())
results = obj['results'] if isinstance(obj, dict) and 'results' in obj else obj
for i, item in enumerate(results, 1):
    q = item.get('search', {}).get('query') or item.get('study_intent') or ''
    print(f'CASE {i}: {q}')
    print('  intent_facets:', item.get('intent_facets', {}).get('intent_facets'))
    print('  planning_shortlist:', item.get('planning', {}).get('shortlist_ids'))
    print('  planning_reasoning:', item.get('planning', {}).get('reasoning_notes'))
    print('  recommendations:')
    for rec in item.get('recommendations', {}).get('phenotype_recommendations', []):
        print('   ', rec.get('phenotype_id'), '|', rec.get('phenotype_name'), '|', rec.get('justification'))
    print()
PY"

/bin/sh -lc "python - <<'PY'
import json
from pathlib import Path
p = Path(\"$OUTPUT_FILE\")
obj = json.loads(p.read_text())
results = obj['results'] if isinstance(obj, dict) and 'results' in obj else obj
for i, item in enumerate(results, 1):
    q = item.get('search', {}).get('query') or item.get('study_intent') or ''
    print(f'CASE {i}: {q}')
    cand = item.get('diagnostics', {}).get('planning_rerank', {}).get('candidates', [])
    for row in cand[:8]:
        kinds = [r.get('kind') for r in row.get('reasons', []) if r.get('kind') in (
            'topic_mismatch',
            'topic_primary',
            'topic_context',
            'context_without_primary',
        )]
        print('  ', row.get('phenotype_id'), '|', row.get('metadata_score'), '|', kinds)
    print()
PY"
