# Mesures — environnement

```
Python 3.12.3
/home/hp/senmarket/.venv/bin/python
git version 2.43.0
ok
12
               total        used        free      shared  buff/cache   available
Mem:           7.6Gi       1.6Gi       1.9Gi       117Mi       4.3Gi       6.0Gi
Swap:          2.0Gi          0B       2.0Gi
```

## Génération du volume (200 000 lignes, tous les défauts)
```

real	0m7.842s
user	0m8.353s
sys	0m0.584s
12
               total        used        free      shared  buff/cache   available
Mem:           7.6Gi       1.6Gi       1.8Gi       117Mi       4.5Gi       6.0Gi
Swap:          2.0Gi          0B       2.0Gi
```

### Mesure 2026-11-05 — commit 95642d2
Commande : `python -m senmarket.generation --run-date 2026-11-06 --rows 200000 --defauts tous --ecraser` (code de sortie : 0)
```
cœurs : 12
	Elapsed (wall clock) time (h:mm:ss or m:ss): 0:07.06
	Maximum resident set size (kbytes): 413920
```

### Formats de fichiers (SM-004), lecture à chaud, médiane de 5, 1re lecture ignorée
Machine : 12 threads, pandas 3.1.1, pyarrow 26.0.1. Partition 2026-11-06.
Commandes : `python -m senmarket.formats data/raw/date=2026-11-06/lignes_commande.csv`
et `... commandes.csv --dates date_commande --colonne date_commande`

| Fichier | Format | Temps médian (s) | Taille (Mo) |
|---|---|---|---|
| lignes_commande | csv | 0.040 | 9.2 |
| lignes_commande | json | 0.863 | 29.7 |
| lignes_commande | jsonl | 0.936 | 29.7 |
| lignes_commande | parquet | 0.029 | 2.8 |
| commandes | csv | 0.017 | 3.1 |
| commandes | json | 0.263 | 8.7 |
| commandes | jsonl | 0.252 | 8.7 |
| commandes | parquet | 0.020 | 0.9 |

Type de `date_commande` : csv/json/jsonl `str`, parquet `datetime64[us]`.
Lecture par morceaux (chunksize) : identique à la lecture complète.

Types inférés par Pandas pour `lignes_commande`, identiques dans les 4 formats :
ligne_commande_id, commande_id, produit_id : str ; quantite, prix_unitaire_xof : int64 ;
montant_xof : str (défauts valeurs_manquantes et montant_texte du chapitre 2 ; à convertir au chapitre 4).

2e exécution (mêmes commandes) : lignes_commande csv 0.037, json 0.773, jsonl 0.918, parquet 0.029 s ;
commandes csv 0.010, json 0.225, jsonl 0.240, parquet 0.013 s.
Constat : JSON reste très loin derrière ; sur les petits fichiers, les valeurs absolues varient d'une exécution à l'autre.
