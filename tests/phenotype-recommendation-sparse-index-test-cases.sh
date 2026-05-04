#!/bin/bash

## Example random sample approach
# # Cipher
# for i in  data/phenotype_index_cipher_omop/definitions/cipher_*; do cat $i | jq '.fullName' >> /tmp/fulnames.txt ; done;
# shuf -n 50 /tmp/fulnames.txt
# "Other disorders of carbohydrate transport and metabolism (MAP)"
# "Dyschromia and Vitiligo (gwPheWAS)"
# "Nerve Plexus Lesions (Phecode)"
# "Ulcerative colitis (chronic) (gwPheWAS)"
# "Pervasive Developmental Disorders (Phecode)"
# # OHDSI
# cut -d, -f2 data/Cohorts.csv | shuf -n 5
# "[P] acetaminophen exposure 10"
# "[P] Acute Hepatic Injury with no pre-existing liver disease"
# "[P] Posterior reversible encephalopathy syndrome PRES"
# "[P][R] Acute myocardial infarction"
# "[P] Antiphospholipid syndrome"




## After this runs, you can inspect a compact summary of the results using this:

OUTPUT_FILE="/tmp/phenotype_recommendation_tests.json"

echo "INFO: creating output file " ${OUTPUT_FILE}
echo '{"results":[' > ${OUTPUT_FILE}

###

# echo "INFO: Cardiac defibrillator in situ (MAP)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with an implanted cardiac defibrillator", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Fasciitis (gwPheWAS)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients diagnosed with fasciitis", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Acute prostatitis (MAP)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with acute prostatitis", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: [P] Esophagectomy"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients who underwent esophagectomy", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: [P][R] Peripheral neuritis"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients diagnosed with peripheral neuritis", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: [P] Concomitant TNF - alpha Inhibitors and IL12_23 Inhibitors - GE 30D overlap"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with concomitant TNF-alpha inhibitor and IL-12/23 inhibitor exposure for at least 30 days", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: [P][R] Allergic rhinitis"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with allergic rhinitis", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Ischemic Heart Disease (Sandhu)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with ischemic heart disease", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Early or Threatened Labor Hemorrhage in Early Pregnancy (Phecode)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Pregnant patients with hemorrhage in early pregnancy or threatened labor", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: [P] Lung Resection"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients who underwent lung resection", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: [P] Laryngitis"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with laryngitis", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Regional Enteritis (Phecode)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with regional enteritis", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Renal Sclerosis NOS (VADC)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with renal sclerosis", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Other cardiomyopathy (MAP)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with cardiomyopathy", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: [P] Posterior reversible encephalopathy syndrome PRES"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with a diagnosis of PRES", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: [P] Anorexia Nervosa"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with anorexia nervosa", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: [P] Dizziness or giddiness including motion sickness and vertigo"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with dizziness, vertigo, or motion sickness", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Polymyalgia Rheumatica (VADC)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with polymyalgia rheumatica", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Adrenal Cortical Steroids Causing Adverse Effects in Therapeutic Use (Phecode)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with adverse effects from therapeutic corticosteroid use", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: [P][R] Low blood pressure"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with low blood pressure", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: [P] Encephalopathy"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with encephalopathy", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: [P] Birdshot chorioretinitis"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with birdshot chorioretinitis", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Macular Degeneration (Senile) of Retina Nos (Phecode)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Older adults with macular degeneration", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Autoimmune Hemolytic Anemias (VADC)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with autoimmune hemolytic anemia", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: [P] Primary adenocarcinoma of rectum MSI-L"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with MSI-low rectal adenocarcinoma", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Blister (gwPheWAS)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with blistering skin lesions", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Stomatitis and mucositis (gwPheWAS)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with stomatitis or mucositis", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Neurofibromatosis type 1 (FP)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with neurofibromatosis type 1", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Keloid scar (gwPheWAS)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with keloid scars", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: [P] acetaminophen exposure 10"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with acetaminophen exposure", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: [P] Antibiotics Rifamycins 10"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients exposed to rifamycin antibiotics", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Joint/ligament sprain (gwPheWAS)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with a joint or ligament sprain", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Miscarriage; stillbirth (MAP)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Pregnant patients with miscarriage or stillbirth", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Arterial embolism and thrombosis of lower extremity artery (MAP)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with arterial embolism or thrombosis of a lower extremity artery", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: [P] New users of Cephalosporin systemetic nested in Urinary Tract Infection"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with a urinary tract infection who are new users of cephalosporins", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: [P] Hospitalization with preinfarction syndrome"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients hospitalized with preinfarction syndrome", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Personal history of diseases of blood and blood-forming organs (MAP)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with a personal history of blood or blood-forming organ disease", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Other Benign Pancreatic Conditions (Nguyen)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with benign pancreatic conditions", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Osteoarthrosis Localized Primary (Phecode)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with primary localized osteoarthritis", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: [P] New users of dihydropyridine calcium channel blockers"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"New users of dihydropyridine calcium channel blockers", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Renal Sclerosis NOS (VADC)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Veteran patients with renal sclerosis", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Polymyalgia Rheumatica (VADC)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Veteran patients with polymyalgia rheumatica", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Autoimmune Hemolytic Anemias (VADC)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Veteran patients with autoimmune hemolytic anemia", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Cardiac Complications Not Elsewhere Classified (VADC)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Veteran patients with cardiac complications", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Fasciitis (gwPheWAS)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients diagnosed with fasciitis", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Stomatitis and mucositis (gwPheWAS)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with stomatitis or mucositis", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Barrett's esophagus (gwPheWAS)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with Barretts esophagus", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Regional Enteritis (Phecode)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with regional enteritis", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Osteoarthrosis Localized Primary (Phecode)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with primary localized osteoarthritis", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Aortic Valve Disease (Phecode)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with aortic valve disease", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Chronic Periodontitis (Phecode)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with chronic periodontitis", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Hypertensive chronic kidney disease (MAP)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with hypertensive chronic kidney disease", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Other cardiomyopathy (MAP)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with cardiomyopathy", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
# echo "," >> ${OUTPUT_FILE}

