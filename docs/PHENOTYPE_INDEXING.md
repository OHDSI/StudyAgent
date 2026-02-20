**Phenotype Indexing (MCP)**

This guide explains how to build the phenotype index used by the MCP `phenotype_search` tool.

**Inputs**
1. Metadata CSV (e.g., from the [OHDSI Phenotype Library](https://github.com/OHDSI/PhenotypeLibrary.git) `insta/Cohorts.csv`)
2. Cohort definition JSON files (e.g., from the [OHDSI Phenotype Library](https://github.com/OHDSI/PhenotypeLibrary.git) `inst/cohorts/` folder)

**Required Environment**
- `EMBED_URL` (OpenAI-compatible embedding endpoint)
- `EMBED_MODEL` (embedding model name)
- `EMBED_API_KEY` (optional if the endpoint requires auth)

**Command**
```bash
python mcp_server/scripts/build_phenotype_index.py \
  --metadata-csv /path/to/Cohorts.csv \
  --definitions-dir /path/to/cohorts \
  --output-dir /path/to/phenotype_index \
  --build-dense
```

**Outputs**
The output directory will contain:
1. `catalog.jsonl` – compact phenotype documents
2. `sparse_index.pkl` – pure‑Python BM25 index
3. `dense.index` – FAISS index (if `--build-dense` is enabled)
4. `meta.json` – index metadata (embedding model, build time, counts)
5. `definitions/` – copies of cohort JSON definitions

**Notes**
1. If FAISS/numpy are not installed, omit `--build-dense` or install them first.
2. Indexing is safe to run repeatedly; it rebuilds the directory contents.
3. Set `PHENOTYPE_INDEX_DIR` in your MCP environment to point at the output directory.
