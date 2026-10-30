"""Baseline SQL : requêtes DuckDB directes sur le Parquet préparé, sans graphe.

Elle utilise la même reconnaissance déterministe des questions ; seules les
règles de l'epic 3 (dédoublonnage par `uid`, valeurs multiples, preuves)
manquent volontairement : c'est ce que la comparaison mesure.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

SQL: dict[int, str] = {
    1: """SELECT acheteur_id, count(DISTINCT uid) FROM src
          WHERE modification_id = 0 AND year(dateNotification) = $year
          GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 10""",
    2: """SELECT trim(titulaire_id), count(DISTINCT uid) FROM src
          WHERE modification_id = 0 AND year(dateNotification) = $year
            AND acheteur_id = $buyer_id AND titulaire_id IS NOT NULL
          GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 10""",
    3: """SELECT substr(codeCPV, 1, 3), count(DISTINCT uid), sum(montant) FROM src
          WHERE modification_id = 0 AND year(dateNotification) = $year
            AND codeCPV IS NOT NULL
          GROUP BY 1""",
    4: """SELECT count(DISTINCT uid), count(DISTINCT (uid, modification_id)) FROM src
          WHERE modification_id > 0 AND year(dateNotification) = $year""",
    5: """SELECT 'nature', nature, count(DISTINCT uid) FROM src
          WHERE modification_id = 0 AND year(dateNotification) = $year
            AND nature IS NOT NULL GROUP BY 2
          UNION ALL
          SELECT 'procedure', procedure, count(DISTINCT uid) FROM src
          WHERE modification_id = 0 AND year(dateNotification) = $year
            AND procedure IS NOT NULL GROUP BY 2""",
    6: """SELECT trim(titulaire_id), count(DISTINCT uid) FROM src
          WHERE modification_id = 0 AND year(dateNotification) = $year
            AND titulaire_id IS NOT NULL
          GROUP BY 1 HAVING count(DISTINCT acheteur_id) > 1""",
    7: """SELECT DISTINCT uid FROM src
          WHERE modification_id = 0 AND year(dateNotification) = $year
            AND objet ILIKE '%' || $theme || '%'
            AND acheteur_region_code = $region_code""",
    8: """SELECT substr(codeCPV, 1, 3), avg(dureeMois) FROM src
          WHERE modification_id = 0 AND year(dateNotification) = $year
            AND codeCPV IS NOT NULL
          GROUP BY 1""",
    9: """SELECT trim(titulaire_id), count(DISTINCT titulaire_nom) FROM src
          WHERE titulaire_id IS NOT NULL
          GROUP BY 1 HAVING count(DISTINCT titulaire_nom) > 1""",
    10: """SELECT n FROM (
             SELECT count(*) FILTER (WHERE montant IS NULL) AS a,
                    count(*) FILTER (WHERE objet IS NULL) AS b,
                    count(*) FILTER (WHERE dureeMois IS NULL) AS c,
                    count(*) FILTER (WHERE titulaire_id IS NULL) AS d,
                    count(*) FILTER (WHERE acheteur_region_code IS NULL) AS e
             FROM src WHERE modification_id = 0
           ) UNPIVOT (n FOR colonne IN (a, b, c, d, e)) WHERE n > 0""",
}


def run(source_path: Path, question_id: int, params: dict) -> list[tuple]:
    connection = duckdb.connect()
    try:
        connection.read_parquet(str(source_path)).create_view("src")
        sql = SQL[question_id]
        used = {key: value for key, value in params.items() if f"${key}" in sql}
        return [tuple(row) for row in connection.execute(sql, used).fetchall()]
    finally:
        connection.close()
