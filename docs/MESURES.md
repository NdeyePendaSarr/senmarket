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
