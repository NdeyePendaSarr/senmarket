"""Génération des données SenMarket : d'abord la « vérité », ensuite (étape 2b) les défauts.

La « vérité » est un jeu de 8 tables parfaitement cohérent, conforme à
``docs/CONTRAT_DONNEES.md``. Elle est entièrement vectorisée avec NumPy ;
Faker ne sert que pour les petites tables (e-mails et téléphones des clients).
"""

from __future__ import annotations

import os
from datetime import date
from typing import Final

import numpy as np
import pandas as pd
from faker import Faker

from senmarket.chemins import charger_env, normaliser_date

# ----------------------------------------------------------------------------
# Référentiels (listes fixes : elles ne dépendent pas de la graine)
# ----------------------------------------------------------------------------

# (ville, région, poids) : Dakar ≈ un tiers des clients, puis une longue traîne.
VILLES: Final[list[tuple[str, str, float]]] = [
    ("Dakar", "Dakar", 33.0), ("Pikine", "Dakar", 5.0), ("Guédiawaye", "Dakar", 3.0),
    ("Rufisque", "Dakar", 2.5), ("Thiès", "Thiès", 8.0), ("Mbour", "Thiès", 6.0),
    ("Touba", "Diourbel", 7.0), ("Diourbel", "Diourbel", 2.5),
    ("Saint-Louis", "Saint-Louis", 6.0), ("Richard-Toll", "Saint-Louis", 1.5),
    ("Kaolack", "Kaolack", 5.0), ("Kaffrine", "Kaffrine", 1.5),
    ("Ziguinchor", "Ziguinchor", 5.0), ("Louga", "Louga", 3.0),
    ("Tambacounda", "Tambacounda", 3.0), ("Kolda", "Kolda", 2.0),
    ("Fatick", "Fatick", 1.5), ("Matam", "Matam", 1.0),
    ("Sédhiou", "Sédhiou", 1.0), ("Kédougou", "Kédougou", 1.0),
]

PRENOMS: Final[list[str]] = [
    "Aïssatou", "Ndèye Fatou", "Fatou", "Awa", "Mariama", "Khadija", "Astou", "Coumba",
    "Mame Diarra", "Rokhaya", "Aminata", "Sokhna", "Yacine", "Maïmouna", "Bineta",
    "Dieynaba", "Adja", "Ndèye Marième", "Rama", "Selbé",
    "Cheikh", "Mamadou", "Moussa", "Ibrahima", "Ousmane", "Abdoulaye", "Modou", "Pape",
    "Serigne", "Alioune", "Babacar", "Omar", "Samba", "Lamine", "Idrissa", "Boubacar",
    "Demba", "Saliou", "Assane", "Souleymane",
]
NOMS: Final[list[str]] = [
    "Diop", "Ndiaye", "Fall", "Sow", "Sène", "Mbaye", "Gueye", "Diallo", "Ba", "Faye",
    "Cissé", "Sarr", "Thiam", "Sy", "Diouf", "Seck", "Ndao", "Niang", "Kane", "Samb",
    "Wade", "Lô", "Badji", "Diatta", "Sagna", "Tine", "Mendy", "Camara", "Sylla", "Touré",
]

VENDEURS: Final[list[str]] = [
    "Teranga Mode", "Baobab Électro", "Sahel Tissus", "Gorée Import", "Lac Rose Beauté",
    "Médina Téléphonie", "Casamance Saveurs", "Kër Gui Maison", "Almadies Boutique",
    "Sandaga Market", "Ngor Électronique", "Petite Côte Distribution", "Fleuve Commerce",
    "Saloum Négoce", "Touba Grossiste", "Yoff Déco", "Thiaroye Marché",
    "Dakar Plateau Shop", "Teungueth Diffusion", "Niayes Primeur",
]

