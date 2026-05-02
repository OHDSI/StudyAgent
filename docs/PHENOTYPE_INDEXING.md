**Phenotype Indexing**

This guide explains how to build the phenotype retrieval index used by the MCP phenotype search and phenotype recommendation flows.

**What The Builder Produces**
The index builder now supports a split workflow:

1. Source parsing and sparse indexing
- builds `catalog.jsonl`
- builds `sparse_index.pkl`
- copies phenotype definition JSON into `definitions/`
- optionally derives compact LLM-assisted `retrieval_keywords`

2. Dense indexing
- builds `dense.index`
- builds or updates `embedding_cache.pkl`
- can run during the main build or later in a dense-only pass using an existing `catalog.jsonl`

**Supported Source Inputs**
You can build from either or both of these source families:

1. OHDSI / OMOP phenotype library inputs
- metadata CSV such as `data/Cohorts.csv`
- cohort definition JSON directory such as `data/cohorts/`

2. VA CIPHER phenotype inputs
- phenotype JSON directory such as `data/cipher-phenotypes/`
- enum JSON such as `data/cipher-phenotypes/enumType 1.json`

**Important Path Rule**
`PHENOTYPE_INDEX_DIR` points to the built index output directory.
It does not control where OHDSI or CIPHER source files reside.
The source files can live anywhere as long as you pass their paths on the command line.

**Prerequisites**
Minimum prerequisites for catalog plus sparse index:
- Python environment with this repo installed
- OHDSI and/or CIPHER source files

Additional prerequisites for LLM-derived retrieval keywords:
- `LLM_API_URL`
- `LLM_API_KEY`
- `LLM_MODEL`

Additional prerequisites for dense index creation:
- `numpy`
- `faiss`
- `EMBED_URL`
- `EMBED_MODEL`
- `EMBED_API_KEY` if your embedding endpoint requires auth

**Main Build Command**
This builds the catalog, sparse index, metadata, copied definitions, and optional keyword cache.

```bash
python mcp_server/scripts/build_phenotype_index.py \
  --metadata-csv data/Cohorts.csv \
  --definitions-dir data/cohorts \
  --cipher-dir data/cipher-phenotypes \
  --cipher-enum "data/cipher-phenotypes/enumType 1.json" \
  --output-dir data/phenotype_index_cipher_omop
```

**Enable LLM-Derived Retrieval Keywords**
This uses chat completion to derive compact `retrieval_keywords` and writes successful generations to `keyword_cache.jsonl`.

```bash
python mcp_server/scripts/build_phenotype_index.py \
  --metadata-csv data/Cohorts.csv \
  --definitions-dir data/cohorts \
  --cipher-dir data/cipher-phenotypes \
  --cipher-enum "data/cipher-phenotypes/enumType 1.json" \
  --derive-keywords-llm \
  --output-dir data/phenotype_index_cipher_omop
```

Notes:
- `keyword_cache.jsonl` is append-oriented and is written incrementally as successful LLM keyword generations occur.
- If no LLM keyword generations succeed, no cache file is created.
- The built `catalog.jsonl` still contains `retrieval_keywords` even when they come from the heuristic fallback rather than the LLM.

**Build Sparse And Dense In One Pass**
Use this when embedding infrastructure is available and you want the full index in one run.

```bash
python mcp_server/scripts/build_phenotype_index.py \
  --metadata-csv data/Cohorts.csv \
  --definitions-dir data/cohorts \
  --cipher-dir data/cipher-phenotypes \
  --cipher-enum "data/cipher-phenotypes/enumType 1.json" \
  --derive-keywords-llm \
  --build-dense \
  --output-dir data/phenotype_index_cipher_omop
```

If the build must fail when dense indexing cannot be produced, add:

```bash
--require-dense
```

**Build Dense Later From An Existing Catalog**
Use this when the catalog and sparse index already exist and you want to add `dense.index` afterward.

```bash
python mcp_server/scripts/build_phenotype_index.py \
  --output-dir data/phenotype_index_cipher_omop \
  --build-dense \
  --dense-only
```

