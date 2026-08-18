# Générateur de CV statique

CV statique, accessible et optimisé pour les ATS, moteurs de recherche et agents IA. Tout le contenu éditable se trouve dans `cv.yml`, créé localement à partir du modèle fictif [`cv.exemple.yml`](cv.exemple.yml).

## Mise à jour rapide

1. Lors de la première utilisation, créer la configuration locale :

```bash
make init
```

Cette commande ne remplace jamais un `cv.yml` existant.

2. Modifier `cv.yml` avec un éditeur de texte.
3. Exécuter :

```bash
make
```

Cette commande régénère et contrôle automatiquement :

- `index.html` : version web responsive et version imprimable ;
- `resume.json` : version structurée compatible JSON Resume ;
- `llms.txt` : version textuelle pour les agents IA ;
- `robots.txt` : règles d'exploration, avec ChatGPT Search autorisé et GPTBot bloqué ;
- `sitemap.xml` : URL canonique et date de mise à jour pour les moteurs de recherche ;
- `assets/cv-qr.svg` : QR code optionnel contenant la vCard ;
- le fichier défini par `meta.pdf_filename` : PDF A4 directement téléchargeable depuis le site.

Les profils déclarés dans `person.profiles` sont affichés avec leur pictogramme sur
le site. Le PDF conserve uniquement un lien vers le CV en ligne.

Ne pas modifier directement ces fichiers générés : leurs changements seraient remplacés à la prochaine génération. Le fichier `cv.yml` est ignoré par Git pour éviter de publier accidentellement les données personnelles ; seul le modèle entièrement fictif est versionné.

Le premier écran est stylé par `styles-critical.css`, automatiquement intégré dans `index.html`. Le reste de la mise en page est chargé sans bloquer le rendu depuis `styles.css`. Toute modification des couleurs ou de l’en-tête doit donc être faite dans `styles-critical.css`.

## Contenu de `cv.yml`

Le fichier est organisé en sections simples :

- `meta` : thème, date de mise à jour et identifiant Google Analytics ;
- `person` : identité, coordonnées, disponibilité et profils ;
- `profile` : présentation, spécialités et habilitation ;
- `experiences` : expériences récentes et antérieures ;
- `skills` : compétences techniques ;
- `certifications` : certifications et liens de vérification ;
- `education` : formations ;
- `languages` : langues ;
- `interests` : centres d’intérêt.

### Personnalisation initiale

Toutes les valeurs propres à une personne ou à son site sont centralisées dans `cv.yml`. Pour réutiliser le projet, commencer par modifier :

```yaml
meta:
  updated: 2026-08-18
  canonical_url: https://cv.example.com/
  pdf_filename: prenom-nom-cv.pdf
  pdf_pages: 2
  description: CV de {name}, spécialiste technique avec plus de {experience_years} ans d'expérience.
  analytics_id: G-XXXXXXXXXX

person:
  first_name: Prénom
  last_name: Nom
  birth_date: 1990-01-01
  eyebrow: Consultante indépendante
  photo: assets/portrait.jpg
```

`meta.updated` indique la dernière modification éditoriale du CV au format
`YYYY-MM-DD`. Le générateur l'utilise comme date ISO dans le sitemap et produit
automatiquement le `DateTime` avec fuseau requis par Google pour
`ProfilePage.dateModified`. L'ancien format mensuel `YYYY-MM` reste accepté et
est interprété comme le premier jour du mois.

`meta.pdf_pages` fixe le nombre exact de pages attendu par le contrôle PDF. Le nom du PDF, son lien de téléchargement, l’URL canonique, l’âge, la photo et ses variantes sont tous calculés depuis ces valeurs ; aucun changement dans les scripts n’est nécessaire.

Les libellés de l’objectif professionnel dans `llms.txt` sont configurables avec `profile.objective_title` et `profile.objective_label`.

Le téléphone est facultatif. Pour le masquer partout, conserver les deux champs vides :

```yaml
person:
  phone_display: ""
  phone_uri: ""
  phone_pdf_only: false
```

Pour le réactiver, renseigner à la fois le format affiché (`phone_display`) et le format international utilisé dans les liens (`phone_uri`).

Pour conserver le téléphone uniquement dans les coordonnées imprimées du PDF et
dans la vCard du QR code, utiliser :

```yaml
person:
  phone_display: "+33 6 12 34 56 78"
  phone_uri: "+33612345678"
  phone_pdf_only: true
```