# (nom, catégorie, prix de catalogue en XOF) : 40 produits, 6 catégories.
PRODUITS: Final[list[tuple[str, str, int]]] = [
    ("Smartphone Android 6 pouces", "Téléphonie", 95000),
    ("Smartphone milieu de gamme", "Téléphonie", 185000),
    ("Smartphone haut de gamme", "Téléphonie", 480000),
    ("Chargeur rapide USB-C", "Téléphonie", 6500),
    ("Écouteurs sans fil", "Téléphonie", 12000),
    ("Coque de protection", "Téléphonie", 2500),
    ("Batterie externe 10000 mAh", "Téléphonie", 15000),
    ("Boubou brodé homme", "Tissus et mode", 45000),
    ("Pagne wax 6 yards", "Tissus et mode", 12000),
    ("Bazin riche 5 mètres", "Tissus et mode", 38000),
    ("Robe en wax", "Tissus et mode", 22000),
    ("Sandales en cuir", "Tissus et mode", 9000),
    ("Sac à main artisanal", "Tissus et mode", 18000),
    ("Riz brisé 50 kg", "Alimentation", 19000),
    ("Huile végétale 5 L", "Alimentation", 6500),
    ("Sucre 25 kg", "Alimentation", 14000),
    ("Lait en poudre 900 g", "Alimentation", 4500),
    ("Café Touba 1 kg", "Alimentation", 5000),
    ("Thé vert (carton)", "Alimentation", 3500),
    ("Bissap séché 500 g", "Alimentation", 1000),
    ("Matelas 2 places", "Maison", 120000),
    ("Marmite en aluminium", "Maison", 7500),
    ("Ventilateur sur pied", "Maison", 28000),
    ("Lampe solaire", "Maison", 11000),
    ("Natte tressée", "Maison", 5500),
    ("Seau et bassine (lot)", "Maison", 3000),
    ("Réfrigérateur 250 L", "Électroménager", 280000),
    ("Congélateur coffre", "Électroménager", 220000),
    ("Climatiseur split", "Électroménager", 450000),
    ("Machine à laver 7 kg", "Électroménager", 260000),
    ("Mixeur", "Électroménager", 18000),
    ("Fer à repasser", "Électroménager", 9500),
    ("Téléviseur 43 pouces", "Électroménager", 195000),
    ("Beurre de karité 250 g", "Beauté", 2500),
    ("Parfum oriental", "Beauté", 25000),
    ("Savon noir", "Beauté", 1500),
    ("Huile de coco", "Beauté", 3500),
    ("Crème hydratante", "Beauté", 6000),
    ("Henné naturel", "Beauté", 1000),
    ("Sèche-cheveux", "Beauté", 15000),
]

STATUTS_COMMANDE: Final[tuple[str, ...]] = ("livree", "expediee", "en_cours", "annulee")
P_STATUTS_COMMANDE: Final[tuple[float, ...]] = (0.70, 0.12, 0.10, 0.08)
METHODES: Final[tuple[str, ...]] = ("wave", "orange_money", "carte", "especes")
P_METHODES: Final[tuple[float, ...]] = (0.45, 0.35, 0.08, 0.12)
STATUTS_PAIEMENT: Final[tuple[str, ...]] = ("reussi", "echoue", "en_attente")
P_STATUTS_PAIEMENT: Final[tuple[float, ...]] = (0.90, 0.06, 0.04)
P_QUANTITE: Final[tuple[float, ...]] = (0.55, 0.25, 0.10, 0.06, 0.04)  # quantités 1 à 5
P_NOTES: Final[tuple[float, ...]] = (0.04, 0.05, 0.13, 0.30, 0.48)  # notes 1 à 5

TAUX_SANS_PAIEMENT: Final[float] = 0.02   # commandes sans aucun paiement (réalisme métier)
TAUX_ECART_PAIEMENT: Final[float] = 0.01  # paiements dont le montant diffère des lignes
TAUX_AVIS_LIVREES: Final[float] = 0.10    # part des commandes livrées qui reçoivent un avis
P_PROMOTION: Final[float] = 0.20          # part des lignes vendues avec une promotion
P_SESSION_ANONYME: Final[float] = 0.30
P_AJOUT_PANIER: Final[float] = 0.40       # 0,40 × 0,375 = 15 % de sessions jusqu'au paiement
P_DEBUT_PAIEMENT: Final[float] = 0.375


# ----------------------------------------------------------------------------
# Outils
# ----------------------------------------------------------------------------

def _ids(prefixe: str, n: int) -> list[str]:
    """Identifiants ``PREFIXE0000001`` ... (préfixe + 7 chiffres)."""
    return [f"{prefixe}{i:07d}" for i in range(1, n + 1)]


def _jours_depuis_epoch(d: date) -> int:
    """Nombre de jours entre le 1970-01-01 et la date ``d``."""
    return (d - date(1970, 1, 1)).days


def _en_dates(jours: np.ndarray) -> np.ndarray:
    """Convertit des jours-depuis-epoch (entiers) en tableau datetime64[D]."""
    return jours.astype("int64").astype("datetime64[D]")


def graine_entiere(seed: int, run_date: date | str) -> int:
    """Combine la graine et la date en UN seul entier (ex. 42 et 2026-11-05 → 4220261105).

    ``Faker.seed`` et ``random.seed`` n'acceptent pas une liste ; NumPy, si.
    """
    return seed * 100_000_000 + int(normaliser_date(run_date).replace("-", ""))


