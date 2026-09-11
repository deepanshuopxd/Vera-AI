import os, time, json, uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Any, Optional

from composer import compose_message
from reply_handler import handle_reply as process_reply

app = FastAPI(title="Vera Bot")
START = time.time()

# In-memory stores
contexts: dict[tuple[str, str], dict] = {}    # (scope, context_id) -> {version, payload}
conversations: dict[str, list] = {}           # conversation_id -> [turns]

# ──────────────────────────────────────────
# Endpoint 1 : GET /v1/healthz
# ──────────────────────────────────────────
@app.get("/v1/healthz")
async def healthz():
    counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
    for (scope, _), _ in contexts.items():
        counts[scope] = counts.get(scope, 0) + 1
    return {
        "status": "ok",
        "uptime_seconds": int(time.time() - START),
        "contexts_loaded": counts
    }

# ──────────────────────────────────────────
# Endpoint 2 : GET /v1/metadata
# ──────────────────────────────────────────
@app.get("/v1/metadata")
async def metadata():
    return {
        "team_name": "Magicpin AI Challengers",
        "team_members": ["Deepanshu"],
        "model": "gpt-4o",                       # Using OpenAI model
        "approach": "4-context composer with trigger-kind dispatch via OpenAI",
        "contact_email": "deepanshu@example.com",
        "version": "1.0.0",
        "submitted_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

# ──────────────────────────────────────────
# Endpoint 3 : POST /v1/context
# ──────────────────────────────────────────
class ContextBody(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: dict[str, Any]
    delivered_at: str

@app.post("/v1/context")
async def push_context(body: ContextBody):
    key = (body.scope, body.context_id)
    current = contexts.get(key)
    
    # Reject Stale versions
    if current and current["version"] > body.version:
        return {
            "accepted": False,
            "reason": "stale_version",
            "current_version": current["version"],
            "received_version": body.version,
            "note": "This context is older than the version we already have."
        }
    
    # Validate Scope
    if body.scope not in ("category", "merchant", "customer", "trigger"):
        return {
            "accepted": False,
            "reason": "invalid_scope",
            "note": f"Unknown scope : {body.scope}"
        }
        
    # Store
    contexts[key] = {
        "version": body.version,
        "payload": body.payload
    }
    return {
        "accepted": True,
        "ack_id": f"ack_{body.context_id}_v{body.version}",
        "stored_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

# ──────────────────────────────────────────
# Endpoint 4 : POST /v1/tick
# ──────────────────────────────────────────
class TickBody(BaseModel):
    now: str
    available_triggers: list[str] = []

@app.post("/v1/tick")
async def tick(body: TickBody):
    actions = []

    for trigger_id in body.available_triggers:
        trigger_data = contexts.get(("trigger", trigger_id), {}).get("payload")
        if not trigger_data: 
            continue
        
        merchant_id = trigger_data.get("merchant_id")
        merchant_data = contexts.get(("merchant", merchant_id), {}).get("payload")
        if not merchant_data:
            continue
        
        category_slug = merchant_data.get("category_slug", "")
        category_data = contexts.get(("category", category_slug), {}).get("payload")
        if not category_data:
            continue
        
        customer_id = trigger_data.get("customer_id")
        customer_data = None
        if customer_id:
            customer_data = contexts.get(("customer", customer_id), {}).get("payload")
        
        # Composer Logic (Calls Grok via composer.py)
        composed = compose_message(category_data, merchant_data, trigger_data, customer_data)

        send_as = "merchant_on_behalf" if customer_data else "vera"
        conv_id = f"conv_{merchant_id}_{trigger_id}"
        
        actions.append({
            "conversation_id": conv_id,
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "send_as": send_as,
            "trigger_id": trigger_id,
            "template_name": f"vera_{trigger_data.get('kind', 'generic')}_v1",
            "template_params": [merchant_data.get("identity", {}).get("name", "")],
            "body": composed["body"],
            "cta": composed["cta"],
            "suppression_key": trigger_data.get("suppression_key", ""),
            "rationale": composed["rationale"]
        })

    return {"actions": actions}

# ──────────────────────────────────────────
# Endpoint 5 : POST /v1/reply
# ──────────────────────────────────────────
class ReplyBody(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: str
    turn_number: int

@app.post("/v1/reply")
async def reply(body: ReplyBody):
    # Log conversation history
    conversations.setdefault(body.conversation_id, []).append({
        "from": body.from_role,
        "message": body.message,
        "turn": body.turn_number
    })
    history = conversations[body.conversation_id]

    # Process Reply (Calls handler in reply_handler.py)
    result = process_reply(
        conversation_id=body.conversation_id,
        merchant_id=body.merchant_id,
        customer_id=body.customer_id,
        from_role=body.from_role,
        message=body.message,
        turn_number=body.turn_number,
        history=history,
        contexts=contexts
    )
    return result
