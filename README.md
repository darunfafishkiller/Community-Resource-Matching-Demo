## Community Resource Matching Demo 

This folder contains of the **community resource matching** demo used in class.  
It shows how to go from **free‑text descriptions of needs/offers** to **structured records, semantic matching, and a simple map view**, with an optional WhatsApp interface via Twilio.



---

### 1. What the demo does

- **Input**: a natural‑language description of a resource *need* or *offer* (e.g., “We need 3 folding tables and 25 chairs this Saturday near the central library.”).
- **Extraction**: an LLM turns the text into a structured record (intent, user type, time window, location, category, etc.).
- **Categorization**: the model maps the resource into one of our predefined **taxonomy categories** (see below).
- **Storage**: the record is written into a small SQLite database (`resources.db`).
- **Matching**: we compute text embeddings and perform **semantic matching** between the current query and existing “provider” records.
- **Visualization**: we place the matched resources on a map and open `resource_map.html` in the browser on your computer.
- **(Optional)**: the same pipeline is wrapped in a Flask + Twilio + WhatsApp integration so that a WhatsApp message can trigger the same matching process and receive a **text‑only** result.

> Note: For this classroom demo, the **user’s latitude/longitude is randomly sampled** from a small bounding box around the **University of Michigan – Ann Arbor** campus. We do **not** try to geocode real user locations.

---

### 2. Resource taxonomy (categories)

The database seeds a small, hand‑crafted taxonomy of resource types in `database.py`:

- **equipment** – physical items like tables, chairs, projectors, sound systems, etc.
- **space** – rooms, venues, meeting spaces.
- **storage** – short‑term or long‑term storage space.
- **event_support** – general event support that is not clearly equipment or space (e.g., “on‑site staff help”).
- **transportation** – vans, trucks, or other forms of transport.
- **materials** – consumable materials and supplies.
- **food_support** – food, snacks, catering, or related support.
- **childcare** – childcare or kid‑related support.
- **volunteer_help** – volunteer time or labor.
- **other** – anything that does not cleanly fit the above.

There is also some simple category post‑processing:
- If the text clearly mentions **tables** or **chairs**, and the initial category is `event_support` or `other`, we **promote** it to `equipment`.  
  This helps demo how we can correct noisy category assignments with small heuristic rules.

The extraction step can also propose a **`new_category`** when nothing fits; we insert it into the taxonomy table for illustration.

---

### 3. Files overview

- `main.py` – command‑line demo that:
  - loads categories and fake provider/seeker records
  - asks the user for one text description
  - runs extraction + matching
  - generates `resource_map.html` and opens it in a browser
  - lets you mark one provider + the current demand as `matched`

- `database.py` – all SQLite logic:
  - creates tables
  - seeds the default taxonomy
  - seeds **fake provider/seeker records** the first time you run the demo
  - helper functions for querying/updating resources

- `extract.py` – talks to the OpenAI Chat Completions API to extract structured fields from free text.

- `embed_match.py` – uses OpenAI embeddings + cosine similarity to match the current query to providers.

- `geo_utils.py` – randomly samples a point around **Ann Arbor** for the user’s location.

- `map_view.py` – builds a Leaflet/Folium map and writes `resource_map.html`.

- `pipeline.py` – shared “one‑shot pipeline” used by both `main.py` and the WhatsApp server.

- `whatsapp_server.py` – Flask server that exposes the pipeline as a Twilio WhatsApp webhook.

- `WHATSAPP_SETUP.md` – step‑by‑step guide (in English in this V2) for configuring ngrok + Twilio + WhatsApp.

- `resources.db` – small SQLite database holding the seeded fake data and any new records you create while testing.

---

### 4. How to run the command‑line demo

All steps below are run in a **terminal** (Terminal.app on macOS, or your system’s command-line interface).

1. **Create and activate a virtual environment** (recommended, but optional):

   ```bash
   cd "/Volumes/T7/URP530/GROUP PROJECT-V2"
   python3 -m venv venv
   source venv/bin/activate   # On macOS / Linux
   # .\venv\Scripts\activate  # On Windows (PowerShell)
   ```

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Create a `.env` file** based on `.env.example`:

   ```bash
   cp .env.example .env
   ```

   Then edit `.env` and set at least:

   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   # (optional) Twilio + PORT if you want to use WhatsApp integration
   ```

   > For this V2 folder we have **removed all real keys**. You must supply your own API key to run the extraction + embedding steps.

4. **Run the main demo** (in the terminal):

   ```bash
   python3 main.py
   ```

   - If `resources.db` is empty, the script will insert **fake provider and seeker records**.
   - You will be prompted to type a free‑text description (or press Enter to use a default example).
   - The script will:
     - call the LLM to extract a structured record
     - insert it into the database
     - perform semantic matching against the existing providers
     - open `resource_map.html` in your default browser
     - print a summary of matched providers in the terminal
     - optionally let you mark a chosen provider + demand as `matched`.

---

### 5. Example prompts to try

You can paste or adapt these into the **terminal** (as a single line when running `python3 main.py`) or into WhatsApp:

- **Equipment need**
  - “We are hosting a community workshop on Saturday afternoon near campus and need 3 folding tables and about 20 chairs.”
- **Space need**
  - “Our student group is looking for a small meeting room for 15 people this Friday evening close to the central library.”
- **Offer of equipment**
  - “I can offer 2 large whiteboards and a projector for community events in Ann Arbor next weekend.”
- **Storage + time window**
  - “We need temporary storage for several boxes of supplies for about two weeks starting next Monday.”
- **Volunteer help**
  - “We are organizing a neighborhood clean‑up and need 10 volunteers for three hours on Sunday morning.”
- **Transportation**
  - “We are looking for a van that can move equipment between campus and a community center on Saturday morning.”

Feel free to change dates, quantities, and locations to see how the extraction and matching behave.

---

### 6. WhatsApp / Twilio demo (text‑only)

The WhatsApp integration wraps the same pipeline in a **Flask server** (`whatsapp_server.py`) and exposes an endpoint for Twilio:

- When a WhatsApp message hits the Twilio Sandbox number, Twilio forwards it via **Webhook** (through ngrok) to:
  - `POST https://<your-ngrok-domain>/whatsapp/webhook`
- The server:
  - runs the same extraction + matching pipeline as `main.py`
  - sends back a **plain‑text summary** of the top matches via WhatsApp

Important limitations for class demo:

- **WhatsApp returns text only.**  
  We **do not** embed the interactive map in WhatsApp. Students should open `resource_map.html` on a **computer browser** to see the locations.
- **User locations are random** within a small box around **Ann Arbor**. This keeps the demo self‑contained and avoids real geocoding or personal location data.
- **Sandbox only**: we use the Twilio WhatsApp Sandbox, which is meant for testing, not production use.

See `WHATSAPP_SETUP.md` in this folder for detailed, step‑by‑step setup instructions (ngrok, Twilio credentials, Sandbox configuration).

---

### 7. What to explain in class

When presenting this demo, you can briefly highlight:

- How **free‑text input** is turned into **structured data** via an LLM.
- How a small **resource taxonomy** helps organize and filter matches (including simple heuristic rules like promoting table/chair requests to `equipment`).
- How we use **embeddings + cosine similarity** for semantic matching instead of exact keyword search.
- Why we **fake user locations** within Ann Arbor for a classroom‑friendly demo.
- The difference between:
  - the **command‑line + map** flow (richer visualization, computer only), and
  - the **WhatsApp flow** (convenient mobile access, but text‑only).

