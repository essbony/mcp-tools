# AI Agent Tool MCP

Projet Python de démonstration autour du **Model Context Protocol (MCP)** et de l'API OpenAI Responses.

Le dépôt montre deux approches complémentaires :

1. **Un serveur MCP local** exposant des outils d'inventaire (`server.py`).
2. **Un client/agent** capable d'appeler ces outils pour répondre à des questions métier (`client.py`).
3. **Un agent avec outil MCP hébergé** connecté à Microsoft Learn MCP (`agent.py`).

---

## Fonctionnalités

- Serveur MCP local basé sur `fastmcp`.
- Outils métier simples :
  - consultation des niveaux de stock ;
  - consultation des ventes hebdomadaires.
- Client interactif en ligne de commande.
- Intégration avec l'API OpenAI Responses.
- Gestion des appels d'outils MCP avec boucles multi-tours.
- Exemple d'agent utilisant un MCP distant : `https://learn.microsoft.com/api/mcp`.
- Configuration par variables d'environnement via `.env`.
- Logging configurable avec `LOG_LEVEL`.

---

## Structure du projet

```text
.
├── agent.py          # Agent utilisant un serveur MCP hébergé Microsoft Learn
├── client.py         # Client interactif connecté au serveur MCP local
├── configs.py        # Chargement des variables d'environnement
├── prompts.py        # Prompts système utilisés par les agents
├── server.py         # Serveur MCP local exposant les outils d'inventaire
├── pyproject.toml    # Métadonnées et dépendances du projet
├── requirements.txt  # Dépendances Python pour installation pip
├── test.py           # Tests/diagnostic du serveur MCP local
├── Dockerfile        # Image Docker du projet
├── docker-compose.yml # Services Docker Compose
├── .env.example      # Exemple de configuration sans secret
├── .gitignore        # Fichiers à exclure de Git
├── README.md         # Documentation du projet
└── __init__.py       # Fichier d'initialisation du package
```

> Le dossier `__pycache__/` est généré automatiquement par Python et ne doit pas être versionné.

---

## Prérequis

- Python **3.13+** d'après `pyproject.toml`.
- Une clé API compatible avec l'API OpenAI Responses.
- Un environnement virtuel Python recommandé.

---

## Installation

### Option 1 — avec `pip`

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Option 2 — avec `uv`

```bash
uv sync
```

---

## Configuration

Créez un fichier `.env` à la racine du projet :

```env
MODEL_ID=votre-modele
BASE_URL=https://api.openai.com/v1
API_KEY=votre-cle-api
LOG_LEVEL=INFO
OPENAI_AGENTS_DISABLE_TRACING=true
```

### Variables utilisées

| Variable | Description |
|---|---|
| `MODEL_ID` | Identifiant du modèle à utiliser. |
| `BASE_URL` | URL de base de l'API compatible OpenAI. |
| `API_KEY` | Clé API. |
| `LOG_LEVEL` | Niveau de logs : `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `OPENAI_AGENTS_DISABLE_TRACING` | Désactive le tracing des agents si défini à `true`. |

> Ne committez jamais votre fichier `.env` s'il contient des secrets.

---

## Utilisation

### 1. Lancer le client MCP local

Le fichier `client.py` démarre automatiquement `server.py` en sous-processus via stdio.

```bash
python client.py
```

Vous pouvez ensuite poser des questions à l'agent, par exemple :

```text
Quels produits dois-je réapprovisionner ?
Quels produits devraient être mis en liquidation ?
Analyse l'inventaire et les ventes de la semaine.
```

Pour quitter :

```text
quit
```

### 2. Lancer uniquement le serveur MCP local

En général ce n'est pas nécessaire, car `client.py` le lance automatiquement. Pour le tester seul :

```bash
python server.py
```

Le serveur expose deux outils MCP :

| Outil | Description |
|---|---|
| `get_inventory_levels` | Retourne les niveaux de stock actuels. |
| `get_weekly_sales` | Retourne les ventes de la dernière semaine. |

### 3. Lancer l'agent avec MCP Microsoft Learn

```bash
python agent.py
```

Cet agent utilise le serveur MCP hébergé Microsoft Learn :

```text
https://learn.microsoft.com/api/mcp
```

Il autorise uniquement les outils suivants :

- `microsoft_docs_search`
- `microsoft_docs_fetch`

La question envoyée par défaut demande les commandes Azure CLI pour créer une Azure Container App avec une identité managée.

---

## Logique métier de l'assistant inventaire

Le prompt dans `prompts.py` définit les règles suivantes :

- recommander un **réapprovisionnement** si :
  - stock `< 10` ;
  - ventes hebdomadaires `> 15`.
- recommander une **liquidation** si :
  - stock `> 20` ;
  - ventes hebdomadaires `< 5`.

Exemples attendus avec les données actuelles :

- Réapprovisionnement probable : `Moisturizer`, `Shampoo`, `Skin Serum`.
- Liquidation probable : `Body Spray`, `Cleanser`.

---

## Description des fichiers

### `server.py`

Crée un serveur MCP nommé `Inventory` avec `FastMCP`.

Il expose :

- `get_inventory_levels()` : retourne un dictionnaire produit → stock.
- `get_weekly_sales()` : retourne un dictionnaire produit → ventes hebdomadaires.

### `client.py`

Client interactif qui :

1. démarre `server.py` via stdio ;
2. initialise une session MCP ;
3. récupère la liste des outils disponibles ;
4. transforme les outils MCP en fonctions utilisables par l'API Responses ;
5. crée une conversation ;
6. gère les appels d'outils demandés par le modèle ;
7. affiche la réponse finale à l'utilisateur.

### `agent.py`

Exemple d'agent utilisant le package `openai-agents` avec un `HostedMCPTool`.

Il se connecte au MCP Microsoft Learn, approuve uniquement certains outils, exécute une question prédéfinie, puis supprime la conversation.

### `configs.py`

Charge la configuration depuis `.env` :

```python
MODEL_ID = os.getenv("MODEL_ID")
BASE_URL = os.getenv("BASE_URL")
API_KEY = os.getenv("API_KEY")
```

### `prompts.py`

Contient les prompts utilisés par :

- l'assistant inventaire local ;
- l'agent MCP générique.

---

## Dépendances principales

- `openai<3`
- `openai-agents`
- `mcp`
- `fastmcp`
- `python-dotenv`
- `uvicorn`

Certaines dépendances Azure sont présentes dans `pyproject.toml` mais commentées dans `requirements.txt`.

---

## Remarques de développement

- `client.py` limite les appels d'outils à `MAX_TOOL_ROUNDS = 10` pour éviter les boucles infinies.
- Les logs verbeux de `httpx`, `httpcore`, `openai._base_client` et `asyncio` sont réduits.
- Le fichier `.env` doit rester local.
- Pensez à ajouter `__pycache__/`, `.env` et `.venv/` dans `.gitignore` si ce n'est pas déjà fait.

---

## Commandes utiles

```bash
# Installer les dépendances
pip install -r requirements.txt

# Lancer le client interactif local
python client.py

# Lancer l'agent Microsoft Learn MCP
python agent.py

# Activer les logs détaillés
LOG_LEVEL=DEBUG python client.py
```

---

## Licence

Aucune licence n'est définie pour le moment.
