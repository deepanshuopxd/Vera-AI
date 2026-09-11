# composer.py — LLM-powered message composition engine (using OpenAI)

import json
import re
from openai import OpenAI
from config import LLM_API_KEY, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS

client = OpenAI(api_key=LLM_API_KEY)

# ──────────────────────────────────────────
# SYSTEM PROMPT (Vera's identity + rules)
# ──────────────────────────────────────────
SYSTEM_PROMPT = """You are Vera, magicpin's merchant-AI assistant on WhatsApp.

RULES — ALWAYS FOLLOW:
1. Use data from the contexts provided — NEVER fabricate numbers, names, or citations
2. Use the merchant's preferred language (Hindi-English code-mix if languages include "hi")
3. Keep messages concise for WhatsApp — no long preambles
4. Use ONE clear CTA at the end (binary YES/STOP preferred, or open-ended)
5. Never use taboo words from the category voice rules
6. For customer-facing messages: send as merchant, not as Vera
7. Anchor on SPECIFIC verifiable facts: numbers, dates, source citations
8. Peer/colleague tone — NOT promotional ("AMAZING DEAL!")
9. Reference the trigger's "why now" clearly
10. Use the merchant's owner first name when available

OUTPUT FORMAT — respond with ONLY this JSON:
{
  "body": "the WhatsApp message text",
  "cta": "binary_yes_no | binary_confirm_cancel | open_ended | multi_choice_slot | none",
  "rationale": "1-2 sentences: why this message, what lever it uses, what it should achieve"
}"""

def compose_message(category: dict, merchant: dict, trigger: dict, customer: dict = None) -> dict:
    """
    Compose a WhatsApp message using all 4 contexts + LLM.
    Returns: {"body": str, "cta": str, "rationale": str}
    """
    user_prompt = _build_prompt(category, merchant, trigger, customer)

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
        )

        raw = response.choices[0].message.content
        result = _parse_llm_response(raw)

        # Post-LLM validation
        result = _validate_output(result, category, merchant, customer)
        return result

    except Exception as e:
        # Fallback: return a safe generic message on failure
        name = merchant.get("identity", {}).get("owner_first_name",
               merchant.get("identity", {}).get("name", "there"))
        return {
            "body": f"Hi {name}, quick update — I have something relevant for your business. Reply YES to hear more.",
            "cta": "binary_yes_no",
            "rationale": f"LLM error fallback: {str(e)[:80]}"
        }

def _build_prompt(category: dict, merchant: dict, trigger: dict, customer: dict = None) -> str:
    """Build a rich prompt from all 4 contexts."""
    identity = merchant.get("identity", {})
    perf = merchant.get("performance", {})
    cat_voice = category.get("voice", {})
    offers = [o.get("title") for o in merchant.get("offers", []) if o.get("status") == "active"]
    signals = merchant.get("signals", [])
    digest = category.get("digest", [])
    peer_stats = category.get("peer_stats", {})
    cust_agg = merchant.get("customer_aggregate", {})

    trigger_kind = trigger.get("kind", "unknown")
    trigger_payload = trigger.get("payload", {})
    trigger_scope = trigger.get("scope", "merchant")

    prompt = f"""COMPOSE A WHATSAPP MESSAGE for the following scenario:

=== CATEGORY: {category.get("slug", "unknown")} ===
Voice tone: {cat_voice.get("tone", "professional")}
Taboo words: {cat_voice.get("vocab_taboo", cat_voice.get("taboos", []))}
Peer stats: avg_rating={peer_stats.get("avg_rating", "?")}, avg_ctr={peer_stats.get("avg_ctr", "?")}
Active offers in catalog: {json.dumps(offers[:3]) if offers else "none"}
Digest items: {json.dumps([{"title": d.get("title"), "source": d.get("source")} for d in digest[:3]])}
Seasonal beats: {json.dumps(category.get("seasonal_beats", [])[:2])}
Trend signals: {json.dumps(category.get("trend_signals", [])[:2])}

=== MERCHANT ===
Name: {identity.get("name", "?")}
Owner first name: {identity.get("owner_first_name", "?")}
City: {identity.get("city", "?")}, Locality: {identity.get("locality", "?")}
Languages: {identity.get("languages", ["en"])}
Subscription: {merchant.get("subscription", {}).get("status", "?")}
Performance (30d): views={perf.get("views", "?")}, calls={perf.get("calls", "?")}, ctr={perf.get("ctr", "?")}
7d delta: views {perf.get("delta_7d", {}).get("views_pct", "?")}%, calls {perf.get("delta_7d", {}).get("calls_pct", "?")}%
Active offers: {offers}
Customer aggregate: {json.dumps(cust_agg)}
Signals: {signals}

=== TRIGGER (why message NOW) ===
Kind: {trigger_kind}
Scope: {trigger_scope}
Source: {trigger.get("source", "?")}
Urgency: {trigger.get("urgency", "?")}
Payload: {json.dumps(trigger_payload)}
"""

    if customer:
        cust_identity = customer.get("identity", {})
        cust_rel = customer.get("relationship", {})
        prompt += f"""
=== CUSTOMER (message goes to this person ON BEHALF of merchant) ===
Name: {cust_identity.get("name", "?")}
Language pref: {cust_identity.get("language_pref", "en")}
State: {customer.get("state", "?")}
Last visit: {cust_rel.get("last_visit", "?")}
Visits total: {cust_rel.get("visits_total", "?")}
NOTE: This is a CUSTOMER-FACING message. send_as = "merchant_on_behalf".
Use the merchant's name, not "Vera". Honor the customer's language preference.
"""
    else:
        prompt += """
=== NO CUSTOMER (merchant-facing message from Vera) ===
This is a MERCHANT-FACING message. send_as = "vera".
"""

    prompt += "\nCompose the message now. Return ONLY the JSON."
    return prompt

def _parse_llm_response(raw: str) -> dict:
    """Extract JSON from LLM response."""
    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            data = json.loads(match.group())
            return {
                "body": data.get("body", ""),
                "cta": data.get("cta", "open_ended"),
                "rationale": data.get("rationale", "")
            }
        except json.JSONDecodeError:
            pass
    return {"body": raw.strip(), "cta": "open_ended", "rationale": "LLM response parsed as plain text"}

def _validate_output(result: dict, category: dict, merchant: dict, customer: dict = None) -> dict:
    """Post-LLM validation and fixes."""
    valid_ctas = {"binary_yes_no", "binary_confirm_cancel", "open_ended", "multi_choice_slot", "none"}
    if result.get("cta") not in valid_ctas:
        result["cta"] = "open_ended"

    taboos = category.get("voice", {}).get("vocab_taboo", category.get("voice", {}).get("taboos", []))
    body_lower = result.get("body", "").lower()
    for taboo in taboos:
        if taboo.lower() in body_lower:
            result["body"] = result["body"].replace(taboo, "***")
            result["rationale"] += f" [WARNING: removed taboo word '{taboo}']"

    return result
