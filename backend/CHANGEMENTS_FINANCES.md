# Backend — module Finances (nouveautés)

> Le backend reçu ne contenait **aucun module de paiement, de salaire ni de cantine**.
> Il n'y avait donc pas de « bug d'encaissement » à corriger dans ce code : le module a été
> **créé** (app `finance`). Aucune trace de cantine n'existait côté backend (rien à retirer).

## Mise en route
```
pip install -r requirements.txt
python manage.py migrate          # school 0009, journal 0003, finance 0001-0002
python manage.py test finance     # tests du module
```
`.env` : `DEVISE=Ar` (facultatif, défaut « Ar »).

## Élèves : parents / tuteur
Champs ajoutés à `/api/school/eleves/` (POST/PUT/GET) : `parent_nom`, `parent_mobile`,
`parent2_nom`, `parent2_mobile` (facultatifs, mobile validé). Présents aussi dans l'import/export Excel.

## API Finances — `/api/finance/` (administrateur seulement)

| Besoin | Appel |
|---|---|
| Listes pour formulaires (types, modes, mois, devise) | `GET parametres/` |
| Tarifs par niveau | `GET tarifs/?annee=` · `PUT tarifs/` · `POST tarifs/copier/ {de, vers, ecraser}` |
| Situation de tous les élèves | `GET situations/?annee=&classe=&q=&statut=impayes\|a_jour&au=AAAA-MM` |
| Situation détaillée d'un élève (mois payés / non payés) | `GET inscriptions/<id>/situation/` |
| Encaisser | `POST paiements/` |
| Liste / détail / annulation / reçu PDF | `GET paiements/` · `GET paiements/<id>/` · `POST paiements/<id>/annuler/ {motif}` · `GET paiements/<id>/recu/?telecharger=1` |
| Catégories dépenses/entrées | `GET/POST categories/` · `PUT/DELETE categories/<id>/` (`?sens=depense\|entree`) |
| Dépenses, entrées, imprévus | `GET/POST mouvements/` · `PUT/DELETE mouvements/<id>/` |
| Employés | `GET/POST employes/` · `PUT/DELETE employes/<id>/` · `GET employes/<id>/situation/` |
| Avances | `GET/POST avances/` · `POST avances/<id>/annuler/` |
| Salaires | `GET/POST salaires/` · `POST salaires/groupe/` · `POST salaires/<id>/annuler/` · `GET salaires/<id>/fiche/` |
| Bilan | `GET bilan/?annee=` ou `?date_debut=&date_fin=` |
| Impressions PDF | `POST pdf/cartes-ecolage/` · `POST pdf/impayes/` · `POST pdf/rapport/` · `POST pdf/etat-salaires/` |
| Catalogue de TOUTES les impressions (menu unique) | `GET impressions/` |

### Tarifs
`PUT tarifs/` : `{annee, niveau, serie, droit_inscription, ecolage_mensuel, autres:[{libelle, montant}], appliquer_a_toutes_series}`
remplace la configuration du niveau. Si l'année n'a aucun tarif, `GET` renvoie ceux de l'année
précédente avec `propose: true` (non enregistrés).

### Encaisser (le montant n'est jamais saisi)
```json
POST /api/finance/paiements/
{"inscription": 12, "type": "ecolage", "mois": ["2026-09","2026-10"], "mode": "especes",
 "date": "2026-10-14", "reference": "", "observation": "", "apercu": false}
```
* `type` : `droit` | `ecolage` (avec `mois`) | `autre` (avec `tarif` = id du frais, voir `situation.autres`).
* `apercu: true` : renvoie lignes et total **sans enregistrer** (pour afficher le montant automatique).
* Erreurs 400 claires : tarif non défini, mois déjà payé, mois hors année, droit déjà payé.
* Réponse 201 : paiement avec `numero` (REC-AAAA-00001), `lignes`, `montant_total`. Reçu : `GET paiements/<id>/recu/`.

### Salaires
```json
POST /api/finance/salaires/
{"employe": 3, "mois": ["2025-12","2026-01","2026-02"], "mode": "especes",
 "autres_retenues": 50000, "motif_retenues": "Pénalité",
 "exceptionnel": false, "montant_exceptionnel": null, "motif_exceptionnel": "",
 "retenue_avance": null, "apercu": false}
```
* Montant = salaire de l'employé × nombre de mois (automatique).
* **Situation exceptionnelle** : `exceptionnel: true` + `montant_exceptionnel` + `motif_exceptionnel` (obligatoire).
* **Avances** : retenues automatiquement (les plus anciennes d'abord) ; `retenue_avance` pour imposer un montant.
  Annuler une paie rend les avances à nouveau dues.
* **Un clic** : `POST salaires/groupe/ {employes: [ids] | "tous", mois: [...], retenues: {"<id>": {montant, motif}}, apercu}`.
  Avec `apercu: true` : tableau récapitulatif (brut, avance retenue, net, erreurs) sans rien payer.

### Import / Export (écran existant `/api/school/export/` et `/import/`)
Nouveaux jeux : `tarifs`, `categories_finance`, `mouvements`, `paiements`, `employes` (import + export),
`salaires`, `avances` (export), `config_matieres` (import + export). Les élèves incluent les parents.

## Limites connues
* Code écrit sans pouvoir exécuter Django dans l'environnement de rédaction : lancez
  `python manage.py migrate` puis `python manage.py test finance school journal`, et
  `python manage.py makemigrations --check` (doit répondre « No changes detected »).
