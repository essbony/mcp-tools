"""
Tests/diagnostic local du projet AI Agent Tool MCP.

Ce script ne fait pas d'appel au modèle LLM et n'utilise pas votre clé API.
Il vérifie principalement que le serveur MCP local démarre, expose les bons outils
et retourne les données d'inventaire attendues.

Utilisation :
    python test.py
"""

import asyncio
import json
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


EXPECTED_TOOLS = {"get_inventory_levels", "get_weekly_sales"}


class TestFailure(Exception):
    """Erreur levée quand un test échoue."""


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise TestFailure(message)


def print_ok(message: str) -> None:
    print(f"✅ {message}")


def print_info(message: str) -> None:
    print(f"ℹ️  {message}")


def extract_tool_data(result: Any) -> Any:
    """
    Extrait les données retournées par un outil MCP.

    Selon les versions de mcp/fastmcp, le résultat peut être disponible dans :
    - structured_content / structuredContent ;
    - content[0].text sous forme JSON ;
    - directement dans un objet Python.
    """
    structured = getattr(result, "structured_content", None)
    if structured is None:
        structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured

    content = getattr(result, "content", None)
    if content:
        texts = []
        for item in content:
            text = getattr(item, "text", None)
            if text is not None:
                texts.append(text)

        if texts:
            raw_text = "\n".join(texts).strip()
            try:
                return json.loads(raw_text)
            except json.JSONDecodeError:
                return raw_text

    return result


async def test_mcp_server() -> None:
    """Démarre server.py en stdio et teste ses outils MCP."""
    server_path = Path("server.py")
    assert_true(server_path.exists(), "server.py est introuvable")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
        env=None,
    )

    async with AsyncExitStack() as exit_stack:
        print_info("Démarrage du serveur MCP local...")
        stdio_transport = await exit_stack.enter_async_context(stdio_client(server_params))
        stdio, write = stdio_transport

        session = await exit_stack.enter_async_context(ClientSession(stdio, write))
        await session.initialize()
        print_ok("Serveur MCP initialisé")

        tools_response = await session.list_tools()
        tool_names = {tool.name for tool in tools_response.tools}

        assert_true(
            EXPECTED_TOOLS.issubset(tool_names),
            f"Outils MCP attendus manquants. Attendus={EXPECTED_TOOLS}, reçus={tool_names}",
        )
        print_ok(f"Outils MCP disponibles : {sorted(tool_names)}")

        inventory_result = await session.call_tool("get_inventory_levels", {})
        sales_result = await session.call_tool("get_weekly_sales", {})

        inventory = extract_tool_data(inventory_result)
        sales = extract_tool_data(sales_result)

        assert_true(isinstance(inventory, dict), "get_inventory_levels doit retourner un dictionnaire")
        assert_true(isinstance(sales, dict), "get_weekly_sales doit retourner un dictionnaire")
        assert_true(len(inventory) > 0, "L'inventaire ne doit pas être vide")
        assert_true(len(sales) > 0, "Les ventes ne doivent pas être vides")
        assert_true(set(inventory) == set(sales), "Les produits d'inventaire et de vente doivent correspondre")

        print_ok(f"Inventaire chargé : {len(inventory)} produits")
        print_ok(f"Ventes chargées : {len(sales)} produits")

        restock = [
            product
            for product, quantity in inventory.items()
            if quantity < 10 and sales.get(product, 0) > 15
        ]
        clearance = [
            product
            for product, quantity in inventory.items()
            if quantity > 20 and sales.get(product, 0) < 5
        ]

        assert_true("Moisturizer" in restock, "Moisturizer devrait être recommandé en réapprovisionnement")
        assert_true("Shampoo" in restock, "Shampoo devrait être recommandé en réapprovisionnement")
        assert_true("Body Spray" in clearance, "Body Spray devrait être recommandé en liquidation")
        assert_true("Cleanser" in clearance, "Cleanser devrait être recommandé en liquidation")

        print_ok(f"Produits à réapprovisionner : {restock}")
        print_ok(f"Produits à liquider : {clearance}")


def test_project_files() -> None:
    """Vérifie la présence des fichiers principaux du projet."""
    required_files = [
        "agent.py",
        "client.py",
        "configs.py",
        "prompts.py",
        "server.py",
        "requirements.txt",
        "README.md",
        "Dockerfile",
        "docker-compose.yml",
        ".dockerignore",
    ]

    for file_name in required_files:
        assert_true(Path(file_name).exists(), f"Fichier manquant : {file_name}")

    print_ok("Tous les fichiers principaux sont présents")


def main() -> None:
    print("\n=== Tests locaux AI Agent Tool MCP ===\n")

    try:
        test_project_files()
        asyncio.run(test_mcp_server())
    except TestFailure as exc:
        print(f"\n❌ TEST ÉCHOUÉ : {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"\n❌ ERREUR INATTENDUE : {type(exc).__name__}: {exc}")
        sys.exit(1)

    print("\n🎉 Tous les tests sont passés avec succès.\n")


if __name__ == "__main__":
    main()
