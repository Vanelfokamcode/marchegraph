from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pyshacl import validate as shacl_validate
from rdflib import Graph, Node, RDF, URIRef
from rdflib.namespace import SH

MG = "https://example.org/marchegraph/"
RULE_ID = URIRef(f"{MG}ruleId")


@dataclass(frozen=True)
class RejectionReason:
    rule_id: str
    message: str
    path: str | None
    value: str | None


@dataclass(frozen=True)
class RejectedRecord:
    focus_node: Node
    triples: tuple[tuple[Node, Node, Node], ...]
    reasons: tuple[RejectionReason, ...]


@dataclass(frozen=True)
class ValidationReport:
    conforms: bool
    summary: str
    violations: tuple[str, ...]
    rejected_records: tuple[RejectedRecord, ...]


def validate_graph(
    data_graph: Graph,
    shapes_graph: Graph,
    ontology_graph: Graph | None = None,
) -> ValidationReport:
    conforms, report_graph, summary = shacl_validate(
        data_graph,
        shacl_graph=shapes_graph,
        ont_graph=ontology_graph,
        inference="none",
        abort_on_first=False,
        allow_infos=False,
        allow_warnings=False,
        meta_shacl=True,
    )
    grouped: dict[Node, list[RejectionReason]] = {}
    for result in report_graph.subjects(RDF.type, SH.ValidationResult):
        focus_node = report_graph.value(result, SH.focusNode)
        if focus_node is None:
            continue
        source_shape = report_graph.value(result, SH.sourceShape)
        rule_identifier = (
            shapes_graph.value(source_shape, RULE_ID)
            if source_shape is not None
            else None
        )
        message = report_graph.value(result, SH.resultMessage)
        path = report_graph.value(result, SH.resultPath)
        value = report_graph.value(result, SH.value)
        grouped.setdefault(focus_node, []).append(
            RejectionReason(
                rule_id=str(rule_identifier or "MG-VAL-SHACL-UNIDENTIFIED"),
                message=str(message or "Violation de validation SHACL."),
                path=str(path) if path is not None else None,
                value=str(value) if value is not None else None,
            )
        )

    rejected_records = tuple(
        RejectedRecord(
            focus_node=focus_node,
            triples=tuple(
                sorted(
                    data_graph.triples((focus_node, None, None)),
                    key=lambda triple: tuple(term.n3() for term in triple),
                )
            ),
            reasons=tuple(
                sorted(
                    reasons,
                    key=lambda reason: (reason.rule_id, reason.message),
                )
            ),
        )
        for focus_node, reasons in sorted(
            grouped.items(),
            key=lambda item: item[0].n3(),
        )
    )
    violations = tuple(
        sorted(
            {
                reason.message
                for record in rejected_records
                for reason in record.reasons
            }
        )
    )
    return ValidationReport(
        conforms=bool(conforms),
        summary=str(summary),
        violations=violations,
        rejected_records=rejected_records,
    )


def write_rejections(report: ValidationReport, output_path: Path) -> None:
    """Persist each rejected RDF record and its validation reasons as JSONL."""
    output_path = output_path.expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output:
        for record in report.rejected_records:
            payload = {
                "focus_node": record.focus_node.n3(),
                "triples": [
                    [subject.n3(), predicate.n3(), object_.n3()]
                    for subject, predicate, object_ in record.triples
                ],
                "reasons": [
                    {
                        "rule_id": reason.rule_id,
                        "message": reason.message,
                        "path": reason.path,
                        "value": reason.value,
                    }
                    for reason in record.reasons
                ],
            }
            output.write(json.dumps(payload, ensure_ascii=False) + "\n")
