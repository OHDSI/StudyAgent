const DEFAULT_TOP_K = 20;
const DEFAULT_MAX_RESULTS = 3;
const DEFAULT_CANDIDATE_LIMIT = 10;
const DEFAULT_CANDIDATE_OFFSET = 0;

const form = document.getElementById("intent-form");
const studyIntentInput = document.getElementById("study-intent");
const recommendationRoleInput = document.getElementById("recommendation-role");
const workflowTypeInput = document.getElementById("workflow-type");
const topKInput = document.getElementById("top-k");
const candidateOffsetInput = document.getElementById("candidate-offset");
const maxResultsInput = document.getElementById("max-results");
const candidateLimitInput = document.getElementById("candidate-limit");
const guardrailSummary = document.getElementById("guardrail-summary");
const excludeSourceDatasetInput = document.getElementById("exclude-source-dataset");
const excludeSourceRecordTypeInput = document.getElementById("exclude-source-record-type");
const excludePhenotypeRoleInput = document.getElementById("exclude-phenotype-role");
const excludeCareSettingScopeInput = document.getElementById("exclude-care-setting-scope");
const excludeExecutableStatusInput = document.getElementById("exclude-executable-status");
const goButton = document.getElementById("go-button");
const clearIntentButton = document.getElementById("clear-intent-button");
const resetResultsButton = document.getElementById("reset-results-button");
const statusEl = document.getElementById("status");
const resultsPanel = document.getElementById("results-panel");
const errorPanel = document.getElementById("error-panel");
const recommendationList = document.getElementById("recommendation-list");
const resultSummary = document.getElementById("result-summary");
const diagnosticsPanel = document.getElementById("diagnostics-panel");
const candidateExclusionsOutput = document.getElementById("candidate-exclusions-output");
const planningCandidatesOutput = document.getElementById("planning-candidates-output");
const jsonOutput = document.getElementById("json-output");
const errorOutput = document.getElementById("error-output");

