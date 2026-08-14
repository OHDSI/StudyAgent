# Phenotype indexing

## Purpose

Phenotype indexing makes previously defined cohort phenotypes searchable. Study Agent uses the index to find phenotypes that may be reused or adapted when a user is defining the target, comparator, or outcome cohort for a study. Search results are starting points for human review; they are not automatically adopted as study definitions.

The core builder creates a local catalog, sparse search index, and a copy of each source definition. Dense/vector search is optional.

## Cohort sources to index

Use the builder with a metadata CSV and a directory of cohort-definition JSON files. Candidate sources include:

- The [OHDSI PhenotypeLibrary](https://github.com/OHDSI/PhenotypeLibrary): use the library metadata (Cohorts.csv) and cohort JSON definitions (cohorts/ sub-folder) from its `inst/` directory.
- Cohorts created in Atlas: export cohort definitions from Atlas, or export them from the WebAPI results schema through an authorized database connection; create a matching metadata CSV.
- Cohorts created with [Capr](https://github.com/OHDSI/Capr): export the cohort-definition JSON files and create a matching metadata CSV.

The metadata CSV identifies cohorts and their descriptive fields. The definition directory provides the corresponding JSON definitions. The builder matches a JSON definition to the metadata cohort identifier (`cohortId` or `id`, falling back to the JSON filename).

## Build the included 20-cohort example

The repository includes a small example derived from PhenotypeLibrary:

- `data/Cohorts.csv` — metadata for 20 cohorts
- `data/Cohorts/` — the corresponding exported cohort-definition JSON files

From the repository root, build a sparse index:

```bash
uv run study-agent-build-phenotype-index \
  --metadata-csv data/Cohorts.csv \
  --definitions-dir data/Cohorts \
  --output-dir data/phenotype_index_sample
```

The command is defined in `pyproject.toml`, so it is available after installing the project. It reads `config.yaml` and the optional secret-only `secrets.env` from the current directory; pass `--config <path>` and `--profile <name>` when needed. Without uv, run `study-agent-build-phenotype-index` from an activated project environment.

The output directory contains:

- `catalog.jsonl` — searchable phenotype records
- `sparse_index.pkl` — sparse retrieval index
- `definitions/` — copied definition JSON files
- `meta.json` — source counts and build metadata

Point the MCP service at the finished index in `config.yaml`:

```yaml
paths:
  phenotype_index: data/phenotype_index_sample
```

Use an absolute path for deployed services when practical.

## Optional dense search

Add `--build-dense` when the embedding service configured through `retrieval.embedding_url` and `retrieval.embedding_model` is available. `EMBED_API_KEY` remains a secret environment variable if the embedding endpoint requires one.

```bash
uv run study-agent-build-phenotype-index \
  --metadata-csv data/Cohorts.csv \
  --definitions-dir data/Cohorts \
  --output-dir data/phenotype_index_sample \
  --build-dense
```

To add dense search later without rebuilding the catalog:

```bash
uv run study-agent-build-phenotype-index \
  --output-dir data/phenotype_index_sample \
  --build-dense \
  --dense-only
```

Add `--require-dense` when a deployment should fail rather than retain sparse-only search.

## Experimental: VA CIPHER inputs and LLM keywords

VA CIPHER support is experimental. Supply its phenotype JSON directory and enum file with `--cipher-dir` and `--cipher-enum`. LLM-derived keywords are also experimental; enable them with `--derive-keywords-llm` only after configuring the LLM endpoint and authentication for the build process.

```bash
uv run study-agent-build-phenotype-index \
  --metadata-csv data/Cohorts.csv \
  --definitions-dir data/Cohorts \
  --cipher-dir data/cipher-phenotypes \
  --cipher-enum "data/cipher-phenotypes/enumType 1.json" \
  --derive-keywords-llm \
  --output-dir data/phenotype_index_experimental
```

Successful LLM keyword generations are cached in `keyword_cache.jsonl` within the output directory. The builder uses heuristic keywords when LLM generation is unavailable or unsuccessful.

## Verify a build

```bash
uv run python - <<'PY'
from study_agent_mcp.retrieval.index import PhenotypeIndex

index = PhenotypeIndex("data/phenotype_index_sample", allow_dense=False).load()
print(index.meta.get("catalog_count"))
PY
```

For larger source collections, build and review the sparse catalog first, then add dense indexing in a later pass.


## Sandbox phenotype search tool

In utilities/phenotype_recommendation_review_app/ there is a simple web application to test phenotype index search. To use it:

1. have the following items configured in config.yaml: llm.api_url, llm.model, paths.phenotype_index
2. have the ACP and MCP running

You can then start the app using the instructions in the README in the
apps folder. When started it will direct you to where to point your
browser.