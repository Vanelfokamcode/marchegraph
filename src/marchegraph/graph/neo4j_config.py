from __future__ import annotations

from urllib.parse import urlparse


LOCAL_NEO4J_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class LocalNeo4jURLError(ValueError):
    pass


def validate_local_neo4j_uri(uri: str) -> None:
    if urlparse(uri).hostname not in LOCAL_NEO4J_HOSTS:
        raise LocalNeo4jURLError(
            "Neo4j doit être local ; l'URI doit utiliser localhost, "
            "127.0.0.1 ou ::1."
        )
