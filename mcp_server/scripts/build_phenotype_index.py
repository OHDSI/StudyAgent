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
import shutil
from typing import Any, Dict, Iterable, List, Optional, Tuple

from study_agent_mcp.retrieval.index import EmbeddingClient, _hash_text, _tokenize

_SPLIT_RE = re.compile(r"[;,|]+")
_METHOD_FAMILY_RULES = {
    "phecode": [r"\bphecode\b", r"\bphecodes\b"],
    "map": [r"\bmap\b"],
    "mvp": [r"\bmvp\b", r"million veteran program"],
    "gw": [r"\bgw\b", r"genome[- ]wide", r"gwas"],
    "gwphewas": [r"\bgwphewas\b", r"gwphewas", r"phewas"],
}


def _parse_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_int_list(value: Any) -> List[int]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        parsed = [_parse_int(v) for v in value]
        return [v for v in parsed if v is not None]
    tokens = re.findall(r"\d+", str(value))
    return [int(tok) for tok in tokens]


def _split_tags(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        items = value
    else:
        text = str(value).replace("#", ",")
        items = _SPLIT_RE.split(text)
    cleaned: List[str] = []
    for item in items:
        text = str(item).strip().strip("#").strip()
        if text:
            cleaned.append(text)
    return list(dict.fromkeys(cleaned))


def _compact_text_parts(parts: Iterable[Any]) -> List[str]:
    cleaned: List[str] = []
    for part in parts:
        if part is None:
            continue
        text = str(part).strip()
        if text:
            cleaned.append(text)
    return cleaned


def _join_text(parts: Iterable[Any]) -> str:
    return "\n\n".join(_compact_text_parts(parts))


def _definition_filename(phenotype_id: str) -> str:
    safe = phenotype_id.replace(":", "__")
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", safe)
    return f"{safe}.json"


def _load_metadata(csv_path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append({key.strip(): value for key, value in row.items()})
    return rows


def _load_ohdsi_definitions(def_dir: Optional[str]) -> Dict[int, Dict[str, Any]]:
    definitions: Dict[int, Dict[str, Any]] = {}
    if not def_dir or not os.path.isdir(def_dir):
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


def _load_cipher_records(cipher_dir: Optional[str]) -> List[Tuple[str, Dict[str, Any]]]:
    records: List[Tuple[str, Dict[str, Any]]] = []
    if not cipher_dir or not os.path.isdir(cipher_dir):
        return records
    for name in sorted(os.listdir(cipher_dir)):
        if not name.endswith(".json"):
            continue
        if name.lower().startswith("enumtype"):
            continue
        path = os.path.join(cipher_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        records.append((path, data))
    return records


def _load_cipher_enum_map(enum_path: Optional[str]) -> Dict[int, Dict[str, Any]]:
    if not enum_path or not os.path.exists(enum_path):
        return {}
    with open(enum_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    enum_map: Dict[int, Dict[str, Any]] = {}

    def _visit(entry: Dict[str, Any], parent_id: Optional[int] = None) -> None:
        enum_id = _parse_int(entry.get("id"))
        if enum_id is None:
            return
        enum_map[enum_id] = {
            "id": enum_id,
            "fieldType": entry.get("fieldType"),
            "fieldName": entry.get("fieldName"),
            "fieldSubType": entry.get("fieldSubType"),
            "description": entry.get("description"),
            "requireOther": entry.get("requireOther"),
            "seqNo": entry.get("seqNo"),
            "vaSpecific": bool(entry.get("vaSpecific")),
            "parent_id": parent_id,
        }
        for child in entry.get("subEnums") or []:
            if isinstance(child, dict):
                _visit(child, enum_id)

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                _visit(item)
    return enum_map


def _normalize_keywords(values: Iterable[Any]) -> List[str]:
    seen = set()
    keywords: List[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        keywords.append(text)
    return keywords


def _method_family_signals(values: Iterable[str]) -> List[str]:
    haystack = "\n".join(values).lower()
    signals: List[str] = []
    for family, patterns in _METHOD_FAMILY_RULES.items():
        for pattern in patterns:
            if re.search(pattern, haystack):
                signals.append(f"method_family:{family}")
                break
    return signals


def _extract_methodology_summary(text: str) -> str:
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    if not sentences:
        return ""
    return sentences[0][:280]


def _copy_definition(output_dir: str, phenotype_id: str, data: Dict[str, Any]) -> str:
    definitions_dir = os.path.join(output_dir, "definitions")
    os.makedirs(definitions_dir, exist_ok=True)
    filename = _definition_filename(phenotype_id)
    path = os.path.join(definitions_dir, filename)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=True)
    return filename


def _copy_source_file(output_dir: str, phenotype_id: str, src_path: str) -> str:
    definitions_dir = os.path.join(output_dir, "definitions")
    os.makedirs(definitions_dir, exist_ok=True)
    filename = _definition_filename(phenotype_id)
    dst_path = os.path.join(definitions_dir, filename)
    shutil.copyfile(src_path, dst_path)
    return filename


def _build_ohdsi_row(meta: Dict[str, Any], definition: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    native_id = _parse_int(meta.get("cohortId"))
    if native_id is None:
        raise ValueError("OHDSI row missing cohortId")
    phenotype_id = f"ohdsi:{native_id}"
    name = meta.get("cohortName") or meta.get("cohortNameLong") or meta.get("cohortNameFormatted") or ""
    short_description = meta.get("logicDescription") or meta.get("notes") or ""
    long_description = _join_text([
        meta.get("logicDescription"),
        meta.get("notes"),
        (definition or {}).get("Description"),
        (definition or {}).get("description"),
    ])
    tags = _split_tags(meta.get("hashTag"))
    keywords = _normalize_keywords(tags + _tokenize(" ".join([name, short_description, long_description])))
    ontology_keys = [str(value) for value in _parse_int_list(meta.get("recommendedReferentConceptIds"))]
    logic_features = {
        "numberOfInclusionRules": _parse_int(meta.get("numberOfInclusionRules")) or 0,
        "numberOfConceptSets": _parse_int(meta.get("numberOfConceptSets")) or 0,
        "domainsInEntryEvents": meta.get("domainsInEntryEvents") or "",
        "hasConditionType": meta.get("hasConditionType") or "",
        "hasDrugType": meta.get("hasDrugType") or "",
        "hasObservationType": meta.get("hasObservationType") or "",
        "hasProcedureType": meta.get("hasProcedureType") or "",
    }
    signals = ["source:ohdsi", "execution:native_ohdsi"]
    status = (meta.get("status") or "").strip()
    if status:
        signals.append(f"status:{status}")
    if str(meta.get("isReferenceCohort") or "").strip() not in ("", "0", "FALSE", "False", "false"):
        signals.append("reference")
    if str(meta.get("hasWashoutInText") or "").strip() not in ("", "0", "FALSE", "False", "false"):
        signals.append("washout")

    provenance = {
        "created_at": meta.get("createdDate") or "",
        "modified_at": meta.get("modifiedDate") or "",
        "version": meta.get("addedVersion") or "",
        "status": status,
        "authors": [],
        "contacts": [],
        "sources": ["OHDSI Phenotype Library"],
        "publications": [],
        "maintainer": meta.get("librarian") or "",
    }
    population_features = {
        "logic_features": logic_features,
        "demographicCriteria": meta.get("demographicCriteria") or "",
        "demographicCriteriaAge": meta.get("demographicCriteriaAge") or "",
        "demographicCriteriaGender": meta.get("demographicCriteriaGender") or "",
        "restrictedByVisit": meta.get("restrictedByVisit") or "",
    }
    validation_features = {
        "validated": None,
        "validation_description": "",
        "adjudication_performed": None,
        "adjudication_method": "",
        "adjudication_level_type": "",
    }
    adaptation_notes = "Native OHDSI cohort likely requires parameter or concept-set adjustment for local study intent."
    translation_inputs = {
        "source_type": "ohdsi_cohort_definition",
        "cohort_id": native_id,
        "name": name,
        "logic_description": short_description,
        "recommended_referent_concept_ids": ontology_keys,
        "logic_features": logic_features,
        "domains_in_entry_events": meta.get("domainsInEntryEvents") or "",
    }
    retrieval_parts = [
        name,
        short_description,
        long_description,
        " ".join(tags),
        " ".join(keywords),
        " ".join(ontology_keys),
        " ".join(signals),
    ]
    retrieval_text = "\n".join(_compact_text_parts(retrieval_parts))
    return {
        "phenotype_id": phenotype_id,
        "source_dataset": "ohdsi_phenotype_library",
        "source_record_type": "cohort_definition",
        "source_native_id": native_id,
        "name": name,
        "short_description": short_description,
        "long_description": long_description,
        "tags": tags,
        "keywords": keywords,
        "signals": signals,
        "ontology_keys": ontology_keys,
        "code_systems": [],
        "concept_evidence": {
            "coded_terms": [],
            "coverage_summary": {
                "has_codes": False,
                "has_labels": False,
                "has_omop_mapping": bool(ontology_keys),
            },
        },
        "validation_features": validation_features,
        "population_features": population_features,
        "provenance": provenance,
        "executable_definition_status": "native_ohdsi",
        "executable_definition_source": "ohdsi_library",
        "execution_readiness_score": 1.0,
        "adaptation_notes": adaptation_notes,
        "translation_inputs": translation_inputs,
        "retrieval_text": retrieval_text,
        "source_meta": {
            "status": status,
            "librarian": meta.get("librarian") or "",
            "addedVersion": meta.get("addedVersion") or "",
            "createdDate": meta.get("createdDate") or "",
            "modifiedDate": meta.get("modifiedDate") or "",
            "lastModifiedBy": meta.get("lastModifiedBy") or "",
        },
        "source_payload_ref": "",
        "definition_ref": "",
    }


def _resolve_enum_label(enum_map: Dict[int, Dict[str, Any]], enum_id: Optional[int]) -> Optional[str]:
    if enum_id is None:
        return None
    item = enum_map.get(enum_id)
    if not item:
        return None
    return item.get("fieldName") or None


def _extract_cipher_code_systems(
    assoc_codes: List[Dict[str, Any]],
    enum_map: Dict[int, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[str]]:
    code_systems: List[Dict[str, Any]] = []
    coded_terms: List[Dict[str, Any]] = []
    keyword_bits: List[str] = []
    has_labels = False
    for entry in assoc_codes or []:
        code_type = _parse_int(entry.get("codeType"))
        sub_code_type = _parse_int(entry.get("subCodeType"))
        system_name = _resolve_enum_label(enum_map, code_type)
        subsystem_name = _resolve_enum_label(enum_map, sub_code_type)
        system_meta = enum_map.get(code_type or -1) or {}
        codes = []
        for code in entry.get("codes") or []:
            if not isinstance(code, dict):
                continue
            value = str(code.get("code") or "").strip()
            if value:
                codes.append(value)
        codes = list(dict.fromkeys(codes))
        description = entry.get("description")
        if description:
            has_labels = True
        if system_name:
            keyword_bits.append(system_name)
            has_labels = True
        if subsystem_name:
            keyword_bits.append(subsystem_name)
            has_labels = True
        code_systems.append(
            {
                "system_id": code_type,
                "system_name": system_name,
                "subsystem_id": sub_code_type,
                "subsystem_name": subsystem_name,
                "codes": codes,
                "description": description,
                "va_specific": bool(system_meta.get("vaSpecific")),
            }
        )
        coded_terms.append(
            {
                "system": system_name or str(code_type) if code_type is not None else "unknown",
                "codes": codes,
                "labels": [text for text in [system_name, subsystem_name, description] if text],
                "omop_candidates": [],
                "embedding_terms": [text for text in [system_name, subsystem_name, description] if text],
            }
        )
    concept_evidence = {
        "coded_terms": coded_terms,
        "coverage_summary": {
            "has_codes": any(item.get("codes") for item in coded_terms),
            "has_labels": has_labels,
            "has_omop_mapping": False,
        },
    }
    return code_systems, concept_evidence, keyword_bits


def _infer_cipher_executable_status(description: str, algorithm_desc: str, code_systems: List[Dict[str, Any]]) -> str:
    rich_text = f"{description}\n{algorithm_desc}".lower()
    if any(item.get("codes") for item in code_systems):
        return "codes_only"
    if any(keyword in rich_text for keyword in ["algorithm", "identify", "outpatient", "inpatient", "criteria"]):
        return "narrative_only"
    return "unknown"


def _build_cipher_row(path: str, data: Dict[str, Any], enum_map: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    native_id = _parse_int(data.get("id"))
    if native_id is None:
        raise ValueError(f"CIPHER record missing id: {path}")
    phenotype_id = f"cipher:{native_id}"
    algorithm = data.get("algorithm") if isinstance(data.get("algorithm"), dict) else {}
    description = data.get("description") or ""
    algorithm_desc = algorithm.get("algorithmDesc") or ""
    population_desc = algorithm.get("populationDesc") or ""
    validation_desc = algorithm.get("validationDescription") or ""
    publication_ack = algorithm.get("publicationAcknowledgement") or ""
    short_description = description or algorithm_desc
    long_description = _join_text([description, algorithm_desc, population_desc, validation_desc, publication_ack])

    tags = _normalize_keywords(
        [
            data.get("phenotypeCategory"),
            *[item.get("keyword") for item in data.get("keywords") or [] if isinstance(item, dict)],
            *[item.get("otherSource") for item in data.get("sources") or [] if isinstance(item, dict)],
        ]
    )
    code_systems, concept_evidence, code_keywords = _extract_cipher_code_systems(
        algorithm.get("assocCodes") or [],
        enum_map,
    )
    methodology_summary = _extract_methodology_summary(description or algorithm_desc)
    methodology_signals = _method_family_signals(tags + [data.get("fullName") or "", description, algorithm_desc])
    keywords = _normalize_keywords(
        tags
        + code_keywords
        + [
            data.get("fullName"),
            description,
            algorithm_desc,
            population_desc,
            *[author.get("author", {}).get("name") for author in algorithm.get("authors") or [] if isinstance(author, dict)],
        ]
    )
    signals = ["source:cipher"]
    status_id = data.get("phenotypeStatusId")
    if status_id is not None:
        signals.append(f"status:{status_id}")
    if data.get("vaDeveloped"):
        signals.append("va_developed")
    if data.get("majorRevision"):
        signals.append("major_revision")
    validated = algorithm.get("validated")
    if validated is True:
        signals.append("validated")
    elif validated is False:
        signals.append("not_validated")
    if data.get("publications"):
        signals.append("has_publication")
    if data.get("toolLinks"):
        signals.append("has_tool_link")
    if algorithm.get("contacts"):
        signals.append("has_contact")
    for code_system in code_systems:
        system_name = (code_system.get("system_name") or "").lower()
        if "icd-9" in system_name:
            signals.append("has_code_system:icd9")
        elif "icd-10" in system_name:
            signals.append("has_code_system:icd10")
        elif "snomed" in system_name:
            signals.append("has_code_system:snomed")
        elif "medication" in system_name:
            signals.append("has_code_system:medication")
    signals.extend(methodology_signals)

    executable_status = _infer_cipher_executable_status(description, algorithm_desc, code_systems)
    signals.append(f"execution:{executable_status}")
    readiness_score = {
        "codes_only": 0.45,
        "narrative_only": 0.25,
        "non_ohdsi_logic_only": 0.6,
        "unknown": 0.15,
    }.get(executable_status, 0.15)

    provenance = {
        "created_at": data.get("created") or "",
        "modified_at": data.get("lastModified") or "",
        "version": data.get("versionInfo") or "",
        "status": data.get("phenotypeStatusId"),
        "authors": [
            author.get("author", {}).get("name")
            for author in algorithm.get("authors") or []
            if isinstance(author, dict) and isinstance(author.get("author"), dict) and author.get("author", {}).get("name")
        ],
        "contacts": [
            email.get("email")
            for contact in algorithm.get("contacts") or []
            if isinstance(contact, dict)
            for email in contact.get("emails") or []
            if isinstance(email, dict) and email.get("email")
        ],
        "sources": [
            item.get("otherSource")
            for item in data.get("sources") or []
            if isinstance(item, dict) and item.get("otherSource")
        ],
        "publications": [
            {"title": pub.get("title"), "link": pub.get("link")}
            for pub in data.get("publications") or []
            if isinstance(pub, dict)
        ],
        "maintainer": "",
    }
    population_features = {
        "population_description": population_desc,
        "context_ids": [item.get("contextId") for item in algorithm.get("contextDevs") or [] if isinstance(item, dict)],
        "data_used_start": algorithm.get("dataUsedStart"),
        "data_used_end": algorithm.get("dataUsedEnd"),
    }
    validation_features = {
        "validated": validated,
        "validation_description": validation_desc,
        "adjudication_performed": algorithm.get("adjudicationPerformed"),
        "adjudication_method": algorithm.get("adjudicationMethod") or "",
        "adjudication_level_type": algorithm.get("adjudicationLevelType"),
        "validation_count": len(algorithm.get("validations") or []),
    }
    methodology_context = {
        "family_tags": [signal.split(":", 1)[1].upper() for signal in methodology_signals],
        "summary": methodology_summary,
        "translation_cautions": [
            "May require OMOP concept-set expansion rather than direct code copy.",
            "May represent an empirically derived grouping rather than a directly executable cohort algorithm.",
        ] if methodology_signals else [],
    }
    adaptation_notes = (
        "CIPHER phenotype provides code evidence and narrative but requires translation into OHDSI cohort entry, exit, and era logic."
    )
    if methodology_signals:
        adaptation_notes = (
            "Phenotype appears derived from PheCode/MAP-style methodology and may need concept expansion and validation against available OMOP domains."
        )
    translation_inputs = {
        "source_type": "cipher_disease_phenotype",
        "phenotype_id": native_id,
        "name": data.get("fullName") or "",
        "disease_summary": description,
        "algorithm_narrative": algorithm_desc,
        "population_description": population_desc,
        "validation_description": validation_desc,
        "code_systems": code_systems,
        "source_family_labels": tags,
        "publication_links": provenance["publications"],
        "tool_link_ids": [item.get("visualToolId") for item in data.get("toolLinks") or [] if isinstance(item, dict)],
        "source_provenance": provenance,
        "methodology_context": methodology_context,
    }
    retrieval_parts = [
        data.get("fullName") or "",
        short_description,
        long_description,
        " ".join(tags),
        " ".join(keywords),
        " ".join(signals),
        " ".join(code_keywords),
        " ".join(code for item in code_systems for code in (item.get("codes") or [])),
        methodology_summary,
        adaptation_notes,
    ]
    retrieval_text = "\n".join(_compact_text_parts(retrieval_parts))
    return {
        "phenotype_id": phenotype_id,
        "source_dataset": "va_cipher",
        "source_record_type": "disease_phenotype",
        "source_native_id": native_id,
        "name": data.get("fullName") or "",
        "short_description": short_description,
        "long_description": long_description,
        "tags": tags,
        "keywords": keywords,
        "signals": list(dict.fromkeys(signals)),
        "ontology_keys": [str(item.get("relatedDiseaseId")) for item in algorithm.get("relatedDiseases") or [] if isinstance(item, dict) and item.get("relatedDiseaseId") is not None],
        "code_systems": code_systems,
        "concept_evidence": concept_evidence,
        "validation_features": validation_features,
        "population_features": population_features,
        "provenance": provenance,
        "executable_definition_status": executable_status,
        "executable_definition_source": "cipher_json",
        "execution_readiness_score": readiness_score,
        "adaptation_notes": adaptation_notes,
        "translation_inputs": translation_inputs,
        "retrieval_text": retrieval_text,
        "source_meta": {
            "uqid": data.get("uqid"),
            "phenotypeStatusId": data.get("phenotypeStatusId"),
            "categoryTypeId": data.get("categoryTypeId"),
            "dbType": data.get("dbType"),
            "vaDeveloped": data.get("vaDeveloped"),
            "revision": data.get("revision"),
            "majorRevision": data.get("majorRevision"),
        },
        "source_payload_ref": path,
        "definition_ref": "",
    }


def _build_sparse_index(catalog: List[Dict[str, Any]], k1: float = 1.5, b: float = 0.75) -> Dict[str, Any]:
    postings: Dict[str, List[Tuple[int, int]]] = {}
    doc_lengths: List[int] = []
    for idx, row in enumerate(catalog):
        text = row.get("retrieval_text") or row.get("name") or ""
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
        text = (row.get("retrieval_text") or row.get("name") or f"phenotype {row.get('phenotype_id')}").strip()
        text_hash = _hash_text(text)
        row["text_for_embedding_hash"] = text_hash
        row["text_for_embedding"] = text
        if cache.get(text_hash) is None:
            texts.append(text)

    if texts:
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            vectors = embed_client.embed_texts(batch)
            if len(vectors) != len(batch):
                raise RuntimeError("Embedding batch size mismatch.")
            for text, vec in zip(batch, vectors):
                cache[_hash_text(text)] = vec

    embeddings = []
    for row in catalog:
        text_hash = row.get("text_for_embedding_hash")
        vector = cache.get(text_hash)
        if vector is None:
            raise RuntimeError(f"Missing embedding for phenotype_id {row.get('phenotype_id')}")
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
    parser.add_argument("--metadata-csv", help="Path to OHDSI metadata CSV.")
    parser.add_argument("--definitions-dir", help="Path to OHDSI cohort JSON definitions.")
    parser.add_argument("--cipher-dir", help="Path to CIPHER phenotype JSON definitions.")
    parser.add_argument("--cipher-enum", help="Path to CIPHER enum JSON for code-system labels.")
    parser.add_argument("--output-dir", required=True, help="Index output directory.")
    parser.add_argument("--build-dense", action="store_true", help="Build dense FAISS index.")
    parser.add_argument("--require-dense", action="store_true", help="Fail if dense index cannot be built.")
    parser.add_argument("--batch-size", type=int, default=64, help="Embedding batch size.")
    args = parser.parse_args()

    if not args.metadata_csv and not args.cipher_dir:
        raise SystemExit("At least one input source is required: --metadata-csv or --cipher-dir")

    definitions = _load_ohdsi_definitions(args.definitions_dir)
    enum_map = _load_cipher_enum_map(args.cipher_enum)

    _ensure_dir(args.output_dir)
    catalog: List[Dict[str, Any]] = []
    source_counts: Dict[str, int] = {}

    if args.metadata_csv:
        metadata_rows = _load_metadata(args.metadata_csv)
        for row in metadata_rows:
            cohort_id = _parse_int(row.get("cohortId"))
            definition = definitions.get(cohort_id) if cohort_id is not None else None
            built = _build_ohdsi_row(row, definition)
            if definition is not None:
                built["definition_ref"] = _copy_definition(args.output_dir, built["phenotype_id"], definition)
            source_counts[built["source_dataset"]] = source_counts.get(built["source_dataset"], 0) + 1
            catalog.append(built)

    if args.cipher_dir:
        for path, record in _load_cipher_records(args.cipher_dir):
            built = _build_cipher_row(path, record, enum_map)
            built["definition_ref"] = _copy_source_file(args.output_dir, built["phenotype_id"], path)
            source_counts[built["source_dataset"]] = source_counts.get(built["source_dataset"], 0) + 1
            catalog.append(built)

    catalog.sort(key=lambda row: (row.get("source_dataset") or "", row.get("name") or "", row.get("phenotype_id") or ""))

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
        _write_catalog(catalog_path, catalog)

    meta = {
        "built_at": dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z"),
        "catalog_count": len(catalog),
        "source_counts": source_counts,
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
