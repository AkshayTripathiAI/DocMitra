"""The DocMitra assistant: a LangGraph tool-calling agent over the user's documents."""
import logging
from datetime import date

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from ..config import settings
from .tools import ALL_TOOLS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are DocMitra, a friendly assistant that helps people in India \
manage personal paperwork: Aadhaar, PAN, driving licence, passport, vehicle RC, \
insurance and PUC.

Rules:
- Use the tools to look at the user's actual documents before answering. Never \
guess what they have.
- ID numbers are masked on purpose. Never ask the user to type a full Aadhaar \
or PAN number.
- For any government procedure, give the checklist from the tool and tell the \
user to confirm on the official portal, because rules and fees change.
- Point out expired or soon-expiring documents and name mismatches across \
documents, and offer to set reminders.
- Reply in the language of the user's latest message: English if they \
wrote in English, Hindi or Hinglish only if they did. Keep it short and practical.

Today is {today}."""


class LLMNotConfigured(RuntimeError):
    pass


class AssistantUnavailable(RuntimeError):
    """The model provider failed even after a retry."""


def _api_key() -> str | None:
    provider = settings.llm_model.split(":", 1)[0]
    return {
        "google_genai": settings.google_api_key,
        "anthropic": settings.anthropic_api_key,
        "groq": settings.groq_api_key,
    }.get(provider) or None


_assistant = None


def get_assistant(model=None):
    """The shared agent, built on first use. Passing `model` (tests) builds a fresh one."""
    global _assistant
    if model is not None:
        return _build(model)
    if _assistant is None:
        if not settings.llm_configured:
            raise LLMNotConfigured(
                f"No API key for {settings.llm_model}. Set it in backend/.env."
            )
        kwargs = {"api_key": key} if (key := _api_key()) else {}
        _assistant = _build(init_chat_model(settings.llm_model, **kwargs))
    return _assistant


def _build(model):
    return create_agent(
        model,
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT.format(today=date.today().isoformat()),
        checkpointer=InMemorySaver(),  # per-thread chat memory; resets on restart
        name="docmitra",
    )


def chat(message: str, thread_id: str, model=None) -> dict:
    agent = get_assistant(model)
    payload = {"messages": [{"role": "user", "content": message}]}
    config = {"configurable": {"thread_id": thread_id}}
    try:
        result = agent.invoke(payload, config=config)
    except Exception:
        # Model providers fail transiently (rate limits, 5xx). Retry once on the same thread so
        # chat memory is kept; at worst the model sees this question twice.
        logger.warning("Agent call failed; retrying once", exc_info=True)
        try:
            result = agent.invoke(payload, config=config)
        except Exception as exc:
            raise AssistantUnavailable("The assistant is temporarily unavailable. Please try again.") from exc
    messages = result["messages"]
    # Tool calls made while answering this message (after the last human turn).
    last_human = max(i for i, m in enumerate(messages) if m.type == "human")
    turn = messages[last_human + 1:]
    reply = next((m for m in reversed(turn) if isinstance(m, AIMessage)), None)
    return {
        "reply": _text(reply) if reply else "",
        "tools_used": [m.name for m in turn if isinstance(m, ToolMessage)],
    }


def _text(message: AIMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if isinstance(part, dict))
