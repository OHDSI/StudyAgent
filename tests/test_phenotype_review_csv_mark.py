import csv
import importlib.util
from pathlib import Path

SCRIPT_PATH = Path("scripts/phenotype_review_csv_mark.py")
SPEC = importlib.util.spec_from_file_location("phenotype_review_csv_mark", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_marker_uses_csv_quoting_for_names_with_commas(tmp_path, monkeypatch):
    source, output = tmp_path / "input.csv", tmp_path / "output.csv"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["concept_id", "concept_name", "review_include_concept", "review_include_descendants"])
        writer.writeheader()
        writer.writerow({"concept_id": "1", "concept_name": "Drug, named", "review_include_concept": "", "review_include_descendants": ""})
    monkeypatch.setattr("sys.argv", ["marker", "--csv", str(source), "--output", str(output), "--include-all", "--include-descendants", "1"])
    assert MODULE.main() == 0
    with output.open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    assert row == {"concept_id": "1", "concept_name": "Drug, named", "review_include_concept": "x", "review_include_descendants": "x"}
