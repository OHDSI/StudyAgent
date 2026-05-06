#!/usr/bin/env bash

OUTPUT_FILE="phenotype_results.json"
SUMMARY_FILE="phenotype_summary.csv"
ENDPOINT="http://127.0.0.1:8765/flows/phenotype_recommendation"

rm -f "$OUTPUT_FILE" "$SUMMARY_FILE"

echo "benchmark_name,elapsed_seconds" > "$SUMMARY_FILE"
echo "[" > "$OUTPUT_FILE"

declare -a NAMES=(
  "Cardiac defibrillator in situ (MAP)"
  "Fasciitis (gwPheWAS)"
  "Acute prostatitis (MAP)"
  "Esophagectomy"
  "Peripheral neuritis"
  "TNF-alpha + IL12/23 overlap"
  "Allergic rhinitis"
  "Ischemic Heart Disease (Sandhu)"
  "Hemorrhage in Early Pregnancy"
  "Lung Resection"
)

declare -a INTENTS=(
  "Patients with an implanted cardiac defibrillator"
  "Patients diagnosed with fasciitis"
  "Patients with acute prostatitis"
  "Patients who underwent esophagectomy"
  "Patients diagnosed with peripheral neuritis"
  "Patients with concomitant TNF-alpha inhibitor and IL-12/23 inhibitor exposure for at least 30 days"
  "Patients with allergic rhinitis"
  "Patients with ischemic heart disease"
  "Pregnant patients with hemorrhage in early pregnancy or threatened labor"
  "Patients who underwent lung resection"
)

first_result=true

for i in "${!NAMES[@]}"; do
  name="${NAMES[$i]}"
  intent="${INTENTS[$i]}"

  echo ""
  echo "================================================="
  echo "INFO: $name"
  echo "================================================="

  body=$(jq -n \
    --arg study_intent "$intent" \
    '{
      study_intent: $study_intent,
      top_k: 20,
      max_results: 3,
      candidate_limit: 10
    }')

  start_ns=$(date +%s%N)

  response=$(curl -s -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "$body")

  curl_status=$?

  end_ns=$(date +%s%N)
  elapsed_seconds=$(awk "BEGIN {printf \"%.3f\", ($end_ns - $start_ns) / 1000000000}")

  if [[ $curl_status -eq 0 && -n "$response" ]]; then
    echo "SUCCESS"
    echo "Elapsed Seconds: $elapsed_seconds"

    echo "\"$name\",$elapsed_seconds" >> "$SUMMARY_FILE"

    if [[ "$first_result" == false ]]; then
      echo "," >> "$OUTPUT_FILE"
    fi

    jq -n \
      --arg benchmark_name "$name" \
      --argjson elapsed_seconds "$elapsed_seconds" \
      --argjson response "$response" \
      '{
        benchmark_name: $benchmark_name,
        elapsed_seconds: $elapsed_seconds,
        response: $response
      }' >> "$OUTPUT_FILE"

    first_result=false

  else
    echo "FAILED"
    echo "curl exit status: $curl_status"

    echo "\"$name\",-1" >> "$SUMMARY_FILE"
  fi
done

echo "" >> "$OUTPUT_FILE"
echo "]" >> "$OUTPUT_FILE"

echo ""
echo "======================================="
echo "BENCHMARK COMPLETE"
echo "======================================="
echo "Detailed Results: $OUTPUT_FILE"
echo "Timing Summary : $SUMMARY_FILE"

echo ""
echo "Average Timing:"
awk -F, '
NR > 1 && $2 > 0 {
  sum += $2
  count += 1
}
END {
  if (count > 0) {
    printf "%.3f\n", sum / count
  } else {
    print "NA"
  }
}
' "$SUMMARY_FILE"

echo ""
echo "Median Timing:"
awk -F, '
NR > 1 && $2 > 0 {
  values[count++] = $2
}
END {
  if (count == 0) {
    print "NA"
    exit
  }

  asort(values)

  mid = int(count / 2)

  if (count % 2 == 1) {
    printf "%.3f\n", values[mid + 1]
  } else {
    printf "%.3f\n", (values[mid] + values[mid + 1]) / 2
  }
}
' "$SUMMARY_FILE"