Avec `phone_pdf_only: true`, le numéro n'est pas ajouté à la fenêtre de contact,
au JSON-LD, à `resume.json` ou à `llms.txt`. Il reste nécessairement présent dans
le code d'impression de la page HTML afin que Chromium puisse produire le PDF ;
le PDF étant public, cette option limite l'affichage mais ne protège pas le numéro
contre une extraction automatisée.

La disponibilité utilise un statut contrôlé et une période libre. La période vaut `sous 1 mois` par défaut, mais peut aussi contenir une date précise :

```yaml
person:
  availability: Ouvert aux opportunités
  availability_period: sous 1 mois
```

Valeurs autorisées pour `availability` : `En recherche active`, `Ouvert aux opportunités`, `Non disponible actuellement` ou une valeur vide. `availability_period` accepte une durée, une date ou une valeur vide. Chaque champ vide est automatiquement omis ; laisser les deux champs vides masque entièrement la disponibilité.

Le QR code vCard du PDF est désactivé par défaut. Il se contrôle avec `person.show_qr_code` :

```yaml
person:
  show_qr_code: false
```

La valeur `true` l’ajoute au PDF et génère `assets/cv-qr.svg`. La valeur `false` retire le QR code du PDF et supprime ce fichier des ressources publiées.

### Choisir un thème

Modifier simplement `meta.theme` au début de `cv.yml`. Ce champ contient uniquement la couleur :

```yaml
meta:
  theme: green
```

Couleurs disponibles :

- `blue` : bleu profond et cyan, couleur actuelle ;
- `green` : vert forêt et menthe ;
- `red` : bordeaux et corail ;
- `purple` : aubergine et lavande ;
- `amber` : brun profond et ambre.
- `grey` : gris ardoise clair et neutre ;

Le mode clair ou sombre n’est pas configuré dans `cv.yml`. Il suit automatiquement la préférence du navigateur (`prefers-color-scheme`). Sur le site, l’engrenage permet de choisir une autre couleur et le switch « Mode sombre » de remplacer localement cette préférence. Ces choix sont mémorisés uniquement dans le navigateur.

Après le changement, exécuter `make update`. La palette choisie s’applique au site et aux accents du PDF sans modifier la mise en page.

Pour ajouter un élément, dupliquer un bloc existant en respectant l’indentation YAML de deux espaces. Une expérience avec `compact: true` apparaît dans « Expériences antérieures », replié par défaut sur le web et automatiquement développé dans le PDF.

Dans `skills`, saisir chaque technologie comme un élément distinct de la liste `keywords`. Cette structure garantit un découpage propre dans `resume.json` :

```yaml
- name: Données & sauvegarde
  keywords: [MySQL, PostgreSQL, Veeam, NetBackup]
```

### Afficher ou masquer l’âge

Le champ `person.show_age` contrôle l’affichage de l’âge dans le site, le PDF et les métadonnées structurées :

```yaml
person:
  birth_date: 1990-01-01
  show_age: false
```

La valeur `false` masque l’âge sans supprimer la date de naissance du fichier source. La valeur `true` l’affiche.

### Édition avec Vim

`cv.yml` est enregistré en UTF-8, avec des apostrophes ASCII pour rester lisible dans les terminaux classiques. Le dépôt contient également un fichier `.editorconfig` qui fixe l’encodage et l’indentation.

Si les accents restent mal affichés, vérifier la locale puis ouvrir explicitement en UTF-8 :

```bash
locale
vim '+set encoding=utf-8 fileencoding=utf-8' cv.yml
```

La locale du terminal devrait être UTF-8, par exemple `C.UTF-8` ou `fr_FR.UTF-8`.

## Commandes

```bash
make init     # créer cv.yml depuis le modèle fictif, sans écraser un fichier existant
make install-browser # créer le venv et installer Playwright + son Chromium
make optimize-photo  # régénérer manuellement les variantes AVIF/WebP/JPEG du portrait
make build    # optimiser le portrait puis régénérer les fichiers
make check    # contrôler le CV et produire le PDF téléchargeable
make update   # build + check + PDF (commande exécutée par un simple make)
make sync     # récupérer Git sans conflit sur les fichiers générés, puis reconstruire
make serve    # prévisualiser sur http://localhost:8000
make pdf      # produire le PDF nommé dans meta.pdf_filename
```

