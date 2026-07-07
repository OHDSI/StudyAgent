const titleEl = document.getElementById("viewer-title");
const subtitleEl = document.getElementById("viewer-subtitle");
const statusEl = document.getElementById("viewer-status");
const viewerPanel = document.getElementById("viewer-panel");
const errorPanel = document.getElementById("viewer-error-panel");
const catalogMetadataEl = document.getElementById("catalog-metadata");
const definitionJsonEl = document.getElementById("definition-json");
const errorEl = document.getElementById("viewer-error");
const rawAssembledLink = document.getElementById("raw-assembled-link");
const rawSourceLink = document.getElementById("raw-source-link");

function setStatus(message) {
  statusEl.textContent = message || "";
}

function renderError(payload) {
  errorEl.textContent = JSON.stringify(payload, null, 2);
  errorPanel.classList.remove("hidden");
  viewerPanel.classList.add("hidden");
  setStatus("");
}

async function load() {
  const params = new URLSearchParams(window.location.search);
  const phenotypeId = (params.get("id") || "").trim();
  if (!phenotypeId) {
    renderError({ error: "invalid_request", detail: "Missing phenotype id." });
    return;
  }

  const assembledUrl = `/api/phenotype/${encodeURIComponent(phenotypeId)}?view=assembled`;
  const sourceUrl = `/api/phenotype/${encodeURIComponent(phenotypeId)}?view=source`;
  rawAssembledLink.href = assembledUrl;
  rawSourceLink.href = sourceUrl;

  setStatus("Loading phenotype definition...");
  try {
    const response = await fetch(assembledUrl);
    const payload = await response.json();
    if (!response.ok) {
      renderError(payload);
      return;
    }

    titleEl.textContent = payload.phenotype_name || payload.phenotype_id || "Phenotype definition";
    subtitleEl.textContent = `${payload.phenotype_id || ""}${payload.source_dataset ? ` · ${payload.source_dataset}` : ""}${payload.source_record_type ? ` · ${payload.source_record_type}` : ""}`;
    catalogMetadataEl.textContent = JSON.stringify(payload.catalog_metadata || {}, null, 2);
    definitionJsonEl.textContent = JSON.stringify(payload.definition || {}, null, 2);
    viewerPanel.classList.remove("hidden");
    errorPanel.classList.add("hidden");
    setStatus("");
  } catch (error) {
    renderError({ error: "request_failed", detail: String(error) });
  }
}

load();
