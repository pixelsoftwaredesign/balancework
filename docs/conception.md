# Conception — Balance And Tax Safety

Architecture MVC en 3 couches et modèle de sécurité.

- Projet : Django 6 / Python 3.12, SQLite (dev) / MySQL (prod, Railway), Cloudflare Pages (front statique).
- Docs liés : `README.md`.

---

## 1. Vue d'ensemble

Le produit est un SaaS du cabinet comptable : site vitrine + prise de RDV + demande de devis,
un **espace client** (dossiers, déclarations, préfactures, messages) et une **back-office admin**
(gestion clients, dossiers, comptabilité, personnel, staff).

Front : HTML/CSS/JS statique (deployé sur Cloudflare Pages), qui consomme une API JSON Django
(deployée sur Railway). Aucun rendu côté serveur pour les modules applicatifs.

```
┌───────────────────────────────┬──────────────────────────────┐
│        PRÉSENTATION          │        APPLICATION           │
│  (views / contrôleurs)       │        (services)            │
│  core/views.py               │  core/security/*             │
│  static/js/*  (client/admin) │  core/services/*             │
│  templates/*                 │  core/mail.py                │
└──────────────┬───────────────┴──────────────┬───────────────┘
               │  HTTP JSON                   │
               ▼                              ▼
┌──────────────────────────────────────────────────────────────┐
│                   PERSISTANCE (data)                        │
│  core/models.py  (ORM Django / MySQL / SQLite)              │
│  core/plan_comptable.py  (seed)                             │
└──────────────────────────────────────────────────────────────┘
```

### Répartition des responsabilités (3 couches)

| Couche | Rôle | Ne fait PAS |
|---|---|---|
| **Présentation** `core/views.py` | Parser HTTP, validation du jeton, appeler le service, sérialiser la réponse JSON | Logique métier, requêtes complexes, règles de sécurité |
| **Application / Services** `core/services/*`, `core/security/*` | Logique métier et sécurité : RBAC, throttling, comptabilité, flux auth | Manipuler `request`/`response` de façon métier, formater l'HTML |
| **Persistance** `core/models.py` | Modèles ORM, contraintes DB, migrations | Règles métier transverses |

