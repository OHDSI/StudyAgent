from __future__ import annotations

import hashlib
import json
import math
import os
import pickle
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _index_paths(index_dir: str) -> Dict[str, str]:
    return {
        "catalog": os.path.join(index_dir, "catalog.jsonl"),
        "sparse": os.path.join(index_dir, "sparse_index.pkl"),
        "dense": os.path.join(index_dir, "dense.index"),
        "meta": os.path.join(index_dir, "meta.json"),
        "definitions": os.path.join(index_dir, "definitions"),
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_catalog(path: str) -> List[Dict[str, Any]]:
    catalog: List[Dict[str, Any]] = []
    if not os.path.exists(path):
        return catalog
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            catalog.append(json.loads(line))
    return catalog


@dataclass
class EmbeddingClient:
    url: str
    model: str
    api_key: Optional[str] = None
    timeout: int = 30

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        payload = json.dumps({"model": self.model, "input": texts}).encode("utf-8")
        request = urllib.request.Request(self.url, data=payload, method="POST")
        request.add_header("Content-Type", "application/json")
        if self.api_key:
            request.add_header("Authorization", f"Bearer {self.api_key}")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Embedding request failed: {exc}") from exc
        data = json.loads(raw)
        if isinstance(data.get("embeddings"), list):
            return data["embeddings"]
        if isinstance(data.get("data"), list):
            return [row.get("embedding") for row in data["data"]]
        if isinstance(data.get("embedding"), list):
            return [data["embedding"]]
        raise RuntimeError("Embedding response missing embeddings payload.")


class PhenotypeIndex:
    def __init__(
        self,
        index_dir: str,
        embedding_client: Optional[EmbeddingClient] = None,
        allow_dense: bool = True,
        allow_sparse: bool = True,
    ) -> None:
        self.index_dir = index_dir
        self.embedding_client = embedding_client
        self.allow_dense = allow_dense
        self.allow_sparse = allow_sparse

        self._catalog: List[Dict[str, Any]] = []
        self._catalog_by_id: Dict[int, Dict[str, Any]] = {}
        self._sparse: Optional[Dict[str, Any]] = None
        self._dense: Optional[Any] = None
        self._meta: Dict[str, Any] = {}

    @property
    def catalog(self) -> List[Dict[str, Any]]:
        return self._catalog

    @property
    def meta(self) -> Dict[str, Any]:
        return self._meta

    def load(self) -> "PhenotypeIndex":
        paths = _index_paths(self.index_dir)
        self._catalog = _load_catalog(paths["catalog"])
        self._catalog_by_id = {}
        for row in self._catalog:
            cid = row.get("cohortId")
            if isinstance(cid, int):
                self._catalog_by_id[cid] = row
        if os.path.exists(paths["meta"]):
            with open(paths["meta"], "r", encoding="utf-8") as handle:
                self._meta = json.load(handle)
        if self.allow_sparse and os.path.exists(paths["sparse"]):
            with open(paths["sparse"], "rb") as handle:
                self._sparse = pickle.load(handle)
        if self.allow_dense and os.path.exists(paths["dense"]):
            try:
                import faiss  # type: ignore
            except ImportError:
                self._dense = None
            else:
                self._dense = faiss.read_index(paths["dense"])
        return self

    def fetch_summary(self, cohort_id: int) -> Optional[Dict[str, Any]]:
        row = self._catalog_by_id.get(cohort_id)
        if not row:
            return None
        return {
            "cohortId": row.get("cohortId"),
            "name": row.get("name"),
            "short_description": row.get("short_description"),
            "tags": row.get("tags") or [],
            "signals": row.get("signals") or [],
            "ontology_keys": row.get("ontology_keys") or [],
            "logic_features": row.get("logic_features") or {},
        }

    def search(
        self,
        query: str,
        top_k: int = 20,
        offset: int = 0,
        dense_k: int = 100,
        sparse_k: int = 100,
        dense_weight: float = 0.9,
        sparse_weight: float = 0.1,
    ) -> List[Dict[str, Any]]:
        if not query:
            return []
        dense_scores: Dict[int, float] = {}
        sparse_scores: Dict[int, float] = {}

        if self._dense is not None and self.embedding_client is not None:
            dense_scores = self._dense_search(query, dense_k)
        if self._sparse is not None:
            sparse_scores = self._sparse_search(query, sparse_k)

        merged: Dict[int, float] = {}
        for doc_id, score in dense_scores.items():
            merged[doc_id] = merged.get(doc_id, 0.0) + dense_weight * score
        for doc_id, score in sparse_scores.items():
            merged[doc_id] = merged.get(doc_id, 0.0) + sparse_weight * score

        ranked_all = sorted(merged.items(), key=lambda item: item[1], reverse=True)
        offset = max(0, int(offset or 0))
        ranked = ranked_all[offset : offset + top_k]
        results: List[Dict[str, Any]] = []
        for doc_id, score in ranked:
            if doc_id < 0 or doc_id >= len(self._catalog):
                continue
            row = self._catalog[doc_id]
            results.append(
                {
                    "cohortId": row.get("cohortId"),
                    "name": row.get("name"),
                    "short_description": row.get("short_description"),
                    "tags": row.get("tags") or [],
                    "signals": row.get("signals") or [],
                    "score": score,
                    "score_dense": dense_scores.get(doc_id),
                    "score_sparse": sparse_scores.get(doc_id),
                }
            )
        return results

    def list_similar(self, cohort_id: int, top_k: int = 10) -> List[Dict[str, Any]]:
        if self._dense is None:
            return []
        doc_id = self._find_doc_id(cohort_id)
        if doc_id is None:
            return []
        try:
            import faiss  # type: ignore
        except ImportError:
            return []
        try:
            vector = self._dense.reconstruct(doc_id)
        except Exception:
            return []
        if vector is None:
            return []
        vector = vector.reshape(1, -1)
        scores, indices = self._dense.search(vector, top_k + 1)
        results: List[Dict[str, Any]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == doc_id:
                continue
            if idx < 0 or idx >= len(self._catalog):
                continue
            row = self._catalog[idx]
            results.append(
                {
                    "cohortId": row.get("cohortId"),
                    "name": row.get("name"),
                    "short_description": row.get("short_description"),
                    "score": float(score),
                }
            )
            if len(results) >= top_k:
                break
        return results

    def _find_doc_id(self, cohort_id: int) -> Optional[int]:
        for idx, row in enumerate(self._catalog):
            if row.get("cohortId") == cohort_id:
                return idx
        return None

    def _dense_search(self, query: str, top_k: int) -> Dict[int, float]:
        if self.embedding_client is None:
            return {}
        try:
            import numpy as np  # type: ignore
        except ImportError:
            return {}
        vectors = self.embedding_client.embed_texts([query])
        if not vectors:
            return {}
        vector = np.array(vectors[0], dtype="float32").reshape(1, -1)
        norm = np.linalg.norm(vector, axis=1, keepdims=True)
        norm[norm == 0.0] = 1.0
        vector = vector / norm
        scores, indices = self._dense.search(vector, top_k)
        dense_scores: Dict[int, float] = {}
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            dense_scores[int(idx)] = float(score)
        return dense_scores

    def _sparse_search(self, query: str, top_k: int) -> Dict[int, float]:
        if self._sparse is None:
            return {}
        terms = _tokenize(query)
        if not terms:
            return {}
        postings = self._sparse["postings"]
        idf = self._sparse["idf"]
        doc_lengths = self._sparse["doc_lengths"]
        avgdl = self._sparse["avgdl"]
        if avgdl == 0:
            return {}
        k1 = self._sparse.get("k1", 1.5)
        b = self._sparse.get("b", 0.75)
        scores: Dict[int, float] = {}
        for term in terms:
            if term not in postings:
                continue
            term_idf = _safe_float(idf.get(term))
            for doc_id, tf in postings[term]:
                denom = tf + k1 * (1.0 - b + b * (doc_lengths[doc_id] / avgdl))
                score = term_idf * (tf * (k1 + 1.0)) / denom
                scores[doc_id] = scores.get(doc_id, 0.0) + score
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]
        return {doc_id: score for doc_id, score in ranked}


_DEFAULT_INDEX: Optional[PhenotypeIndex] = None


def get_default_index() -> PhenotypeIndex:
    global _DEFAULT_INDEX
    if _DEFAULT_INDEX is None:
        index_dir = os.getenv("PHENOTYPE_INDEX_DIR", "data/phenotype_index")
        embed_url = os.getenv("EMBED_URL", "http://localhost:3000/ollama/api/embed")
        embed_model = os.getenv("EMBED_MODEL", "qwen3-embedding:4b")
        api_key = os.getenv("EMBED_API_KEY")
        embedding_client = EmbeddingClient(url=embed_url, model=embed_model, api_key=api_key)
        _DEFAULT_INDEX = PhenotypeIndex(index_dir=index_dir, embedding_client=embedding_client).load()
    return _DEFAULT_INDEX
