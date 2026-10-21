"""Telegram: send reports, ask for approval on outreach drafts, and read your button taps."""
import json
import re
import urllib.parse
import urllib.request

import config
import store


def enabled():
    return bool(config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID) and not config.DEMO


def call(method, **params):
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/{method}"
    data = urllib.parse.urlencode({k: json.dumps(v) if isinstance(v, (dict, list)) else v
                                   for k, v in params.items()}).encode()
    with urllib.request.urlopen(url, data=data, timeout=30) as r:
        return json.load(r)["result"]


def send(text, buttons=None):
    if not enabled():
        print("[telegram disabled]\n" + text)
        return
    params = {"chat_id": config.TELEGRAM_CHAT_ID, "text": text[:4000], "disable_web_page_preview": "true"}
    if buttons:
        params["reply_markup"] = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in buttons]]}
    call("sendMessage", **params)


def ask_approval(draft):
    send(f"✉️ Outreach draft {draft['id']}\nTo: {draft['vendor']} <{draft['to']}>\n"
         f"Subject: {draft['subject']}\n\n{draft['body']}",
         buttons=[("✅ Send", f"approve:{draft['id']}"), ("❌ Drop", f"reject:{draft['id']}")])


def apply_decision(data):
    """'approve:<id>' or 'reject:<id>' -> update the draft. Returns a short reply."""
    action, _, oid = data.partition(":")
    p = store.path("outreach", f"{oid}.json")
    if action not in ("approve", "reject") or not re.fullmatch(r"[\w-]+", oid) or not p.exists():
        return "Unknown action"
    draft = json.loads(p.read_text())
    if draft["status"] != "pending":
        return f"Already {draft['status']}"
    draft["status"] = "approved" if action == "approve" else "rejected"
    store.save(f"outreach/{oid}.json", draft)
    return f"{draft['vendor']}: {draft['status']}"


def poll():
    """Process button taps since the last poll. Only your own chat is obeyed."""
    if not enabled():
        return []
    state = store.load("state.json", {})
    updates = call("getUpdates", offset=state.get("tg_offset", 0), timeout=0)
    done = []
    for u in updates:
        state["tg_offset"] = u["update_id"] + 1
        cb = u.get("callback_query")
        if not cb or str(cb["message"]["chat"]["id"]) != str(config.TELEGRAM_CHAT_ID):
            continue
        reply = apply_decision(cb.get("data", ""))
        call("answerCallbackQuery", callback_query_id=cb["id"], text=reply)
        done.append(reply)
    store.save("state.json", state)
    return done
