# Contrat de données SenMarket

Version 1 — 2026-11-05. Ce fichier est la référence : le générateur, le nettoyage,
l'analyse et les modules suivants s'y conforment.

## Conventions

- **Montants** : francs CFA (XOF), **entiers** (pas de centimes). Jamais de `float`.
- **Dates** : `AAAA-MM-JJ`. `date_evenement` est un horodatage.
- **Identifiants** : texte stable, préfixe + 7 chiffres (voir plus bas).
- **Données synthétiques** : elles ne représentent aucune transaction réelle.

## Les trois décisions

1. **Granularité.** Une ligne de `commandes` est une commande ; une ligne de
   `lignes_commande` est un produit dans une commande ; le panier d'une commande
   est la somme de ses lignes, jamais la valeur d'une ligne.
2. **Identifiants.** Chaque entité a un identifiant texte à préfixe ; un nom n'est
   jamais une clé, car deux clients homonymes seraient fusionnés.
3. **Prix.** Le prix de catalogue est dans `produits.prix_catalogue_xof` ; le prix
   payé est dans `lignes_commande.prix_unitaire_xof` et peut différer du catalogue
   (promotion jusqu'à ±10 %), ce qui permet de changer le catalogue sans réécrire
   l'histoire.

## Identifiants

| Entité | Format | Exemple |
|---|---|---|
| client | `CLI` + 7 chiffres | `CLI0000001` |
| vendeur | `VEN` + 7 chiffres | `VEN0000001` |
| produit | `PRD` + 7 chiffres | `PRD0000007` |
| commande | `CMD` + 7 chiffres | `CMD0000001` |
| ligne de commande | `LIG` + 7 chiffres | `LIG0000001` |
| paiement | `PAI` + 7 chiffres | `PAI0000001` |
| avis | `AVI` + 7 chiffres | `AVI0000001` |
| événement de navigation | `NAV` + 7 chiffres | `NAV0000001` |

## Tables

| Table | Clé primaire | Colonnes (type, contraintes) |
|---|---|---|
| `clients` | `client_id` | `nom_client` (texte), `email` (texte, facultatif), `telephone` (texte, facultatif), `ville` (texte), `region` (texte), `date_inscription` (date) |
| `vendeurs` | `vendeur_id` | `nom_vendeur` (texte), `ville` (texte), `region` (texte) |
| `produits` | `produit_id` | `nom_produit` (texte), `categorie` (texte), `vendeur_id` → `vendeurs`, `prix_catalogue_xof` (entier), `actif` (booléen) |
| `commandes` | `commande_id` | `client_id` → `clients`, `date_commande` (date), `statut` ∈ {`livree`, `expediee`, `en_cours`, `annulee`} |
| `lignes_commande` | `ligne_commande_id` | `commande_id` → `commandes`, `produit_id` → `produits`, `quantite` (entier > 0), `prix_unitaire_xof` (entier), `montant_xof` (entier) |
| `paiements` | `paiement_id` | `commande_id` → `commandes`, `methode_paiement` ∈ {`wave`, `orange_money`, `carte`, `especes`}, `statut_paiement` ∈ {`reussi`, `echoue`, `en_attente`}, `montant_xof` (entier), `date_paiement` (date) |
| `avis` | `avis_id` | `client_id` → `clients`, `produit_id` → `produits`, `commande_id` → `commandes`, `note` (entier, 1 à 5), `date_avis` (date) |
| `navigation` | `evenement_id` | `session_id` (texte), `client_id` → `clients` (facultatif), `produit_id` → `produits` (facultatif), `type_evenement` ∈ {`vue_produit`, `ajout_panier`, `debut_paiement`}, `date_evenement` (horodatage) |

`email` et `telephone` sont synthétiques : ils servent au Module 10 (repérer et masquer
les données personnelles). Les colonnes `stock`, `commentaire` et `reference_transaction`
n'existent pas ici : le Module 1 les crée.

## Règles métier

Connues dès maintenant :

- `montant_xof` d'une ligne = `quantite` × `prix_unitaire_xof`.
- `prix_unitaire_xof` est compris entre 90 % et 110 % de `prix_catalogue_xof`.
- Une ligne normale ne dépasse pas 5 × 500 000 XOF (ordre de grandeur du sujet) ;
  10 000 000 XOF est donc aberrant.
- Le montant d'un paiement devrait égaler la somme des lignes de sa commande :
  c'est mesuré par le contrôle de pré-vol du Module 1, pas garanti.

À fixer au chapitre 2 (règles de nettoyage) : plages de dates, format de `session_id`,
bornes de `prix_catalogue_xof`, formats de `email` et `telephone`, règles sur les
commandes `annulee`.

## Ordres de grandeur pour `--rows N` (N lignes de commande)

| Table | Volume approximatif |
|---|---|
| `commandes` | N / 2,5 |
| `clients` | N / 3 |
| `vendeurs` | 20 |
| `produits` | 40 |
| `avis` | N / 10 |
| `navigation` | 2 × N |

## Décisions de génération (chapitre 2, étape 2a)

- `session_id` : `SES` + 8 chiffres.
- Statuts de commande de la vérité : 70 % `livree`, 12 % `expediee`, 10 % `en_cours`, 8 % `annulee`.
- Avis : 10 % des commandes `livree`, un seul produit parmi ceux de la commande.
- `email` absent pour 10 % des clients, `telephone` pour 5 %, dès la vérité (champs facultatifs).
- Promotion : 20 % des lignes, prix payé entre 90 % et 110 % du catalogue, arrondi à 5 XOF.
- Écarts métier volontaires (pas des défauts) : ~2 % des commandes sans paiement, ~1 % des paiements dont
  le montant diffère de la somme des lignes.
