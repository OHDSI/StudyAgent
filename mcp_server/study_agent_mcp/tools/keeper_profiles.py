from __future__ import annotations

from collections import defaultdict
import hashlib
import logging
import time
from datetime import date
from typing import Any, Dict, Iterable, List, Tuple

import sqlalchemy as sa

from ._common import with_meta
from ._omop import connect, safe_identifier


logger = logging.getLogger(__name__)


def _target_to_numeric(target: str) -> int:
    if target == "Disease of interest":
        return 1
    if target == "Alternative diagnoses":
        return 0
    if target == "Both":
        return 2
    return -1


def _numeric_to_target(value: int) -> str:
    if value == 2:
        return "Both"
    if value == 1:
        return "Disease of interest"
    if value == 0:
        return "Alternative diagnoses"
    return "Other"


def _day_diff(start: date | None, end: date | None) -> int:
    if start is None or end is None:
        return 0
    return int((end - start).days)


def _rows_to_dicts(rows: Iterable[Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for row in rows:
        items.append(dict(row._mapping))
    return items


def _query_rows(connection: sa.Connection, sql: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    return _rows_to_dicts(connection.execute(sa.text(sql), params))


def _table_name(schema: str, table: str) -> str:
    return f"{safe_identifier(schema, 'schema')}.{safe_identifier(table, 'table')}"


def _resolve_engine_name() -> str:
    import os

    return (
        os.getenv("OMOP_DB_ENGINE")
        or os.getenv("ENGINE")
        or ""
    ).strip()


def _concept_set_counts_by_lane(keeper_concept_sets: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in keeper_concept_sets:
        lane = str(item.get("conceptSetName") or "unlabeled")
        counts[lane] = counts.get(lane, 0) + 1
    return counts


def _connection_identity(connection: sa.Connection) -> Dict[str, Any]:
    """Return non-secret connection identity for cross-process diagnostics."""
    url = connection.engine.url
    identity = {
        "dialect": str(url.get_backend_name() or ""),
        "driver": str(url.get_driver_name() or ""),
        "host": str(url.host or ""),
        "port": int(url.port) if url.port is not None else None,
        "database": str(url.database or ""),
    }
    material = "|".join(str(identity[key] or "") for key in ("dialect", "driver", "host", "port", "database"))
    identity["target_hash"] = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return identity


def _cohort_rows(
    connection: sa.Connection,
    cohort_database_schema: str,
    cohort_table: str,
    cohort_definition_id: int,
    sample_size: int,
    person_ids: List[str],
) -> List[Dict[str, Any]]:
    cohort_ref = _table_name(cohort_database_schema, cohort_table)
    sql = f"""
        SELECT subject_id, cohort_start_date, cohort_end_date
        FROM {cohort_ref}
        WHERE cohort_definition_id = :cohort_definition_id
    """
    params: Dict[str, Any] = {"cohort_definition_id": int(cohort_definition_id)}
    if person_ids:
        sql += " AND CAST(subject_id AS TEXT) IN :person_ids"
        statement = sa.text(sql).bindparams(sa.bindparam("person_ids", expanding=True))
        rows = _rows_to_dicts(connection.execute(statement, params | {"person_ids": [str(pid) for pid in person_ids]}))
    else:
        rows = _query_rows(connection, sql, params)
    rows = sorted(rows, key=lambda item: (item.get("subject_id"), item.get("cohort_start_date")))
    selected = rows[: max(int(sample_size), 1)]
    output = []
    for index, row in enumerate(selected, start=1):
        output.append(
            {
                "generatedId": str(index),
                "subject_id": int(row["subject_id"]),
                "cohort_start_date": row["cohort_start_date"],
                "cohort_end_date": row.get("cohort_end_date"),
            }
        )
    return output


def _expand_concept_sets(
    connection: sa.Connection,
    cdm_database_schema: str,
    keeper_concept_sets: List[Dict[str, Any]],
    use_descendants: bool,
) -> Dict[int, Dict[str, Any]]:
    concept_rows = []
    doi_seed_ids = {int(item["conceptId"]) for item in keeper_concept_sets if item.get("conceptSetName") == "doi"}
    concept_schema = safe_identifier(cdm_database_schema, "cdm_database_schema")
    concept_lookup: Dict[int, Dict[str, Any]] = {}
    for item in keeper_concept_sets:
        concept_id = int(item["conceptId"])
        concept_lookup.setdefault(
            concept_id,
            {
                "conceptId": concept_id,
                "conceptName": item.get("conceptName", ""),
                "vocabularyId": item.get("vocabularyId", ""),
                "domainId": item.get("domainId", ""),
                "conceptClassId": item.get("conceptClassId", ""),
                "target_numeric": _target_to_numeric(item.get("target", "Other")),
                "conceptSetNames": set(),
            },
        )
        concept_lookup[concept_id]["conceptSetNames"].add(item.get("conceptSetName", ""))
        concept_lookup[concept_id]["target_numeric"] = max(
            concept_lookup[concept_id]["target_numeric"], _target_to_numeric(item.get("target", "Other"))
        )
        concept_rows.append(item)
    if not use_descendants or not concept_rows:
        return concept_lookup

    statement = sa.text(
        f"""
        SELECT
            ca.ancestor_concept_id,
            ca.descendant_concept_id,
            descendant.concept_name AS descendant_concept_name,
            descendant.vocabulary_id AS descendant_vocabulary_id,
            descendant.domain_id AS descendant_domain_id,
            descendant.concept_class_id AS descendant_concept_class_id
        FROM {concept_schema}.concept_ancestor ca
        INNER JOIN {concept_schema}.concept descendant
            ON descendant.concept_id = ca.descendant_concept_id
        WHERE ca.ancestor_concept_id IN :ancestor_ids
        """
    ).bindparams(sa.bindparam("ancestor_ids", expanding=True))
    rows = _rows_to_dicts(
        connection.execute(
            statement,
            {"ancestor_ids": sorted({int(item["conceptId"]) for item in concept_rows})},
        )
    )
    doi_descendants = {int(row["descendant_concept_id"]) for row in rows if int(row["ancestor_concept_id"]) in doi_seed_ids}
    items_by_id = {int(item["conceptId"]): item for item in concept_rows}
    for row in rows:
        ancestor_id = int(row["ancestor_concept_id"])
        descendant_id = int(row["descendant_concept_id"])
        source = items_by_id.get(ancestor_id)
        if source is None:
            continue
        concept_set_name = source.get("conceptSetName", "")
        if concept_set_name == "alternativeDiagnosis" and descendant_id in doi_descendants:
            continue
        entry = concept_lookup.setdefault(
            descendant_id,
            {
                "conceptId": descendant_id,
                "conceptName": row.get("descendant_concept_name", "") or "",
                "vocabularyId": row.get("descendant_vocabulary_id", "") or "",
                "domainId": row.get("descendant_domain_id", "") or "",
                "conceptClassId": row.get("descendant_concept_class_id", "") or "",
                "target_numeric": -1,
                "conceptSetNames": set(),
            },
        )
        entry["conceptSetNames"].add(concept_set_name)
        if descendant_id in doi_descendants:
            entry["target_numeric"] = 1
        else:
            entry["target_numeric"] = max(entry["target_numeric"], _target_to_numeric(source.get("target", "Other")))
    return concept_lookup


def _append_record(
    records: List[Dict[str, Any]],
    generated_id: str,
    category: str,
    concept_name: str,
    start_day: int = 0,
    end_day: int = 0,
    concept_id: int | None = None,
    target: str = "Other",
    extra_data: str = "",
) -> None:
    records.append(
        {
            "generatedId": generated_id,
            "startDay": int(start_day),
            "endDay": int(end_day),
            "conceptId": concept_id,
            "conceptName": concept_name,
            "category": category,
            "target": target,
            "extraData": extra_data,
        }
    )


def _extract_records(
    connection: sa.Connection,
    cdm_database_schema: str,
    cohort_rows: List[Dict[str, Any]],
    concept_lookup: Dict[int, Dict[str, Any]],
    phenotype_name: str,
    remove_pii: bool,
) -> List[Dict[str, Any]]:
    cdm = safe_identifier(cdm_database_schema, "cdm_database_schema")
    records: List[Dict[str, Any]] = []
    symptom_ids = {cid for cid, meta in concept_lookup.items() if "symptoms" in meta["conceptSetNames"]} - {
        cid for cid, meta in concept_lookup.items() if meta["conceptSetNames"] & {"doi", "complications"}
    }
    prior_post_disease_ids = {cid for cid, meta in concept_lookup.items() if meta["conceptSetNames"] & {"doi", "complications"}}
    drug_ids = {cid for cid, meta in concept_lookup.items() if "drugs" in meta["conceptSetNames"]}
    treat_proc_ids = {cid for cid, meta in concept_lookup.items() if "treatmentProcedures" in meta["conceptSetNames"]}
    alt_dx_ids = {cid for cid, meta in concept_lookup.items() if "alternativeDiagnosis" in meta["conceptSetNames"]}
    diag_proc_ids = {cid for cid, meta in concept_lookup.items() if "diagnosticProcedures" in meta["conceptSetNames"]}
    measurement_ids = {cid for cid, meta in concept_lookup.items() if "measurements" in meta["conceptSetNames"]}

    for cohort in cohort_rows:
        generated_id = cohort["generatedId"]
        person_id = cohort["subject_id"]
        cohort_start = cohort["cohort_start_date"]

        demo_rows = _query_rows(
            connection,
            f"""
            SELECT
                p.person_id,
                p.year_of_birth,
                g.concept_name AS gender_name,
                r.concept_name AS race_name,
                e.concept_name AS ethnicity_name,
                op.observation_period_start_date,
                op.observation_period_end_date
            FROM {cdm}.person p
            INNER JOIN {cdm}.concept g ON p.gender_concept_id = g.concept_id
            LEFT JOIN {cdm}.concept r ON p.race_concept_id = r.concept_id AND p.race_concept_id != 0
            LEFT JOIN {cdm}.concept e ON p.ethnicity_concept_id = e.concept_id AND p.ethnicity_concept_id != 0
            LEFT JOIN {cdm}.observation_period op
                ON op.person_id = p.person_id
               AND op.observation_period_start_date <= :cohort_start_date
               AND op.observation_period_end_date >= :cohort_start_date
            WHERE p.person_id = :person_id
            LIMIT 1
            """,
            {"person_id": person_id, "cohort_start_date": cohort_start},
        )
        if demo_rows:
            demo = demo_rows[0]
            age = None
            if demo.get("year_of_birth"):
                age = int(cohort_start.year) - int(demo["year_of_birth"])
            if not remove_pii:
                _append_record(records, generated_id, "personId", str(person_id))
                _append_record(records, generated_id, "cohortStartDate", cohort_start.isoformat())
            _append_record(records, generated_id, "age", str(age if age is not None else ""))
            _append_record(records, generated_id, "sex", demo.get("gender_name") or "", concept_id=None, target="Disease of interest")
            _append_record(
                records,
                generated_id,
                "observationPeriod",
                "Observation period",
                start_day=_day_diff(cohort_start, demo.get("observation_period_start_date")),
                end_day=_day_diff(cohort_start, demo.get("observation_period_end_date")),
                target="Disease of interest",
            )
            _append_record(records, generated_id, "race", demo.get("race_name") or "", target="Disease of interest")
            _append_record(records, generated_id, "ethnicity", demo.get("ethnicity_name") or "", target="Disease of interest")

        if phenotype_name:
            _append_record(records, generated_id, "phenotype", phenotype_name)

        def concept_target(concept_id: int | None) -> str:
            if concept_id is None:
                return "Other"
            meta = concept_lookup.get(int(concept_id))
            if not meta:
                return "Other"
            return _numeric_to_target(int(meta.get("target_numeric", -1)))

        presentation_rows = _query_rows(
            connection,
            f"""
            SELECT
                co.condition_concept_id AS concept_id,
                c.concept_name,
                type_c.concept_name AS type_name,
                status_c.concept_name AS status_name
            FROM {cdm}.condition_occurrence co
            INNER JOIN {cdm}.concept c ON co.condition_concept_id = c.concept_id
            LEFT JOIN {cdm}.concept type_c ON co.condition_type_concept_id = type_c.concept_id AND co.condition_type_concept_id != 0
            LEFT JOIN {cdm}.concept status_c ON co.condition_status_concept_id = status_c.concept_id AND co.condition_status_concept_id != 0
            WHERE co.person_id = :person_id
              AND co.condition_start_date = :cohort_start_date
            """,
            {"person_id": person_id, "cohort_start_date": cohort_start},
        )
        for row in presentation_rows:
            extras = [value for value in [row.get("type_name"), row.get("status_name")] if value]
            _append_record(
                records,
                generated_id,
                "presentation",
                row.get("concept_name") or "",
                concept_id=row.get("concept_id"),
                target=concept_target(row.get("concept_id")),
                extra_data=", ".join(extras),
            )

        visit_rows = _query_rows(
            connection,
            f"""
            SELECT
                vo.visit_concept_id AS concept_id,
                vc.concept_name,
                sp.concept_name AS specialty_name,
                vo.visit_start_date,
                vo.visit_end_date
            FROM {cdm}.visit_occurrence vo
            INNER JOIN {cdm}.concept vc ON vo.visit_concept_id = vc.concept_id
            LEFT JOIN {cdm}.provider p ON vo.provider_id = p.provider_id
            LEFT JOIN {cdm}.concept sp ON p.specialty_concept_id = sp.concept_id AND p.specialty_concept_id != 0
            WHERE vo.person_id = :person_id
            """,
            {"person_id": person_id},
        )
        for row in visit_rows:
            start_day = _day_diff(cohort_start, row.get("visit_start_date"))
            end_day = _day_diff(cohort_start, row.get("visit_end_date"))
            if end_day < -30 or start_day > 30:
                continue
            _append_record(
                records,
                generated_id,
                "visits",
                row.get("concept_name") or "",
                start_day=start_day,
                end_day=end_day,
                concept_id=row.get("concept_id"),
                target="Disease of interest",
                extra_data=row.get("specialty_name") or "",
            )

        def add_condition_era_records(ids: set[int], category: str, lower: int | None, upper: int | None, before_only: bool = False, after_only: bool = False, force_target: str | None = None) -> None:
            if not ids:
                return
            statement = sa.text(
                f"""
                SELECT ce.condition_concept_id AS concept_id, c.concept_name, ce.condition_era_start_date
                FROM {cdm}.condition_era ce
                INNER JOIN {cdm}.concept c ON ce.condition_concept_id = c.concept_id
                WHERE ce.person_id = :person_id
                  AND ce.condition_concept_id IN :concept_ids
                """
            ).bindparams(sa.bindparam("concept_ids", expanding=True))
            rows = _rows_to_dicts(connection.execute(statement, {"person_id": person_id, "concept_ids": sorted(ids)}))
            for row in rows:
                start_day = _day_diff(cohort_start, row.get("condition_era_start_date"))
                if before_only and start_day >= 0:
                    continue
                if after_only and start_day <= 0:
                    continue
                if lower is not None and start_day < lower:
                    continue
                if upper is not None and start_day > upper:
                    continue
                _append_record(
                    records,
                    generated_id,
                    category,
                    row.get("concept_name") or "",
                    start_day=start_day,
                    concept_id=row.get("concept_id"),
                    target=force_target or concept_target(row.get("concept_id")),
                )

        add_condition_era_records(symptom_ids, "symptoms", -30, -1)
        add_condition_era_records(prior_post_disease_ids, "priorDisease", None, None, before_only=True)
        add_condition_era_records(prior_post_disease_ids, "postDisease", None, None, after_only=True)
        add_condition_era_records(alt_dx_ids, "alternativeDiagnoses", -90, 90, force_target="Alternative diagnoses")

        observation_ids = symptom_ids
        if observation_ids:
            statement = sa.text(
                f"""
                SELECT o.observation_concept_id AS concept_id, c.concept_name, o.observation_date
                FROM {cdm}.observation o
                INNER JOIN {cdm}.concept c ON o.observation_concept_id = c.concept_id
                WHERE o.person_id = :person_id
                  AND o.observation_concept_id IN :concept_ids
                """
            ).bindparams(sa.bindparam("concept_ids", expanding=True))
            rows = _rows_to_dicts(connection.execute(statement, {"person_id": person_id, "concept_ids": sorted(observation_ids)}))
            for row in rows:
                start_day = _day_diff(cohort_start, row.get("observation_date"))
                if start_day >= 0 or start_day < -30:
                    continue
                _append_record(
                    records,
                    generated_id,
                    "symptoms",
                    row.get("concept_name") or "",
                    start_day=start_day,
                    concept_id=row.get("concept_id"),
                    target=concept_target(row.get("concept_id")),
                )

        def add_drug_records(ids: set[int], category: str, before_only: bool = False, after_only: bool = False) -> None:
            if not ids:
                return
            statement = sa.text(
                f"""
                SELECT de.drug_concept_id AS concept_id, c.concept_name, de.drug_era_start_date, de.drug_era_end_date
                FROM {cdm}.drug_era de
                INNER JOIN {cdm}.concept c ON de.drug_concept_id = c.concept_id
                WHERE de.person_id = :person_id
                  AND de.drug_concept_id IN :concept_ids
                """
            ).bindparams(sa.bindparam("concept_ids", expanding=True))
            rows = _rows_to_dicts(connection.execute(statement, {"person_id": person_id, "concept_ids": sorted(ids)}))
            for row in rows:
                start_day = _day_diff(cohort_start, row.get("drug_era_start_date"))
                end_day = _day_diff(cohort_start, row.get("drug_era_end_date"))
                if before_only and start_day >= 0:
                    continue
                if after_only and start_day < 0:
                    continue
                _append_record(
                    records,
                    generated_id,
                    category,
                    row.get("concept_name") or "",
                    start_day=start_day,
                    end_day=end_day,
                    concept_id=row.get("concept_id"),
                    target=concept_target(row.get("concept_id")),
                )

        add_drug_records(drug_ids, "priorDrugs", before_only=True)
        add_drug_records(drug_ids, "postDrugs", after_only=True)

        def add_procedure_records(ids: set[int], category: str, lower: int | None, upper: int | None, before_only: bool = False, after_only: bool = False) -> None:
            if not ids:
                return
            statement = sa.text(
                f"""
                SELECT po.procedure_concept_id AS concept_id, c.concept_name, po.procedure_date
                FROM {cdm}.procedure_occurrence po
                INNER JOIN {cdm}.concept c ON po.procedure_concept_id = c.concept_id
                WHERE po.person_id = :person_id
                  AND po.procedure_concept_id IN :concept_ids
                """
            ).bindparams(sa.bindparam("concept_ids", expanding=True))
            rows = _rows_to_dicts(connection.execute(statement, {"person_id": person_id, "concept_ids": sorted(ids)}))
            for row in rows:
                start_day = _day_diff(cohort_start, row.get("procedure_date"))
                if before_only and start_day >= 0:
                    continue
                if after_only and start_day < 0:
                    continue
                if lower is not None and start_day < lower:
                    continue
                if upper is not None and start_day > upper:
                    continue
                _append_record(
                    records,
                    generated_id,
                    category,
                    row.get("concept_name") or "",
                    start_day=start_day,
                    concept_id=row.get("concept_id"),
                    target=concept_target(row.get("concept_id")),
                )

        add_procedure_records(treat_proc_ids, "priorTreatmentProcedures", None, None, before_only=True)
        add_procedure_records(treat_proc_ids, "postTreatmentProcedures", None, None, after_only=True)
        add_procedure_records(diag_proc_ids, "diagnosticProcedures", -30, 30)

        if measurement_ids:
            statement = sa.text(
                f"""
                SELECT
                    m.measurement_concept_id AS concept_id,
                    c.concept_name,
                    m.measurement_date,
                    m.value_as_number,
                    m.value_as_concept_id,
                    value_c.concept_name AS value_concept_name,
                    operator_c.concept_name AS operator_name,
                    unit_c.concept_name AS unit_name,
                    m.range_low,
                    m.range_high
                FROM {cdm}.measurement m
                INNER JOIN {cdm}.concept c ON m.measurement_concept_id = c.concept_id
                LEFT JOIN {cdm}.concept value_c ON m.value_as_concept_id = value_c.concept_id
                LEFT JOIN {cdm}.concept operator_c ON m.operator_concept_id = operator_c.concept_id
                LEFT JOIN {cdm}.concept unit_c ON m.unit_concept_id = unit_c.concept_id
                WHERE m.person_id = :person_id
                  AND m.measurement_concept_id IN :concept_ids
                """
            ).bindparams(sa.bindparam("concept_ids", expanding=True))
            rows = _rows_to_dicts(connection.execute(statement, {"person_id": person_id, "concept_ids": sorted(measurement_ids)}))
            for row in rows:
                start_day = _day_diff(cohort_start, row.get("measurement_date"))
                if start_day < -30 or start_day > 30:
                    continue
                extra = ""
                if row.get("value_concept_name"):
                    extra = row["value_concept_name"]
                elif row.get("value_as_number") is not None:
                    abnormal = ""
                    if row.get("range_high") is not None and row["value_as_number"] > row["range_high"]:
                        abnormal = ", abnormal - high"
                    elif row.get("range_low") is not None and row["value_as_number"] < row["range_low"]:
                        abnormal = ", abnormal - low"
                    elif row.get("range_low") is not None and row.get("range_high") is not None:
                        abnormal = ", normal"
                    extra = f"{row.get('operator_name') or ''}{row['value_as_number']}{(' ' + row['unit_name']) if row.get('unit_name') else ''}{abnormal}"
                _append_record(
                    records,
                    generated_id,
                    "measurements",
                    row.get("concept_name") or "",
                    start_day=start_day,
                    concept_id=row.get("concept_id"),
                    target=concept_target(row.get("concept_id")),
                    extra_data=extra,
                )

        death_rows = _query_rows(
            connection,
            f"""
            SELECT d.death_date, d.cause_concept_id AS concept_id, c.concept_name
            FROM {cdm}.death d
            LEFT JOIN {cdm}.concept c ON d.cause_concept_id = c.concept_id
            WHERE d.person_id = :person_id
            """,
            {"person_id": person_id},
        )
        for row in death_rows:
            start_day = _day_diff(cohort_start, row.get("death_date"))
            if start_day <= 0:
                continue
            concept_name = f"Death due to {row['concept_name']}" if row.get("concept_name") else "Death"
            _append_record(records, generated_id, "death", concept_name, start_day=start_day, concept_id=row.get("concept_id"), target="Disease of interest")

    cohort_ref = _table_name(cdm_database_schema, "person")
    person_count_rows = _query_rows(connection, f"SELECT COUNT(*) AS person_count FROM {cohort_ref}", {})
    total_persons = int(person_count_rows[0]["person_count"]) if person_count_rows else 0
    prevalence = 0.0
    if total_persons > 0 and cohort_rows:
        prevalence = len({row["subject_id"] for row in cohort_rows}) / float(total_persons)
    for generated_id in {row["generatedId"] for row in cohort_rows}:
        _append_record(records, generated_id, "cohortPrevalence", f"{prevalence:.5f}")
    return records


def _generate_label(keeper_table: str, items: List[Dict[str, Any]]) -> str:
    items = sorted(items, key=lambda row: (int(row.get("startDay", 0)), int(row.get("endDay", 0))))
    concept_name = items[0].get("conceptName", "") or ""
    if keeper_table == "presentation":
        extra = items[0].get("extraData", "") or ""
        return f"{concept_name} ({extra})" if extra else concept_name
    if keeper_table == "visits":
        extra = items[0].get("extraData", "") or ""
        day_part = ", ".join(
            f"day {row['startDay']}" if int(row.get("startDay", 0)) == int(row.get("endDay", 0)) else f"days {row['startDay']} to {row['endDay']}"
            for row in items
        )
        base = concept_name + (f" - {extra}" if extra else "")
        return f"{base} ({day_part})"
    if keeper_table in {"priorDrugs", "postDrugs"}:
        spans = []
        for row in items:
            start_day = int(row.get("startDay", 0))
            end_day = int(row.get("endDay", start_day))
            duration = end_day - start_day + 1
            spans.append(f"day {start_day} for {duration} day{'' if duration == 1 else 's'}")
        return f"{concept_name} ({', '.join(spans)})"
    if keeper_table == "measurements":
        spans = []
        for row in items:
            extra = row.get("extraData", "") or ""
            start_day = int(row.get("startDay", 0))
            spans.append(f"{start_day} with value {extra}" if extra else str(start_day))
        return f"{concept_name} (day {', '.join(spans)})"
    return f"{concept_name} (day {', '.join(str(int(row.get('startDay', 0))) for row in items)})"


def _profile_rows_from_records(profile_records: List[Dict[str, Any]], remove_pii: bool) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in profile_records:
        grouped[str(row.get("generatedId") or "")].append(row)

    outputs: List[Dict[str, Any]] = []
    keeper_tables = [
        "presentation",
        "visits",
        "symptoms",
        "priorDisease",
        "postDisease",
        "priorDrugs",
        "postDrugs",
        "priorTreatmentProcedures",
        "postTreatmentProcedures",
        "alternativeDiagnoses",
        "diagnosticProcedures",
        "measurements",
        "death",
    ]
    for generated_id, rows in grouped.items():
        row_out: Dict[str, Any] = {
            "generatedId": generated_id,
            "phenotype": "",
            "age": "",
            "sex": "",
            "gender": "",
            "observationPeriod": "",
            "race": "",
            "ethnicity": "",
            "presentation": "",
            "visits": "",
            "visitContext": "",
            "symptoms": "",
            "priorDisease": "",
            "postDisease": "",
            "afterDisease": "",
            "priorDrugs": "",
            "postDrugs": "",
            "afterDrugs": "",
            "priorTreatmentProcedures": "",
            "postTreatmentProcedures": "",
            "afterTreatmentProcedures": "",
            "alternativeDiagnoses": "",
            "alternativeDiagnosis": "",
            "diagnosticProcedures": "",
            "measurements": "",
            "death": "",
            "cohortPrevalence": None,
        }
        by_category: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for item in rows:
            by_category[str(item.get("category") or "")].append(item)
        if by_category.get("phenotype"):
            row_out["phenotype"] = by_category["phenotype"][0].get("conceptName", "") or ""
        if by_category.get("age"):
            row_out["age"] = by_category["age"][0].get("conceptName", "") or ""
        if by_category.get("sex"):
            row_out["sex"] = by_category["sex"][0].get("conceptName", "") or ""
            row_out["gender"] = row_out["sex"]
        if by_category.get("observationPeriod"):
            op = by_category["observationPeriod"][0]
            row_out["observationPeriod"] = f"{op.get('startDay', 0)} days - {op.get('endDay', 0)} days"
        if by_category.get("race"):
            row_out["race"] = by_category["race"][0].get("conceptName", "") or ""
        if by_category.get("ethnicity"):
            row_out["ethnicity"] = by_category["ethnicity"][0].get("conceptName", "") or ""
        if by_category.get("cohortPrevalence"):
            try:
                row_out["cohortPrevalence"] = float(by_category["cohortPrevalence"][0].get("conceptName"))
            except (TypeError, ValueError):
                row_out["cohortPrevalence"] = None

        for keeper_table in keeper_tables:
            items = by_category.get(keeper_table) or []
            if not items:
                continue
            sortable = []
            for item in items:
                target = item.get("target")
                sort_order = 2 if target == "Disease of interest" else 1 if target == "Both" else 0 if target == "Alternative diagnoses" else -1
                extra_group = item.get("extraData", "") if keeper_table in {"presentation", "visits"} else ""
                sortable.append((item.get("conceptName", ""), sort_order, extra_group, item))
            grouped_items: Dict[Tuple[str, int, str], List[Dict[str, Any]]] = defaultdict(list)
            for concept_name, sort_order, extra_group, item in sortable:
                grouped_items[(concept_name, sort_order, extra_group)].append(item)
            labels = []
            for (concept_name, sort_order, extra_group), merged_items in grouped_items.items():
                labels.append((sort_order, _generate_label(keeper_table, merged_items)))
            labels.sort(key=lambda item: (-item[0], item[1]))
            text = "; ".join(label for _, label in labels)
            row_out[keeper_table] = text
        row_out["visitContext"] = row_out["visits"]
        row_out["alternativeDiagnosis"] = row_out["alternativeDiagnoses"]
        row_out["afterDisease"] = row_out["postDisease"]
        row_out["afterDrugs"] = row_out["postDrugs"]
        row_out["afterTreatmentProcedures"] = row_out["postTreatmentProcedures"]
        if not remove_pii:
            if by_category.get("personId"):
                row_out["personId"] = by_category["personId"][0].get("conceptName", "") or ""
            if by_category.get("cohortStartDate"):
                row_out["cohortStartDate"] = by_category["cohortStartDate"][0].get("conceptName", "") or ""
        outputs.append(row_out)
    outputs.sort(key=lambda row: str(row.get("generatedId", "")))
    return outputs


def register(mcp: object) -> None:
    @mcp.tool(name="keeper_profile_extract")
    def keeper_profile_extract_tool(
        cdm_database_schema: str,
        cohort_database_schema: str,
        cohort_table: str,
        cohort_definition_id: int,
        keeper_concept_sets: List[Dict[str, Any]],
        sample_size: int = 20,
        person_ids: List[str] = [],
        phenotype_name: str = "",
        use_descendants: bool = True,
        remove_pii: bool = True,
    ) -> Dict[str, Any]:
        engine_name = _resolve_engine_name()
        if not engine_name:
            return with_meta({"error": "omop_db_engine_unconfigured"}, "keeper_profile_extract")
        started = time.perf_counter()
        stage = "connect"
        lane_counts = _concept_set_counts_by_lane(keeper_concept_sets)
        logger.info(
            "keeper_profile_extract start cohort=%s.%s id=%s sample_size=%s concept_items=%s lanes=%s descendants=%s",
            cohort_database_schema,
            cohort_table,
            cohort_definition_id,
            sample_size,
            len(keeper_concept_sets),
            lane_counts,
            use_descendants,
        )
        try:
            with connect(engine_name) as connection:
                connection_identity = _connection_identity(connection)
                stage = "cohort_sampling"
                cohort_rows = _cohort_rows(
                    connection=connection,
                    cohort_database_schema=cohort_database_schema,
                    cohort_table=cohort_table,
                    cohort_definition_id=cohort_definition_id,
                    sample_size=sample_size,
                    person_ids=person_ids,
                )
                logger.info(
                    "keeper_profile_extract sampled target_hash=%s rows=%s seconds=%.2f",
                    connection_identity["target_hash"],
                    len(cohort_rows),
                    time.perf_counter() - started,
                )
                stage = "concept_expansion"
                concept_lookup = _expand_concept_sets(
                    connection=connection,
                    cdm_database_schema=cdm_database_schema,
                    keeper_concept_sets=keeper_concept_sets,
                    use_descendants=use_descendants,
                )
                logger.info(
                    "keeper_profile_extract expanded target_hash=%s concepts=%s seconds=%.2f",
                    connection_identity["target_hash"],
                    len(concept_lookup),
                    time.perf_counter() - started,
                )
                stage = "record_extraction"
                records = _extract_records(
                    connection=connection,
                    cdm_database_schema=cdm_database_schema,
                    cohort_rows=cohort_rows,
                    concept_lookup=concept_lookup,
                    phenotype_name=phenotype_name,
                    remove_pii=remove_pii,
                )
        except Exception:
            logger.exception(
                "keeper_profile_extract failed stage=%s cohort=%s.%s id=%s concept_items=%s lanes=%s seconds=%.2f",
                stage,
                cohort_database_schema,
                cohort_table,
                cohort_definition_id,
                len(keeper_concept_sets),
                lane_counts,
                time.perf_counter() - started,
            )
            raise
        elapsed = time.perf_counter() - started
        logger.info(
            "keeper_profile_extract complete target_hash=%s cohort=%s.%s id=%s sampled=%s records=%s seconds=%.2f",
            connection_identity["target_hash"],
            cohort_database_schema,
            cohort_table,
            cohort_definition_id,
            len(cohort_rows),
            len(records),
            elapsed,
        )
        return with_meta(
            {
                "profile_records": records,
                "record_count": len(records),
                "sample_size_requested": int(sample_size),
                "sample_size_returned": len(cohort_rows),
                "sampling_mode": "ordered_head",
                "connection_identity": connection_identity,
                "cohort_source": {
                    "schema": cohort_database_schema,
                    "table": cohort_table,
                    "cohort_definition_id": int(cohort_definition_id),
                },
                "input_concept_set_count": len(keeper_concept_sets),
                "input_concept_set_counts_by_lane": lane_counts,
                "elapsed_seconds": elapsed,
            },
            "keeper_profile_extract",
        )

    @mcp.tool(name="keeper_profile_to_rows")
    def keeper_profile_to_rows_tool(profile_records: List[Dict[str, Any]], remove_pii: bool = True) -> Dict[str, Any]:
        rows = _profile_rows_from_records(profile_records or [], remove_pii=remove_pii)
        return with_meta(
            {
                "rows": rows,
                "row_count": len(rows),
            },
            "keeper_profile_to_rows",
        )

    return None
