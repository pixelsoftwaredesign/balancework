"""Service facturation tenant : TVA, droit de timbre, retenue à la source,
écriture comptable automatique et export XML TEJ (CCT-RS-V2)."""

from decimal import Decimal, ROUND_HALF_UP

from ..models import CompteComptable, EcritureComptable, Facture

CENT = Decimal("100")
MILLIME = Decimal("0.001")

SEUIL_TIMBRE_TND = Decimal("1000.000")
MONTANT_TIMBRE_TND = Decimal("1.000")
SEUIL_RETENUE_ACQUISITION_TND = Decimal("1000.000")

# Comptes du plan comptable tunisien utilisés par l'écriture automatique.
COMPTE_CLIENTS = "431"
COMPTE_FOURNISSEURS = "401"
COMPTE_TVA_DEDUCTIBLE = "442"
COMPTE_TVA_COLLECTEE = "443"
COMPTE_RETENUES = "445"
COMPTE_VENTES = "707"

COMPTE_CHARGE_PAR_NATURE = {
    "acquisition": "607",       # Achats non stockés
    "honoraires_reel": "637",   # Honoraires
    "honoraires_forfait": "637",
    "loyer": "633",             # Loyers
    "dividendes": "65",         # Autres charges d'exploitation
    "cession": "65",
    "non_resident": "65",
}

# Taux de retenue à la source par nature d'opération (Art. 52 Code IRPP/IS).
TAUX_RS_PAR_NATURE = {
    "acquisition": Decimal("1.00"),
    "honoraires_reel": Decimal("3.00"),
    "honoraires_forfait": Decimal("10.00"),
    "loyer": Decimal("10.00"),
    "dividendes": Decimal("10.00"),
    "cession": Decimal("5.00"),
    "non_resident": Decimal("10.00"),
}

LIBELLE_RETENUE = "Retenue à la source"

IDENTIFIANT_TAG_TEJ = {
    "matricule": "MatriculeFiscal",
    "cin": "CIN",
    "passeport": "Passeport",
    "cartesejour": "CarteSejour",
}

MATRICULE_RE = r"^\d{7}[A-Z]$"


def _arr(v):
    return Decimal(str(v)).quantize(MILLIME, rounding=ROUND_HALF_UP)


def _millimes(v):
    return int((Decimal(str(v)) * Decimal("1000")).quantize(0, rounding=ROUND_HALF_UP))


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")


def calculer_montants(montant_ht, taux_tva, nature_operation, type_facture, taux_rs=None):
    """Calcule TVA, TTC, droit de timbre, retenue à la source et net à payer.

    Base de la retenue = (TTC − timbre) × taux, jamais le HT.
    Le droit de timbre (1 DT) s'applique sur les factures ≥ 1 000 DT TTC (LF 2022).
    La retenue sur acquisitions ne s'applique qu'à partir de 1 000 DT TTC.
    """
    ht = _arr(montant_ht)
    tva = _arr(ht * Decimal(str(taux_tva)) / CENT)
    ttc = _arr(ht + tva)
    timbre = MONTANT_TIMBRE_TND if ttc >= SEUIL_TIMBRE_TND else Decimal("0.000")
    if taux_rs is None:
        taux_rs = TAUX_RS_PAR_NATURE.get(nature_operation, Decimal("0.00"))
    else:
        taux_rs = Decimal(str(taux_rs))
    rs = Decimal("0.000")
    if type_facture == "achat":
        if nature_operation == "acquisition" and ttc < SEUIL_RETENUE_ACQUISITION_TND:
            taux_rs = Decimal("0.00")
        if taux_rs > 0:
            rs = _arr((ttc - timbre) * taux_rs / CENT)
    net = _arr(ttc - rs)
    return {
        "montant_ht": ht,
        "taux_tva": Decimal(str(taux_tva)),
        "montant_tva": tva,
        "montant_ttc": ttc,
        "timbre_fiscal": timbre,
        "retenue_source_taux": taux_rs,
        "retenue_source_montant": rs,
        "net_a_payer": net,
    }


