# ==== LES IMPORTS ====
import os
import sys
import asyncio
import json
import logging  

from contextlib import AsyncExitStack
from dotenv import load_dotenv  
from openai import AsyncOpenAI
from openai.types.responses.response_input_param import FunctionCallOutput, ResponseInputParam

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from prompts import ASSISTANT_PROMPT
from configs import BASE_URL, API_KEY, MODEL_ID

# === Environnement et logging (après tous les imports) ===
load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
for noisy in ("httpx", "httpcore", "openai._base_client", "asyncio"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("mcp-client")

MAX_TOOL_ROUNDS = 10

# Clear the console
os.system('cls' if os.name == 'nt' else 'clear')


async def connect_to_server(exit_stack: AsyncExitStack):
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["server.py"],
        env=None
    )

    # === Start the MCP server ===
    log.info("Démarrage du serveur MCP (stdio) : %s server.py", sys.executable)  # ← logging
    stdio_transport = await exit_stack.enter_async_context(stdio_client(server_params))
    stdio, write = stdio_transport

    # Create an MCP client session
    session = await exit_stack.enter_async_context(ClientSession(stdio, write))
    await session.initialize()

    # === List available tools ===
    response = await session.list_tools()
    tools = response.tools
    log.info("Connecté au serveur MCP, outils : %s", [tool.name for tool in tools])  # ← logging

    return session


async def chat_loop(session):

    # Connect to the OpenAI client
    client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)

    # Get the mcp tools available from the server
    response = await session.list_tools()
    tools = response.tools

    # Build a function for each tool
    def make_tool_func(tool_name):
        async def tool_func(**kwargs):
            result = await session.call_tool(tool_name, kwargs)
            return result

        tool_func.__name__ = tool_name
        return tool_func

    # Store the functions in a dictionary for easy access when processing function calls
    functions_dict = {tool.name: make_tool_func(tool.name) for tool in tools}

    # Create function tool definitions (format API Responses)
    mcp_function_tools = []
    for tool in tools:
        mcp_function_tools.append({
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
            "strict": False,
        })

    # "Agent" : défini localement, passé à chaque appel
    agent = {
        "model": MODEL_ID,
        "instructions": ASSISTANT_PROMPT,
        "tools": mcp_function_tools,
    }
    log.info("Agent configuré (modèle : %s, %d outils)", MODEL_ID, len(mcp_function_tools))  # ← logging

    # Create a conversation for the chat session
    conversation = await client.conversations.create()
    log.info("Conversation créée : %s", conversation.id)  # ← logging

    try:
        while True:
            user_input = input("Enter a prompt for the inventory agent. Use 'quit' to exit.\nUSER: ").strip()
            if user_input.lower() == "quit":
                log.info("Fin de la session par l'utilisateur")  # ← logging
                break
            if not user_input:  # ← évite d'envoyer un message vide
                continue

            log.debug("Message utilisateur (%d caractères)", len(user_input))  # ← logging
            input_list: ResponseInputParam = [{"role": "user", "content": user_input}]

            for round_no in range(1, MAX_TOOL_ROUNDS + 1):
                log.debug("Appel au modèle (tour %d)", round_no)  # ← logging
                response = await client.responses.create(
                    **agent,
                    conversation=conversation.id,
                    input=input_list,
                )

                # Check the run status for failures
                if response.status == "failed":
                    log.error("Réponse en échec : %s", response.error)  # ← logging
                    break

                # === Process function calls ===
                input_list = []
                for item in response.output:
                    if item.type == "function_call":
                        log.info("Appel d'outil : %s %s", item.name, item.arguments)  # ← logging
                        required_function = functions_dict.get(item.name)
                        if required_function is None:
                            log.warning("Outil inconnu demandé par le modèle : %s", item.name)  # ← logging
                            text = f"Outil inconnu : {item.name}"
                        else:
                            try:  # ← logging : une erreur d'outil ne doit pas tuer le chat
                                output = await required_function(**json.loads(item.arguments))
                                text = "\n".join(c.text for c in output.content if hasattr(c, "text"))
                                log.debug("Résultat de %s : %d caractères", item.name, len(text))
                            except Exception:
                                log.exception("Échec de l'outil %s", item.name)
                                text = f"Erreur lors de l'exécution de l'outil {item.name}"

                        input_list.append(
                            FunctionCallOutput(
                                type="function_call_output",
                                call_id=item.call_id,
                                output=text,
                            )
                        )

                # Pas d'appel d'outil -> c'est la réponse finale
                if not input_list:
                    print(f"Agent response: {response.output_text}")
                    break
            else:
                log.warning("Limite de %d tours d'outils atteinte, arrêt", MAX_TOOL_ROUNDS)  # ← logging

    finally:
        # Clean up
        log.info("Nettoyage de la conversation %s", conversation.id)  
        await client.conversations.delete(conversation.id)


async def main():
    exit_stack = AsyncExitStack()
    try:
        session = await connect_to_server(exit_stack)
        await chat_loop(session)
    except Exception:  
        log.exception("Erreur fatale dans le client MCP")
        raise
    finally:
        await exit_stack.aclose()


if __name__ == "__main__":
    asyncio.run(main())