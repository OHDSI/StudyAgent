from __future__ import annotations

import argparse
import atexit
import json
import os
import re
import shlex
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

try:
    import readline
except ImportError:  # pragma: no cover
    readline = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_base_url() -> str:
    explicit = (os.getenv("STUDY_AGENT_DEMO_ACP_URL") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    host = (os.getenv("STUDY_AGENT_HOST") or "127.0.0.1").strip() or "127.0.0.1"
    port = (os.getenv("STUDY_AGENT_PORT") or "8765").strip() or "8765"
    return f"http://{host}:{port}"


def _default_output_dir() -> Path:
    raw = (os.getenv("STUDY_AGENT_DEMO_OUTPUT_DIR") or "demo-shell-output").strip()
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _slugify(value: str, default: str = "result") -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return text or default


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _split_query_text(value: str) -> List[str]:
    return [item.strip() for item in (value or "").split(";") if item.strip()]


def _read_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_logo() -> str:
    path = _repo_root() / "ohdsi-logo-ascii.txt"
    try:
        return path.read_text(encoding="utf-8").rstrip()
    except OSError:
        return "OHDSI Study Agent Demo Shell"


class ShellArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


class HelpShown(Exception):
    pass


def _build_parser(
    prog: str,
    description: str,
    configure: Callable[[ShellArgumentParser], None],
) -> ShellArgumentParser:
    parser = ShellArgumentParser(prog=prog, description=description, add_help=False)
    parser.add_argument("-h", "--help", action="store_true", dest="_help")
    configure(parser)
    return parser


@dataclass
class ACPClient:
    base_url: str
    timeout: int = 360

    def get(self, path: str) -> Dict[str, Any]:
        request = urllib.request.Request(f"{self.base_url}{path}", method="GET")
        return self._send(request)

    def post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._send(request)

    def _send(self, request: urllib.request.Request) -> Dict[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            detail: Any = payload
            try:
                detail = json.loads(payload)
            except json.JSONDecodeError:
                pass
            raise RuntimeError(f"http_error status={exc.code} detail={detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"connection_failed detail={exc.reason}") from exc


@dataclass
class DemoSession:
    output_dir: Path
    last_intent_split: Optional[Path] = None
    last_recommendation: Optional[Path] = None
    last_vocab_search: Optional[Path] = None
    last_phoebe_related: Optional[Path] = None
    last_keeper_concepts: Optional[Path] = None
    last_keeper_review: Optional[Path] = None
    last_phenotype_name: str = ""
    current_study_intent: str = ""
    current_workflow_type: str = ""
    current_step: str = ""
    current_role: str = ""
    current_context: Dict[str, Any] = field(default_factory=dict)


def _extract_nested(payload: Dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_rows_payload(data: Any) -> Optional[List[Dict[str, Any]]]:
    if isinstance(data, dict):
        rows = data.get("rows")
        if isinstance(rows, list):
            return rows
        full_rows = _extract_nested(data, "full_result", "rows")
        if isinstance(full_rows, list):
            return full_rows
    return None


def _extract_keeper_row(data: Any, row_index: int) -> Dict[str, Any]:
    if isinstance(data, dict):
        if isinstance(data.get("keeper_row"), dict):
            return data["keeper_row"]
        rows = _extract_rows_payload(data)
        if rows is not None:
            if row_index < 0 or row_index >= len(rows):
                raise ValueError(f"row_index {row_index} out of range")
            row = rows[row_index]
            if not isinstance(row, dict):
                raise ValueError("selected row is not an object")
            return row
        if "generatedId" in data or "presentation" in data or "visitContext" in data:
            return data
    if isinstance(data, list):
        if row_index < 0 or row_index >= len(data):
            raise ValueError(f"row_index {row_index} out of range")
        row = data[row_index]
        if isinstance(row, dict):
            return row
    raise ValueError("could not locate a keeper row in the provided file")


def _infer_phenotype_name(data: Any) -> str:
    if isinstance(data, dict):
        for key in ("phenotype", "phenotype_name", "disease_name"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        full_result = data.get("full_result")
        if isinstance(full_result, dict):
            return _infer_phenotype_name(full_result)
    return ""


@dataclass
class StudyAgentDemoShell:
    client: ACPClient
    session: DemoSession
    parsers: Dict[str, ShellArgumentParser] = field(init=False)

    def __post_init__(self) -> None:
        self.session.output_dir.mkdir(parents=True, exist_ok=True)
        self.parsers = self._build_parsers()
        self._configure_line_editing()

    def run(self) -> int:
        print(_read_logo())
        print(f"ACP: {self.client.base_url}")
        print(f"Output directory: {self.session.output_dir}")
        print("Type /help for commands.")
        while True:
            try:
                line = input("study-agent> ").strip()
            except EOFError:
                print()
                return 0
            except KeyboardInterrupt:
                print()
                continue
            if not line:
                continue
            try:
                should_continue = self.handle_line(line)
            except HelpShown:
                should_continue = True
            except Exception as exc:
                print(f"error: {exc}")
                should_continue = True
            if not should_continue:
                return 0

    def handle_line(self, line: str) -> bool:
        if not line.startswith("/"):
            print("Commands must start with '/'. Use /help.")
            return True
        argv = shlex.split(line)
        command = argv[0]
        if command in ("/quit", "/exit"):
            return False
        if command == "/help":
            self._print_help()
            return True
        if command == "/services":
            self._handle_services()
            return True
        handler = {
            "/phenotype-intent-split": self._handle_intent_split,
            "/phenotype-recommend": self._handle_recommend,
            "/ohdsi": self._handle_workflow_dialogue,
            "/vocab-search-standard": self._handle_vocab_search,
            "/vocab-phoebe-related": self._handle_phoebe_related,
            "/keeper-generate-concepts": self._handle_keeper_generate_concepts,
            "/keeper-review-row": self._handle_keeper_review_row,
        }.get(command)
        if handler is None:
            print(f"Unknown command: {command}")
            print("Use /help.")
            return True
        handler(argv[1:])
        return True

    def _build_parsers(self) -> Dict[str, ShellArgumentParser]:
        return {
            "/phenotype-intent-split": _build_parser(
                "/phenotype-intent-split",
                "Split a study intent into target and outcome statements.",
                lambda parser: parser.add_argument("text", nargs=argparse.REMAINDER),
            ),
            "/phenotype-recommend": _build_parser(
                "/phenotype-recommend",
                "Recommend phenotype candidates for a study intent.",
                self._configure_recommend_parser,
            ),
            "/ohdsi": _build_parser(
                "/ohdsi",
                "Ask a contextual workflow question using the current session state.",
                lambda parser: parser.add_argument("text", nargs=argparse.REMAINDER),
            ),
            "/vocab-search-standard": _build_parser(
                "/vocab-search-standard",
                "Search standard OMOP concepts for one or more semicolon-separated terms.",
                self._configure_vocab_search_parser,
            ),
            "/vocab-phoebe-related": _build_parser(
                "/vocab-phoebe-related",
                "Fetch Phoebe-related concepts for a comma-separated list of concept IDs.",
                self._configure_phoebe_parser,
            ),
            "/keeper-generate-concepts": _build_parser(
                "/keeper-generate-concepts",
                "Generate Keeper concept sets and save them to disk.",
                self._configure_keeper_generate_parser,
            ),
            "/keeper-review-row": _build_parser(
                "/keeper-review-row",
                "Review a single sanitized Keeper row from a JSON file.",
                self._configure_keeper_review_parser,
            ),
        }

    def _configure_recommend_parser(self, parser: ShellArgumentParser) -> None:
        parser.add_argument("--top-k", type=int, default=20)
        parser.add_argument("--max-results", type=int, default=5)
        parser.add_argument("--candidate-limit", type=int, default=5)
        parser.add_argument("text", nargs=argparse.REMAINDER)

    def _configure_vocab_search_parser(self, parser: ShellArgumentParser) -> None:
        parser.add_argument("--domains", default="Condition")
        parser.add_argument("--classes", default="")
        parser.add_argument("--limit", type=int, default=5)
        parser.add_argument("--provider", default="")
        parser.add_argument("queries", nargs=argparse.REMAINDER)

    def _configure_phoebe_parser(self, parser: ShellArgumentParser) -> None:
        parser.add_argument("--relationships", default="")
        parser.add_argument("--provider", default="")
        parser.add_argument("concept_ids", nargs=argparse.REMAINDER)

    def _configure_keeper_generate_parser(self, parser: ShellArgumentParser) -> None:
        parser.add_argument("--domains", default="")
        parser.add_argument("--candidate-limit", type=int, default=10)
        parser.add_argument("--min-record-count", type=int, default=0)
        parser.add_argument("--vocab-provider", default="")
        parser.add_argument("--phoebe-provider", default="")
        parser.add_argument("--output", default="")
        parser.add_argument("phenotype", nargs=argparse.REMAINDER)

    def _configure_keeper_review_parser(self, parser: ShellArgumentParser) -> None:
        parser.add_argument("--row-index", type=int, default=0)
        parser.add_argument("--disease-name", default="")
        parser.add_argument("--concepts-file", default="")
        parser.add_argument("--output", default="")
        parser.add_argument("row_file", nargs="?")

    def _parse(self, command: str, argv: Sequence[str]) -> argparse.Namespace:
        parser = self.parsers[command]
        args = parser.parse_args(list(argv))
        if getattr(args, "_help", False):
            print(parser.format_help().strip())
            raise HelpShown()
        return args

    def _post_flow(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.client.post(path, payload)

    def _post_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return self.client.post("/tools/call", {"name": name, "arguments": arguments})

    def _save_result(self, stem: str, payload: Dict[str, Any], requested_path: str = "") -> Path:
        if requested_path:
            path = Path(requested_path)
            if not path.is_absolute():
                path = Path.cwd() / path
        else:
            path = self.session.output_dir / f"{stem}-{_timestamp()}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        return path

    def _require_ok(self, payload: Dict[str, Any]) -> None:
        if payload.get("status") == "error":
            detail = payload.get("error") or payload.get("detail") or payload
            raise RuntimeError(detail)

    def _print_help(self) -> None:
        print("Commands:")
        print("/phenotype-intent-split <study intent>")
        print("/phenotype-recommend [--top-k N] [--max-results N] [--candidate-limit N] <study intent>")
        print("/ohdsi <question about the current workflow context>")
        print("/vocab-search-standard [--domains CSV] [--classes CSV] [--limit N] [--provider NAME] <term1 ; term2>")
        print("/vocab-phoebe-related [--relationships CSV] [--provider NAME] <concept_id1,concept_id2>")
        print("/keeper-generate-concepts [--domains CSV] [--candidate-limit N] [--min-record-count N] [--vocab-provider NAME] [--phoebe-provider NAME] [--output PATH] <phenotype>")
        print("/keeper-review-row [--row-index N] [--disease-name NAME] [--concepts-file PATH] [--output PATH] <row-or-rows-json>")
        print("/services")
        print("/help")
        print("/quit")

    def _configure_line_editing(self) -> None:
        if readline is None:
            return
        history_path = self.session.output_dir / ".study-agent-demo-history"
        try:
            readline.parse_and_bind("tab: complete")
            readline.parse_and_bind("set editing-mode emacs")
        except Exception:
            pass
        try:
            if history_path.exists():
                readline.read_history_file(str(history_path))
        except Exception:
            pass

        def _save_history() -> None:
            try:
                readline.write_history_file(str(history_path))
            except Exception:
                pass

        atexit.register(_save_history)

    def _handle_services(self) -> None:
        payload = self.client.get("/services")
        services = payload.get("services") or []
        print(f"services: {len(services)}")
        for service in services:
            name = service.get("name", "")
            endpoint = service.get("endpoint", "")
            implemented = service.get("implemented")
            print(f"- {name}: {endpoint} implemented={implemented}")
        warnings = payload.get("warnings") or []
        if warnings:
            print("warnings:")
            for warning in warnings:
                print(f"- {warning}")

    def _handle_intent_split(self, argv: Sequence[str]) -> None:
        args = self._parse("/phenotype-intent-split", argv)
        study_intent = " ".join(args.text).strip()
        if not study_intent:
            raise ValueError("missing study intent")
        result = self._post_flow("/flows/phenotype_intent_split", {"study_intent": study_intent})
        self._require_ok(result)
        artifact = self._save_result("phenotype-intent-split", result)
        self.session.last_intent_split = artifact
        split = result.get("intent_split") or {}
        print(f"status: {result.get('status')}")
        print(f"target: {split.get('target_statement', '')}")
        print(f"outcome: {split.get('outcome_statement', '')}")
        rationale = split.get("rationale")
        if rationale:
            print(f"rationale: {rationale}")
        questions = split.get("questions") or []
        if questions:
            print("questions:")
            for question in questions:
                print(f"- {question}")
        self.session.current_study_intent = study_intent
        self.session.current_workflow_type = "phenotype"
        self.session.current_step = "intent_split"
        self.session.current_role = ""
        self.session.current_context = {
            "target_statement": split.get("target_statement", ""),
            "outcome_statement": split.get("outcome_statement", ""),
        }
        self._print_llm_summary(result)
        print(f"saved: {artifact}")

    def _handle_recommend(self, argv: Sequence[str]) -> None:
        args = self._parse("/phenotype-recommend", argv)
        study_intent = " ".join(args.text).strip()
        if not study_intent:
            raise ValueError("missing study intent")
        payload = {
            "study_intent": study_intent,
            "top_k": args.top_k,
            "max_results": args.max_results,
            "candidate_limit": args.candidate_limit,
        }
        result = self._post_flow("/flows/phenotype_recommendation", payload)
        self._require_ok(result)
        artifact = self._save_result("phenotype-recommend", result)
        self.session.last_recommendation = artifact
        recommendations_payload = result.get("recommendations") or {}
        recommendations = recommendations_payload.get("phenotype_recommendations") or []
        print(f"status: {result.get('status')}")
        print(f"recommendations: {len(recommendations)}")
        for idx, item in enumerate(recommendations, start=1):
            phenotype_id = item.get("phenotype_id", "")
            phenotype_name = item.get("phenotype_name") or item.get("name") or ""
            reasoning = item.get("reason") or item.get("rationale") or item.get("justification") or ""
            print(f"{idx}. phenotype_id={phenotype_id} name={phenotype_name}")
            if reasoning:
                print(f"   {reasoning}")
        self.session.current_study_intent = study_intent
        self.session.current_workflow_type = "phenotype"
        self.session.current_step = "phenotype_recommendation"
        self.session.current_role = ""
        self.session.current_context = {
            "top_k": args.top_k,
            "max_results": args.max_results,
            "candidate_limit": args.candidate_limit,
            "recommendation_count": len(recommendations),
        }
        self._print_llm_summary(result)
        print(f"saved: {artifact}")

    def _handle_workflow_dialogue(self, argv: Sequence[str]) -> None:
        args = self._parse("/ohdsi", argv)
        user_prompt = " ".join(args.text).strip()
        if not user_prompt:
            raise ValueError("missing dialogue question")
        payload = {
            "user_prompt": user_prompt,
            "study_intent": self.session.current_study_intent,
            "workflow_type": self.session.current_workflow_type,
            "current_step": self.session.current_step,
            "current_role": self.session.current_role,
            "current_context": self.session.current_context,
        }
        result = self._post_flow("/flows/workflow_context_dialogue", payload)
        self._require_ok(result)
        dialogue = result.get("dialogue") or {}
        print(f"status: {result.get('status')}")
        print(dialogue.get("answer", ""))
        for label, key in (("current step guidance", "current_step_guidance"), ("cautions", "cautions"), ("suggested next actions", "suggested_next_actions")):
            items = dialogue.get(key) or []
            if not items:
                continue
            print(f"{label}:")
            for item in items:
                print(f"- {item}")
        self._print_llm_summary(result)

    def _handle_vocab_search(self, argv: Sequence[str]) -> None:
        args = self._parse("/vocab-search-standard", argv)
        raw_query_text = " ".join(args.queries).strip()
        queries = _split_query_text(raw_query_text)
        if not queries:
            raise ValueError("provide one or more queries separated by ';'")
        domains = _split_csv(args.domains)
        concept_classes = _split_csv(args.classes)
        results = []
        for query in queries:
            payload = self._post_tool(
                "vocab_search_standard",
                {
                    "query": query,
                    "domains": domains,
                    "concept_classes": concept_classes,
                    "limit": args.limit,
                    "provider": args.provider,
                },
            )
            self._require_ok(payload)
            full = payload.get("full_result") or {}
            results.append({"query": query, "response": payload})
            print(f"query: {query}")
            print(f"provider: {full.get('provider', args.provider or '(default)')}")
            if full.get("error"):
                print(f"error: {full.get('error')}")
                continue
            concepts = full.get("concepts") or []
            for idx, concept in enumerate(concepts, start=1):
                print(
                    f"{idx}. {concept.get('conceptId')} | {concept.get('conceptName')} | "
                    f"{concept.get('domainId')} | {concept.get('vocabularyId')}"
                )
        artifact = self._save_result("vocab-search-standard", {"queries": queries, "results": results})
        self.session.last_vocab_search = artifact
        print(f"saved: {artifact}")

    def _handle_phoebe_related(self, argv: Sequence[str]) -> None:
        args = self._parse("/vocab-phoebe-related", argv)
        raw_ids = "".join(args.concept_ids).strip()
        concept_ids = []
        for value in _split_csv(raw_ids):
            try:
                concept_ids.append(int(value))
            except ValueError as exc:
                raise ValueError(f"invalid concept id: {value}") from exc
        if not concept_ids:
            raise ValueError("missing concept IDs")
        relationship_ids = _split_csv(args.relationships)
        result = self._post_tool(
            "phoebe_related_concepts",
            {
                "concept_ids": concept_ids,
                "relationship_ids": relationship_ids,
                "provider": args.provider,
            },
        )
        self._require_ok(result)
        full = result.get("full_result") or {}
        print(f"status: {result.get('status')}")
        print(f"provider: {full.get('provider', args.provider or '(default)')}")
        if full.get("error"):
            print(f"error: {full.get('error')}")
        else:
            concepts = full.get("concepts") or []
            print(f"related concepts: {len(concepts)}")
            for idx, concept in enumerate(concepts, start=1):
                print(
                    f"{idx}. source={concept.get('sourceConceptId', '')} -> "
                    f"{concept.get('conceptId')} | {concept.get('conceptName')} | "
                    f"{concept.get('relationshipId', '')}"
                )
        artifact = self._save_result("vocab-phoebe-related", result)
        self.session.last_phoebe_related = artifact
        print(f"saved: {artifact}")

    def _handle_keeper_generate_concepts(self, argv: Sequence[str]) -> None:
        args = self._parse("/keeper-generate-concepts", argv)
        phenotype = " ".join(args.phenotype).strip()
        if not phenotype:
            raise ValueError("missing phenotype")
        payload = {
            "phenotype": phenotype,
            "domain_keys": _split_csv(args.domains),
            "candidate_limit": args.candidate_limit,
            "min_record_count": args.min_record_count,
            "vocab_search_provider": args.vocab_provider,
            "phoebe_provider": args.phoebe_provider,
            "include_diagnostics": True,
        }
        result = self._post_flow("/flows/keeper_concept_sets_generate", payload)
        self._require_ok(result)
        artifact = self._save_result(
            f"keeper-concepts-{_slugify(phenotype)}",
            result,
            requested_path=args.output,
        )
        self.session.last_keeper_concepts = artifact
        self.session.last_phenotype_name = phenotype
        print(f"status: {result.get('status')}")
        print(f"phenotype: {result.get('phenotype', phenotype)}")
        concept_sets = result.get("concept_sets") or []
        domains = result.get("domains") or []
        print(f"concepts: {len(concept_sets)}")
        for domain in domains:
            concepts = domain.get("concepts") or []
            print(
                f"- domain={domain.get('domain_key')} target={domain.get('target')} "
                f"terms={len(domain.get('terms') or [])} concepts={len(concepts)}"
            )
        self._print_llm_summary(result)
        print(f"saved: {artifact}")

    def _handle_keeper_review_row(self, argv: Sequence[str]) -> None:
        args = self._parse("/keeper-review-row", argv)
        row_file = args.row_file
        if not row_file:
            raise ValueError("missing row file")
        row_path = Path(row_file)
        if not row_path.is_absolute():
            row_path = Path.cwd() / row_path
        row_data = _read_json_file(row_path)
        keeper_row = _extract_keeper_row(row_data, args.row_index)

        disease_name = (args.disease_name or "").strip()
        if not disease_name and args.concepts_file:
            concepts_path = Path(args.concepts_file)
            if not concepts_path.is_absolute():
                concepts_path = Path.cwd() / concepts_path
            disease_name = _infer_phenotype_name(_read_json_file(concepts_path))
        if not disease_name:
            disease_name = _infer_phenotype_name(row_data)
        if not disease_name:
            disease_name = self.session.last_phenotype_name
        if not disease_name:
            raise ValueError("missing disease name; provide --disease-name or --concepts-file")

        result = self._post_flow(
            "/flows/phenotype_validation_review",
            {
                "disease_name": disease_name,
                "keeper_row": keeper_row,
            },
        )
        self._require_ok(result)
        artifact = self._save_result(
            f"keeper-review-{_slugify(disease_name)}",
            result,
            requested_path=args.output,
        )
        self.session.last_keeper_review = artifact
        full = result.get("full_result") or {}
        print(f"status: {result.get('status')}")
        print(f"disease_name: {disease_name}")
        print(f"label: {full.get('label', '')}")
        rationale = full.get("rationale")
        if rationale:
            print(f"rationale: {rationale}")
        self._print_llm_summary(result)
        print(f"saved: {artifact}")

    def _print_llm_summary(self, result: Dict[str, Any]) -> None:
        llm_used = result.get("llm_used")
        llm_status = result.get("llm_status")
        diagnostics = result.get("diagnostics") or {}
        if llm_used is not None:
            print(f"llm_used: {llm_used}")
        if llm_status:
            print(f"llm_status: {llm_status}")
        fallback_reason = result.get("fallback_reason") or diagnostics.get("fallback_reason")
        if fallback_reason:
            print(f"fallback_reason: {fallback_reason}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if args and args[0] in ("-h", "--help"):
        print("study-agent-demo-shell")
        print(f"default ACP URL: {_default_base_url()}")
        print(f"default output dir: {_default_output_dir()}")
        return 0
    shell = StudyAgentDemoShell(
        client=ACPClient(base_url=_default_base_url()),
        session=DemoSession(output_dir=_default_output_dir()),
    )
    return shell.run()


if __name__ == "__main__":
    raise SystemExit(main())
