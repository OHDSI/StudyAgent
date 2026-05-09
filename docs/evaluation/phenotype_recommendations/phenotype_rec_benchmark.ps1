$OUTPUT_FILE = "phenotype_results.json"
$SUMMARY_FILE = "phenotype_summary.csv"

$endpoint = "http://127.0.0.1:8765/flows/phenotype_recommendation"

$tests = @(
    @{
        Name = "Cardiac defibrillator in situ (MAP)"
        Intent = "Patients with an implanted cardiac defibrillator"
    },
    @{
        Name = "Fasciitis (gwPheWAS)"
        Intent = "Patients diagnosed with fasciitis"
    },
    @{
        Name = "Acute prostatitis (MAP)"
        Intent = "Patients with acute prostatitis"
    },
    @{
        Name = "Esophagectomy"
        Intent = "Patients who underwent esophagectomy"
    },
    @{
        Name = "Peripheral neuritis"
        Intent = "Patients diagnosed with peripheral neuritis"
    },
    @{
        Name = "TNF-alpha + IL12/23 overlap"
        Intent = "Patients with concomitant TNF-alpha inhibitor and IL-12/23 inhibitor exposure for at least 30 days"
    },
    @{
        Name = "Allergic rhinitis"
        Intent = "Patients with allergic rhinitis"
    },
    @{
        Name = "Ischemic Heart Disease (Sandhu)"
        Intent = "Patients with ischemic heart disease"
    },
    @{
        Name = "Hemorrhage in Early Pregnancy"
        Intent = "Pregnant patients with hemorrhage in early pregnancy or threatened labor"
    },
    @{
        Name = "Lung Resection"
        Intent = "Patients who underwent lung resection"
    }
)

# Clear old files
if (Test-Path $OUTPUT_FILE) {
    Remove-Item $OUTPUT_FILE
}

if (Test-Path $SUMMARY_FILE) {
    Remove-Item $SUMMARY_FILE
}

$allResults = @()
$summaryRows = @()

foreach ($test in $tests) {

    Write-Host ""
    Write-Host "================================================="
    Write-Host "INFO: $($test.Name)"
    Write-Host "================================================="

    $body = @{
        study_intent = $test.Intent
        top_k = 20
        max_results = 3
        candidate_limit = 10
    } | ConvertTo-Json

    $sw = [System.Diagnostics.Stopwatch]::StartNew()

    try {

        $response = Invoke-RestMethod `
            -Uri $endpoint `
            -Method POST `
            -ContentType "application/json" `
            -Body $body

        $sw.Stop()

        $elapsed = [math]::Round($sw.Elapsed.TotalSeconds, 3)

        Write-Host "SUCCESS"
        Write-Host "Elapsed Seconds: $elapsed"

        $resultObject = @{
            benchmark_name = $test.Name
            elapsed_seconds = $elapsed
            response = $response
        }

        $allResults += $resultObject

        $summaryRows += [PSCustomObject]@{
            benchmark_name = $test.Name
            elapsed_seconds = $elapsed
        }

    }
    catch {

        $sw.Stop()

        Write-Host "FAILED"
        Write-Host $_.Exception.Message

        $summaryRows += [PSCustomObject]@{
            benchmark_name = $test.Name
            elapsed_seconds = -1
        }
    }
}

# Write detailed JSON
$allResults | ConvertTo-Json -Depth 20 | Out-File $OUTPUT_FILE

# Write CSV summary
$summaryRows | Export-Csv $SUMMARY_FILE -NoTypeInformation

Write-Host ""
Write-Host "======================================="
Write-Host "BENCHMARK COMPLETE"
Write-Host "======================================="
Write-Host "Detailed Results: $OUTPUT_FILE"
Write-Host "Timing Summary : $SUMMARY_FILE"

Write-Host ""
Write-Host "Average Timing:"
$avg = ($summaryRows | Where-Object {$_.elapsed_seconds -gt 0} | Measure-Object elapsed_seconds -Average).Average
Write-Host ([math]::Round($avg,3))

$times = $summaryRows |
    Where-Object {$_.elapsed_seconds -gt 0} |
    Select-Object -ExpandProperty elapsed_seconds |
    Sort-Object

$median = $times[[math]::Floor($times.Count / 2)]

Write-Host ""
Write-Host "Median Timing:"
Write-Host $median