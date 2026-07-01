from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request
from collections import Counter
from typing import Any, Dict, List

import sqlalchemy as sa
import yaml
from omop_alchemy import create_engine_with_dependencies

from ._common import with_meta
from study_agent_core.net import rewrite_container_host_url

_CACHE: Dict[str, Any] = {}
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
logger = logging.getLogger("study_agent.mcp.keeper_concept_sets")


def _text_fingerprint(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()[:12]


def _prompt_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "keeper_concept_sets"))


def _load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_yaml(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _render_template(template: str, values: Dict[str, Any]) -> str:
    return template.format_map({key: str(value) for key, value in values.items()})


def _normalize_concept(concept: Dict[str, Any]) -> Dict[str, Any]:
    concept_id = concept.get("conceptId", concept.get("concept_id"))
    if concept_id in (None, ""):
        return {}
    try:
        concept_id = int(concept_id)
    except (TypeError, ValueError):
        return {}
    record_count = concept.get("recordCount", concept.get("record_count"))
    if record_count in ("", None):
        record_count = None
    elif isinstance(record_count, str):
        try:
            record_count = int(record_count)
        except ValueError:
            record_count = None
    score = concept.get("score")
    if score in ("", None):
        score = None
    elif isinstance(score, str):
        try:
            score = float(score)
        except ValueError:
            score = None
    return {
        "conceptId": concept_id,
        "conceptName": str(concept.get("conceptName", concept.get("concept_name", "")) or ""),
        "vocabularyId": str(concept.get("vocabularyId", concept.get("vocabulary_id", "")) or ""),
        "domainId": str(concept.get("domainId", concept.get("domain_id", "")) or ""),
        "conceptClassId": str(concept.get("conceptClassId", concept.get("concept_class_id", "")) or ""),
        "standardConcept": str(concept.get("standardConcept", concept.get("standard_concept", "")) or ""),
        "recordCount": record_count,
        "score": score,
        "relationshipId": str(concept.get("relationshipId", concept.get("relationship_id", "")) or ""),
        "sourceConceptId": concept.get("sourceConceptId", concept.get("source_concept_id")),
        "sourceTerm": str(concept.get("sourceTerm", concept.get("source_term", "")) or ""),
        "sourceStage": str(concept.get("sourceStage", concept.get("source_stage", "")) or ""),
    }


def _dedupe_concepts(concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped = []
    for concept in concepts:
        normalized = _normalize_concept(concept)
        concept_id = normalized.get("conceptId")
        if not concept_id or concept_id in seen:
            continue
        seen.add(concept_id)
        deduped.append(normalized)
    return deduped


def _parse_csv_env(name: str) -> List[str]:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return []
    return [value.strip() for value in raw.split(",") if value.strip()]


def _parse_int_env(name: str) -> int:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return 0
    try:
        value = int(raw)
    except ValueError:
        logger.warning("invalid_int_env name=%s value=%s", name, raw)
        return 0
    return max(value, 0)


def _relationship_counts(concepts: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = Counter()
    for concept in concepts:
        relationship = str(concept.get("relationshipId") or "")
        counts[relationship or "<empty>"] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _apply_phoebe_expansion_controls(
    concepts: List[Dict[str, Any]],
    requested_relationship_ids: List[str] | None = None,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    deduped = _dedupe_concepts(concepts)
    requested = [value for value in (requested_relationship_ids or []) if value]
    configured = _parse_csv_env("PHOEBE_RELATIONSHIP_IDS")

    allowed_relationships: List[str] = []
    if requested:
        allowed_relationships = requested
    elif configured:
        allowed_relationships = configured

    if allowed_relationships:
        allowed = set(allowed_relationships)
        deduped = [concept for concept in deduped if str(concept.get("relationshipId") or "") in allowed]

    max_per_relationship = _parse_int_env("PHOEBE_MAX_CONCEPTS_PER_RELATIONSHIP")
    if max_per_relationship > 0:
        seen_per_relationship: Dict[str, int] = {}
        capped: List[Dict[str, Any]] = []
        for concept in deduped:
            relationship = str(concept.get("relationshipId") or "")
            current = seen_per_relationship.get(relationship, 0)
            if current >= max_per_relationship:
                continue
            seen_per_relationship[relationship] = current + 1
            capped.append(concept)
        deduped = capped

    max_total = _parse_int_env("PHOEBE_MAX_CONCEPTS")
    if max_total > 0:
        deduped = deduped[:max_total]

    controls = {
        "requested_relationship_ids": requested,
        "configured_relationship_ids": configured,
        "applied_relationship_ids": allowed_relationships,
        "max_concepts_per_relationship": max_per_relationship,
        "max_concepts": max_total,
        "relationship_counts": _relationship_counts(deduped),
    }
    return deduped, controls


def _load_bundle() -> Dict[str, Any]:
    cached = _CACHE.get("bundle")
    if cached is not None:
        return cached
    base = _prompt_dir()
    payload = {
        "task": "keeper_concept_sets_generate",
        "overview": _load_text(os.path.join(base, "overview_keeper_concept_sets.md")),
        "spec_generate_terms": _load_text(os.path.join(base, "spec_keeper_generate_terms.md")),
        "spec_filter_concepts": _load_text(os.path.join(base, "spec_keeper_filter_concepts.md")),
        "output_schema_generate_terms": _load_json(
            os.path.join(base, "output_schema_keeper_generate_terms.json")
        ),
        "output_schema_filter_concepts": _load_json(
            os.path.join(base, "output_schema_keeper_filter_concepts.json")
        ),
        "domains": _load_yaml(os.path.join(base, "domains_keeper_concept_sets.yaml")) or [],
    }
    _CACHE["bundle"] = payload
    return payload


def _domain_map() -> Dict[str, Dict[str, Any]]:
    payload = _load_bundle()
    return {
        str(entry.get("parameterName")): entry
        for entry in payload.get("domains", [])
        if isinstance(entry, dict) and entry.get("parameterName")
    }


def _provider_value(explicit: str, env_name: str) -> str:
    value = (explicit or os.getenv(env_name, "")).strip()
    return value


def _safe_identifier(value: str, label: str) -> str:
    if not value or not _IDENTIFIER_RE.match(value):
        raise RuntimeError(f"invalid_{label}")
    return value


def _resolve_vocab_engine_name() -> str:
    engine_name = (
        os.getenv("OMOP_DB_ENGINE")
        or os.getenv("ENGINE")
        or ""
    ).strip()
    if engine_name:
        return engine_name
    raise RuntimeError("omop_db_engine_unconfigured")


def _resolve_vocab_metadata_provider(explicit: str = "") -> str:
    value = (explicit or os.getenv("VOCAB_METADATA_PROVIDER", "")).strip()
    if value:
        return value
    if (
        os.getenv("OMOP_DB_ENGINE")
        or os.getenv("ENGINE")
    ):
        return "db"
    return ""


def _load_http_json(url: str, timeout: int = 30) -> Any:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def _post_http_json(
    url: str,
    payload: Dict[str, Any],
    timeout: int = 30,
    retries: int = 0,
    backoff_seconds: float = 0.0,
    log_label: str = "http_post",
) -> Any:
    body = json.dumps(payload).encode("utf-8")
    attempt = 0
    last_error: Exception | None = None
    while attempt <= max(retries, 0):
        request = urllib.request.Request(url, data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
            return json.loads(raw)
        except Exception as exc:
            last_error = exc
            if attempt >= max(retries, 0):
                raise
            logger.warning(
                "%s retrying attempt=%s retries=%s url=%s error=%s",
                log_label,
                attempt + 1,
                retries,
                url,
                exc,
            )
            if backoff_seconds > 0:
                time.sleep(backoff_seconds * (attempt + 1))
            attempt += 1
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"{log_label}_failed")


def _search_standard_via_hecate(
    query: str,
    domains: List[str] | None,
    concept_classes: List[str] | None,
    limit: int,
) -> Dict[str, Any]:
    endpoint = os.getenv("VOCAB_SEARCH_URL", "https://hecate.pantheon-hds.com/api/search_standard")
    endpoint = rewrite_container_host_url(endpoint)
    timeout = int(os.getenv("VOCAB_SEARCH_TIMEOUT", "30"))
    logger.debug(
        "vocab_search provider=hecate_api query_len=%s query_sha=%s domains=%s concept_classes=%s limit=%s timeout=%s",
        len(query or ""),
        _text_fingerprint(query),
        domains,
        concept_classes,
        limit,
        timeout,
    )
    params = {
        "q": query,
        "limit": max(int(limit), 1),
    }
    if domains:
        params["domain_id"] = ",".join(domains)
    if concept_classes:
        params["concept_class_id"] = ",".join(concept_classes)
    url = endpoint + "?" + urllib.parse.urlencode(params)
    payload = _load_http_json(url, timeout=timeout)
    concept_rows: List[Dict[str, Any]] = []
    if isinstance(payload, dict):
        concepts = payload.get("concepts") or []
        concept_rows.extend(concepts if isinstance(concepts, list) else [])
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and isinstance(item.get("concepts"), list):
                score = item.get("score")
                for concept in item.get("concepts") or []:
                    if not isinstance(concept, dict):
                        continue
                    concept_with_score = dict(concept)
                    if score is not None and concept_with_score.get("score") in (None, ""):
                        concept_with_score["score"] = score
                    concept_rows.append(concept_with_score)
            elif isinstance(item, dict):
                concept_rows.append(item)
    normalized = _dedupe_concepts(concept_rows)
    logger.debug(
        "vocab_search provider=hecate_api query_sha=%s results=%s",
        _text_fingerprint(query),
        len(normalized),
    )
    return {"concepts": normalized, "count": len(normalized), "provider": "hecate_api", "url": endpoint}


def _iter_generic_result_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("results", "items", "concepts", "matches", "rows", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _search_standard_via_generic_api(
    query: str,
    domains: List[str] | None,
    concept_classes: List[str] | None,
    limit: int,
) -> Dict[str, Any]:
    endpoint = os.getenv("VOCAB_SEARCH_URL", "http://127.0.0.1:18080/search")
    endpoint = rewrite_container_host_url(endpoint)
    timeout = int(os.getenv("VOCAB_SEARCH_TIMEOUT", "30"))
    logger.debug(
        "vocab_search provider=generic_search_api query_len=%s query_sha=%s domains=%s concept_classes=%s limit=%s timeout=%s",
        len(query or ""),
        _text_fingerprint(query),
        domains,
        concept_classes,
        limit,
        timeout,
    )
    query_prefix = os.getenv("VOCAB_SEARCH_QUERY_PREFIX", "")
    query_text = f"{query_prefix}{query}" if query_prefix else query
    request_payload: Dict[str, Any] = {
        "query_id": os.getenv("VOCAB_SEARCH_QUERY_ID", "1"),
        "query_text": query_text,
        "k": max(int(limit), 1),
    }
    if domains:
        request_payload["domains"] = domains
    if concept_classes:
        request_payload["concept_classes"] = concept_classes
    payload = _post_http_json(endpoint, request_payload, timeout=timeout)
    normalized = _dedupe_concepts(_iter_generic_result_rows(payload))
    filtered = [
        concept
        for concept in normalized
        if (not domains or not concept.get("domainId") or concept.get("domainId") in domains)
        and (not concept_classes or not concept.get("conceptClassId") or concept.get("conceptClassId") in concept_classes)
    ]
    return {
        "concepts": filtered,
        "count": len(filtered),
        "provider": "generic_search_api",
        "url": endpoint,
        "request_payload": request_payload,
    }


def _phoebe_hecate_bulk_url() -> str:
    configured = (os.getenv("PHOEBE_BULK_URL", "") or "").strip()
    if configured:
        return rewrite_container_host_url(configured)
    legacy = (os.getenv("PHOEBE_URL_TEMPLATE", "") or "").strip()
    if legacy:
        raise RuntimeError("PHOEBE_URL_TEMPLATE is no longer supported for hecate_api; set PHOEBE_BULK_URL")
    return rewrite_container_host_url("https://hecate.pantheon-hds.com/api/concepts/phoebe/bulk")


def _iter_phoebe_bulk_concepts(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("results")
    else:
        rows = []
    related: List[Dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        source_concept_id = row.get("conceptId", row.get("concept_id", row.get("id")))
        concepts = row.get("concepts")
        if concepts is None:
            concepts = row.get("results")
        if not isinstance(concepts, list):
            continue
        for concept in _dedupe_concepts(concepts):
            if concept.get("sourceConceptId") in (None, ""):
                concept["sourceConceptId"] = source_concept_id
            related.append(concept)
    return related


def _phoebe_via_hecate_bulk(
    concept_ids: List[int],
    relationship_ids: List[str] | None,
    timeout: int,
    endpoint: str,
) -> List[Dict[str, Any]]:
    relationships = set(relationship_ids or [])
    retries = _parse_int_env("PHOEBE_HTTP_RETRIES")
    backoff_ms = _parse_int_env("PHOEBE_HTTP_BACKOFF_MS")
    backoff_seconds = backoff_ms / 1000 if backoff_ms > 0 else 0.0
    related: List[Dict[str, Any]] = []
    chunk_count = (len(concept_ids) + 99) // 100 if concept_ids else 0
    for chunk_index, offset in enumerate(range(0, len(concept_ids), 100), start=1):
        chunk = concept_ids[offset : offset + 100]
        logger.debug(
            "phoebe_bulk_chunk provider=hecate_api chunk_index=%s chunk_count=%s chunk_size=%s retries=%s endpoint=%s",
            chunk_index,
            chunk_count,
            len(chunk),
            retries,
            endpoint,
        )
        payload = _post_http_json(
            endpoint,
            {"ids": chunk},
            timeout=timeout,
            retries=retries,
            backoff_seconds=backoff_seconds,
            log_label="phoebe_bulk_post",
        )
        for concept in _iter_phoebe_bulk_concepts(payload):
            if relationships and concept.get("relationshipId") not in relationships:
                continue
            related.append(concept)
    return related


def _phoebe_via_hecate(concept_ids: List[int], relationship_ids: List[str] | None) -> Dict[str, Any]:
    started = time.perf_counter()
    timeout = int(os.getenv("PHOEBE_TIMEOUT", "30"))
    endpoint = _phoebe_hecate_bulk_url()
    logger.debug(
        "phoebe provider=hecate_api concept_ids=%s relationship_ids=%s timeout=%s",
        len(concept_ids),
        relationship_ids,
        timeout,
    )
    related = _phoebe_via_hecate_bulk(concept_ids, relationship_ids, timeout, endpoint)
    raw_deduped = _dedupe_concepts(related)
    filtered, controls = _apply_phoebe_expansion_controls(raw_deduped, relationship_ids)
    logger.debug(
        "phoebe provider=hecate_api seconds=%.2f raw_results=%s final_results=%s relationships=%s applied_relationship_ids=%s max_per_relationship=%s max_total=%s",
        time.perf_counter() - started,
        len(raw_deduped),
        len(filtered),
        controls.get("relationship_counts"),
        controls.get("applied_relationship_ids"),
        controls.get("max_concepts_per_relationship"),
        controls.get("max_concepts"),
    )
    return {
        "concepts": filtered,
        "count": len(filtered),
        "provider": "hecate_api",
        "url": endpoint,
        "controls": controls,
        "raw_count": len(raw_deduped),
        "requested_concept_count": len(concept_ids),
        "bulk_chunk_count": (len(concept_ids) + 99) // 100 if concept_ids else 0,
    }


def _phoebe_via_db(concept_ids: List[int], relationship_ids: List[str] | None) -> Dict[str, Any]:
    if not concept_ids:
        return {"concepts": [], "count": 0, "provider": "db"}
    started = time.perf_counter()
    engine_name = _resolve_vocab_engine_name()
    schema = _safe_identifier(os.getenv("VOCAB_DATABASE_SCHEMA", "vocabulary"), "vocab_database_schema")
    recommend_table = _safe_identifier(os.getenv("PHOEBE_DB_TABLE", "concept_recommended"), "phoebe_db_table")
    concept_table = _safe_identifier(os.getenv("VOCAB_CONCEPT_TABLE", "concept"), "vocab_concept_table")
    engine = create_engine_with_dependencies(engine_name, future=True)
    logger.debug(
        "phoebe provider=db engine=<not shown - check config> concept_ids=%s relationship_ids=%s",
        len(concept_ids),
        relationship_ids,
    )

    relationship_clause = ""
    params: Dict[str, Any] = {"concept_ids": list(concept_ids)}
    bindparams = [sa.bindparam("concept_ids", expanding=True)]
    if relationship_ids:
        relationship_clause = " AND cr.relationship_id IN :relationship_ids"
        params["relationship_ids"] = list(relationship_ids)
        bindparams.append(sa.bindparam("relationship_ids", expanding=True))

    sql = sa.text(
        f"""
        SELECT
            cr.concept_id_1 AS source_concept_id,
            cr.concept_id_2 AS concept_id,
            cr.relationship_id AS relationship_id,
            c.concept_name AS concept_name,
            c.domain_id AS domain_id,
            c.vocabulary_id AS vocabulary_id,
            c.concept_class_id AS concept_class_id,
            c.standard_concept AS standard_concept
        FROM {schema}.{recommend_table} cr
        JOIN {schema}.{concept_table} c
          ON c.concept_id = cr.concept_id_2
        WHERE cr.concept_id_1 IN :concept_ids
        {relationship_clause}
        """
    ).bindparams(*bindparams)

    query_started = time.perf_counter()
    with engine.connect() as connection:
        rows = connection.execute(sql, params).mappings().all()
    query_seconds = time.perf_counter() - query_started

    concepts = []
    for row in rows:
        concepts.append(
            {
                "conceptId": row.get("concept_id"),
                "conceptName": row.get("concept_name", ""),
                "vocabularyId": row.get("vocabulary_id", ""),
                "domainId": row.get("domain_id", ""),
                "conceptClassId": row.get("concept_class_id", ""),
                "standardConcept": row.get("standard_concept", ""),
                "relationshipId": row.get("relationship_id", ""),
                "sourceConceptId": row.get("source_concept_id"),
            }
        )
    raw_deduped = _dedupe_concepts(concepts)
    filtered, controls = _apply_phoebe_expansion_controls(raw_deduped, relationship_ids)
    logger.debug(
        "phoebe provider=db engine=<not shown - check config> query_seconds=%.2f total_seconds=%.2f rows=%s raw_results=%s final_results=%s relationships=%s applied_relationship_ids=%s max_per_relationship=%s max_total=%s",
        query_seconds,
        time.perf_counter() - started,
        len(rows),
        len(raw_deduped),
        len(filtered),
        controls.get("relationship_counts"),
        controls.get("applied_relationship_ids"),
        controls.get("max_concepts_per_relationship"),
        controls.get("max_concepts"),
    )
    return {
        "concepts": filtered,
        "count": len(filtered),
        "provider": "db",
        "controls": controls,
        "raw_count": len(raw_deduped),
    }


def _fetch_concepts_via_db(
    concept_ids: List[int],
    domains: List[str] | None = None,
    concept_classes: List[str] | None = None,
    require_standard: bool = False,
) -> Dict[str, Any]:
    if not concept_ids:
        return {"concepts": [], "count": 0, "provider": "db"}
    started = time.perf_counter()
    engine_name = _resolve_vocab_engine_name()
    schema = _safe_identifier(os.getenv("VOCAB_DATABASE_SCHEMA", "vocabulary"), "vocab_database_schema")
    concept_table = _safe_identifier(os.getenv("VOCAB_CONCEPT_TABLE", "concept"), "vocab_concept_table")
    engine = create_engine_with_dependencies(engine_name, future=True)
    logger.debug(
        "vocab_fetch provider=db engine=<not shown - check config> concept_ids=%s domains=%s concept_classes=%s require_standard=%s",
        len(concept_ids),
        domains,
        concept_classes,
        require_standard,
    )

    conditions = ["concept_id IN :concept_ids"]
    params: Dict[str, Any] = {"concept_ids": list(concept_ids)}
    bindparams = [sa.bindparam("concept_ids", expanding=True)]
    if require_standard:
        conditions.append("standard_concept IN :standard_concepts")
        params["standard_concepts"] = ["S", "C"]
        bindparams.append(sa.bindparam("standard_concepts", expanding=True))
    if domains:
        conditions.append("domain_id IN :domain_ids")
        params["domain_ids"] = list(domains)
        bindparams.append(sa.bindparam("domain_ids", expanding=True))
    if concept_classes:
        conditions.append("concept_class_id IN :concept_classes")
        params["concept_classes"] = list(concept_classes)
        bindparams.append(sa.bindparam("concept_classes", expanding=True))

    sql = sa.text(
        f"""
        SELECT
            concept_id,
            concept_name,
            domain_id,
            vocabulary_id,
            concept_class_id,
            standard_concept
        FROM {schema}.{concept_table}
        WHERE {" AND ".join(conditions)}
        """
    ).bindparams(*bindparams)

    query_started = time.perf_counter()
    with engine.connect() as connection:
        rows = connection.execute(sql, params).mappings().all()
    query_seconds = time.perf_counter() - query_started

    concepts = []
    for row in rows:
        concepts.append(
            {
                "conceptId": row.get("concept_id"),
                "conceptName": row.get("concept_name", ""),
                "vocabularyId": row.get("vocabulary_id", ""),
                "domainId": row.get("domain_id", ""),
                "conceptClassId": row.get("concept_class_id", ""),
                "standardConcept": row.get("standard_concept", ""),
            }
        )
    deduped = _dedupe_concepts(concepts)
    logger.debug(
        "vocab_fetch provider=db engine=<not shown - check config> query_seconds=%.2f total_seconds=%.2f rows=%s results=%s missing=%s",
        query_seconds,
        time.perf_counter() - started,
        len(rows),
        len(deduped),
        max(len(concept_ids) - len(deduped), 0),
    )
    return {"concepts": deduped, "count": len(deduped), "provider": "db"}


def _merge_inline_with_db(
    inline_concepts: List[Dict[str, Any]],
    db_concepts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    inline_by_id = {}
    for concept in _dedupe_concepts(inline_concepts):
        concept_id = concept.get("conceptId")
        if concept_id is not None:
            inline_by_id[concept_id] = concept
    merged = []
    for db_concept in _dedupe_concepts(db_concepts):
        concept_id = db_concept.get("conceptId")
        combined = dict(db_concept)
        if concept_id in inline_by_id:
            inline = inline_by_id[concept_id]
            for key in ("score", "recordCount", "sourceTerm", "sourceStage", "relationshipId", "sourceConceptId"):
                value = inline.get(key)
                if value not in (None, "", []):
                    combined[key] = value
        merged.append(combined)
    return merged


def _concepts_need_db_enrichment(concepts: List[Dict[str, Any]]) -> bool:
    for concept in _dedupe_concepts(concepts):
        if not concept.get("conceptName") or not concept.get("domainId") or not concept.get("standardConcept"):
            return True
    return False


def register(mcp: object) -> None:
    @mcp.tool(name="keeper_concept_set_bundle")
    def keeper_concept_set_bundle_tool(
        phenotype: str,
        domain_key: str = "",
        target: str = "Disease of interest",
    ) -> Dict[str, Any]:
        bundle = dict(_load_bundle())
        domains = _domain_map()
        if not domain_key:
            bundle["phenotype"] = phenotype
            bundle["target"] = target
            return with_meta(bundle, "keeper_concept_set_bundle")
        domain = domains.get(domain_key)
        if domain is None:
            return with_meta({"error": f"unsupported domain_key {domain_key}"}, "keeper_concept_set_bundle")
        payload = {
            "task": bundle["task"],
            "overview": bundle["overview"],
            "phenotype": phenotype,
            "target": target,
            "domain": domain,
            "spec_generate_terms": bundle["spec_generate_terms"],
            "spec_filter_concepts": bundle["spec_filter_concepts"],
            "output_schema_generate_terms": bundle["output_schema_generate_terms"],
            "output_schema_filter_concepts": bundle["output_schema_filter_concepts"],
            "term_generation_prompt": _render_template(
                str(domain.get("systemPromptTerms", "") or ""),
                {"phenotype": phenotype, "target": target},
            ),
            "concept_filter_prompt": _render_template(
                str(domain.get("systemPromptRemoveNonRelevant", "") or ""),
                {"phenotype": phenotype, "target": target},
            ),
        }
        return with_meta(payload, "keeper_concept_set_bundle")

    @mcp.tool(name="vocab_search_standard")
    def vocab_search_standard_tool(
        query: str,
        domains: List[str] | None = None,
        concept_classes: List[str] | None = None,
        limit: int = 20,
        provider: str = "",
        results: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        concepts = _dedupe_concepts(results or [])
        if concepts:
            filtered = [
                concept
                for concept in concepts
                if (not domains or concept.get("domainId") in domains)
                and (not concept_classes or concept.get("conceptClassId") in concept_classes)
            ]
            return with_meta(
                {"concepts": filtered, "count": len(filtered), "provider": provider or "inline_results"},
                "vocab_search_standard",
            )
        selected_provider = _provider_value(provider, "VOCAB_SEARCH_PROVIDER")
        if not selected_provider:
            return with_meta(
                {"error": "vocab_search_provider_unconfigured", "concepts": [], "count": 0},
                "vocab_search_standard",
            )
        if selected_provider == "none":
            return with_meta({"concepts": [], "count": 0, "provider": selected_provider}, "vocab_search_standard")
        if selected_provider == "hecate_api":
            try:
                payload = _search_standard_via_hecate(query, domains, concept_classes, limit)
            except Exception as exc:
                return with_meta(
                    {
                        "error": "vocab_search_provider_failed",
                        "provider": selected_provider,
                        "details": str(exc),
                        "concepts": [],
                        "count": 0,
                    },
                    "vocab_search_standard",
                )
            return with_meta(payload, "vocab_search_standard")
        if selected_provider == "generic_search_api":
            try:
                payload = _search_standard_via_generic_api(query, domains, concept_classes, limit)
            except Exception as exc:
                return with_meta(
                    {
                        "error": "vocab_search_provider_failed",
                        "provider": selected_provider,
                        "details": str(exc),
                        "concepts": [],
                        "count": 0,
                    },
                    "vocab_search_standard",
                )
            return with_meta(payload, "vocab_search_standard")
        return with_meta(
            {
                "error": "vocab_search_provider_not_implemented",
                "provider": selected_provider,
                "concepts": [],
                "count": 0,
            },
            "vocab_search_standard",
        )

    @mcp.tool(name="phoebe_related_concepts")
    def phoebe_related_concepts_tool(
        concept_ids: List[int],
        relationship_ids: List[str] | None = None,
        provider: str = "",
        related_concepts: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        relationships = set(relationship_ids or [])
        concepts = _dedupe_concepts(related_concepts or [])
        if concepts:
            if relationships:
                concepts = [concept for concept in concepts if concept.get("relationshipId") in relationships]
            return with_meta(
                {"concepts": concepts, "count": len(concepts), "provider": provider or "inline_results"},
                "phoebe_related_concepts",
            )
        selected_provider = _provider_value(provider, "PHOEBE_PROVIDER")
        if not selected_provider:
            return with_meta(
                {"error": "phoebe_provider_unconfigured", "concepts": [], "count": 0},
                "phoebe_related_concepts",
            )
        if selected_provider == "none":
            return with_meta({"concepts": [], "count": 0, "provider": selected_provider}, "phoebe_related_concepts")
        if selected_provider == "hecate_api":
            try:
                payload = _phoebe_via_hecate(concept_ids, relationship_ids)
            except Exception as exc:
                return with_meta(
                    {
                        "error": "phoebe_provider_failed",
                        "provider": selected_provider,
                        "details": str(exc),
                        "concepts": [],
                        "count": 0,
                    },
                    "phoebe_related_concepts",
                )
            return with_meta(payload, "phoebe_related_concepts")
        if selected_provider == "db":
            try:
                payload = _phoebe_via_db(concept_ids, relationship_ids)
            except Exception as exc:
                return with_meta(
                    {
                        "error": "phoebe_provider_failed",
                        "provider": selected_provider,
                        "details": str(exc),
                        "concepts": [],
                        "count": 0,
                    },
                    "phoebe_related_concepts",
                )
            return with_meta(payload, "phoebe_related_concepts")
        return with_meta(
            {
                "error": "phoebe_provider_not_implemented",
                "provider": selected_provider,
                "concepts": [],
                "count": 0,
            },
            "phoebe_related_concepts",
        )

    @mcp.tool(name="vocab_filter_standard_concepts")
    def vocab_filter_standard_concepts_tool(
        concepts: List[Dict[str, Any]],
        domains: List[str] | None = None,
        concept_classes: List[str] | None = None,
        provider: str = "",
    ) -> Dict[str, Any]:
        deduped = _dedupe_concepts(concepts)
        metadata_provider = _resolve_vocab_metadata_provider(provider)
        if metadata_provider == "db" and _concepts_need_db_enrichment(deduped):
            try:
                db_payload = _fetch_concepts_via_db(
                    [concept["conceptId"] for concept in deduped if concept.get("conceptId") is not None],
                    domains=domains,
                    concept_classes=concept_classes,
                    require_standard=True,
                )
            except Exception as exc:
                return with_meta(
                    {
                        "error": "vocab_filter_standard_concepts_failed",
                        "provider": metadata_provider,
                        "details": str(exc),
                    },
                    "vocab_filter_standard_concepts",
                )
            merged = _merge_inline_with_db(deduped, db_payload.get("concepts") or [])
            return with_meta(
                {"concepts": merged, "count": len(merged), "provider": metadata_provider},
                "vocab_filter_standard_concepts",
            )

        filtered = []
        for concept in deduped:
            standard = concept.get("standardConcept")
            if standard and standard not in ("S", "C"):
                continue
            if domains and concept.get("domainId") not in domains:
                continue
            if concept_classes and concept.get("conceptClassId") not in concept_classes:
                continue
            filtered.append(concept)
        return with_meta({"concepts": filtered, "count": len(filtered)}, "vocab_filter_standard_concepts")

    @mcp.tool(name="vocab_remove_descendants")
    def vocab_remove_descendants_tool(
        concepts: List[Dict[str, Any]],
        ancestor_pairs: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        normalized = _dedupe_concepts(concepts)
        selected_ids = {concept["conceptId"] for concept in normalized}
        descendants_to_drop = set()
        for pair in ancestor_pairs or []:
            ancestor_id = pair.get("ancestor_concept_id", pair.get("ancestorConceptId"))
            descendant_id = pair.get("descendant_concept_id", pair.get("descendantConceptId"))
            if ancestor_id in selected_ids and descendant_id in selected_ids and ancestor_id != descendant_id:
                descendants_to_drop.add(descendant_id)
        kept = [concept for concept in normalized if concept["conceptId"] not in descendants_to_drop]
        return with_meta(
            {
                "concepts": kept,
                "count": len(kept),
                "removed_concept_ids": sorted(descendants_to_drop),
            },
            "vocab_remove_descendants",
        )

    @mcp.tool(name="vocab_add_nonchildren")
    def vocab_add_nonchildren_tool(
        concepts: List[Dict[str, Any]],
        new_concepts: List[Dict[str, Any]],
        ancestor_pairs: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        base = _dedupe_concepts(concepts)
        base_ids = {concept["conceptId"] for concept in base}
        descendants_to_skip = set()
        for pair in ancestor_pairs or []:
            ancestor_id = pair.get("ancestor_concept_id", pair.get("ancestorConceptId"))
            descendant_id = pair.get("descendant_concept_id", pair.get("descendantConceptId"))
            if ancestor_id in base_ids and descendant_id != ancestor_id:
                descendants_to_skip.add(descendant_id)
        merged = list(base)
        seen = set(base_ids)
        for concept in _dedupe_concepts(new_concepts):
            concept_id = concept["conceptId"]
            if concept_id in seen or concept_id in descendants_to_skip:
                continue
            seen.add(concept_id)
            merged.append(concept)
        return with_meta({"concepts": merged, "count": len(merged)}, "vocab_add_nonchildren")

    @mcp.tool(name="vocab_fetch_concepts")
    def vocab_fetch_concepts_tool(
        concept_ids: List[int],
        concepts: List[Dict[str, Any]] | None = None,
        provider: str = "",
    ) -> Dict[str, Any]:
        deduped = _dedupe_concepts(concepts or [])
        metadata_provider = _resolve_vocab_metadata_provider(provider)
        if deduped and metadata_provider == "db" and _concepts_need_db_enrichment(deduped):
            try:
                db_payload = _fetch_concepts_via_db(concept_ids, require_standard=False)
            except Exception as exc:
                return with_meta(
                    {
                        "error": "vocab_fetch_concepts_failed",
                        "provider": metadata_provider,
                        "details": str(exc),
                        "concepts": [],
                        "count": 0,
                    },
                    "vocab_fetch_concepts",
                )
            merged = _merge_inline_with_db(deduped, db_payload.get("concepts") or [])
            by_id = {concept["conceptId"]: concept for concept in merged}
            found = [by_id[concept_id] for concept_id in concept_ids if concept_id in by_id]
            missing = [concept_id for concept_id in concept_ids if concept_id not in by_id]
            return with_meta(
                {"concepts": found, "count": len(found), "missing_concept_ids": missing, "provider": metadata_provider},
                "vocab_fetch_concepts",
            )
        if deduped:
            by_id = {concept["conceptId"]: concept for concept in deduped}
            found = [by_id[concept_id] for concept_id in concept_ids if concept_id in by_id]
            missing = [concept_id for concept_id in concept_ids if concept_id not in by_id]
            return with_meta(
                {"concepts": found, "count": len(found), "missing_concept_ids": missing},
                "vocab_fetch_concepts",
            )
        if metadata_provider == "db":
            try:
                db_payload = _fetch_concepts_via_db(concept_ids, require_standard=False)
            except Exception as exc:
                return with_meta(
                    {
                        "error": "vocab_fetch_concepts_failed",
                        "provider": metadata_provider,
                        "details": str(exc),
                        "concepts": [],
                        "count": 0,
                    },
                    "vocab_fetch_concepts",
                )
            found = db_payload.get("concepts") or []
            found_ids = {concept.get("conceptId") for concept in found}
            missing = [concept_id for concept_id in concept_ids if concept_id not in found_ids]
            return with_meta(
                {"concepts": found, "count": len(found), "missing_concept_ids": missing, "provider": metadata_provider},
                "vocab_fetch_concepts",
            )
        return with_meta(
            {"error": "vocab_fetch_concepts_not_implemented", "concepts": [], "count": 0},
            "vocab_fetch_concepts",
        )

    return None
