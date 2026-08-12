"""Plan comptable tunisien standard : classes 1-7, comptes, sous-comptes, comptes enfants."""

PLAN_COMPTABLE_TUNISIEN = {
    "1": {"intitule": "Comptes de capitaux", "enfants": {
        "10": "Capital",
        "11": "Réserves",
        "12": "Report à nouveau",
        "13": "Résultat de l'exercice",
        "14": "Subventions d'équipement",
        "15": "Provisions",
        "16": "Emprunts et dettes de financement",
        "17": "Dépôts et cautionnements",
        "18": "Écart de conversion (actif / passif)",
    }},
    "2": {"intitule": "Comptes d'actifs (immobilisations)", "enfants": {
        "21": "Immobilisations incorporelles",
        "22": "Terrains",
        "23": "Constructions",
        "24": "Matériel et outillage",
        "25": "Autres immobilisations corporelles",
        "26": "Immobilisations financières",
        "27": "Amortissements des immobilisations",
    }},
    "3": {"intitule": "Comptes de stocks et en-cours", "enfants": {
        "31": "Marchandises",
        "32": "Matières premières et fournitures",
        "33": "Produits fabriqués",
        "34": "En-cours de production",
        "35": "Avances et acomptes versés sur commandes de stocks",
    }},
    "4": {"intitule": "Comptes de tiers", "enfants": {
        "40": {"intitule": "Fournisseurs et comptes rattachés", "enfants": {
            "401": "Fournisseurs locaux",
            "402": "Fournisseurs étrangers",
            "407": "Effets à payer aux fournisseurs",
            "408": "Fournisseurs — factures non parvenues",
        }},
        "41": "Effets à payer",
        "42": "Clients, avances et acomptes reçus",
        "43": {"intitule": "Clients et comptes rattachés", "enfants": {
            "431": "Clients",
            "432": "Clients étrangers",
            "437": "Effets à recevoir",
            "438": "Clients — factures à établir",
        }},
        "44": {"intitule": "État et organismes publics", "enfants": {
            "441": "État — impôts et taxes",
            "442": "État — TVA déductible",
            "443": "État — TVA collectée",
            "444": "État — impôts sur les sociétés",
            "445": "État — retenues à la source",
            "446": "État — patente",
            "448": "Charges à payer — État",
        }},
        "45": "Associés",
        "46": {"intitule": "Organismes sociaux", "enfants": {
            "461": "CNSS",
            "465": "Assurance groupe",
            "468": "Organismes sociaux — charges à payer",
        }},
        "47": "Comptes transitoires ou d'attente",
    }},
    "5": {"intitule": "Comptes de trésorerie", "enfants": {
        "52": "Titres de placement",
        "53": {"intitule": "Banques", "enfants": {
            "531": {"intitule": "Banque — compte courant", "enfants": {
                "5311": "Banque — compte courant en TND",
            }},
            "532": "Banque — compte épargne",
            "538": "Banque — frais",
        }},
        "54": {"intitule": "Caisse", "enfants": {
            "541": "Caisse principale",
        }},
        "58": "Chèques postaux (CCP)",
    }},
    "6": {"intitule": "Comptes de charges", "enfants": {
        "60": {"intitule": "Achats", "enfants": {
            "601": "Achats de matières premières",
            "602": "Achats de produits consommables",
            "603": "Achats de marchandises",
            "607": "Achats non stockés de matières et fournitures",
        }},
        "61": "Variation des stocks",
        "63": {"intitule": "Services extérieurs", "enfants": {
            "631": "Transports",
            "632": "Frais de publicité",
            "633": "Loyers",
            "634": "Entretien et réparations",
            "637": "Honoraires",
        }},
        "64": {"intitule": "Charges de personnel", "enfants": {
            "640": "Rémunérations du personnel",
            "641": "Charges sociales",
            "645": "Autres charges de personnel",
        }},
        "65": "Autres charges d'exploitation",
        "66": {"intitule": "Charges financières", "enfants": {
            "661": "Charges d'intérêts",
            "663": "Agios bancaires",
            "666": "Pertes de change",
        }},
        "67": "Charges exceptionnelles",
        "68": "Dotations aux amortissements, provisions et aux pertes de valeur",
    }},
    "7": {"intitule": "Comptes de produits", "enfants": {
        "70": {"intitule": "Ventes", "enfants": {
            "701": "Ventes de marchandises",
            "703": "Ventes de produits fabriqués",
            "707": "Prestations de services",
        }},
        "71": "Variation des stocks",
        "75": {"intitule": "Produits d'exploitation", "enfants": {
            "751": "Produits accessoires",
        }},
        "76": "Produits financiers",
        "77": "Produits exceptionnels",
        "78": "Reprises sur amortissements, provisions et pertes de valeur",
    }},
}


def seed_plan_comptable(entreprise):
    """Crée le plan comptable tunisien standard pour une entreprise (tenant)."""
    if entreprise.comptes.exists():
        return False

    def _seed(node, parent):
        for numero, item in node.items():
            if isinstance(item, str):
                entreprise.comptes.create(parent=parent, numero=numero, intitule=item)
            else:
                compte = entreprise.comptes.create(
                    parent=parent, numero=numero, intitule=item["intitule"]
                )
                _seed(item["enfants"], compte)

    _seed(PLAN_COMPTABLE_TUNISIEN, None)
    return True