function setLoading(isLoading, message = "") {
  goButton.disabled = isLoading;
  clearIntentButton.disabled = isLoading;
  if (resetResultsButton) {
    resetResultsButton.disabled = isLoading;
  }
  statusEl.textContent = message;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function compactText(value) {
  const text = String(value || "").trim();
  return text || "";
}

function parseCsvValues(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function parsePositiveInteger(value, fallback) {
  const text = String(value ?? "").trim();
  if (!text) {
    return fallback;
  }
  const parsed = Number.parseInt(text, 10);
  if (!Number.isInteger(parsed) || parsed < 1) {
    throw new Error("Recommendation tuning fields must be positive integers.");
  }
  return parsed;
}

function parseNonNegativeInteger(value, fallback) {
  const text = String(value ?? "").trim();
  if (!text) {
    return fallback;
  }
  const parsed = Number.parseInt(text, 10);
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error("Candidate offset must be a non-negative integer.");
  }
  return parsed;
}

function buildExcludeMetadata() {
  const entries = [
    ["source_dataset", parseCsvValues(excludeSourceDatasetInput.value)],
    ["source_record_type", parseCsvValues(excludeSourceRecordTypeInput.value)],
    ["phenotype_role", parseCsvValues(excludePhenotypeRoleInput.value)],
    ["care_setting_scope", parseCsvValues(excludeCareSettingScopeInput.value)],
    ["executable_definition_status", parseCsvValues(excludeExecutableStatusInput.value)],
  ];
  const payload = {};
  entries.forEach(([key, values]) => {
    if (values.length) {
      payload[key] = values;
    }
  });
  return payload;
}

function formatBadge(label, value) {
  const text = compactText(value);
  if (!text) {
    return "";
  }
  return `<span class="badge"><span class="badge-label">${escapeHtml(label)}:</span> ${escapeHtml(text)}</span>`;
}

function renderGuardrailSummary(payload) {
  const effectiveLimits = payload?.diagnostics?.effective_limits || {};
  const stageCounts = payload?.diagnostics?.stage_counts || {};
  const shortlistEnforcement = payload?.diagnostics?.planning_rerank?.shortlist_enforcement || {};
  const cards = [
    {
      label: "Retrieval coverage",
      value: `${effectiveLimits.top_k ?? "-"} / offset ${effectiveLimits.candidate_offset ?? 0}`,
      note: `${stageCounts.retrieved ?? 0} retrieved before downstream pruning.`,
    },
    {
      label: "Planner breadth",
      value: `${effectiveLimits.candidate_limit ?? "-"} shortlist budget`,
      note: `planning window ${effectiveLimits.planning_window ?? "-"}, top band ${effectiveLimits.planning_top_band ?? "-"}.`,
    },
    {
      label: "Final output cap",
      value: `${effectiveLimits.max_results ?? "-"} max results`,
      note: `${stageCounts.final_recommendations ?? 0} recommendation(s) returned after enforcement.`,
    },
    {
      label: "Enforcement pool",
      value: `${effectiveLimits.strict_top_k ?? "-"} strict top-k`,
      note: `${shortlistEnforcement.quality_threshold_skipped_ids?.length || 0} skipped on quality, ${shortlistEnforcement.duplicate_topic_ids?.length || 0} deduped.`,
    },
    {
      label: "Stage counts",
      value: `${stageCounts.planner_allowed ?? 0} planner / ${stageCounts.shortlist ?? 0} shortlist`,
      note: `${stageCounts.after_metadata_exclusions ?? 0} remained after metadata exclusion.`,
    },
    {
      label: "Role-match gate",
      value: payload?.diagnostics?.role_match_gate?.required_kind || "not active",
      note: payload?.diagnostics?.role_match_gate?.skip_reason || "No role-specific skip reason recorded.",
    },
  ];

  guardrailSummary.innerHTML = cards.map((card) => `
    <article class="guardrail-card">
      <h4>${escapeHtml(card.label)}</h4>
      <p>${escapeHtml(card.value)}</p>
      <small>${escapeHtml(card.note)}</small>
    </article>
  `).join("");
}

function clearResults() {
  recommendationList.innerHTML = "";
  resultSummary.textContent = "";
  candidateExclusionsOutput.textContent = "";
  planningCandidatesOutput.textContent = "";
  jsonOutput.textContent = "";
  errorOutput.textContent = "";
  guardrailSummary.innerHTML = '<div class="guardrail-empty muted">Run a recommendation to populate effective limits and stage counts.</div>';
  diagnosticsPanel.classList.add("hidden");
  resultsPanel.classList.add("hidden");
  errorPanel.classList.add("hidden");
  statusEl.textContent = "";
}

function buildSearchMetadataMap(payload) {
  const map = new Map();
  const results = payload?.search?.results || [];
  results.forEach((item) => {
    if (item?.phenotype_id) {
      map.set(item.phenotype_id, item);
    }
  });
  return map;
}

function resolveRecommendationMetadata(item, metadataMap) {
  const byId = metadataMap.get(item?.phenotype_id || "") || {};
  return {
    source_dataset: item?.source_dataset || byId.source_dataset || "",
    source_record_type: item?.source_record_type || byId.source_record_type || "",
    phenotype_role: item?.phenotype_role || byId.phenotype_role || "",
    care_setting_scope: item?.care_setting_scope || byId.care_setting_scope || "",
    executable_definition_status: item?.executable_definition_status || byId.executable_definition_status || "",
    execution_readiness_score:
      item?.execution_readiness_score ?? byId.execution_readiness_score ?? "",
  };
}

function renderRecommendations(payload) {
  const recommendations = payload?.recommendations?.phenotype_recommendations || [];
  const shortlist = payload?.planning?.shortlist_ids || [];
  const candidateExclusions = payload?.diagnostics?.candidate_exclusions || [];
  const planningCandidates = payload?.diagnostics?.planning_rerank?.candidates || payload?.diagnostics?.planning?.candidates || [];
  const metadataMap = buildSearchMetadataMap(payload);

  recommendationList.innerHTML = "";
  if (!recommendations.length) {
    recommendationList.innerHTML = '<li class="empty-state">No recommendations returned.</li>';
  } else {
    recommendations.forEach((item, index) => {
      const li = document.createElement("li");
      li.className = "recommendation-item";
      const title = escapeHtml(item.phenotype_name || item.phenotype_id || `Recommendation ${index + 1}`);
      const phenotypeId = escapeHtml(item.phenotype_id || "");
      const justification = escapeHtml(item.justification || "No justification returned.");
      const confidence = escapeHtml(item.confidence || "");
      const phenotypeHref = item.phenotype_id ? `./phenotype.html?id=${encodeURIComponent(item.phenotype_id)}` : "#";
      const metadata = resolveRecommendationMetadata(item, metadataMap);
      const badgeMarkup = [
        formatBadge("Dataset", metadata.source_dataset),
        formatBadge("Type", metadata.source_record_type),
        formatBadge("Role", metadata.phenotype_role),
        formatBadge("Setting", metadata.care_setting_scope),
        formatBadge("Executable", metadata.executable_definition_status),
        formatBadge("Readiness", metadata.execution_readiness_score),
      ].filter(Boolean).join("");

      li.innerHTML = `
        <div class="recommendation-topline">
          <span class="rank">#${index + 1}</span>
          <div>
            <h3>${title}</h3>
            <p class="meta">${phenotypeId}${confidence ? ` · confidence: ${confidence}` : ""}</p>
          </div>
        </div>
        ${badgeMarkup ? `<div class="badge-row">${badgeMarkup}</div>` : ""}
        <p class="justification">${justification}</p>
        ${item.phenotype_id ? `<p class="card-link-row"><a class="card-link" href="${phenotypeHref}" target="_blank" rel="noopener noreferrer">Open phenotype definition</a></p>` : ""}
      `;
      recommendationList.appendChild(li);
    });
  }

  renderGuardrailSummary(payload);
  resultSummary.textContent = `Returned ${recommendations.length} recommendation(s). Shortlist ids: ${shortlist.join(", ") || "none"}.`;
  candidateExclusionsOutput.textContent = JSON.stringify(candidateExclusions, null, 2);
  planningCandidatesOutput.textContent = JSON.stringify(planningCandidates, null, 2);
  diagnosticsPanel.classList.toggle("hidden", !candidateExclusions.length && !planningCandidates.length);
  jsonOutput.textContent = JSON.stringify(payload, null, 2);
  resultsPanel.classList.remove("hidden");
  errorPanel.classList.add("hidden");
}

function renderError(payload) {
  errorOutput.textContent = JSON.stringify(payload, null, 2);
  errorPanel.classList.remove("hidden");
  resultsPanel.classList.add("hidden");
}

function resetFormFields() {
  studyIntentInput.value = "";
  recommendationRoleInput.value = "";
  workflowTypeInput.value = "";
  topKInput.value = String(DEFAULT_TOP_K);
  candidateOffsetInput.value = String(DEFAULT_CANDIDATE_OFFSET);
  maxResultsInput.value = String(DEFAULT_MAX_RESULTS);
  candidateLimitInput.value = String(DEFAULT_CANDIDATE_LIMIT);
  excludeSourceDatasetInput.value = "";
  excludeSourceRecordTypeInput.value = "";
  excludePhenotypeRoleInput.value = "";
  excludeCareSettingScopeInput.value = "";
  excludeExecutableStatusInput.value = "";
}

clearIntentButton.addEventListener("click", () => {
  resetFormFields();
  studyIntentInput.focus();
  statusEl.textContent = "";
});

if (resetResultsButton) {
  resetResultsButton.addEventListener("click", () => {
    clearResults();
  });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const studyIntent = studyIntentInput.value.trim();
  if (!studyIntent) {
    renderError({ error: "invalid_request", detail: "Study intent is required." });
    return;
  }

  let topK;
  let candidateOffset;
  let maxResults;
  let candidateLimit;
  try {
    topK = parsePositiveInteger(topKInput.value, DEFAULT_TOP_K);
    candidateOffset = parseNonNegativeInteger(candidateOffsetInput.value, DEFAULT_CANDIDATE_OFFSET);
    maxResults = parsePositiveInteger(maxResultsInput.value, DEFAULT_MAX_RESULTS);
    candidateLimit = parsePositiveInteger(candidateLimitInput.value, DEFAULT_CANDIDATE_LIMIT);
  } catch (error) {
    renderError({ error: "invalid_request", detail: String(error.message || error) });
    return;
  }

  const recommendationRole = recommendationRoleInput.value.trim();
  const workflowType = workflowTypeInput.value.trim();
  const excludeMetadata = buildExcludeMetadata();
  const requestPayload = {
    study_intent: studyIntent,
    top_k: topK,
    candidate_offset: candidateOffset,
    max_results: maxResults,
    candidate_limit: candidateLimit,
  };
  if (recommendationRole) {
    requestPayload.recommendation_role = recommendationRole;
  }
  if (workflowType) {
    requestPayload.workflow_type = workflowType;
  }
  if (Object.keys(excludeMetadata).length) {
    requestPayload.exclude_metadata = excludeMetadata;
  }

  setLoading(true, "Running phenotype recommendation...");
  try {
    const response = await fetch("/api/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestPayload),
    });
    const payload = await response.json();
    if (!response.ok) {
      renderError(payload);
    } else {
      renderRecommendations(payload);
    }
  } catch (error) {
    renderError({ error: "request_failed", detail: String(error) });
  } finally {
    setLoading(false, "");
  }
});
