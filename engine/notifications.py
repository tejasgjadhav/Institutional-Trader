"""
Signal Notifications — Telegram + WhatsApp + Phone call (all optional, free-first).

Each channel fires only if its credentials are present in .env. Nothing here
sends an order — it just alerts you so you can place the trade manually.

FREE channels:
  • Telegram  — official Bot API, unlimited, most reliable.
  • WhatsApp  — CallMeBot bot (one-time opt-in), free.
  • Phone call — CallMeBot free TTS call (best-effort); or Twilio (paid, reliable).

Setup steps are printed by `print_setup_help()` and documented in the README.
"""
import os
import logging
import urllib.parse
import requests

logger = logging.getLogger(__name__)

# ── credentials (from .env) ───────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID")

CALLMEBOT_WA_PHONE  = os.getenv("CALLMEBOT_WHATSAPP_PHONE")   # e.g. +9198xxxxxxx
CALLMEBOT_WA_APIKEY = os.getenv("CALLMEBOT_WHATSAPP_APIKEY")

CALLMEBOT_CALL_PHONE = os.getenv("CALLMEBOT_CALL_PHONE")      # free TTS phone call
# Twilio (paid, reliable phone calls) — optional
TWILIO_SID   = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_FROM  = os.getenv("TWILIO_FROM")
TWILIO_TO    = os.getenv("TWILIO_TO")


# ── individual channels ───────────────────────────────────────────────────────

def send_telegram(text: str) -> bool:
    """Free, reliable. Needs TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID."""
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"
        }, timeout=10)
        ok = r.status_code == 200
        if not ok:
            logger.warning(f"Telegram failed: {r.status_code} {r.text[:120]}")
        return ok
    except Exception as e:
        logger.warning(f"Telegram error: {e}")
        return False


def send_whatsapp(text: str) -> bool:
    """Free via CallMeBot. Needs CALLMEBOT_WHATSAPP_PHONE + _APIKEY."""
    if not (CALLMEBOT_WA_PHONE and CALLMEBOT_WA_APIKEY):
        return False
    try:
        url = "https://api.callmebot.com/whatsapp.php?" + urllib.parse.urlencode({
            "phone": CALLMEBOT_WA_PHONE, "text": text, "apikey": CALLMEBOT_WA_APIKEY
        })
        r = requests.get(url, timeout=15)
        ok = r.status_code in (200, 203)
        if not ok:
            logger.warning(f"WhatsApp failed: {r.status_code} {r.text[:120]}")
        return ok
    except Exception as e:
        logger.warning(f"WhatsApp error: {e}")
        return False


def make_phone_call(text: str) -> bool:
    """
    Ring the user's phone. Tries Twilio first (paid, reliable) if configured,
    else CallMeBot's free TTS call (best-effort).
    """
    # Twilio — reliable, paid
    if all([TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM, TWILIO_TO]):
        try:
            twiml = f"<Response><Say voice='alice'>{text}</Say></Response>"
            r = requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Calls.json",
                data={"From": TWILIO_FROM, "To": TWILIO_TO, "Twiml": twiml},
                auth=(TWILIO_SID, TWILIO_TOKEN), timeout=15)
            ok = r.status_code in (200, 201)
            if not ok:
                logger.warning(f"Twilio call failed: {r.status_code} {r.text[:120]}")
            return ok
        except Exception as e:
            logger.warning(f"Twilio error: {e}")
            return False

    # CallMeBot free TTS call — best-effort
    if CALLMEBOT_CALL_PHONE:
        try:
            url = "https://api.callmebot.com/start.php?" + urllib.parse.urlencode({
                "source": "api", "user": CALLMEBOT_CALL_PHONE,
                "text": text, "lang": "en-US-Standard-B", "rpt": 2
            })
            r = requests.get(url, timeout=20)
            return r.status_code == 200
        except Exception as e:
            logger.warning(f"CallMeBot call error: {e}")
            return False
    return False


# ── high-level: notify on a signal ────────────────────────────────────────────