def _compte(entreprise, numero):
    """Récupère ou crée un compte du plan comptable pour une entreprise."""
    compte = CompteComptable.objects.filter(entreprise=entreprise, numero=numero).first()
    if compte:
        return compte
    parent = None
    if len(numero) > 1:
        parent = CompteComptable.objects.filter(entreprise=entreprise, numero=numero[:-1]).first()
    return CompteComptable.objects.create(
        entreprise=entreprise, parent=parent, numero=numero,
        intitule=f"Compte {numero} (auto)",
    )


def sync_ecriture(facture):
    """Crée l'écriture comptable quand la facture passe validée, la supprime sinon.

    Retourne (ecriture|None, erreur|None).
    """
    if facture.statut == "valide":
        if facture.ecriture_id:
            return facture.ecriture, None
        return creer_ecriture(facture)
    if facture.ecriture_id:
        ecr = facture.ecriture
        facture.ecriture = None
        facture.save(update_fields=["ecriture"])
        ecr.delete()
    return None, None


def creer_ecriture(facture):
    try:
        entreprise = facture.entreprise
        libelle = f"{facture.get_type_facture_display()} {facture.numero} — {facture.tiers}"
        if facture.type_facture == "vente":
            journal = "ventes"
            lignes = [
                (COMPTE_CLIENTS, facture.montant_ttc, "0"),
                (COMPTE_VENTES, "0", facture.montant_ht),
            ]
            if facture.montant_tva > 0:
                lignes.append((COMPTE_TVA_COLLECTEE, "0", facture.montant_tva))
        else:
            journal = "achats"
            charge = COMPTE_CHARGE_PAR_NATURE.get(facture.nature_operation, "607")
            lignes = [
                (charge, facture.montant_ht, "0"),
                (COMPTE_FOURNISSEURS, "0", facture.net_a_payer),
            ]
            if facture.montant_tva > 0:
                lignes.append((COMPTE_TVA_DEDUCTIBLE, facture.montant_tva, "0"))
            if facture.retenue_source_montant > 0:
                lignes.append((COMPTE_RETENUES, "0", facture.retenue_source_montant))
        ecriture = EcritureComptable.objects.create(
            entreprise=entreprise, journal=journal, numero_piece=f"{facture.numero}",
            date=facture.date, libelle=libelle, statut="valide",
        )
        for numero, debit, credit in lignes:
            ecriture.lignes.create(
                compte=_compte(entreprise, numero), libelle=LIBELLE_RETENUE if numero == COMPTE_RETENUES else "",
                debit=debit, credit=credit,
            )
        facture.ecriture = ecriture
        facture.save(update_fields=["ecriture"])
        return ecriture, None
    except Exception as exc:  # pragma: no cover - garde-fou d'intégrité
        return None, str(exc)


def controles_conformite(factures):
    """Contrôles de conformité TEJ par facture. Retourne une liste de dicts."""
    resultats = []
    vus = set()
    for f in factures:
        ref = f"RS-{f.pk:06d}"
        points = []
        if not (f.tiers or "").strip():
            points.append({"niveau": "erreur", "message": "Le tiers est manquant."})
        if not (f.tiers_identifiant or "").strip():
            points.append({"niveau": "erreur", "message": "L'identifiant fiscal du tiers est manquant."})
        elif f.tiers_identifiant_type == "matricule" and not __import__("re").match(MATRICULE_RE, f.tiers_identifiant.strip()):
            points.append({"niveau": "erreur", "message": "Matricule fiscal invalide (attendu : 7 chiffres + 1 lettre, ex. 1234567A)."})
        if ref in vus:
            points.append({"niveau": "erreur", "message": "Référence de certificat en double."})
        vus.add(ref)
        net = _arr(f.montant_ttc - f.retenue_source_montant)
        if net != f.net_a_payer:
            points.append({"niveau": "avertissement", "message": f"Net servi {f.net_a_payer} ≠ TTC {f.montant_ttc} − retenue {f.retenue_source_montant}."})
        resultats.append({"facture_id": f.id, "numero": f.numero, "tiers": f.tiers, "points": points})
    return resultats


