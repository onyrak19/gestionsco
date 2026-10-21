# Frontend — Gestion Scolaire

Interface React (Create React App) pour le backend Django (`../backend`).

    npm install
    npm start          # développement : http://localhost:3000 (API sur le port 8000)
    npm run build      # compile vers frontend/build, servi ensuite par Django
    npm test

## Nouveautés (alignées sur le module `finance` du backend)

Menu **Finances** (administrateur) :
- `/admin/finances` — bilan (année ou période), rapport PDF
- `/admin/finances/encaissements` — situation de tous les élèves (impayés), cartes d'écolage, liste des impayés
- `/admin/finances/eleves/:inscription` — mois payés / non payés, encaissement avec montant calculé par le serveur (aperçu), reçu PDF, annulation avec motif
- `/admin/finances/paiements` — historique, reçus, annulations
- `/admin/finances/tarifs` — droit, écolage mensuel et autres frais par niveau (copie d'une année à l'autre)
- `/admin/finances/depenses`, `/entrees`, `/categories` — dépenses (dont imprévus), entrées d'argent, catégories
- `/admin/finances/employes`, `/salaires` — employés, paie individuelle ou en un clic, avances, retenues, situation exceptionnelle, fiches de paie, état des salaires

Autres changements : parents / tuteur sur la fiche élève (création et modification), impressions financières
dans l'écran « Impressions », lien « Écolage » dans le parcours de l'élève.
La devise (`DEVISE` dans le `.env` du backend, « Ar » par défaut) est lue via `/api/finance/parametres/`.