def _graine_env() -> int:
    charger_env()
    return int(os.environ.get("SENMARKET_SEED", "42"))


# ----------------------------------------------------------------------------
# La « vérité » : 8 tables propres
# ----------------------------------------------------------------------------

def generer_verite(
    rows: int,
    run_date: date | str,
    jours: int = 365,
    seed: int | None = None,
) -> dict[str, pd.DataFrame]:
    """Génère les 8 tables cohérentes (aucun défaut).

    Args:
        rows: nombre de lignes de commande (``lignes_commande``), au moins 10.
        run_date: date d'exécution ; aucune date de la vérité ne la dépasse.
        jours: les commandes couvrent les ``jours`` jours qui précèdent ``run_date``.
        seed: graine ; par défaut SENMARKET_SEED.
    """
    if rows < 10:
        raise ValueError(f"rows doit valoir au moins 10 (reçu {rows})")
    if jours < 1:
        raise ValueError(f"jours doit valoir au moins 1 (reçu {jours})")

    iso = normaliser_date(run_date)
    jour_run = _jours_depuis_epoch(date.fromisoformat(iso))
    graine = _graine_env() if seed is None else seed
    # La liste [graine, AAAAMMJJ] est acceptée par NumPy ; Faker reçoit un entier.
    rng = np.random.default_rng([graine, int(iso.replace("-", ""))])
    fake = Faker("fr_FR")
    fake.seed_instance(graine_entiere(graine, iso))

    n_clients = max(rows // 3, 1)
    n_commandes = max(round(rows / 2.5), 1)

    # --- vendeurs et produits -------------------------------------------------
    n_vendeurs = len(VENDEURS)
    p_villes = np.array([v[2] for v in VILLES], dtype=float)
    p_villes /= p_villes.sum()

    idx_ville_vendeur = rng.choice(len(VILLES), size=n_vendeurs, p=p_villes)
    vendeurs = pd.DataFrame({
        "vendeur_id": _ids("VEN", n_vendeurs),
        "nom_vendeur": VENDEURS,
        "ville": [VILLES[i][0] for i in idx_ville_vendeur],
        "region": [VILLES[i][1] for i in idx_ville_vendeur],
    })

    n_produits = len(PRODUITS)
    produits = pd.DataFrame({
        "produit_id": _ids("PRD", n_produits),
        "nom_produit": [p[0] for p in PRODUITS],
        "categorie": [p[1] for p in PRODUITS],
        "vendeur_id": vendeurs["vendeur_id"].to_numpy()[rng.integers(0, n_vendeurs, n_produits)],
        "prix_catalogue_xof": np.array([p[2] for p in PRODUITS], dtype=np.int64),
        "actif": rng.random(n_produits) < 0.95,
    })
    # Popularité de type Zipf : quelques produits très demandés, beaucoup de rares.
    rang = rng.permutation(n_produits) + 1
    p_produits = 1.0 / rang**1.1
    p_produits /= p_produits.sum()

    # --- clients ---------------------------------------------------------------
    idx_ville = rng.choice(len(VILLES), size=n_clients, p=p_villes)
    prenoms = rng.integers(0, len(PRENOMS), n_clients)
    noms = rng.integers(0, len(NOMS), n_clients)
    jour_inscription = jour_run - rng.integers(0, jours + 365 + 1, n_clients)
    emails = [fake.free_email() for _ in range(n_clients)]
    telephones = [fake.numerify("+221 7# ### ## ##") for _ in range(n_clients)]
    email_absent = rng.random(n_clients) < 0.10
    tel_absent = rng.random(n_clients) < 0.05
    clients = pd.DataFrame({
        "client_id": _ids("CLI", n_clients),
        "nom_client": [f"{PRENOMS[p]} {NOMS[n]}" for p, n in zip(prenoms, noms, strict=True)],
        "email": [None if a else e for e, a in zip(emails, email_absent, strict=True)],
        "telephone": [None if a else t for t, a in zip(telephones, tel_absent, strict=True)],
        "ville": [VILLES[i][0] for i in idx_ville],
        "region": [VILLES[i][1] for i in idx_ville],
        "date_inscription": _en_dates(jour_inscription),
    })

    # Clients « lourds » : une minorité passe beaucoup de commandes (loi log-normale).
    poids_clients = rng.lognormal(mean=0.0, sigma=1.2, size=n_clients)
    poids_clients /= poids_clients.sum()

    # --- commandes -------------------------------------------------------------
    idx_client_cmd = rng.choice(n_clients, size=n_commandes, p=poids_clients)
    debut = jour_run - jours
    borne_basse = np.maximum(jour_inscription[idx_client_cmd], debut)
    etendue = jour_run - borne_basse + 1
    jour_cmd = borne_basse + (rng.random(n_commandes) * etendue).astype(np.int64)
    ordre = np.argsort(jour_cmd, kind="stable")  # identifiants croissants avec le temps
    idx_client_cmd, jour_cmd = idx_client_cmd[ordre], jour_cmd[ordre]
    statut_cmd = rng.choice(STATUTS_COMMANDE, size=n_commandes, p=P_STATUTS_COMMANDE)
    commandes = pd.DataFrame({
        "commande_id": _ids("CMD", n_commandes),
        "client_id": clients["client_id"].to_numpy()[idx_client_cmd],
        "date_commande": _en_dates(jour_cmd),
        "statut": statut_cmd,
    })

    # --- lignes de commande ----------------------------------------------------
    # Chaque commande a au moins une ligne ; les lignes restantes sont réparties au hasard.
    nb_lignes = 1 + np.bincount(rng.integers(0, n_commandes, rows - n_commandes),
                                minlength=n_commandes)
    idx_cmd_ligne = np.repeat(np.arange(n_commandes), nb_lignes)
    idx_produit = rng.choice(n_produits, size=rows, p=p_produits)
    # Un même produit ne doit pas figurer deux fois dans une commande : on retire jusqu'à
    # ce qu'il n'y ait plus de doublon (converge vite : 40 produits, ~2,5 lignes par commande).
    for _ in range(100):
        doublon = pd.DataFrame({"c": idx_cmd_ligne, "p": idx_produit}).duplicated().to_numpy()
        if not doublon.any():
            break
        idx_produit[doublon] = rng.choice(n_produits, size=int(doublon.sum()), p=p_produits)

    catalogue = produits["prix_catalogue_xof"].to_numpy()[idx_produit]
    promo = np.where(rng.random(rows) < P_PROMOTION, rng.uniform(-0.10, 0.10, rows), 0.0)
    prix = (np.rint(catalogue * (1.0 + promo) / 5.0) * 5).astype(np.int64)
    # Bornes entières exactes : jamais en dehors de ±10 % du catalogue.
    prix = np.clip(prix, -(-9 * catalogue // 10), 11 * catalogue // 10)
    quantite = rng.choice(np.arange(1, 6), size=rows, p=P_QUANTITE).astype(np.int64)
    lignes = pd.DataFrame({
        "ligne_commande_id": _ids("LIG", rows),
        "commande_id": commandes["commande_id"].to_numpy()[idx_cmd_ligne],
        "produit_id": produits["produit_id"].to_numpy()[idx_produit],
        "quantite": quantite,
        "prix_unitaire_xof": prix,
        "montant_xof": quantite * prix,
    })

    # --- paiements : un par commande, sauf ~2 % (réalisme métier, pas un défaut) ----
    total_cmd = np.zeros(n_commandes, dtype=np.int64)
    np.add.at(total_cmd, idx_cmd_ligne, lignes["montant_xof"].to_numpy())
    paye = rng.random(n_commandes) >= TAUX_SANS_PAIEMENT
    idx_pay = np.flatnonzero(paye)
    montant_pay = total_cmd[idx_pay].copy()
    ecart = rng.random(len(idx_pay)) < TAUX_ECART_PAIEMENT  # frais ou remise (écart voulu)
    coef = rng.choice(np.array([95, 90, 102]), size=len(idx_pay))  # en pourcent
    montant_pay = np.where(ecart, montant_pay * coef // 100, montant_pay)
    jour_pay = np.minimum(jour_cmd[idx_pay] + rng.integers(0, 4, len(idx_pay)), jour_run)
    paiements = pd.DataFrame({
        "paiement_id": _ids("PAI", len(idx_pay)),
        "commande_id": commandes["commande_id"].to_numpy()[idx_pay],
        "methode_paiement": rng.choice(METHODES, size=len(idx_pay), p=P_METHODES),
        "statut_paiement": rng.choice(STATUTS_PAIEMENT, size=len(idx_pay), p=P_STATUTS_PAIEMENT),
        "montant_xof": montant_pay.astype(np.int64),
        "date_paiement": _en_dates(jour_pay),
    })

    # --- avis : sur ~10 % des commandes livrées -------------------------------------
    livrees = np.flatnonzero((statut_cmd == "livree")
                             & (rng.random(n_commandes) < TAUX_AVIS_LIVREES))
    debut_lignes = np.cumsum(nb_lignes) - nb_lignes  # position de la 1re ligne de chaque commande
    ligne_choisie = debut_lignes[livrees] + (rng.random(len(livrees)) * nb_lignes[livrees]).astype(
        np.int64)
    avis = pd.DataFrame({
        "avis_id": _ids("AVI", len(livrees)),
        "client_id": commandes["client_id"].to_numpy()[livrees],
        "produit_id": lignes["produit_id"].to_numpy()[ligne_choisie],
        "commande_id": commandes["commande_id"].to_numpy()[livrees],
        "note": rng.choice(np.arange(1, 6), size=len(livrees), p=P_NOTES).astype(np.int64),
        "date_avis": _en_dates(np.minimum(jour_cmd[livrees] + rng.integers(1, 31, len(livrees)),
                                          jour_run)),
    })

    # --- navigation : des sessions vue_produit → ajout_panier → debut_paiement -----------
    navigation = _generer_navigation(rng, rows, n_clients, n_produits, p_produits,
                                     poids_clients, jour_run, jours, clients, produits)

    return {
        "clients": clients, "vendeurs": vendeurs, "produits": produits,
        "commandes": commandes, "lignes_commande": lignes, "paiements": paiements,
        "avis": avis, "navigation": navigation,
    }


def _generer_navigation(
    rng: np.random.Generator,
    rows: int,
    n_clients: int,
    n_produits: int,
    p_produits: np.ndarray,
    poids_clients: np.ndarray,
    jour_run: int,
    jours: int,
    clients: pd.DataFrame,
    produits: pd.DataFrame,
) -> pd.DataFrame:
    """Sessions de navigation : environ ``2 × rows`` événements, 15 % jusqu'au paiement."""
    moyenne_evenements = 1 + 1.2 + P_AJOUT_PANIER + P_AJOUT_PANIER * P_DEBUT_PAIEMENT
    n_sessions = max(round(2 * rows / moyenne_evenements), 1)

    nb_vues = 1 + rng.poisson(1.2, n_sessions)
    a_panier = rng.random(n_sessions) < P_AJOUT_PANIER
    a_paiement = a_panier & (rng.random(n_sessions) < P_DEBUT_PAIEMENT)
    nb_events = nb_vues + a_panier + a_paiement

    session = np.repeat(np.arange(n_sessions), nb_events)
    debut_session = np.cumsum(nb_events) - nb_events
    position = np.arange(len(session)) - np.repeat(debut_session, nb_events)
    vues_rep = np.repeat(nb_vues, nb_events)
    type_code = np.where(position < vues_rep, 0, np.where(position == vues_rep, 1, 2))

    # Panier et paiement portent sur le premier produit consulté de la session.
    produit = rng.choice(n_produits, size=len(session), p=p_produits)
    premier = np.empty(n_sessions, dtype=np.int64)
    premier[session[position == 0]] = produit[position == 0]
    produit = np.where(type_code > 0, premier[session], produit)

    # Horodatage : début de session au hasard sur la période, puis 5 à 120 s entre événements.
    jour_session = jour_run - 1 - rng.integers(0, jours, n_sessions)  # jamais le jour même
    seconde_debut = rng.integers(0, 22 * 3600, n_sessions)
    pas = rng.integers(5, 120, len(session))
    pas[position == 0] = 0
    cumul = np.cumsum(pas)
    cumul_session = cumul - np.repeat(cumul[debut_session], nb_events)
    secondes = jour_session[session] * 86_400 + seconde_debut[session] + cumul_session

    anonyme = rng.random(n_sessions) < P_SESSION_ANONYME
    idx_client = rng.choice(n_clients, size=n_sessions, p=poids_clients)
    ids_clients = clients["client_id"].to_numpy()[idx_client[session]].astype(object)
    ids_clients[anonyme[session]] = None

    types = np.array(["vue_produit", "ajout_panier", "debut_paiement"])
    nav = pd.DataFrame({
        "session_id": [f"SES{s:08d}" for s in (session + 1)],
        "client_id": ids_clients,
        "produit_id": produits["produit_id"].to_numpy()[produit],
        "type_evenement": types[type_code],
        "date_evenement": secondes.astype("datetime64[s]"),
        "_position": position,
    })
    # Tri explicite (reproductibilité) puis identifiants croissants avec le temps.
    nav = nav.sort_values(["date_evenement", "session_id", "_position"], kind="stable")
    nav = nav.drop(columns="_position").reset_index(drop=True)
    nav.insert(0, "evenement_id", _ids("NAV", len(nav)))
    return nav