Contrat : une vue ne contient plus que de l'orchestration ; toute règle de fond est testée
dans un service (injection de `request` limitée aux fonctions d'infrastructure : IP, header).

---

## 2. Architecture MVC

### 2.1 Modèles (M)

`core/models.py` — tous les modèles Django :

- **Site / acquisition** : `Service` (hiérarchique), `DevisRequest`, `Appointment`, `Message`
- **Clients & dossiers** : `Client` (OneToOne `User`), `ClientServiceSuivi` (dossier),
  `DossierTask`, `DossierAttachment`, `ClientMessage`, `ServiceFollowUp`, `DeclarationFiscale`,
  `Prefacture`, `Payment`, `Collaborateur`
- **Comptabilité (tenant)** : `Entreprise` (OneToOne `Client`), `CompteComptable` (arbre),
  `EcritureComptable`, `LigneEcriture`
- **Sécurité** : `AuthToken` (client), `StaffProfile`/`StaffToken` (RBAC admin), `SecurityLog`

Contraintes métier portées par le modèle : compte `PROTECT` sur les lignes d'écriture,
`unique_together` (entreprise, numéro), écriture équilibrée (`est_equilibree`).

### 2.2 Vues / contrôleurs (C/V)

`core/urls.py` route vers `core/views.py` :

- API publique : `/api/services`, `/api/availability`, `/api/contact`, `/api/devis`, `/api/rendezvous`
- API client : `/api/auth/*`, `/api/client/*`
- API admin : `/api/admin/*` (jeton Bearer + RBAC)
- Pages statiques : `TemplateView` sur les gabarits

### 2.3 Vues du front (statiques)

`templates/*.html` + `static/js/*.js` : `admin.js` (back-office, onglets par ressource +
comptabilité + staff), `client.js` (espace client), `main.js` (site public).

---

## 3. Modèle de sécurité

### 3.1 Principes

1. **API sans session** : toutes les API applicatives sont token-based (Bearer).
   Le `CSRF` n'est donc pas requis pour ces routes (`csrf_exempt`) — le token porteur
   joue le rôle de preuve d'identité. La protection CSRF reste active pour toute page
   Django servant du HTML (site vitrine).
2. **Jetons jamais loggés** : seuls des préfixes tronqués (`key[:12]`) sont affichés.
3. **Comparaison à temps constant** du jeton admin statique (`hmac.compare_digest`).
4. **Journal de sécurité** (`SecurityLog`) : connexions (ok/échec), inscriptions,
   jetons créés/révoqués/expirés, throttling, staff créé, rôle modifié.
5. **Toutes les écritures `log_security` sont silencieuses** (ne font jamais échouer une requête).

### 3.2 RBAC admin (`core/security/rbac.py`)

Rôles (niveaux) :

| Rôle | Niveau | Exemples d'accès |
|---|---|---|
| `admin` | 100 | Tout + gestion du staff |
| `gestionnaire` | 80 | Clients, dossiers, personnel, finances |
| `comptable` | 60 | Plan comptable, écritures, grand-livre, bilan, préfactures, paiements |
| `lecture` | 40 | Consultation uniquement |

- Jeton statique `ADMIN_TOKEN` = super-admin (niveau 1000), conservé comme passe-partout.
- `StaffToken` : jeton Bearer rattaché à un `StaffProfile` (rôle + actif), expiration 7 jours,
  révocable, `last_used_at` suivi.
- `require_level(min_level)` : 401 sans jeton, 403 si privilèges insuffisants.
- Matrice par table dans `ACCESS_LEVELS` (lecture / écriture) :
  `comptes`/`ecritures` (60/60), `entreprises` (40/60), `payments`/`prefactures` (60/80),
  `collaborateurs` (80/100), reste (40/80).

### 3.3 Authentification espace client (`core/security/auth_service.py`)

- `User` Django : mots de passe hachés (PBKDF2/Argon2 par défaut), jamais renvoyés.
- **Politique de mot de passe** : ≥ 8 caractères, ≥ 1 lettre, ≥ 1 chiffre, pas trop répétitif.
- **Throttling** (`core/security/throttle.py`) : après 5 échecs en 15 min (par e-mail **ou** IP)
  sur le login, réponse `429` et événement `throttled` journalisé.
- **Jeton** : `AuthToken` — expiration 30 jours (configurable `CLIENT_TOKEN_TTL_DAYS`),
  rotation à chaque login, `last_used_at` mis à jour, jeton expiré supprimé.
- Côté client (`client.js`) : en cas de `401`, la session est nettoyée et l'utilisateur
  invité à se reconnecter.

### 3.4 Transport & production

- HTTPS via Cloudflare : `SECURE_SSL_REDIRECT`, HSTS, `SESSION_COOKIE_SECURE`,
  `CSRF_COOKIE_SECURE`, `SECURE_CONTENT_TYPE_NOSNIFF`, `SECURE_REFERRER_POLICY`.
- IP client derrière proxy : `HTTP_X_FORWARDED_FOR` dans `security/audit.client_ip`.

---

## 4. Comptabilité (domaine phare)

- **Tenant** : chaque `Entreprise` (client du cabinet) possède son propre plan comptable
  tunisien (classes 1-7 hiérarchisées), seedé par `core/plan_comptable.py` (idempotent).
- **Écritures** : journaux `od/ventes/achats/banque/caisse`, pièces équilibrées
  (total débit = total crédit), statut `brouillon`/`valide`.
- **États** : seules les écritures **validées** alimentent le grand-livre, la balance,
  le bilan (actif = classes 2/3/4-débiteur/5 ; passif = 1/4-créditeur/résultat)
  et le compte de résultat (classe 7 − classe 6).
- Toute la logique vit dans `core/services/comptabilite.py` (couche service) ;
  les vues ne font que de la sérialisation JSON.
- Niveaux d'accès : lecture comptable → niveau 60 minimum.

### 4.1 Espace entreprise (tenant)

- Page publique `/espace-entreprise/` (`templates/espace_entreprise.html` +
  `static/js/espace_entreprise.js`) : le client connecté gère la comptabilité
  **de sa propre entreprise** (plan comptable éditable, pièces/journaux, grand
  livre, bilan) et retrouve ses dossiers + déclarations (même contenu que
  l'espace client).
- API unique `POST/GET/DELETE /api/client/comptabilite`
  (`core/views.py:api_client_comptabilite`), scotée au client :
  - **GET** → `{entreprise, plan (arbre), plan_total, ecritures, grand_livre, bilan}`,
    avec `bilan = {bilan: {actif, passif, total_actif, total_passif}, resultat: {...}}`.
  - **POST** → actions `ecriture_create`, `ecriture_statut`, `compte_create`, `compte_update`.
  - **DELETE** → `{kind: "ecriture"|"compte", id}` ; comptes protégés s'ils portent
    des écritures (`ProtectedError` → 400) ou s'ils ont des enfants.
- Isolation tenant : toutes les requêtes sont filtrées par `entreprise=client.entreprise` ;
  un client sans entreprise reçoit 404 ; les comptes d'une autre entreprise sont introuvables.
- Testé de bout en bout (`EspaceEntrepriseComptabiliteTests` : auth, 404 sans
  entreprise, pièce équilibrée→bilan, pièce déséquilibrée refusée, comptes protégés,
  non-intrusion entre entreprises).

### 4.2 Facturation tenant

- Modèle `Facture` (`core/models.py`) : vente/achat, n° et date, tiers + identifiant
  fiscal (matricule/CIN/passeport/carte de séjour), nature d'opération, HT/TVA/TTC,
  droit de timbre, retenue à la source, net à payer, statut (brouillon/validée/annulée).
- Service `core/services/facturation.py` :
  - `calculer_montants` : TVA, TTC, **droit de timbre 1 DT si TTC ≥ 1 000 DT** (LF 2022),
    **retenue = (TTC − timbre) × taux** (jamais le HT), net = TTC − retenue ; seuil de
    1 000 DT TTC pour les acquisitions (Art. 52 Code IRPP/IS).
  - `sync_ecriture` / `creer_ecriture` : la validation d'une facture génère
    **automatiquement une écriture comptable équilibrée** :
    - vente → 431 (clients, TTC) / 707 (HT) / 443 (TVA collectée) ;
    - achat → compte de charge (607/637/633/65 selon nature) / 401 (fournisseurs, net)
      / 442 (TVA déductible) / 445 (retenues à la source).
  - Annulation d'une facture ⇒ suppression de l'écriture ; une facture dont l'écriture
    est validée ne peut être modifiée/annulée sans repasser l'écriture en brouillon.
- API `POST/GET /api/client/factures` (tenant) + table admin `factures` (RBAC 40/60).

### 4.3 Conformité & export TEJ (retenue à la source)

- **TEJ** = plateforme `tej.finances.gov.tn` (Art. 41 LF 2022) : déclaration mensuelle
  des retenues à la source avant le **28 du mois suivant**, fichier XML **CCT-RS-V2`.
- `facturation.construire_declaration_tej` : regroupe les factures d'achat **validées
  avec retenue** du mois par bénéficiaire → un `<Certificat>` par tiers, avec
  `<IdTaxpayer>` (exactement un identifiant : MatriculeFiscal/CIN/Passeport/CarteSejour),
  `Ref_certif_chez_declarant` unique, et des opérations dont les montants sont en
  **millimes entiers** ; `MontantNetServi = MontantTTC − MontantRS`.
- `facturation.controles_conformite` (bloquants avant export) : tiers/identifiant requis,
  format du matricule (`\d{7}[A-Z]`), références uniques, cohérence net = TTC − retenue.
- API `GET /api/client/tej?mois=AAAA-MM` : renvoie controles + certificats + totaux +
  le XML ; refuse (400) tant qu'une facture est non conforme. L'onglet TEJ de l'espace
  entreprise permet de vérifier puis de **télécharger le XML** (`Blob`).

---

## 5. Refactor en 3 couches — état

| Fichier | Couche | Contenu |
|---|---|---|
| `core/views.py` | Présentation | Orchestration HTTP, JSON, sérialisation |
| `core/security/auth_service.py` | Application | register / login / logout / policy mot de passe |
| `core/security/rbac.py` | Application | niveaux de rôle, `require_level` |
| `core/security/tokens.py` | Application | jetons Bearer, TTL, comparaison constante |
| `core/security/throttle.py` | Application | limitation des tentatives |
| `core/security/audit.py` | Application | journal de sécurité + IP client |
| `core/services/comptabilite.py` | Application | plan, grand-livre, bilan, résultat |
| `core/services/facturation.py` | Application | TVA, timbre, retenue, écritures auto, XML TEJ |
| `core/models.py` | Persistance | modèles + contraintes |
| `core/plan_comptable.py` | Persistance | seed du plan comptable |

### Règles du refactor (à suivre pour les nouvelles fonctionnalités)

1. Pas de logique métier dans les vues : appeler un service (`core/services/` ou `core/security/`).
2. Les services n'émettent pas de réponse HTTP ; ils renvoient des structures/objets.
3. Toute règle de sécurité va dans `core/security/` ; toute règle de domaine dans `core/services/`.
4. Accès aux données uniquement via l'ORM dans la couche persistance ; les services
   restent agnostiques du moteur de stockage.

---

## 6. Fichiers de sécurité clés

- `core/security/__init__.py` — point d'entrée du package sécurité
- `core/security/rbac.py` — `require_level`, `role_level_for_request`, `role_levels`
- `core/security/tokens.py` — `bearer_token`, `admin_token_ok`, `client_token_for_request`,
  `staff_token_for_request`, `new_client_token`, `new_staff_token`
- `core/security/auth_service.py` — `password_policy_errors`, `register`, `login`, `logout`
- `core/security/throttle.py` — `record_failure`, `is_throttled`
- `core/security/audit.py` — `log_security`, `client_ip`
- `core/services/comptabilite.py` — `plan_tree`, `plan_init`, `grand_livre`, `bilan`
- Endpoints RBAC : `api_admin_staff`, `api_admin_staff_token`, `api_admin_security_log`
  (niveau 100), routeés dans `core/urls.py`.
