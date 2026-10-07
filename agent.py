import asyncio
import logging
import os

from agents import (
    Agent,
    HostedMCPTool,
    Runner,
    set_default_openai_api,
    set_default_openai_client,
    set_tracing_disabled,
)
from dotenv import load_dotenv
from openai import AsyncOpenAI

from configs import API_KEY, BASE_URL, MODEL_ID
from prompts import AGENT_PROMPT

# === Environnement et logging (après tous les imports) ===
load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
for noisy in ("httpx", "httpcore", "openai._base_client", "asyncio"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("mcp-agent")
logging.getLogger("httpx").setLevel(logging.WARNING)

# === Constantes ===
MCP_URL = "https://learn.microsoft.com/api/mcp"
ALLOWED_TOOLS = {"microsoft_docs_search", "microsoft_docs_fetch"}
QUESTION = (
    "Give me the Azure CLI commands to create an Azure Container App "
    "with a managed identity."
)

# === Client async relié au SDK ===
set_tracing_disabled(True)
openai_client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
set_default_openai_client(openai_client, use_for_tracing=False)
set_default_openai_api("responses")


# === Callback d'approbation MCP ===
def approve_tool(request):
    name = request.data.name
    if name in ALLOWED_TOOLS:
        log.info("Appel MCP approuvé : %s", name)
        return {"approve": True}
    log.warning("Appel MCP refusé : %s", name)
    return {"approve": False, "reason": "Outil non autorisé"}


# === Outil MCP ===
mcp_tool = HostedMCPTool(
    tool_config={
        "type": "mcp",
        "server_label": "api-specs",
        "server_url": MCP_URL,
        "require_approval": "always",
    },
    on_approval_request=approve_tool,
)

# === Agent ===
agent = Agent(
    name="ExpenseClaimAgent",
    instructions=AGENT_PROMPT,
    model=MODEL_ID,
    tools=[mcp_tool],
)
log.info("Agent créé : %s (modèle : %s)", agent.name, MODEL_ID)


async def main() -> None:
    conversation = None
    try:
        conversation = await openai_client.conversations.create()
        log.info("Conversation créée : %s", conversation.id)

        log.info("Question envoyée à l'agent")
        result = await Runner.run(
            agent,
            QUESTION,
            conversation_id=conversation.id,
            max_turns=10,
        )
        log.debug("Réponse reçue (%d caractères)", len(str(result.final_output)))
        print(f"\nAgent response: {result.final_output}")
    except Exception:
        log.exception("Échec de l'exécution de l'agent")
        raise
    finally:
        if conversation is not None:
            await openai_client.conversations.delete(conversation.id)
            log.info("Conversation supprimée : %s", conversation.id)

if __name__ == "__main__":
    asyncio.run(main())
    