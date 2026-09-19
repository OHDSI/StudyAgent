<#
.SYNOPSIS
Run an air-gap-safe evaluation of ACP phenotype retrieval and recommendations.

.DESCRIPTION
For each unstructured query, this script calls the running ACP endpoint with
top_k, candidate_limit, and max_results all set to ResultCount (20 by default).
It writes two separate ranked candidate files:

* retrieval_candidates.csv: the raw MCP hybrid-retrieval ranking from
  response.search.results. Use this for retrieval metrics.
* recommendation_candidates.csv: the post-ACP clinical/recommendation ranking
  from response.recommendations.phenotype_recommendations.

If QrelsCsv is supplied, the script also writes per-query and aggregate
hit@K/AP@K/MAP@K CSVs. AP@K is normalized by min(number of relevant judgments,
K); MAP@K is the mean AP@K across successful queries that have at least one
positive relevance judgment. Failed ACP calls are recorded in errors.csv and
excluded from metric denominators.

No PowerShell modules, Python packages, R packages, or network access beyond
the configured local ACP endpoint are required.

.PARAMETER QueryCsv
CSV with required columns query_id and query_text. Optional query_label is
copied into the output files.

.PARAMETER QrelsCsv
Optional long-form relevance CSV with query_id, phenotype_id, and optional
relevance columns. A missing relevance value is treated as relevant; 0, false,
or no is treated as non-relevant. Use stable IDs such as cipher:2054 or
ohdsi:1037, not display names.