Pour une photo matricielle (JPEG, PNG, WebP…), `make`, `make update`, `make build` et
`make check` créent automatiquement les variantes `-180` et `-360` utilisées par le
HTML. Seul le fichier indiqué dans `person.photo` doit donc être copié sur une nouvelle
installation. Un portrait SVG ne nécessite aucune variante.

Exécuter `make install-browser` une seule fois. Cette commande crée `.venv`, y installe les modules Python, télécharge le Chromium isolé géré par Playwright et installe ses bibliothèques Linux. L'installation des bibliothèques système demande les droits `root` ou `sudo`. Aucun Chrome ou Chromium système n'est requis. Playwright est obligatoire pour `make`, car le PDF téléchargeable est produit et contrôlé à chaque publication.

Pour relancer manuellement la même installation sur un serveur Linux minimal :

```bash
./.venv/bin/python -m playwright install --with-deps chromium
```

### Mettre à jour depuis Git

`index.html`, `resume.json`, `llms.txt` et, lorsqu’il est activé, le QR code sont générés pour permettre un déploiement statique. Après un `make build`, leurs changements peuvent bloquer un `git pull`. Utiliser `make sync` : il restaure uniquement ces sorties reproductibles, conserve les sources éditables (notamment `cv.yml`), effectue le pull avec autostash, puis régénère et contrôle le CV. Un conflit réel dans `cv.yml` reste volontairement signalé par Git.

## Prérequis

- Python 3.10 ou ultérieur ;
- le module `venv` de Python ;
- `qrencode` pour la vCard lorsque le QR code est activé ;
- `make`.

Sous Debian/Ubuntu :

```bash
sudo apt-get install python3-venv qrencode make
make install-browser
```

## Déploiement Apache

Après `make update`, copier les fichiers statiques générés et leurs ressources dans le dossier Apache souhaité. Tous les liens internes sont relatifs : le CV peut être installé à la racine ou dans un sous-dossier.

Fichiers nécessaires en production :

```text
index.html
.htaccess
<valeur de meta.pdf_filename>
styles.css
profile.js
contact.js
theme.js
resume.json
llms.txt
robots.txt
assets/
```

Le fichier `.htaccess` désactive le listing des dossiers, bloque l’accès aux sources du générateur, ajoute une politique CSP et les principaux en-têtes de sécurité, met les images en cache pendant 30 jours, puis interdit l’indexation de tous les PDF. Le virtual host Apache doit autoriser ces directives et charger `mod_headers` et `mod_rewrite`. Par exemple :

```apache
<Directory /var/www/cv>
    AllowOverride AuthConfig FileInfo Indexes Options=Indexes
    Require all granted
</Directory>
```

Après modification de la configuration Apache, vérifier puis recharger le service avec `apachectl configtest` et `systemctl reload apache2`.

`styles-critical.css` n’est pas nécessaire en production : son contenu est déjà intégré dans `index.html` pendant la génération.

Les sources `cv.yml`, `templates/`, `scripts/` et le `Makefile` ne sont pas nécessaires sur le serveur web.

Les pictogrammes sont stockés localement pour éviter toute dépendance au chargement. LinkedIn et GitHub proviennent de [Simple Icons](https://simpleicons.org/) et Malt de son [kit média officiel](https://newsroom.malt.com/media-kit-uk).

Le portrait original est celui indiqué par `person.photo`. Après son remplacement, exécuter `make optimize-photo`, puis `make update` pour reconstruire automatiquement les variantes responsives AVIF, WebP et JPEG à côté de ce fichier. Le modèle utilise `assets/portrait-placeholder.svg`, qui ne nécessite aucune optimisation.

## Contrôles automatiques

Le script [`scripts/check_cv.sh`](scripts/check_cv.sh) vérifie notamment :

- la validité du YAML, du JSON et du JSON-LD ;
- la synchronisation de toutes les sorties avec `cv.yml` ;
- la présence des ressources et l’absence de liens vers l’ancien CV ;
- le calcul automatique de l’âge ;
- les vues ordinateur, tablette et smartphone ;
- la présence de toutes les expériences dans le PDF ;
- l’ordre de lecture ATS ;
- le nombre exact de pages A4 défini par `meta.pdf_pages`, avec le Chromium isolé de Playwright.

Le même contrôle est exécuté automatiquement par GitHub Actions.
