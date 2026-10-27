# Profilage initial des DECP

## Périmètre et méthode

Ce profilage porte sur le fichier consolidé `data/decp.parquet` disponible
localement. Le fichier est ignoré par Git ; la date exacte de son extraction
n'est donc pas enregistrée. La copie profilée pèse 250 253 419 octets et son
SHA-256 est
`b39257f135aada4637797239489dce63365c9e9ac793688af45d9d06eed7b6f0`. Ces
valeurs identifient cette copie exacte, sans établir sa date d'extraction.
Les chiffres ci-dessous décrivent ce snapshot et doivent être recalculés après
tout changement de fichier.

Les statistiques annuelles d'attribution filtrent les lignes avec
`modification_id = 0` et une `dateNotification` dans l'année. Les comptes de
marchés utilisent `COUNT(DISTINCT uid)`, pas le nombre de lignes. La fiche du
jeu de données définit `uid` comme la concaténation de l'identifiant acheteur,
de l'identifiant du marché et du code CPV.

Le script de profilage est [profilage_01.py](../src/profilage_01.py). Les
requêtes ponctuelles complémentaires utilisées pour les dénominateurs exacts
sont décrites dans les résultats ci-dessous ; elles ne sont pas encore
intégrées au script.

## Résultats observés

### Volume et versions

- En 2025, 315 998 lignes d'attribution correspondent à 273 425 `uid`
  distincts. Il y a donc plusieurs lignes pour certains marchés, notamment
  lorsqu'il y a plusieurs titulaires.
- Pour les lignes notifiées en 2025, le fichier contient aussi 271 210 lignes
  de modification, associées à 104 722 `uid` distincts. Elles doivent être
  étudiées séparément des attributions initiales.
- Le profilage mensuel précédent donne environ 288 000 marchés en 2024 contre
  273 000 en 2025 (environ -5 %). Il montre une saisonnalité similaire, avec
  notamment un pic en juillet, un creux en août et un pic en décembre. Les
  premiers mois de 2024 n'indiquent pas de rampe de collecte évidente.

### Répartition géographique en 2025

| Région de l'acheteur | Marchés distincts |
|---|---:|
| Île-de-France | 40 998 |
| Auvergne-Rhône-Alpes | 36 804 |
| Occitanie | 26 293 |
| Nouvelle-Aquitaine | 24 433 |
| Grand Est | 22 671 |
| Provence-Alpes-Côte d'Azur | 22 044 |
| Hauts-de-France | 18 268 |
| Bretagne | 17 197 |
| Pays de la Loire | 17 041 |
| Normandie | 13 061 |
| Bourgogne-Franche-Comté | 11 141 |
| Centre-Val de Loire | 9 377 |
| Autres régions | 12 098 |
| Région non renseignée | 1 999 |

L'Île-de-France représente 40 998 marchés sur 273 425, soit 14,99 %. Les
comptes régionaux sont par région de l'acheteur, pas par lieu d'exécution.

### Identifiants des titulaires en 2025

Sur les 315 998 lignes d'attribution :

- 309 470 (97,93 %) ont le type d'identifiant `SIRET` ;
- 4 689 (1,48 %) n'ont pas de type d'identifiant renseigné ;
- les autres types comprennent `HORS-UE`, `TVA`, `IREP`, `UE`, `RIDET`,
  `FRWF` et `TAHITI` ;
- la casse n'est pas entièrement normalisée (`SIRET` et `siret`).

À distinguer du champ `titulaire_id` : il est manquant sur 4 930 lignes en 2025
(1,56 %), contre 38 442 en 2024 (11,81 %). La comparaison de résolution
d'entités entre années devra tenir compte de cette différence de complétude.

### Valeurs manquantes

Les taux ci-dessous sont calculés sur les lignes d'attribution initiale :

| Champ | 2024 | 2025 |
|---|---:|---:|
| `acheteur_id` | 0 % | 0 % |
| `titulaire_id` | 11,81 % | 1,56 % |
| `montant` | 0,57 % | 0,18 % |
| `codeCPV` | <0,01 % | <0,01 % |
| `objet` | 0,04 % | 0 % |
| `lieuExecution_code` | 0,08 % | <0,01 % |
| `acheteur_region_code` | 0,52 % | 0,69 % |
| `offresRecues` | 14,80 % | 13,64 % |

Les dénominateurs sont 325 470 lignes pour 2024 et 315 998 pour 2025.

### Montants et dates de publication

- En 2025, 6 811 lignes sont marquées `suspect` et 1 184 `aberrant` par
  `montant_anomalie`. Ces indicateurs appellent une vérification ; ils ne
  justifient pas à eux seuls l'exclusion des marchés.
- Parmi les lignes avec une date de publication, le délai médian entre
  notification et publication est de 20 jours en 2025 (25 en 2024).
- Le délai est négatif pour 13 395 lignes en 2025 (4,24 % des lignes avec date
  de publication), contre 12 244 en 2024 (3,76 %). Les dates concernées sont
  à investiguer avant toute interprétation temporelle. Ce seul indicateur ne
  permet pas de conclure que le millésime est complet ou incomplet.

## Décisions de périmètre proposées

1. Retenir **2025, toutes régions**, comme périmètre principal. L'Île-de-France
   ne constitue qu'environ 15 % du volume et n'est pas nécessaire pour rendre
   le jeu manipulable.
2. Garder **2024 comme comparaison secondaire**, en signalant explicitement
   l'écart de complétude du champ `titulaire_id`.
3. Pour les agrégats d'attribution, filtrer `modification_id = 0` et compter
   les `uid` distincts. Traiter les modifications comme un historique séparé,
   plutôt que de les ajouter aux volumes d'attributions.
4. Ne pas exclure automatiquement les montants signalés ni les lignes aux
   dates incohérentes : mesurer l'effet de règles de qualité documentées.

## Limites et prochaines vérifications

- La copie locale est identifiable par son SHA-256 et sa taille, mais sa date
  d'extraction n'est pas enregistrée ; les chiffres ne sont pas garantis
  identiques à une extraction ultérieure.
- Vérifier les règles exactes de construction de `uid` et les cas où les
  identifiants changent entre versions.
- Examiner les lignes à délai de publication négatif et distinguer les dates
  manquantes des délais effectivement calculables.
- Le jeu décrit les attributions, pas les paiements ou l'exécution financière
  des marchés.