.EXAMPLE
.\phenotype_recommendation_evaluation.ps1 `
  -QueryCsv .\phenotype_queries.csv `
  -QrelsCsv .\phenotype_qrels.csv `
  -OutputDir .\phenotype-evaluation-output

Example query CSV:
  query_id,query_text,query_label
  acute_prostatitis,"Patients with acute prostatitis",Acute prostatitis

Example qrels CSV:
  query_id,phenotype_id,relevance
  acute_prostatitis,cipher:2054,1
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$QueryCsv,

  [string]$QrelsCsv,

  [string]$AcpUrl = "http://127.0.0.1:8765/flows/phenotype_recommendation",

  [string]$OutputDir = (Join-Path (Get-Location) ("phenotype-evaluation-" + (Get-Date -Format "yyyyMMdd-HHmmss"))),

  [ValidateRange(1, 1000)]
  [int]$ResultCount = 20,

  [int[]]$MetricK = @(1, 3, 5, 10, 20),

  [ValidateRange(1, 3600)]
  [int]$TimeoutSec = 1800,

  [string]$RecommendationRole,

  [string]$WorkflowType,

  [string]$RunLabel,

  [string]$ModelIdentifier,

  [string]$ModelVersion,

  [string]$ServingStack,

  [string]$InferenceSettings
)

$ErrorActionPreference = "Stop"

function Get-Value {
  param(
    [object]$Object,
    [string]$Name,
    [object]$Default = $null
  )
  if ($null -eq $Object) { return $Default }
  if ($Object -is [System.Collections.IDictionary]) {
    if ($Object.Contains($Name)) { return $Object[$Name] }
    return $Default
  }
  $property = $Object.PSObject.Properties[$Name]
  if ($null -eq $property) { return $Default }
  return $property.Value
}

function Get-Text {
  param([object]$Value)
  if ($null -eq $Value) { return "" }
  return [string]$Value
}

function Convert-ToCsvCell {
  param([object]$Value)
  if ($null -eq $Value) { return "" }
  if ($Value -is [string] -or $Value -is [ValueType]) { return $Value }
  return ($Value | ConvertTo-Json -Depth 12 -Compress)
}

function Write-CsvWithHeaders {
  param(
    [object[]]$Rows,
    [string]$Path,
    [string[]]$Columns
  )
  if ($Rows.Count -gt 0) {
    $Rows | Select-Object $Columns | Export-Csv -LiteralPath $Path -NoTypeInformation -Encoding UTF8
  }
  else {
    Set-Content -LiteralPath $Path -Value ($Columns -join ",") -Encoding UTF8
  }
}

function Test-PositiveRelevance {
  param([object]$Value)
  $text = (Get-Text $Value).Trim().ToLowerInvariant()
  if ($text -in @("0", "false", "no", "n")) { return $false }
  return $true
}

function Add-OutputError {
  param([string]$QueryId, [string]$QueryText, [string]$Message)
  $script:errorRows += [PSCustomObject]@{
    query_id = $QueryId
    query_text = $QueryText
    error = $Message
  }
}

if (-not (Test-Path -LiteralPath $QueryCsv -PathType Leaf)) {
  throw "QueryCsv was not found: $QueryCsv"
}
if ($QrelsCsv -and -not (Test-Path -LiteralPath $QrelsCsv -PathType Leaf)) {
  throw "QrelsCsv was not found: $QrelsCsv"
}

$queries = @(Import-Csv -LiteralPath $QueryCsv)
if ($queries.Count -eq 0) { throw "QueryCsv contains no data rows: $QueryCsv" }

$seenQueryIds = @{}
foreach ($query in $queries) {
  $queryId = (Get-Text (Get-Value $query "query_id")).Trim()
  $queryText = (Get-Text (Get-Value $query "query_text")).Trim()
  if (-not $queryId) { throw "Each QueryCsv row requires query_id." }
  if (-not $queryText) { throw "Query '$queryId' has an empty query_text." }
  if ($seenQueryIds.ContainsKey($queryId)) { throw "QueryCsv contains duplicate query_id '$queryId'." }
  $seenQueryIds[$queryId] = $true
}

$relevantByQuery = @{}
if ($QrelsCsv) {
  foreach ($qrel in @(Import-Csv -LiteralPath $QrelsCsv)) {
    $queryId = (Get-Text (Get-Value $qrel "query_id")).Trim()
    $phenotypeId = (Get-Text (Get-Value $qrel "phenotype_id")).Trim()
    if (-not $queryId -or -not $phenotypeId) {
      throw "Each QrelsCsv row requires query_id and phenotype_id."
    }
    if (-not $seenQueryIds.ContainsKey($queryId)) {
      throw "QrelsCsv references unknown query_id '$queryId'."
    }
    if (-not (Test-PositiveRelevance (Get-Value $qrel "relevance"))) { continue }
    if (-not $relevantByQuery.ContainsKey($queryId)) {
      $relevantByQuery[$queryId] = New-Object 'System.Collections.Generic.HashSet[string]'
    }
    [void]$relevantByQuery[$queryId].Add($phenotypeId)
  }
}

$MetricK = @($MetricK | Where-Object { $_ -ge 1 -and $_ -le $ResultCount } | Sort-Object -Unique)
if ($MetricK.Count -eq 0) { throw "MetricK must contain at least one value from 1 through ResultCount ($ResultCount)." }

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$responsesDir = Join-Path $OutputDir "responses"
New-Item -ItemType Directory -Force -Path $responsesDir | Out-Null

$retrievalRows = @()
$recommendationRows = @()
$runRows = @()
$errorRows = @()
$stageRows = @{}
$successfulQueryIds = @()

Write-Host "ACP endpoint: $AcpUrl"
Write-Host "Queries: $($queries.Count); requested results per stage: $ResultCount"

foreach ($query in $queries) {
  $queryId = (Get-Text (Get-Value $query "query_id")).Trim()
  $queryText = (Get-Text (Get-Value $query "query_text")).Trim()
  $queryLabel = (Get-Text (Get-Value $query "query_label")).Trim()
  if (-not $queryLabel) { $queryLabel = $queryId }
  Write-Host "[$queryId] $queryLabel"

  $body = @{
    study_intent = $queryText
    top_k = $ResultCount
    candidate_limit = $ResultCount
    max_results = $ResultCount
  }
  if ($RecommendationRole) { $body.recommendation_role = $RecommendationRole }
  if ($WorkflowType) { $body.workflow_type = $WorkflowType }

  $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
  try {
    $response = Invoke-RestMethod -Uri $AcpUrl -Method Post -ContentType "application/json" -Body ($body | ConvertTo-Json -Depth 8) -TimeoutSec $TimeoutSec
    $stopwatch.Stop()
  }
  catch {
    $stopwatch.Stop()
    $message = $_.Exception.Message
    Add-OutputError $queryId $queryText $message
    $runRows += [PSCustomObject]@{
      query_id = $queryId; query_label = $queryLabel; query_text = $queryText
      status = "request_failed"; elapsed_seconds = [math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
      retrieved_count = 0; post_exclusion_count = 0; planning_reranked_count = 0
      shortlist_count = 0; final_recommendation_count = 0; fallback_reason = ""
      llm_status = ""; request_top_k = $ResultCount; request_candidate_limit = $ResultCount
      request_max_results = $ResultCount
    }
    Write-Warning "[$queryId] ACP request failed: $message"
    continue
  }

  $safeId = ($queryId -replace '[^A-Za-z0-9._-]', '_')
  $snapshotPath = Join-Path $responsesDir ("{0}.json" -f $safeId)
  $response | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $snapshotPath -Encoding UTF8

  $search = Get-Value $response "search" @{}
  $rawCandidates = @(Get-Value $search "results" @())
  $recommendations = Get-Value $response "recommendations" @{}
  $finalCandidates = @(Get-Value $recommendations "phenotype_recommendations" @())
  $diagnostics = Get-Value $response "diagnostics" @{}
  $stageCounts = Get-Value $diagnostics "stage_counts" @{}
  $relevantIds = if ($relevantByQuery.ContainsKey($queryId)) { $relevantByQuery[$queryId] } else { $null }

  $retrievalStageKey = "$queryId|retrieval"
  $recommendationStageKey = "$queryId|recommendation"
  $stageRows[$retrievalStageKey] = @()
  $stageRows[$recommendationStageKey] = @()

  $rank = 0
  foreach ($candidate in $rawCandidates) {
    $rank++
    $phenotypeId = (Get-Text (Get-Value $candidate "phenotype_id")).Trim()
    $isRelevant = if ($null -eq $relevantIds) { $null } else { $relevantIds.Contains($phenotypeId) }
    $row = [PSCustomObject]@{
      query_id = $queryId; query_label = $queryLabel; query_text = $queryText; stage = "retrieval"; rank = $rank
      phenotype_id = $phenotypeId; phenotype_name = Get-Text (Get-Value $candidate "name")
      source_dataset = Get-Text (Get-Value $candidate "source_dataset")
      source_record_type = Get-Text (Get-Value $candidate "source_record_type")
      primary_clinical_topic = Get-Text (Get-Value $candidate "primary_clinical_topic")
      phenotype_role = Get-Text (Get-Value $candidate "phenotype_role")
      executable_definition_status = Get-Text (Get-Value $candidate "executable_definition_status")
      score = Get-Value $candidate "score"; score_dense = Get-Value $candidate "score_dense"
      score_sparse = Get-Value $candidate "score_sparse"; is_relevant = $isRelevant
    }
    $retrievalRows += $row
    $stageRows[$retrievalStageKey] += $row
  }

  $rank = 0
  foreach ($candidate in $finalCandidates) {
    $rank++
    $phenotypeId = (Get-Text (Get-Value $candidate "phenotype_id")).Trim()
    $isRelevant = if ($null -eq $relevantIds) { $null } else { $relevantIds.Contains($phenotypeId) }
    $row = [PSCustomObject]@{
      query_id = $queryId; query_label = $queryLabel; query_text = $queryText; stage = "recommendation"; rank = $rank
      phenotype_id = $phenotypeId; phenotype_name = Get-Text (Get-Value $candidate "phenotype_name")
      computability_status = Get-Text (Get-Value $candidate "computability_status")
      justification = Get-Text (Get-Value $candidate "justification")
      confidence = Get-Value $candidate "confidence"; is_relevant = $isRelevant
    }
    $recommendationRows += $row
    $stageRows[$recommendationStageKey] += $row
  }

  $successfulQueryIds += $queryId
  $runRows += [PSCustomObject]@{
    query_id = $queryId; query_label = $queryLabel; query_text = $queryText
    status = Get-Text (Get-Value $response "status")
    elapsed_seconds = [math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
    retrieved_count = Get-Value $stageCounts "retrieved" $rawCandidates.Count
    post_exclusion_count = Get-Value $stageCounts "after_metadata_exclusions" ""
    planning_reranked_count = Get-Value $stageCounts "planning_reranked" ""
    shortlist_count = Get-Value $stageCounts "shortlist" ""
    final_recommendation_count = Get-Value $stageCounts "final_recommendations" $finalCandidates.Count
    fallback_reason = Get-Text (Get-Value $response "fallback_reason")
    llm_status = Get-Text (Get-Value $response "llm_status")
    request_top_k = $ResultCount; request_candidate_limit = $ResultCount; request_max_results = $ResultCount
  }
  Write-Host "  retrieval=$($rawCandidates.Count); recommendations=$($finalCandidates.Count); elapsed=$([math]::Round($stopwatch.Elapsed.TotalSeconds, 2))s"
}

$retrievalColumns = @("query_id", "query_label", "query_text", "stage", "rank", "phenotype_id", "phenotype_name", "source_dataset", "source_record_type", "primary_clinical_topic", "phenotype_role", "executable_definition_status", "score", "score_dense", "score_sparse", "is_relevant")
$recommendationColumns = @("query_id", "query_label", "query_text", "stage", "rank", "phenotype_id", "phenotype_name", "computability_status", "justification", "confidence", "is_relevant")
$runColumns = @("query_id", "query_label", "query_text", "status", "elapsed_seconds", "retrieved_count", "post_exclusion_count", "planning_reranked_count", "shortlist_count", "final_recommendation_count", "fallback_reason", "llm_status", "request_top_k", "request_candidate_limit", "request_max_results")

Write-CsvWithHeaders $retrievalRows (Join-Path $OutputDir "retrieval_candidates.csv") $retrievalColumns
Write-CsvWithHeaders $recommendationRows (Join-Path $OutputDir "recommendation_candidates.csv") $recommendationColumns
Write-CsvWithHeaders $runRows (Join-Path $OutputDir "query_run_summary.csv") $runColumns
Write-CsvWithHeaders $errorRows (Join-Path $OutputDir "errors.csv") @("query_id", "query_text", "error")

$metricsByQuery = @()
$metricsSummary = @{}
if ($QrelsCsv) {
  foreach ($queryId in $successfulQueryIds) {
    if (-not $relevantByQuery.ContainsKey($queryId)) { continue }
    $relevantIds = $relevantByQuery[$queryId]
    if ($relevantIds.Count -eq 0) { continue }
    foreach ($stage in @("retrieval", "recommendation")) {
      $rows = @($stageRows["$queryId|$stage"] | Sort-Object rank)
      foreach ($k in $MetricK) {
        $hits = 0
        $precisionSum = 0.0
        $position = 0
        foreach ($row in $rows) {
          $position++
          if ($position -gt $k) { break }
          if ($relevantIds.Contains((Get-Text $row.phenotype_id))) {
            $hits++
            $precisionSum += ($hits / [double]$position)
          }
        }
        $apDenominator = [math]::Min($relevantIds.Count, $k)
        $apAtK = if ($apDenominator -gt 0) { $precisionSum / $apDenominator } else { 0.0 }
        $metricRow = [PSCustomObject]@{
          query_id = $queryId; stage = $stage; k = $k; relevant_count = $relevantIds.Count
          returned_count = $rows.Count; hit_at_k = [int]($hits -gt 0); ap_at_k = [math]::Round($apAtK, 8)
        }
        $metricsByQuery += $metricRow
        $summaryKey = "$stage|$k"
        if (-not $metricsSummary.ContainsKey($summaryKey)) {
          $metricsSummary[$summaryKey] = [PSCustomObject]@{ stage = $stage; k = $k; evaluable_queries = 0; hits = 0; ap_sum = 0.0 }
        }
        $summary = $metricsSummary[$summaryKey]
        $summary.evaluable_queries++
        $summary.hits += $metricRow.hit_at_k
        $summary.ap_sum += $apAtK
      }
    }
  }
}

$metricsSummaryRows = @()
foreach ($summary in @($metricsSummary.Values | Sort-Object stage, k)) {
  $metricsSummaryRows += [PSCustomObject]@{
    stage = $summary.stage; k = $summary.k; evaluable_queries = $summary.evaluable_queries
    hits = $summary.hits
    hit_rate_at_k = if ($summary.evaluable_queries) { [math]::Round($summary.hits / [double]$summary.evaluable_queries, 8) } else { "" }
    map_at_k = if ($summary.evaluable_queries) { [math]::Round($summary.ap_sum / [double]$summary.evaluable_queries, 8) } else { "" }
  }
}

Write-CsvWithHeaders $metricsByQuery (Join-Path $OutputDir "metrics_by_query.csv") @("query_id", "stage", "k", "relevant_count", "returned_count", "hit_at_k", "ap_at_k")
Write-CsvWithHeaders $metricsSummaryRows (Join-Path $OutputDir "metrics_summary.csv") @("stage", "k", "evaluable_queries", "hits", "hit_rate_at_k", "map_at_k")

$metadata = [PSCustomObject]@{
  run_utc = (Get-Date).ToUniversalTime().ToString("o")
  run_label = $RunLabel
  model_identifier = $ModelIdentifier
  model_version = $ModelVersion
  serving_stack = $ServingStack
  inference_settings = $InferenceSettings
  acp_url = $AcpUrl
  query_csv = (Resolve-Path -LiteralPath $QueryCsv).Path
  qrels_csv = if ($QrelsCsv) { (Resolve-Path -LiteralPath $QrelsCsv).Path } else { "" }
  result_count = $ResultCount
  metric_k = ($MetricK -join ",")
  timeout_seconds = $TimeoutSec
  recommendation_role = $RecommendationRole
  workflow_type = $WorkflowType
  powershell_version = $PSVersionTable.PSVersion.ToString()
  successful_queries = $successfulQueryIds.Count
  failed_queries = $errorRows.Count
}
$metadata | Export-Csv -LiteralPath (Join-Path $OutputDir "run_metadata.csv") -NoTypeInformation -Encoding UTF8

Write-Host ""
Write-Host "Evaluation complete: $OutputDir"
Write-Host "  Raw retrieval rankings: retrieval_candidates.csv"
Write-Host "  Post-filter recommendations: recommendation_candidates.csv"
Write-Host "  Query-level metrics: metrics_by_query.csv"
Write-Host "  Aggregate metrics: metrics_summary.csv"
Write-Host "  ACP response snapshots: responses\\"
