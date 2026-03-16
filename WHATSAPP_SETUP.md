# Connect the demo to WhatsApp via Twilio

This guide shows how to connect the **community resource matching demo** to WhatsApp using **Twilio**.  
You send a message in WhatsApp, and the demo replies with a **text summary** of matching resources.

Before you start, make sure you have already followed `README.md` to install dependencies and create your `.env`.

## 1. Configure Twilio and the WhatsApp Sandbox

1. Sign up for [Twilio](https://www.twilio.com/try-twilio) and open the [Console](https://console.twilio.com).
2. In the left sidebar go to **Messaging → Try it out → Send a WhatsApp message** to find the **WhatsApp Sandbox**.
3. Follow the instructions on that page to join the sandbox from your own WhatsApp number (scan QR code or send the join phrase).
4. In the Console copy:
   - your **Account SID**
   - your **Auth Token**
   - the Sandbox **From** number (looks like `whatsapp:+14155238886`).

In the project folder, edit `.env`:

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
```

## 2. Expose your local server to Twilio with ngrok

Twilio needs a **public HTTPS URL** to call your webhook. While running locally, we use **ngrok** to tunnel to your machine.

1. Install [ngrok](https://ngrok.com/download) and sign in to get an authtoken.
2. In a terminal (keep it open), run:

```bash
ngrok http 5000
```

3. In the ngrok output, find the **Forwarding** line. The left-hand HTTPS URL is your public address, e.g.  
   `https://clorinda-dryadic-zulma.ngrok-free.dev` (new free domains often end with `.ngrok-free.dev`).

## 3. Configure the Twilio webhook

1. Go back to Twilio Console → **Messaging → Try it out → Send a WhatsApp message → Sandbox settings**.
2. Under **When a message comes in**, set:
   - URL: `https://<your-ngrok-domain>/whatsapp/webhook`  
     for example: `https://clorinda-dryadic-zulma.ngrok-free.dev/whatsapp/webhook`
   - Method: **POST**
3. Click **Save**.

## 4. Start the local Flask server

From the project directory:

```bash
python whatsapp_server.py
```

By default the server listens on **port 5000**; your ngrok tunnel must point to the same port (`ngrok http 5000`).

If you see **“Port 5000 is in use”** on macOS (often due to **AirPlay Receiver**):

- **Option A**: Disable AirPlay Receiver in **System Settings → General → AirDrop & Handoff**.
- **Option B**: Use a different port:
  ```bash
  PORT=5001 python whatsapp_server.py
  ```
  And in another terminal:
  ```bash
  ngrok http 5001
  ```
  In Twilio, keep using the HTTPS ngrok address, for example `https://xxx.ngrok-free.dev/whatsapp/webhook`.

## 5. Test with WhatsApp

Using the phone number that joined the sandbox, send a WhatsApp message to the Twilio sandbox number (for example `+1 415 523 8886`), such as:

> We are organizing a small workshop this Saturday afternoon near the library and need 3 folding tables and 25 chairs.

Within a few seconds you should receive a text reply listing matched resources (ID, category, description, quantity, time, location, etc.).  
The **interactive map is not sent to WhatsApp** – please open `resource_map.html` on a computer to view locations.

## Troubleshooting (no reply)

1. **Check the local terminal**  
   In the window running `python whatsapp_server.py`, after sending a WhatsApp message you should see:  
   `[WhatsApp] Incoming message From=... Body=...`  
   - If you never see this line, the request is not reaching your machine – continue with steps 2 and 3.  
   - If you see it but there is no reply, look for `[WhatsApp] Exception while processing message` or Twilio send failures.

2. **Confirm Twilio is calling the right URL**  
   Open [Twilio Console → Monitor → Logs](https://console.twilio.com/us1/monitor/logs), find the Messaging log entry for your test, and check the webhook URL + HTTP status code.  
   - The URL must be `https://<your-ngrok-domain>/whatsapp/webhook` with no extra spaces.  
   - 5xx or timeouts usually mean ngrok is not running or the port is wrong.

3. **Confirm ngrok is forwarding**  
   Open **http://127.0.0.1:4040** in a browser (ngrok’s inspector). After sending a WhatsApp message, you should see a new POST to `/whatsapp/webhook`.  
   - If there is no request, the Twilio webhook URL is wrong or not saved.  
   - If there is a request but the status is not 200, look for errors in the Flask terminal.

4. **ngrok “Visit Site” interstitial page**  
   If ngrok shows a 403 or an HTML “Visit Site” page in the 4040 inspector, visit `https://<your-ngrok-domain>/health` in a browser and click through once, then try WhatsApp again. Alternatively, use a paid ngrok plan or a different tunneling solution.

## Notes

- **Single-turn interaction**: each WhatsApp message is treated as a new request; we do not maintain a multi-turn conversation or let you mark IDs as `matched` over WhatsApp.
- **Shared database**: the WhatsApp flow uses the same `resources.db` as the command-line demo, with the same schema, fake data, and pipeline logic.
- **Demo only**: this setup is for classroom demonstration. A real deployment would use a production WhatsApp Business API number and a proper server instead of ngrok.
