MERGE (g:CPV {code: "45200000"}) SET g.libelle = "Travaux de génie civil"
MERGE (p:CPV {code: "45233000"}) SET p.libelle = "Travaux de chaussées"
MERGE (c:CPV {code: "45233140"}) SET c.libelle = "Travaux routiers"
MERGE (p)-[:A_POUR_PARENT]->(g)
MERGE (c)-[:A_POUR_PARENT]->(p)
MERGE (a:Acheteur {id: "ville-exemple"}) SET a.nom = "Ville d'Exemple"
MERGE (t:Titulaire {siret: "00000000000000"}) SET t.nom = "Durand Travaux SARL"
MERGE (m:Marche {id: "2025-001"})
  SET m.objet = "Réfection de la voirie du centre-ville", m.montantHT = 250000.00
MERGE (m)-[:ACHETEUR]->(a)
MERGE (m)-[:TITULAIRE]->(t)
MERGE (m)-[:CATEGORIE_CPV]->(c);

// Question : tous les marchés de génie civil, y compris les codes plus précis
MATCH (m:Marche)-[:CATEGORIE_CPV]->(:CPV)-[:A_POUR_PARENT*0..]->(:CPV {code: "45200000"})
RETURN m.id, m.objet;
