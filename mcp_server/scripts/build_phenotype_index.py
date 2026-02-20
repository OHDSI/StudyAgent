#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import pickle
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from study_agent_mcp.retrieval.index import EmbeddingClient, _hash_text, _tokenize

_SPLIT_RE = re.compile(r"[;,|\\s]+")


def _parse_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_int_list(value: Any) -> List[int]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [_parse_int(v) for v in value if _parse_int(v) is not None]
    tokens = re.findall(r"\\d+", str(value))
    return [int(tok) for tok in tokens]


def _split_tags(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = _SPLIT_RE.split(str(value))
    return [item.strip("#").strip() for item in items if item.strip()]


def _load_metadata(csv_path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append({key.strip(): value for key, value in row.items()})
    return rows


def _load_definitions(def_dir: Optional[str]) -> Dict[int, Dict[str, Any]]:
    definitions: Dict[int, Dict[str, Any]] = {}
    if not def_dir:
        return definitions
    if not os.path.isdir(def_dir):
        return definitions
    for name in os.listdir(def_dir):
        if not name.endswith(".json"):
            continue
        path = os.path.join(def_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        cohort_id = _parse_int(data.get("cohortId") or data.get("id"))
        if cohort_id is None:
            cohort_id = _parse_int(os.path.splitext(name)[0])
        if cohort_id is None:
            continue
        definitions[cohort_id] = data
    return definitions


def _build_catalog_row(meta: Dict[str, Any], definition: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    cohort_id = _parse_int(meta.get("cohortId"))
    name = meta.get("cohortName") or meta.get("cohortNameLong") or meta.get("cohortNameFormatted") or ""
    short_description = meta.get("logicDescription") or meta.get("notes") or ""
    tags = _split_tags(meta.get("hashTag"))
    ontology_keys = _parse_int_list(meta.get("recommendedReferentConceptIds"))
    signals = []
    status = meta.get("status")
    if status:
        signals.append(f"status:{status}")
    if meta.get("isReferenceCohort"):
        signals.append("reference")
    if meta.get("hasWashoutInText"):
        signals.append("washout")
    logic_features = {
        "numberOfInclusionRules": _parse_int(meta.get("numberOfInclusionRules")) or 0,
        "numberOfConceptSets": _parse_int(meta.get("numberOfConceptSets")) or 0,
        "domainsInEntryEvents": meta.get("domainsInEntryEvents") or "",
        "hasConditionType": meta.get("hasConditionType") or "",
        "hasDrugType": meta.get("hasDrugType") or "",
        "hasObservationType": meta.get("hasObservationType") or "",
        "hasProcedureType": meta.get("hasProcedureType") or "",
    }

    pop_keywords = list(dict.fromkeys(_tokenize(" ".join([name, short_description, " ".join(tags)]))))
    if definition:
        description = definition.get("description") or definition.get("name") or ""
        if description:
            pop_keywords.extend(_tokenize(description))
            pop_keywords = list(dict.fromkeys(pop_keywords))

    source_meta = {
        "librarian": meta.get("librarian"),
        "status": meta.get("status"),
        "addedVersion": meta.get("addedVersion"),
        "createdDate": meta.get("createdDate"),
        "modifiedDate": meta.get("modifiedDate"),
        "lastModifiedBy": meta.get("lastModifiedBy"),
    }

    return {
        "cohortId": cohort_id,
        "name": name,
        "short_description": short_description,
        "tags": tags,
        "ontology_keys": ontology_keys,
        "signals": signals,
        "logic_features": logic_features,
        "pop_keywords": pop_keywords,
        "source_meta": source_meta,
    }


def _build_sparse_index(catalog: List[Dict[str, Any]], k1: float = 1.5, b: float = 0.75) -> Dict[str, Any]:
    postings: Dict[str, List[Tuple[int, int]]] = {}
    doc_lengths: List[int] = []
    for idx, row in enumerate(catalog):
        text = " ".join(
            [
                row.get("name") or "",
                row.get("short_description") or "",
                " ".join(row.get("tags") or []),
                " ".join(row.get("pop_keywords") or []),
            ]
        )
        terms = _tokenize(text)
        doc_lengths.append(len(terms))
        tf: Dict[str, int] = {}
        for term in terms:
            tf[term] = tf.get(term, 0) + 1
        for term, count in tf.items():
            postings.setdefault(term, []).append((idx, count))
    doc_count = len(catalog)
    avgdl = sum(doc_lengths) / doc_count if doc_count else 0.0
    idf = {}
    for term, plist in postings.items():
        df = len(plist)
        idf[term] = math.log((doc_count - df + 0.5) / (df + 0.5) + 1.0)
    return {
        "postings": postings,
        "idf": idf,
        "doc_lengths": doc_lengths,
        "avgdl": avgdl,
        "k1": k1,
        "b": b,
    }


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_catalog(path: str, catalog: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        for row in catalog:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _load_cache(path: str) -> Dict[str, List[float]]:
    if not os.path.exists(path):
        return {}
    with open(path, "rb") as handle:
        return pickle.load(handle)


def _save_cache(path: str, cache: Dict[str, List[float]]) -> None:
    with open(path, "wb") as handle:
        pickle.dump(cache, handle)


def _build_dense_index(
    catalog: List[Dict[str, Any]],
    output_path: str,
    embed_client: EmbeddingClient,
    cache_path: str,
    batch_size: int = 64,
    require_dense: bool = False,
) -> Dict[str, Any]:
    try:
        import numpy as np  # type: ignore
        import faiss  # type: ignore
    except ImportError as exc:
        if require_dense:
            raise RuntimeError("FAISS and numpy are required for dense indexing.") from exc
        return {"status": "skipped", "reason": "faiss_or_numpy_missing"}

    cache = _load_cache(cache_path)
    texts: List[str] = []
    for row in catalog:
        text = " ".join(
            [
                row.get("name") or "",
                row.get("short_description") or "",
                " ".join(row.get("pop_keywords") or []),
            ]
        ).strip()
        if not text:
            text = row.get("name") or f"cohort {row.get('cohortId')}"
        text_hash = _hash_text(text)
        row["text_for_embedding_hash"] = text_hash
        row["text_for_embedding"] = text
        cached = cache.get(text_hash)
        if cached is None:
            texts.append(text)

    if texts:
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            vectors = embed_client.embed_texts(batch)
            if len(vectors) != len(batch):
                raise RuntimeError("Embedding batch size mismatch.")
            for text, vec in zip(batch, vectors):
                cache[_hash_text(text)] = vec

    # Rebuild embeddings list in catalog order
    embeddings = []
    for row in catalog:
        text_hash = row.get("text_for_embedding_hash")
        vector = cache.get(text_hash)
        if vector is None:
            raise RuntimeError(f"Missing embedding for cohortId {row.get('cohortId')}")
        embeddings.append(vector)

    vectors = np.array(embeddings, dtype="float32")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    vectors = vectors / norms
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)
    faiss.write_index(index, output_path)
    _save_cache(cache_path, cache)
    return {"status": "ok", "dim": int(dim), "count": int(vectors.shape[0])}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build phenotype retrieval index.")
    parser.add_argument("--metadata-csv", required=True, help="Path to metadata CSV.")
    parser.add_argument("--definitions-dir", help="Path to cohort JSON definitions.")
    parser.add_argument("--output-dir", required=True, help="Index output directory.")
    parser.add_argument("--build-dense", action="store_true", help="Build dense FAISS index.")
    parser.add_argument("--require-dense", action="store_true", help="Fail if dense index cannot be built.")
    parser.add_argument("--batch-size", type=int, default=64, help="Embedding batch size.")
    args = parser.parse_args()

    metadata_rows = _load_metadata(args.metadata_csv)
    definitions = _load_definitions(args.definitions_dir)

    catalog: List[Dict[str, Any]] = []
    for row in metadata_rows:
        cohort_id = _parse_int(row.get("cohortId"))
        definition = definitions.get(cohort_id) if cohort_id is not None else None
        catalog.append(_build_catalog_row(row, definition))

    _ensure_dir(args.output_dir)
    definitions_out = os.path.join(args.output_dir, "definitions")
    if args.definitions_dir:
        _ensure_dir(definitions_out)
        for cohort_id, data in definitions.items():
            path = os.path.join(definitions_out, f"{cohort_id}.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=True)

    catalog_path = os.path.join(args.output_dir, "catalog.jsonl")
    _write_catalog(catalog_path, catalog)

    sparse_index = _build_sparse_index(catalog)
    with open(os.path.join(args.output_dir, "sparse_index.pkl"), "wb") as handle:
        pickle.dump(sparse_index, handle)

    dense_info = {"status": "skipped"}
    if args.build_dense:
        embed_url = os.getenv("EMBED_URL", "http://localhost:3000/ollama/api/embed")
        embed_model = os.getenv("EMBED_MODEL", "qwen3-embedding:4b")
        api_key = os.getenv("EMBED_API_KEY")
        client = EmbeddingClient(url=embed_url, model=embed_model, api_key=api_key)
        dense_info = _build_dense_index(
            catalog=catalog,
            output_path=os.path.join(args.output_dir, "dense.index"),
            embed_client=client,
            cache_path=os.path.join(args.output_dir, "embedding_cache.pkl"),
            batch_size=args.batch_size,
            require_dense=args.require_dense,
        )

    meta = {
        "built_at": dt.datetime.utcnow().isoformat() + "Z",
        "catalog_count": len(catalog),
        "dense": dense_info,
        "sparse": {
            "doc_count": len(catalog),
            "k1": sparse_index["k1"],
            "b": sparse_index["b"],
        },
        "embedding_model": os.getenv("EMBED_MODEL", "qwen3-embedding:4b"),
        "embedding_url": os.getenv("EMBED_URL", "http://localhost:3000/ollama/api/embed"),
    }
    with open(os.path.join(args.output_dir, "meta.json"), "w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=True, indent=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
