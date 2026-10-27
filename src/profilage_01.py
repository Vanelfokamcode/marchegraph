import duckdb

con = duckdb.connect()
con.sql("CREATE VIEW decp AS SELECT * FROM 'data/decp.parquet'")

A25 = "dateNotification BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'"
A2425 = "dateNotification BETWEEN DATE '2024-01-01' AND DATE '2025-12-31'"

def show(titre, sql):
    print(f"\n=== {titre} ===")
    con.sql(sql).show(max_rows=60)

show("Marchés 2025 par région de l'acheteur", f"""
SELECT acheteur_region_nom AS region, COUNT(DISTINCT uid) AS marches
FROM decp WHERE modification_id = 0 AND {A25}
GROUP BY 1 ORDER BY 2 DESC""")

show("Lignes notifiées en 2025 : attributions et modifications", f"""
SELECT (modification_id > 0) AS est_modification,
       COUNT(*) AS lignes, COUNT(DISTINCT uid) AS marches
FROM decp WHERE {A25} GROUP BY 1 ORDER BY 1""")

show("Types d'identifiant des titulaires (2025, attributions)", f"""
SELECT titulaire_typeIdentifiant, COUNT(*) AS lignes
FROM decp WHERE modification_id = 0 AND {A25}
GROUP BY 1 ORDER BY 2 DESC""")

show("Pourcentage de valeurs manquantes par année (attributions)", f"""
SELECT year(dateNotification) AS annee, COUNT(*) AS lignes,
  ROUND(100.0*AVG((acheteur_id IS NULL)::INT),2) AS acheteur_id,
  ROUND(100.0*AVG((titulaire_id IS NULL)::INT),2) AS titulaire_id,
  ROUND(100.0*AVG((montant IS NULL)::INT),2) AS montant,
  ROUND(100.0*AVG((codeCPV IS NULL)::INT),2) AS codeCPV,
  ROUND(100.0*AVG((objet IS NULL)::INT),2) AS objet,
  ROUND(100.0*AVG((lieuExecution_code IS NULL)::INT),2) AS lieu_execution,
  ROUND(100.0*AVG((acheteur_region_code IS NULL)::INT),2) AS region_acheteur,
  ROUND(100.0*AVG((offresRecues IS NULL)::INT),2) AS offres_recues
FROM decp WHERE modification_id = 0 AND {A2425}
GROUP BY 1 ORDER BY 1""")

show("Anomalies de montant (2025, attributions)", f"""
SELECT montant_anomalie, COUNT(*) AS lignes
FROM decp WHERE modification_id = 0 AND {A25}
GROUP BY 1 ORDER BY 2 DESC""")

show("Délai entre notification et publication, en jours", f"""
SELECT year(dateNotification) AS annee,
  quantile_cont(d, 0.1) AS p10, quantile_cont(d, 0.5) AS p50,
  quantile_cont(d, 0.9) AS p90, quantile_cont(d, 0.99) AS p99,
  SUM((d < 0)::INT) AS delais_negatifs
FROM (SELECT dateNotification,
             date_diff('day', dateNotification, datePublicationDonnees) AS d
      FROM decp
      WHERE modification_id = 0 AND {A2425} AND datePublicationDonnees IS NOT NULL)
GROUP BY 1 ORDER BY 1""")