# echo "INFO: Scleritis and episcleritis (MAP)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
#   -H 'Content-Type: application/json' \
#   -d '{"study_intent":"Patients with scleritis or episcleritis", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool >> ${OUTPUT_FILE}
#echo "," >> ${OUTPUT_FILE}


# echo "INFO: Other disorders of carbohydrate transport and metabolism (MAP)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"Patients with a carbohydrate transport and metabolism disorder", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}
# echo ","  >> ${OUTPUT_FILE}

# echo "INFO: [P] acetaminophen exposure 10"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"patients with a drug exposure to acetaminophen in the hospital setting", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}
# echo ","  >> ${OUTPUT_FILE}

# echo "INFO: Dyschromia and Vitiligo"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"Patients diagnosed with dyschromia and vitiligo", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}
# echo ","  >> ${OUTPUT_FILE}

# echo "INFO: Acute Hepatic Injury with no pre-existing liver disease"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"Patients with with no pre-existing liver disease who receive a diagnosis of acute hepatic injury ", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}
# echo ","  >> ${OUTPUT_FILE}

# echo "INFO: Nerve Plexus Lesions"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"A PheCode-based definition of patients with nerve plexus lesions", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}
# echo ","  >> ${OUTPUT_FILE}

# echo "INFO: Posterior reversible encephalopathy syndrome PRES"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"patients with a diagnosis of PRES", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}
# echo ","  >> ${OUTPUT_FILE}

# echo "INFO: Ulcerative colitis (chronic)"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"patients with chronic ulcerative colitis", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}
# echo ","  >> ${OUTPUT_FILE}

# echo "INFO: Pervasive Developmental Disorders"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"Veteran patients with developmental disorders that are pervasive", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}
# echo ","  >> ${OUTPUT_FILE}

# echo "INFO: Acute myocardial infarction"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"patients with at least 2 recorded diagnoses of acute myocardial infarction", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}
# echo ","  >> ${OUTPUT_FILE}

# echo "INFO: Antiphospholipid syndrome"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"patients diagnosed with antiphospholipid syndrome who have recieved care in the outpatient setting", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}
# echo ","  >> ${OUTPUT_FILE}


# echo "INFO: dementia in older adults"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"older adults with a likely diagnosis of ADRD or late-stage dementia", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}

# echo ","  >> ${OUTPUT_FILE}


# echo "INFO:  GI bleeding adverse event outcome"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"patients who experienced a GI bleed adverse event", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}

# echo "," >> ${OUTPUT_FILE}


# echo "INFO: running COVID outpatient diagnosis cohort"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"patients who received a COVID-19 diagnosis in the outpatient setting", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool > /tmp/result.json >> ${OUTPUT_FILE}

# echo ","  >> ${OUTPUT_FILE}

# echo "INFO: running abdominal aortic aneurysm in veterans"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"veterans who experienced an abdominal aortic aneurysm ", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool > /tmp/result.json >> ${OUTPUT_FILE}

# echo "," >> ${OUTPUT_FILE}

# echo "INFO: COPD phenotype using diagnosis codes"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"patients with COPD according to diagnostic codes in the EHR", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}

# echo "," >> ${OUTPUT_FILE}

# echo "INFO: heart failure hospitalization cohort"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"patients hospitalized at least once for heart failure", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}

# echo ","  >> ${OUTPUT_FILE}

# echo "INFO: diabetes medication-based phenotype"
# curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation   -H 'Content-Type: application/json'   -d '{"study_intent":"patients who appear to have diabetes based on a medication-based phenotype", "top_k":20, "max_results":3, "candidate_limit":10}' | python -m json.tool  >> ${OUTPUT_FILE}


echo ']}' >> ${OUTPUT_FILE}

###

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
    pr = item.get('diagnostics', {}).get('planning_rerank', {})
    print(f'CASE {i}: {q}')
    print('  intent_facets_raw:', pr.get('intent_facets_raw'))
    print('  intent_facets_effective:', pr.get('intent_facets_effective'))
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
        reasons = []
        for r in row.get('reasons', []):
            kind = r.get('kind')
            if kind in (
                'topic_mismatch',
                'topic_primary',
                'topic_context',
                'context_without_primary',
                'dynamic_clinical_alias_match',
                'dynamic_clinical_alias_context',
            ):
                reasons.append((kind, r.get('detail')))
        print('  ', row.get('phenotype_id'), '|', row.get('metadata_score'), '|', reasons)
    print()
PY"