def construire_declaration_tej(entreprise, annee, mois):
    """Construit la déclaration TEJ mensuelle (CCT-RS-V2) depuis les factures d'achat validées.

    Retourne (xml|None, certificats, totaux, controles, erreur|None).
    """
    factures = (
        Facture.objects.filter(
            entreprise=entreprise, type_facture="achat", statut="valide",
            date__year=annee, date__month=mois, retenue_source_montant__gt=0,
        )
        .order_by("tiers", "date", "id")
    )
    if not factures.exists():
        return None, [], {}, [], "Aucune facture d'achat validée avec retenue à la source sur cette période."

    controles = controles_conformite(list(factures))
    erreurs = [c for c in controles if any(p["niveau"] == "erreur" for p in c["points"])]
    if erreurs:
        return None, [], {}, controles, f"Contrôle de conformité bloquant : facture {erreurs[0]['numero']} — {erreurs[0]['points'][0]['message']}"

    par_benef = {}
    for f in factures:
        key = (f.tiers_identifiant_type, (f.tiers_identifiant or "").strip())
        par_benef.setdefault(key, []).append(f)

    certificats = []
    total_ttc = Decimal("0")
    total_rs = Decimal("0")
    total_timbre = Decimal("0")
    for (id_type, id_value), items in par_benef.items():
        operations = []
        for f in items:
            operations.append({
                "numero": f.numero,
                "date": f.date.strftime("%Y-%m-%d"),
                "montant_ht": _millimes(f.montant_ht),
                "taux_rs": f"{f.retenue_source_taux:.2f}",
                "montant_ttc": _millimes(f.montant_ttc),
                "montant_rs": _millimes(f.retenue_source_montant),
                "montant_net_servi": _millimes(f.net_a_payer),
                "ref": f"RS-{f.pk:06d}",
            })
            total_ttc += f.montant_ttc
            total_rs += f.retenue_source_montant
            total_timbre += f.timbre_fiscal
        certificats.append({
            "tiers": items[0].tiers,
            "identifiant_type": id_type,
            "identifiant": id_value,
            "operations": operations,
        })

    xml = _serialiser(entreprise, annee, mois, certificats)
    totaux = {
        "nb_certificats": len(certificats),
        "nb_operations": len(factures),
        "total_ttc": str(_arr(total_ttc)),
        "total_retenue": str(_arr(total_rs)),
        "total_timbre": str(_arr(total_timbre)),
        "total_net": str(_arr(total_ttc - total_rs)),
    }
    return xml, certificats, totaux, controles, None


def _serialiser(entreprise, annee, mois, certificats):
    certs = []
    for c in certificats:
        tag = IDENTIFIANT_TAG_TEJ.get(c["identifiant_type"], "MatriculeFiscal")
        ops = "".join(
            f"""
          <Operation>
            <MontantHT>{o['montant_ht']}</MontantHT>
            <TauxRS>{o['taux_rs']}</TauxRS>
            <MontantTTC>{o['montant_ttc']}</MontantTTC>
            <MontantRS>{o['montant_rs']}</MontantRS>
            <MontantNetServi>{o['montant_net_servi']}</MontantNetServi>
          </Operation>"""
            for o in c["operations"]
        )
        certs.append(f"""
      <Certificat>
        <Beneficiaire>
          <IdTaxpayer>
            <{tag}>{_esc(c['identifiant'])}</{tag}>
          </IdTaxpayer>
        </Beneficiaire>
        <DatePayement>{c['operations'][0]['date']}</DatePayement>
        <Ref_certif_chez_declarant>{c['operations'][0]['ref']}</Ref_certif_chez_declarant>
        <ListeOperations>{ops}
        </ListeOperations>
      </Certificat>""")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<DeclarationsRS>\n"
        f"  <Declarant>{_esc(entreprise.raison_sociale)}</Declarant>\n"
        "  <ReferenceDeclaration>\n"
        "    <ActeDepot>AJOUT</ActeDepot>\n"
        f"    <AnneeDepot>{int(annee)}</AnneeDepot>\n"
        f"    <MoisDepot>{int(mois):02d}</MoisDepot>\n"
        "  </ReferenceDeclaration>\n"
        "  <AjouterCertificats>"
        + "".join(certs)
        + "\n  </AjouterCertificats>\n"
        "</DeclarationsRS>"
    )
