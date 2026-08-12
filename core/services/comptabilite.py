"""Service comptabilité : plan, grand-livre, bilan (logique métier).

Couche "application/service" : aucune connaissance HTTP ici, uniquement
des objets métier et de la persistance (ORM Django). Les vues appellent
ces fonctions et se chargent uniquement de la présentation JSON.
"""
from datetime import date
from decimal import Decimal

from django.db.models import Sum

from ..models import CompteComptable, Entreprise, LigneEcriture
from ..plan_comptable import seed_plan_comptable

MISSING = "0.000"


def entreprise_for_id(entreprise_id):
    return Entreprise.objects.filter(pk=entreprise_id).first()


def validated_lignes(entreprise, from_date=None, to_date=None):
    """Lignes d'écritures validées (seules prises en compte dans les états)."""
    lignes = LigneEcriture.objects.filter(
        ecriture__entreprise=entreprise, ecriture__statut="valide"
    ).select_related("compte", "ecriture")
    if from_date:
        lignes = lignes.filter(ecriture__date__gte=from_date)
    if to_date:
        lignes = lignes.filter(ecriture__date__lte=to_date)
    return lignes


def parse_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except (ValueError, TypeError):
        return None


# ---------------- Plan comptable ----------------

def _node(c):
    return {
        "id": c.id,
        "numero": c.numero,
        "intitule": c.intitule,
        "niveau": c.niveau,
        "active": c.active,
        "enfants": [_node(e) for e in sorted(c.enfants.all(), key=lambda x: x.numero)],
    }


def plan_tree(entreprise):
    racines = sorted([c for c in entreprise.comptes.all() if not c.parent_id], key=lambda x: x.numero)
    return [_node(r) for r in racines]


def plan_init(entreprise) -> bool:
    """Seed du plan comptable tunisien (idempotent). Renvoie True si créé."""
    return seed_plan_comptable(entreprise)


# ---------------- Grand livre / balance ----------------

def grand_livre(entreprise, from_date=None, to_date=None):
    lignes = list(validated_lignes(entreprise, from_date, to_date))
    accs = {}
    for ln in lignes:
        acc = accs.setdefault(ln.compte_id, {
            "compte_id": ln.compte_id,
            "numero": ln.compte.numero,
            "intitule": ln.compte.intitule,
            "classe": ln.compte.classe,
            "debit": Decimal("0"),
            "credit": Decimal("0"),
            "nb": 0,
        })
        acc["debit"] += ln.debit
        acc["credit"] += ln.credit
        acc["nb"] += 1
    for acc in accs.values():
        solde = acc["debit"] - acc["credit"]
        acc["solde"] = str(solde)
        acc["solde_debiteur"] = str(solde) if solde > 0 else MISSING
        acc["solde_crediteur"] = str(-solde) if solde < 0 else MISSING
    comptes = sorted(accs.values(), key=lambda x: x["numero"])
    mouvements = [
        {
            "id": ln.id,
            "date": ln.ecriture.date.strftime("%d/%m/%Y"),
            "piece": ln.ecriture.numero_piece,
            "libelle": ln.libelle or ln.ecriture.libelle,
            "compte_id": ln.compte_id,
            "numero": ln.compte.numero,
            "debit": str(ln.debit),
            "credit": str(ln.credit),
        }
        for ln in sorted(lignes, key=lambda x: (x.ecriture.date, x.ecriture_id, x.id))
    ]
    return {
        "comptes": comptes,
        "mouvements": mouvements,
        "total_debit": str(sum(a["debit"] for a in comptes)),
        "total_credit": str(sum(a["credit"] for a in comptes)),
    }


# ---------------- Bilan & résultat ----------------

def bilan(entreprise, from_date=None, to_date=None):
    lignes = validated_lignes(entreprise, from_date, to_date)
    comptes = list(CompteComptable.objects.filter(
        entreprise=entreprise, lignes__in=lignes
    ).distinct())
    accs = {c.id: {"classe": c.classe, "numero": c.numero, "intitule": c.intitule,
                    "debit": Decimal("0"), "credit": Decimal("0")} for c in comptes}
    for ln in lignes:
        accs[ln.compte_id]["debit"] += ln.debit
        accs[ln.compte_id]["credit"] += ln.credit

    def solde(acc):
        return acc["debit"] - acc["credit"]

    def section(classe, sens):
        rows = [a for a in accs.values() if a["classe"] == classe]
        total = Decimal("0")
        details = []
        for a in sorted(rows, key=lambda x: x["numero"]):
            s = solde(a)
            if sens == "debit" and s > 0:
                total += s
                details.append({"numero": a["numero"], "intitule": a["intitule"], "montant": format(s, ".3f")})
            if sens == "credit" and s < 0:
                total += -s
                details.append({"numero": a["numero"], "intitule": a["intitule"], "montant": format(-s, ".3f")})
        return {"details": details, "total": format(total, ".3f")}

    actif_immo = section("2", "debit")
    actif_stocks = section("3", "debit")
    actif_treso = section("5", "debit")
    creances = section("4", "debit")
    dettes = section("4", "credit")
    capitaux = section("1", "credit")
    charges = section("6", "debit")
    produits = section("7", "credit")

    total_charges = Decimal(charges["total"])
    total_produits = Decimal(produits["total"])
    resultat = total_produits - total_charges
    total_actif = Decimal(actif_immo["total"]) + Decimal(actif_stocks["total"]) + Decimal(actif_treso["total"]) + Decimal(creances["total"])
    total_passif = Decimal(capitaux["total"]) + Decimal(dettes["total"]) + resultat
    return {
        "bilan": {
            "actif": [
                {"label": "Actifs non courants (immobilisations)", "detail": actif_immo["details"], "total": actif_immo["total"]},
                {"label": "Stocks", "detail": actif_stocks["details"], "total": actif_stocks["total"]},
                {"label": "Créances et comptes de tiers débiteurs", "detail": creances["details"], "total": creances["total"]},
                {"label": "Trésorerie et équivalents de trésorerie", "detail": actif_treso["details"], "total": actif_treso["total"]},
            ],
            "passif": [
                {"label": "Capitaux propres", "detail": capitaux["details"], "total": capitaux["total"]},
                {"label": "Dettes et comptes de tiers créditeurs", "detail": dettes["details"], "total": dettes["total"]},
                {"label": "Résultat de l'exercice", "detail": [], "total": format(resultat, ".3f")},
            ],
            "total_actif": format(total_actif, ".3f"),
            "total_passif": format(total_passif, ".3f"),
        },
        "resultat": {
            "charges": {"details": charges["details"], "total": charges["total"]},
            "produits": {"details": produits["details"], "total": produits["total"]},
            "resultat": format(resultat, ".3f"),
        },
    }


def ecriture_totaux(ecriture):
    return {
        "total_debit": str(ecriture.lignes.aggregate(s=Sum("debit"))["s"] or 0),
        "total_credit": str(ecriture.lignes.aggregate(s=Sum("credit"))["s"] or 0),
    }
