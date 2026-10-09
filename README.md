# infra-backup

Système de sauvegarde déclarative de l'infrastructure personnelle.

## Lancement manuel

```bash
python infrabackup.py
```

Execution à blanc
```bash
python infrabackup.py --dry-run
```

---

## Concept

L'objectif n'est **pas** de cloner des machines, mais de capturer leur **état déclaratif** : ce qu'il faut pour les reconstruire. Tout est stocké en **texte brut dans un repo Git**, ce qui permet :

- de voir exactement ce qui a changé entre deux sauvegardes (`git diff`)
- de conserver un historique daté de chaque machine (`git log`)
- de retrouver l'état d'avant un changement problématique (`git checkout`)

---

## Architecture

```
PC Fixe Ubuntu (orchestrateur)
│
├── SSH  → MediaCenter (CoreELEC)
├── SSH  → Autres machines Linux
├── HTTP → Routeur (export config)
└── local → lui-même (pas de SSH)

         ↓

    backup/ (repo Git)
         ↓
    push vers repo distant
```

Le PC Fixe est l'unique orchestrateur. Il se connecte en SSH (ou HTTP) à toutes les autres machines, collecte les informations, génère les rapports, et commite le tout dans le repo Git.

---

## Structure des fichiers

```
InfraBackup/                   # Application
├── README.md                  # Ce fichier — spec + manuel
├── infrabackup.py             # Orchestrateur principal
└── tools/
    ├── reports.py             # Catalogue centralisé des rapports disponibles
    ├── ssh.py                 # Fonctions SSH
    ├── files.py               # Copie de fichiers distants (rsync)
    ├── git_watch.py           # Surveillance des repos Git
    └── runner.py              # Wrapper subprocess / mode dry-run

backup/                        # Destination : dépôt Git distinct
├── pc-fixe.toml                # Config du PC Fixe (exécution locale)
├── mediacenter.toml            # Config du MediaCenter CoreELEC
├── printing3d.toml             # Config de l'imprimante 3D
├── pc-fixe/
│   ├── files/                 # Fichiers copiés
│   └── reports/               # Rapports générés (texte brut)
├── mediacenter/
│   ├── files/
│   └── reports/
└── printing3d/
    └── files/
```

> Le dossier `backup/` doit être initialisé comme repo Git (`git init`) et avoir un remote configuré.

Dans `infrabackup.py`, `OUTPUT_DIR` définit la destination (actuellement `/home/moi/GIT/backup`)
et `CONFIG_DIR = OUTPUT_DIR` place les configurations à sa racine. Adapter `OUTPUT_DIR`
au chemin du dépôt `backup` sur la machine qui exécute l'application.

---

## Fonctionnement

`infrabackup.py` itère sur les fichiers `*.toml` à la racine de `CONFIG_DIR`, sans parcourir les sous-dossiers, charge chacun, puis exécute automatiquement les modules selon ce qui est défini :

| Clé TOML définie et non vide | Module exécuté |
|------------------------------|---------------|
| `files` | `tools/files.py` — copie les fichiers via rsync |
| `reports` | `tools/reports.py` — exécute les commandes et sauvegarde la sortie |
| `git_repos` | `tools/git_watch.py` — vérifie l'état de chaque repo Git |

À la fin de chaque machine, les changements dans `backup/<machine>/` sont commités dans Git avec un message horodaté.

---

## Format d'un fichier `.toml`

```toml
# Identification de la machine
name = "mediacenter"         # Nom du dossier dans backup/
host = "192.168.1.50"        # IP ou hostname. "localhost" pour le PC Fixe
user = "root"                # Utilisateur SSH

# Fichiers à copier depuis la machine distante
files = [
    "/storage/.kodi/userdata/guisettings.xml",
    "/storage/.kodi/userdata/sources.xml",
    "/storage/.kodi/userdata/favourites.xml",
    "/storage/.kodi/userdata/passwords.xml",
    "/storage/.config/autostart.sh",
]

# Rapports à générer (noms définis dans tools/reports.py)
reports = [
    "kodi-addons",
    "services",
    "disques",
]

# Repos Git à surveiller sur cette machine
git_repos = [
    "/storage/repos/mon-repo",
]
```

---

## Catalogue des rapports disponibles (`tools/reports.py`)

| Nom | Commande | Usage |
|-----|---------|-------|
| `apt-manual` | `apt-mark showmanual` | Liste des paquets installés manuellement (Ubuntu/Debian) |
| `apt-versions` | `dpkg-query -W --showformat=...` | Idem avec versions |
| `flatpak` | `flatpak list --app --columns=name,version` | Applications Flatpak |
| `snap` | `snap list` | Applications Snap |
| `services` | `systemctl list-units --type=service --state=running` | Services actifs |
| `docker` | `docker ps --format ...` | Containers Docker en cours avec version d'image |
| `disques` | `df -h` | Utilisation des disques |
| `reseau` | `ip addr && ip route` | Configuration réseau |
| `materiel` | `lshw -short` | Inventaire matériel |
| `partitions` | `lsblk` | Partitionnement des disques |
| `crontab` | `crontab -l` | Tâches cron de l'utilisateur |
| `gnome` | `dconf dump /` | Configuration GNOME complète |
| `kodi-addons` | `ls /storage/.kodi/addons/` | Liste des addons Kodi installés |

Pour ajouter un rapport : ajouter une entrée dans `REPORT_CATALOG` dans `tools/reports.py`.

---

## Surveillance Git (`GIT_REPOS`)

Pour chaque repo listé dans `GIT_REPOS`, le script vérifie et rapporte :

- **Modifications non commitées** (`git status --short`)
- **Commits locaux non poussés** (`git log @{u}.. --oneline`)
- **Commits distants non tirés** (`git fetch` + `git log ..@{u} --oneline`)

Le rapport est sauvegardé dans `backup/<machine>/reports/git-status.txt`.

---

## Ajout d'une machine

1. Créer `<nom>.toml` à la racine du dépôt `backup` en s'inspirant des exemples
2. Relancer `python infrabackup.py`

Aucune modification des scripts nécessaire.

---

## Initialisation du repo Git de sortie

```bash
cd /home/moi/GIT/backup/
git init
git remote add origin <url-de-ton-repo-distant>
```

## Sécurité

- Les clés SSH vers les machines cibles doivent être configurées sur le PC Fixe (`~/.ssh/config`)
- **Ne jamais commiter de secrets en clair** : mots de passe, tokens, clés privées
- Les fichiers `passwords.xml` (Kodi) ou `.env` (Docker) copiés dans `backup/` doivent être listés dans `.gitignore` ou chiffrés avant commit
- Le repo Git distant doit être **privé**
