"""
whatsapp_server.py

Expose the community resource matching pipeline to WhatsApp via Twilio.
Users send a free-text message; the server runs the pipeline and replies
with a text summary of matched resources. Requires Twilio + ngrok setup.
"""

import os
from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from dotenv import load_dotenv
from pipeline import run_matching_pipeline, format_matches_for_reply

load_dotenv()

app = Flask(__name__)

# Twilio configuration (read from environment variables)
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM")  # e.g., whatsapp:+14155238886 (sandbox)


def send_whatsapp_reply(to_number: str, body: str) -> bool:
    """Send a WhatsApp text reply via Twilio."""
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM]):
        print("[WhatsApp] Twilio not configured (missing SID/Token/From); cannot send reply.")
        return False
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    try:
        client.messages.create(
            body=body,
            from_=TWILIO_WHATSAPP_FROM,
            to=to_number,
        )
        return True
    except Exception as e:
        print(f"[WhatsApp] Twilio send failed: {e}")
        return False


@app.route("/whatsapp/webhook", methods=["POST"])
def whatsapp_webhook():
    """
    Inbound webhook endpoint configured in Twilio WhatsApp Sandbox.
    For each incoming message, run the matching pipeline and reply
    with a text summary of the best matching resources.
    """
    incoming_body = (request.form.get("Body") or "").strip()
    from_number = request.form.get("From", "")
    print(f"[WhatsApp] Incoming message From={from_number!r} Body={incoming_body!r}")

    if not incoming_body:
        resp = MessagingResponse()
        resp.message(
            "Please send a short description of your resource need or offer, "
            "for example: 'We need 3 tables and 25 chairs near the library this Saturday afternoon.'"
        )
        return str(resp), 200, {"Content-Type": "text/xml"}

    try:
        result = run_matching_pipeline(incoming_body)
        matches = result["matches"]
        reply_text = format_matches_for_reply(matches)
    except Exception as e:
        print(f"[WhatsApp] Exception while processing message: {e}")
        reply_text = (
            "An error occurred while processing your request. "
            f"Please try again later. Error detail (truncated): {str(e)[:100]}"
        )

    # If Twilio credentials are set, use the REST API to send the full reply body
    # (to avoid TwiML text length limitations); otherwise, fall back to TwiML only.
    if send_whatsapp_reply(from_number, reply_text):
        print(f"[WhatsApp] Replied via API -> {from_number}")
        resp = MessagingResponse()
        return str(resp), 200, {"Content-Type": "text/xml"}

    resp = MessagingResponse()
    resp.message(reply_text[:1600])  # Twilio single-message length limit
    return str(resp), 200, {"Content-Type": "text/xml"}


@app.route("/health", methods=["GET"])
def health():
    return "ok", 200


def ensure_tables():
    """Ensure database tables and seed data exist (mirrors main.py behavior without dropping data)."""
    import database

    database.create_tables()
    database.seed_default_categories()
    if database.get_resources_row_count() == 0:
        database.seed_fake_provider_records()
        database.seed_fake_seeker_records()


if __name__ == "__main__":
    ensure_tables()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
