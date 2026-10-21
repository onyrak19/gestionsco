# Gestion Scolaire

Application de gestion d'un établissement scolaire, de la petite section à la terminale :
années, classes, matières et coefficients, élèves, inscriptions, enseignants, notes,
bulletins, cartes d'élève, certificats de scolarité et fiches d'appel.

- **backend/** : API Django + Django REST Framework (authentification JWT, PDF avec ReportLab)
- **frontend/** : interface React

Nouveautés des versions 5 et 6 : photo d'élève et pièces jointes (facultatives), un seul enseignant par matière
et par classe, saisie des notes élève par élève, section **Impressions** (bulletins, cartes d'élève, certificats,
fiches d'appel, par classes), **import / export Excel**, journal d'activité (traçabilité, historique replié
sur l'accueil), accès depuis tous les appareils du Wi-Fi et interface entièrement redessinée (thème sombre et clair).

Deux rôles : **administrateur** (gère tout, saisit et consulte les notes de toutes les classes)
et **enseignant** (s'inscrit, est validé par un administrateur, puis saisit les notes de ses classes/matières).

## Mise en ligne

Voir **DEPLOY.md** (hébergement gratuit sur Render : Dockerfile et `render.yaml` fournis).

## Installation

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows   (Linux/Mac : source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # Linux/Mac : cp .env.example .env   puis adapter les valeurs
python manage.py migrate
python manage.py createsuperuser # ce compte est automatiquement administrateur
python manage.py runserver
```

Base de données : SQLite par défaut (rien à installer). Pour MySQL, mettez `DB_ENGINE=mysql` dans `.env`
(créez la base `gestion_scolaire_v1`) et installez aussi `pip install -r requirements-mysql.txt`.
En ligne (Render), la base PostgreSQL est branchée automatiquement : voir **DEPLOY.md**.

### Frontend

```bash
cd frontend
npm install
npm start                        # http://localhost:3000
```

L'adresse de l'API est détectée automatiquement (voir `frontend/.env.example`).

## Utilisation en réseau local (Wi-Fi)

Tous les appareils connectés au même Wi-Fi (téléphones, tablettes, autres ordinateurs) peuvent utiliser
l'application, sans rien installer : seul le PC qui l'héberge doit rester allumé.

**Méthode simple (recommandée)** — depuis le dossier du projet :

```bash
python lancer_reseau.py
```

Le script compile l'interface si nécessaire (Node.js requis sur ce PC), démarre le serveur et affiche
l'adresse à ouvrir sur les autres appareils, par exemple `http://192.168.1.20:8000`.
Une seule adresse, un seul programme. Après une modification du code de l'interface, relancez simplement le script.

**Méthode développement** — deux terminaux : `python manage.py runserver 0.0.0.0:8000` dans `backend`,
et `npm start` dans `frontend` ; les autres appareils ouvrent `http://<adresse du PC>:3000`.

À savoir :
- Le PC et les autres appareils doivent être sur le **même réseau Wi-Fi**.
- **Pare-feu Windows** : à la première exécution, autorisez Python sur les « réseaux privés ». Si besoin,
  ouvrez le port 8000 (et 3000 en méthode développement).
- L'adresse IP du PC peut changer ; réservez-lui une adresse fixe dans votre box si possible.
- Ce mode (`RESEAU_LOCAL`, actif tant que `DJANGO_DEBUG=True`) convient à un réseau de confiance, pas à internet.
- L'application est en `http` : n'y saisissez pas de données depuis un réseau Wi-Fi public.

### Mise à jour d'une installation existante

`pip install -r requirements.txt` (dépendances : ReportLab, **Pillow** pour les photos) puis `python manage.py migrate`
(migrations : photo et pièces jointes, journal d'activité, une seule affectation par matière et par classe).
**Sauvegardez la base avant de migrer.** Nouvelle dépendance : **openpyxl** (fichiers Excel).
Si des matières ont déjà plusieurs enseignants dans une même classe, `migrate` n'échoue pas et ne supprime rien :
il liste les cas et l'écran **Affectations** les signale « à corriger » (retirez les enseignants en trop).
Les photos et pièces jointes sont stockées dans `backend/media/` (à inclure dans vos sauvegardes, dossier réglable
avec `MEDIA_ROOT`).
Les données existantes sont conservées : les inscriptions reçoivent un numéro d'ordre par classe,
les matières sans code reçoivent un code automatique, les matricules existants ne changent pas.
Les anciennes classes (sans niveau) restent utilisables ; modifiez-les (bouton crayon) pour leur donner un niveau
et activer la configuration des matières et les règles de passage.

## Mise en route (première utilisation)

1. Connectez-vous avec le compte créé par `createsuperuser`.
2. **Établissement** : renseignez le nom, l'adresse, la ville et le directeur (en-tête des PDF).
3. **Années scolaires** : créez l'année et activez-la.
4. **Matières** : créez les matières avec leur coefficient par défaut (modifiable à tout moment avec **Modifier**).
5. **Classes** : choisissez le niveau (de « Petite section » à « Terminale », ou saisissez-le),
   la série en Première/Terminale (L, S, OSE ou autre) et le numéro de la classe.
   Cliquez sur **Matières** : cochez les matières enseignées et fixez leurs coefficients.
   Cette configuration s'applique à **toutes les classes de même niveau** (et de même série en
   Première/Terminale) pour l'année.
6. **Élèves** (photo facultative) puis **Inscriptions** (pièces jointes facultatives : acte de naissance,
   certificat…) : l'année en cours est sélectionnée automatiquement ; le numéro dans
   la classe (1er inscrit = n°1) et le matricule sont attribués automatiquement.
7. Les enseignants créent un compte (« Créer un compte » sur la page de connexion) ; validez-les dans
   **Enseignants**, puis donnez-leur des **Affectations** (à redéfinir chaque année). Une matière n'a **qu'un seul enseignant par classe** :
   pour en changer, utilisez « Changer d'enseignant » (ou « Remplacer » dans le formulaire).
8. Saisie des notes (enseignants pour leurs classes, administrateur pour toutes) et consultation dans **Relevés de classe**.

## Saisie des notes

Après avoir choisi la classe, la matière et le trimestre, deux façons de saisir :

- **Vue tableau** : tous les élèves d'un coup, dans les cases.
- **Commencer la saisie** : un seul élève à l'écran, du n° 1 au dernier (avec sa photo s'il en a une).
  Tapez J1, **Entrée**, J2, **Entrée**… ; **Enregistrer et suivant** (ou Entrée dans le dernier champ) enregistre
  automatiquement puis affiche le numéro suivant. Les pastilles numérotées permettent de revenir à un élève.
  Une note hors de 0–20 bloque le passage au suivant ; aucune requête n'est envoyée si rien n'a changé.

## Import / Export Excel

Menu **Documents et données → Import / Export Excel** (administrateur).

- **Exporter** : « Toutes les données » (un classeur, une feuille par type : élèves, inscriptions, classes, années,
  matières, enseignants, affectations, notes avec moyennes, résultats et rangs, journal) ou « Choisir les données ».
  Filtres facultatifs : année, classes, trimestre. Une feuille « Résumé » récapitule l'export. Les mots de passe ne sont jamais exportés.
- **Importer** : choisissez le type (élèves, matières, classes, inscriptions, notes, affectations), téléchargez le
  **modèle Excel** (colonnes + mode d'emploi), remplissez-le, puis déposez le fichier. **Vérifier le fichier** montre
  exactement ce qui sera créé, mis à jour ou refusé (avec le numéro de ligne de chaque erreur) **sans rien enregistrer** ;
  ensuite seulement, **Importer**. Chaque ligne suit les mêmes règles que la saisie à l'écran (année clôturée, notes de 0 à 20,
  un seul enseignant par matière…). S'il y a des erreurs, rien n'est importé, sauf si vous cochez « Importer quand même les lignes valides ».
- Les doublons sont ignorés (élève déjà présent, classe déjà créée…). Dans un import de notes, une case vide ne modifie pas la note existante.
- Un export peut être ré-importé tel quel (les colonnes calculées sont ignorées). Format `.xlsx` uniquement, 5 Mo et 20 000 lignes au maximum.
- Chaque export et import est inscrit dans le journal d'activité.

## Thème

Bouton lune / soleil en bas du menu : thème sombre ou clair (mémorisé sur chaque appareil ; par défaut, celui de l'appareil).

## Journal d'activité (traçabilité)

**Administration → Journal d'activité** (administrateur) liste, du plus récent au plus ancien, tout ce qui se passe :
connexions et échecs de connexion, notes saisies ou modifiées (ancienne → nouvelle valeur), inscriptions, pièces jointes,
élèves, classes, matières, affectations, années (clôture), comptes enseignants, impressions de PDF.
Exemple : « Enseignant Jean Martin a saisi la note de Marie Dupont (n° 3) en SVT — 3ème 1, 2026-2027, 1er trimestre : J1 = 12 ».
Filtres : texte libre, utilisateur, catégorie, action, année, dates ; actualisation automatique possible.
Le journal est en ajout seulement : aucune modification ni suppression n'est possible depuis l'application.
Pour des raisons de confidentialité, un identifiant de connexion inconnu n'est jamais recopié dans le journal.

## Règles de gestion

- **Moyenne d'une matière** = (moyenne de J1/J2/J3 + examen) / 2. Une note à 0 compte ; une case vide non.
- **Moyenne générale** d'un trimestre = moyenne pondérée par les coefficients configurés pour le niveau/série.
  **Moyenne annuelle** = moyenne des trimestres.
- **Clôture d'une année** : demande le mot de passe de l'administrateur, calcule la moyenne annuelle de chaque
  élève et le classe **passant** (moyenne ≥ 10, réglable avec `SEUIL_PASSAGE`) ou **redoublant**.
  Sans note : « à décider » (à indiquer dans le dossier de l'élève). La décision peut être corrigée à la main.
  Une année clôturée n'est plus modifiable.
- **Inscription en classe supérieure** : un élève *passant* doit s'inscrire dans le niveau juste au-dessus
  (Seconde → Première → Terminale, en gardant sa série) ; un *redoublant* doit refaire le même niveau ;
  l'année précédente doit être clôturée. Un nouvel élève peut entrer dans n'importe quel niveau.
- Un élève ne peut être inscrit que dans **une seule classe par année**.

## Impressions (PDF)

Cartes d'élève (avec QR code et photo), bulletins (par trimestre, avec photo), certificats de scolarité, fiches d'appel
(par classe, pour la semaine choisie). Menu **Impressions** : choisissez le document (bulletins, cartes d'élève,
certificats de scolarité ou fiches d'appel), l'année, puis une, plusieurs ou toutes les classes : un seul PDF réunit
tous les documents. Depuis **Inscriptions** ou la fiche d'une classe : sélectionnez des
élèves ou « tout sélectionner ». Depuis le dossier d'un élève : documents de n'importe quelle année.
Les listes se trient par ordre alphabétique ou par numéro.

## Tests

```bash
cd backend  && python manage.py test        # DB_ENGINE=sqlite recommandé
cd frontend && npm test -- --watchAll=false
```

## Mise en production

Dans `backend/.env` : `DJANGO_DEBUG=False`, une `DJANGO_SECRET_KEY` aléatoire,
`RESEAU_LOCAL=False`, `DJANGO_ALLOWED_HOSTS` et `CORS_ALLOWED_ORIGINS` avec votre domaine, un mot de passe
MySQL non vide. Servez l'API derrière HTTPS. Les photos et pièces jointes ne sont jamais publiques : elles
ne sont délivrées qu'à un utilisateur connecté et autorisé.
