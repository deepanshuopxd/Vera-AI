# reply_handler.py — Multi-turn reply handling with pattern detection (using OpenAI)

import json
import re
from openai import OpenAI
from config import LLM_API_KEY, LLM_MODEL, LLM_TEMPERATURE

client = OpenAI(api_key=LLM_API_KEY)

def handle_reply(conversation_id: str, merchant_id: str, customer_id: str,
                 from_role: str, message: str, turn_number: int,
                 history: list, contexts: dict) -> dict:
    """
    Handle a merchant/customer reply. Detects patterns first (fast path),
    falls back to LLM for complex replies.
    """
    message_lower = message.lower().strip()

    # 1. Auto-reply detection
    auto_result = _detect_auto_reply(message_lower, history)
    if auto_result: return auto_result

    # 2. Hostile / opt-out detection
    hostile_result = _detect_hostile(message_lower)
    if hostile_result: return hostile_result

    # 3. Intent transition (merchant commits)
    intent_result = _detect_intent_transition(message_lower, turn_number)
    if intent_result: return intent_result

    # 4. SLOW PATH: LLM-powered reply via Grok
    return _llm_reply(conversation_id, merchant_id, customer_id, from_role, message, history, contexts)

def _detect_auto_reply(message_lower: str, history: list) -> dict | None:
    auto_signals = [
        "thank you for contacting", "our team will respond", "automated message",
        "automated reply", "auto-reply", "we will get back to you",
        "thanks for reaching out", "your message is important"
    ]
    if not any(signal in message_lower for signal in auto_signals):
        return None

    auto_count = sum(
        1 for h in history
        if h.get("from") in ("merchant", "customer")
        and any(s in h.get("message", "").lower() for s in auto_signals)
    )

    if auto_count >= 3:
        return {"action": "end", "rationale": f"Auto-reply {auto_count}x — no real engagement. Closing."}
    elif auto_count >= 2:
        return {"action": "wait", "wait_seconds": 86400, "rationale": f"Auto-reply {auto_count}x — Wait 24h."}
    else:
        return {
            "action": "send",
            "body": "Looks like an auto-reply 😊 When the owner sees this, just reply 'Yes' to continue.",
            "cta": "binary_yes_no",
            "rationale": "First auto-reply detected; prompting actual owner."
        }

def _detect_hostile(message_lower: str) -> dict | None:
    hard_stop = ["stop messaging", "unsubscribe", "block", "report spam"]
    soft_stop = ["not interested", "don't contact", "stop", "no thanks", "leave me alone"]
    hostile = ["useless", "spam", "waste of time", "shut up", "go away"]

    if any(s in message_lower for s in hard_stop):
        return {"action": "end", "rationale": "Merchant explicitly opted out (hard stop). Closing."}
    if any(s in message_lower for s in hostile):
        return {
            "action": "send",
            "body": "Apologies for the inconvenience — I won't message again. 🙏",
            "cta": "none",
            "rationale": "Hostile response detected. Brief apology, then closing."
        }
    if any(s in message_lower for s in soft_stop):
        return {"action": "end", "rationale": "Merchant signaled not interested. Closing gracefully."}
    return None

def _detect_intent_transition(message_lower: str, turn_number: int) -> dict | None:
    commit_signals = [
        "let's do it", "lets do it", "ok do it", "go ahead",
        "proceed", "let's go", "yes do it", "confirm",
        "haan karo", "kar do", "chalo", "yes please"
    ]
    if turn_number >= 2 and any(s in message_lower for s in commit_signals):
        return {
            "action": "send",
            "body": "Great — working on it now. Will have the draft ready in under a minute. Reply CONFIRM to send.",
            "cta": "binary_confirm_cancel",
            "rationale": "Merchant explicitly committed. Switching to action mode."
        }
    return None

def _llm_reply(conversation_id: str, merchant_id: str, customer_id: str,
               from_role: str, message: str, history: list, contexts: dict) -> dict:
    history_str = ""
    for h in history[-6:]:
        role = h.get("from", "unknown")
        msg = h.get("message", "")[:200]
        history_str += f"  [{role}]: {msg}\n"

    merchant_data = contexts.get(("merchant", merchant_id), {}).get("payload", {})
    merchant_name = merchant_data.get("identity", {}).get("name", "the merchant")

    prompt = f"""You are Vera, magicpin's AI assistant. Continue this WhatsApp conversation.

CONVERSATION SO FAR:
{history_str}
LATEST MESSAGE from {from_role}: "{message}"

MERCHANT: {merchant_name}

RULES:
- Keep response concise (WhatsApp format)
- Don't re-introduce yourself
- Advance the conversation toward a useful outcome

Respond with ONLY this JSON:
{{"action": "send", "body": "your reply", "cta": "open_ended", "rationale": "why this reply"}}
OR {{"action": "wait", "wait_seconds": 1800, "rationale": "why waiting"}}
OR {{"action": "end", "rationale": "why ending"}}"""

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.choices[0].message.content
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            return json.loads(match.group())
    except Exception as e:
        pass

    return {
        "action": "send",
        "body": "Got it — let me work on that. Will update you shortly.",
        "cta": "open_ended",
        "rationale": "Fallback reply — acknowledged and advancing."
    }