This mode:
- reads the existing `catalog.jsonl`
- builds `dense.index`
- updates `embedding_cache.pkl`
- updates the `dense` section in `meta.json`

This mode does not:
- rebuild `catalog.jsonl` from source phenotype files
- rebuild `sparse_index.pkl`
- rerun LLM keyword derivation

**Output Directory Contents**
After the main build, the output directory typically contains:

1. `catalog.jsonl`
- shared phenotype documents for OHDSI and CIPHER sources
- includes derived fields such as `retrieval_keywords`, `retrieval_keywords_source`, `retrieval_concept_labels`, and `methodology_summary`

2. `sparse_index.pkl`
- BM25-style sparse retrieval index

3. `meta.json`
- build counts
- dense build status
- keyword derivation metadata
- embedding configuration metadata

4. `definitions/`
- copied phenotype or cohort definition JSON files

5. `keyword_cache.jsonl`
- optional append-only cache of successful LLM-derived retrieval keyword generations

After dense indexing, the directory may also contain:

6. `dense.index`
- FAISS dense index

7. `embedding_cache.pkl`
- cached text embeddings keyed by hash of `retrieval_text`

**Recommended Environment Variable**
Point the MCP retrieval layer at the built index directory:

```bash
export PHENOTYPE_INDEX_DIR=/absolute/path/to/data/phenotype_index_cipher_omop
```

If `PHENOTYPE_INDEX_DIR` is not set, the retrieval layer falls back to the repo-relative default `data/phenotype_index`.

**Sanity Check**
After a build, you can inspect the index quickly with:

```bash
python - <<'PY'
from study_agent_mcp.retrieval.index import PhenotypeIndex
idx = PhenotypeIndex("data/phenotype_index_cipher_omop", allow_dense=False).load()
print(idx.meta.get("catalog_count"))
print(idx.fetch_summary("ohdsi:2"))
print(idx.fetch_summary("cipher:1976"))
print(idx.meta.get("keyword_derivation"))
PY
```

**Dense Status Check**
To confirm whether dense indexing was created:

```bash
python - <<'PY'
import json
from pathlib import Path
meta = json.loads(Path("data/phenotype_index_cipher_omop/meta.json").read_text())
print(meta.get("dense"))
PY
```

*Metadata indexing check*

```
/bin/sh -lc "python - <<'PY'
import json
from pathlib import Path
wanted = {
    'ohdsi:482','ohdsi:794','ohdsi:299','ohdsi:417','ohdsi:77','ohdsi:888',
    'ohdsi:979','ohdsi:1303','ohdsi:938','ohdsi:577','ohdsi:1347',
    'cipher:16285','cipher:4032','cipher:3962','cipher:16273','cipher:16291'
}
path = Path('data/phenotype_index/catalog.jsonl')
rows = {}
for line in path.read_text().splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    pid = row.get('phenotype_id')
    if pid in wanted:
        rows[pid] = {
            'phenotype_id': pid,
            'name': row.get('name'),
            'recommendation_metadata_source': row.get('recommendation_metadata_source'),
            'primary_clinical_topic': row.get('primary_clinical_topic'),
            'phenotype_role': row.get('phenotype_role'),
            'care_setting_scope': row.get('care_setting_scope'),
            'population_scope': row.get('population_scope'),
            'target_vs_context_conditions': row.get('target_vs_context_conditions'),
            'exclude_from_primary_topic_match': row.get('exclude_from_primary_topic_match'),
            'recommendation_summary': row.get('recommendation_summary'),
        }
print(json.dumps(rows, indent=2, sort_keys=True))
PY"
```


**Operational Notes**
1. For large builds, a practical workflow is:
- build catalog plus sparse index first
- optionally enable LLM-derived keywords
- add dense indexing in a separate `--dense-only` pass

2. The builder is safe to rerun, but the main build rewrites `catalog.jsonl`, `sparse_index.pkl`, and `meta.json`.

3. Dense-only mode is intended specifically to avoid rerunning the main sparse build when only `dense.index` is missing.
