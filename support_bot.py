#!/usr/bin/env python3
"""
support_bot.py – Väljer Support Duty (primär + backup) för veckan
och postar i Slack. Körs automatiskt varje måndag via GitHub Actions.

Konfiguration:
  POOL               = listan med Slack User IDs som ingår i rotationen
  SLACK_WEBHOOK_URL  = miljövariabel (GitHub Secret)
  SLACK_BOT_TOKEN    = miljövariabel (GitHub Secret) – VALFRI, behövs bara
                       för att uppdatera Channel Topic
  SLACK_CHANNEL_ID   = miljövariabel – VALFRI, för Channel Topic-uppdatering

Hur du hittar Slack User IDs:
  Klicka på en persons profil → "···" (mer) → "Kopiera member-ID"
"""

import json
import os
import random
import datetime
import urllib.request
import urllib.error

# ─── KONFIGURERA POOL HÄR ────────────────────────────────────────────────────
# Ersätt med faktiska Slack User IDs (format: U012AB3CD)
# Namn: (Slack User ID, vikt)
# Vikt 1.0 = normal  |  0.5 = halvt så ofta  |  0.2 = sällan
POOL = [
    ("U0450PC2Y9H", 1.0),   # Dennis Lundgren
    ("U03G4KL9QDD", 1.0),   # Erik Åström
    ("U0459W0926K", 0.8),   # Guillaume Lorin   ← väljs 80% av fallen
    ("U06TB02GY4U", 1.0),   # Muzzafer Arpacik
    ("U039J28MYUF", 0.2),   # Mats Lundberg     ← väljs sällan
    ("U03G4KL4K8X", 1.0),   # Simon Gribert
    ("U0A5QA2BZ",   0.3),   # Tomas Öquist
    ("U3WBSPKPW",   0,5),   # Anders Björkman← väljs sällan
]
STATE_FILE = "last_week.json"

# ─────────────────────────────────────────────────────────────────────────────


def load_last_week():
    """Läser förra veckans par från state-filen."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"primary": None, "backup": None, "week": 0}


def save_this_week(primary_id, backup_id):
    """Sparar veckans par i state-filen (committas tillbaka till repo)."""
    with open(STATE_FILE, "w") as f:
        json.dump({
            "primary": primary_id,
            "backup": backup_id,
            "week": datetime.date.today().isocalendar()[1]
        }, f, indent=2)


def already_ran_this_week():
    """Förhindrar dubbelkörning om båda cron-triggers råkar gälla samma vecka."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            state = json.load(f)
        if state.get("week") == datetime.date.today().isocalendar()[1]:
            print("⏭️  Redan kört denna vecka, hoppar över.")
            return True
    return False


def pick_pair(pool, exclude_ids):
    available = [(uid, w) for uid, w in pool if uid not in exclude_ids]
    if len(available) < 2:
        available = list(pool)

    if len(available) < 2:
        raise ValueError(f"Poolen måste ha minst 2 personer, har {len(available)}.")

    ids     = [uid for uid, w in available]
    weights = [w   for uid, w in available]

    primary = random.choices(ids, weights=weights, k=1)[0]
    available = [(uid, w) for uid, w in available if uid != primary]
    ids     = [uid for uid, w in available]
    weights = [w   for uid, w in available]
    backup  = random.choices(ids, weights=weights, k=1)[0]

    return primary, backup


def slack_display_name(user_id):
    """Returnerar @mention-format för Slack."""
    return f"<@{user_id}>"


def get_week_dates():
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    friday = monday + datetime.timedelta(days=4)
    week_num = today.isocalendar()[1]
    return monday, friday, week_num


def post_to_slack(webhook_url, primary_id, backup_id):
    monday, friday, week_num = get_week_dates()
    date_range = f"{monday.strftime('%d %b')} – {friday.strftime('%d %b %Y')}"

    primary_mention = slack_display_name(primary_id)
    backup_mention  = slack_display_name(backup_id)

    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"📋 Support Duty – Vecka {week_num}"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*🟢 Primär:*\n{primary_mention}"},
                    {"type": "mrkdwn", "text": f"*🟡 Backup:*\n{backup_mention}"},
                ]
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"📅 {date_range}   ·   Primär löser RED & BLUE. Backup täcker upp vid frånvaro eller högt tryck."}
                ]
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "_RED = akut, @mention primär, respons inom 30 min_ | _BLUE = normal, hanteras i supportfönster_"}
            }
        ]
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode()
        if body != "ok":
            raise RuntimeError(f"Slack webhook svarade: {body}")
    print(f"✅ Postat till Slack: primär={primary_id}, backup={backup_id}")


def update_channel_topic(bot_token, channel_id, primary_id, backup_id):
    """Uppdaterar Channel Topic – kräver Slack Bot Token med channels:manage scope."""
    monday, friday, week_num = get_week_dates()
    topic = (
        f"Support Duty v{week_num}: "
        f"Primär @{primary_id} | Backup @{backup_id} | "
        f"{monday.strftime('%d/%m')}–{friday.strftime('%d/%m')} | "
        "RED=akut 30min | BLUE=24h"
    )
    payload = json.dumps({"channel": channel_id, "topic": topic}).encode("utf-8")
    req = urllib.request.Request(
        "https://slack.com/api/conversations.setTopic",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bot_token}"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode())
        if not result.get("ok"):
            print(f"⚠️  Channel Topic-uppdatering misslyckades: {result.get('error')}")
        else:
            print("✅ Channel Topic uppdaterat")


def main():
    if already_ran_this_week():
        return

    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise EnvironmentError("SLACK_WEBHOOK_URL är inte satt som miljövariabel.")

    last_week = load_last_week()
    exclude = [last_week["primary"], last_week["backup"]]
    exclude = [e for e in exclude if e]

    primary_id, backup_id = pick_pair(POOL, exclude)
    print(f"Vald: primär={primary_id}, backup={backup_id}")

    post_to_slack(webhook_url, primary_id, backup_id)
    save_this_week(primary_id, backup_id)

    # Valfritt: uppdatera Channel Topic
    bot_token  = os.environ.get("SLACK_BOT_TOKEN")
    channel_id = os.environ.get("SLACK_CHANNEL_ID")
    if bot_token and channel_id:
        update_channel_topic(bot_token, channel_id, primary_id, backup_id)


if __name__ == "__main__":
    main()
