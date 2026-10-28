from __future__ import annotations

from dataclasses import dataclass

from pyshacl import validate
from rdflib import Graph, URIRef


@dataclass(frozen=True)
class ValidationReport:
    conforms: bool
    summary: str
    violations: tuple[str, ...]


def validate_graph(
    data_graph: Graph,
    shapes_graph: Graph,
    ontology_graph: Graph | None = None,
) -> ValidationReport:
    conforms, report_graph, summary = validate(
        data_graph,
        shacl_graph=shapes_graph,
        ont_graph=ontology_graph,
        inference="none",
        abort_on_first=False,
        allow_infos=False,
        allow_warnings=False,
        meta_shacl=True,
    )
    violations = tuple(
        sorted(
            str(message)
            for message in report_graph.objects(
                None,
                URIRef("http://www.w3.org/ns/shacl#resultMessage"),
            )
        )
    )
    return ValidationReport(
        conforms=bool(conforms),
        summary=str(summary),
        violations=violations,
    )
