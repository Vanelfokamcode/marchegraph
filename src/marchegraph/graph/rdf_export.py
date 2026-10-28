from __future__ import annotations

from urllib.parse import quote

from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import OWL, SKOS, XSD

from marchegraph.graph.demo_data import DemoData

MG = Namespace("https://example.org/marchegraph/")
RESOURCE = "https://marchegraph.local/resource/"


def resource(kind: str, identifier: str) -> URIRef:
    return URIRef(f"{RESOURCE}{kind}/{quote(identifier, safe='')}")


def graph_from_data(data: DemoData) -> Graph:
    graph = Graph()
    graph.bind("mg", MG)
    graph.bind("owl", OWL)
    graph.bind("xsd", XSD)

    for buyer in data.buyers:
        subject = resource("acheteur", buyer.identifier)
        graph.add((subject, RDF.type, MG.Acheteur))
        graph.add((subject, MG.identifiant, Literal(buyer.identifier)))
        graph.add((subject, MG.nom, Literal(buyer.name, lang="fr")))

    for holder in data.holders:
        subject = resource("titulaire", holder.identifier)
        graph.add((subject, RDF.type, MG.Titulaire))
        graph.add((subject, MG.identifiant, Literal(holder.identifier)))
        graph.add((subject, MG.nom, Literal(holder.name, lang="fr")))
        graph.add(
            (
                subject,
                MG.typeIdentifiant,
                Literal(holder.identifier_type),
            )
        )
        graph.add(
            (
                subject,
                MG.valeurIdentifiant,
                Literal(holder.identifier_value),
            )
        )
        if holder.identifier_type == "SIRET":
            graph.add(
                (
                    subject,
                    MG.siret,
                    Literal(holder.identifier_value),
                )
            )

    for market in data.markets:
        subject = resource("marche", market.uid)
        graph.add((subject, RDF.type, MG.Marche))
        graph.add((subject, MG.uid, Literal(market.uid)))
        graph.add((subject, MG.annee, Literal(market.year, datatype=XSD.gYear)))
        graph.add((subject, MG.objet, Literal(market.subject, lang="fr")))
        graph.add(
            (
                subject,
                MG.montantHT,
                Literal(market.amount_ht, datatype=XSD.decimal),
            )
        )
        cpv = URIRef(f"{MG}cpv-{quote(market.cpv_code, safe='')}")
        graph.add((cpv, RDF.type, SKOS.Concept))
        graph.add((cpv, SKOS.inScheme, MG.CPV))
        graph.add((cpv, SKOS.notation, Literal(market.cpv_code)))
        graph.add((subject, MG.categorieCPV, cpv))
        graph.add(
            (
                subject,
                MG.acheteur,
                resource("acheteur", market.buyer_id),
            )
        )
        for holder_id in market.holder_ids:
            graph.add(
                (
                    subject,
                    MG.titulaire,
                    resource("titulaire", holder_id),
                )
            )

    for modification in data.modifications:
        subject = resource("modification", modification.identifier)
        graph.add((subject, RDF.type, MG.Modification))
        graph.add((subject, MG.identifiant, Literal(modification.identifier)))
        graph.add(
            (
                subject,
                MG.modificationDe,
                resource("marche", modification.market_uid),
            )
        )
        graph.add((subject, MG.objet, Literal(modification.subject, lang="fr")))

    return graph