def _format_signal(order: dict) -> tuple:
    """Build (rich_text, short_voice) from a build_live_option_order dict."""
    sym = order.get("symbol", "?")
    inst = order.get("instrument", "")
    strike = int(order.get("strike", 0))
    exp = order.get("expiry", "")
    prem = order.get("premium", 0)
    tgt = order.get("target_premium", 0)
    stp = order.get("stop_premium", 0)
    cap = order.get("capital")
    cap_s = f"Rs {cap:,.0f}" if cap else "-"

    text = (
        f"<b>SIGNAL</b>  BUY {sym} {strike} {inst}\n"
        f"Expiry: {exp}\n"
        f"Premium: Rs {prem:.2f}\n"
        f"Target: Rs {tgt:.2f} (+10%)\n"
        f"Stop:   Rs {stp:.2f} (-20%)\n"
        f"Capital/lot: {cap_s}\n"
        f"(Place manually in Upstox — paper mode)"
    )
    voice = (f"New trade signal. Buy {sym} {strike} {inst}. "
             f"Premium {prem:.0f} rupees. Check the dashboard.")
    return text, voice


def notify_signal(order: dict) -> dict:
    """
    Fire all configured channels for one trade-ready signal.
    Returns {channel: bool} so the caller can log what went out.
    """
    text, voice = _format_signal(order)
    results = {
        "telegram": send_telegram(text),
        "whatsapp": send_whatsapp(text.replace("<b>", "*").replace("</b>", "*")),
        "call":     make_phone_call(voice),
    }
    active = [k for k, v in results.items() if v]
    if active:
        logger.info(f"Notified via: {', '.join(active)}")
    else:
        logger.info("No notification channels configured (see notifications.print_setup_help)")
    return results


def channels_status() -> dict:
    """Which channels are configured right now."""
    return {
        "telegram": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        "whatsapp": bool(CALLMEBOT_WA_PHONE and CALLMEBOT_WA_APIKEY),
        "call_callmebot": bool(CALLMEBOT_CALL_PHONE),
        "call_twilio": all([TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM, TWILIO_TO]),
    }


def print_setup_help():
    print("""
╔══════════════════════════════════════════════════════════════════════════╗
║  SIGNAL NOTIFICATIONS — one-time setup (add results to .env)               ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║  1) TELEGRAM  (free, most reliable) ────────────────────────────────────   ║
║     • In Telegram, search @BotFather → /newbot → follow prompts.           ║
║     • Copy the bot TOKEN it gives you.                                      ║
║     • Message your new bot once (say 'hi').                                 ║
║     • Get your chat id: open                                               ║
║       https://api.telegram.org/bot<TOKEN>/getUpdates → find "chat":{"id":} ║
║     • .env:  TELEGRAM_BOT_TOKEN=...   TELEGRAM_CHAT_ID=...                  ║
║                                                                            ║
║  2) WHATSAPP  (free, CallMeBot) ────────────────────────────────────────   ║
║     • Save +34 644 51 95 23 as a contact.                                  ║
║     • WhatsApp it:  "I allow callmebot to send me messages"                ║
║     • It replies with your personal APIKEY.                                ║
║     • .env:  CALLMEBOT_WHATSAPP_PHONE=+9198xxxxxxx                          ║
║              CALLMEBOT_WHATSAPP_APIKEY=...                                  ║
║                                                                            ║
║  3) PHONE CALL ─────────────────────────────────────────────────────────   ║
║     FREE (best-effort): CALLMEBOT_CALL_PHONE=+9198xxxxxxx                   ║
║     RELIABLE (paid, free trial): Twilio                                     ║
║       TWILIO_SID=...  TWILIO_TOKEN=...  TWILIO_FROM=+1...  TWILIO_TO=+91... ║
║                                                                            ║
╚══════════════════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    print("Configured channels:", channels_status())
    print_setup_help()
    # quick live test if anything is set up
    demo = {"symbol": "TEST", "instrument": "CALL", "strike": 100, "expiry": "30-Jun",
            "premium": 12.5, "target_premium": 13.75, "stop_premium": 10.0, "capital": 25000}
    if any(channels_status().values()):
        print("Sending a test alert...")
        print(notify_signal(demo))
