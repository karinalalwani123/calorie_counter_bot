import streamlit as st
import json
import re
import datetime
import requests

st.set_page_config(
    page_title="CalBot – Daily Calorie Tracker",
    page_icon="🥗",
    layout="wide",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=DM+Mono&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .main { background: #f7f6f2; }
    .block-container { padding-top: 2rem; max-width: 1100px; }
    .metric-card {
        background: white; border-radius: 16px;
        padding: 1rem 0.5rem; border: 1px solid #e8e6df; text-align: center;
    }
    .metric-label { font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: .03em; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .metric-value { font-size: 24px; font-weight: 600; color: #1a1a1a; }
    .metric-sub   { font-size: 12px; color: #aaa; margin-top: 2px; }
    .prog-wrap { background: #ede9df; border-radius: 99px; height: 10px; margin: .5rem 0 1.5rem; overflow: hidden; }
    .prog-fill { height: 100%; border-radius: 99px; }
    .bubble-user {
        background: #1a1a1a; color: white;
        border-radius: 18px 18px 4px 18px;
        padding: .75rem 1rem; margin: .5rem 0 .5rem auto;
        max-width: 75%; width: fit-content; font-size: 14.5px; line-height: 1.55;
    }
    .bubble-bot {
        background: white; color: #1a1a1a; border: 1px solid #e8e6df;
        border-radius: 18px 18px 18px 4px;
        padding: .75rem 1rem; margin: .5rem auto .5rem 0;
        max-width: 85%; width: fit-content; font-size: 14.5px; line-height: 1.6;
    }
    .food-row {
        display: flex; align-items: center; justify-content: space-between;
        padding: .5rem .75rem; border-radius: 10px; margin-bottom: 6px;
        background: #fafaf7; border: 1px solid #eeede7; font-size: 14px;
    }
    .food-name { font-weight: 500; flex: 1; }
    .food-cal  { color: #d4843a; font-weight: 600; font-family: 'DM Mono', monospace; margin-left: 12px; }
    .section-title { font-size: 13px; font-weight: 600; color: #888; text-transform: uppercase; letter-spacing: .06em; margin: 1.25rem 0 .6rem; }
    .db-badge { font-size: 10px; background: #e8f5e9; color: #2e7d32; border-radius: 99px; padding: 1px 7px; margin-left: 6px; font-weight: 500; }
    .est-badge { font-size: 10px; background: #fff3e0; color: #e65100; border-radius: 99px; padding: 1px 7px; margin-left: 6px; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "meta-llama/llama-3.3-70b-instruct"

# ── Open Food Facts lookup ─────────────────────────────────────────────────────
def search_nutrition_db(food_query):
    """Search Open Food Facts for nutrition data. Returns per-100g data."""
    try:
        url = "https://world.openfoodfacts.org/cgi/search.pl"
        params = {
            "search_terms": food_query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": 5,
            "fields": "product_name,nutriments,serving_size,serving_quantity",
        }
        resp = requests.get(url, params=params, timeout=8)
        data = resp.json()
        products = data.get("products", [])
        if not products:
            return None
        # Pick best product — prefer one with complete nutriment data
        for product in products:
            n = product.get("nutriments", {})
            if all(k in n for k in ["energy-kcal_100g", "proteins_100g", "carbohydrates_100g", "fat_100g"]):
                return {
                    "name": product.get("product_name", food_query),
                    "calories_per_100g": round(n.get("energy-kcal_100g", 0), 1),
                    "protein_per_100g":  round(n.get("proteins_100g", 0), 1),
                    "carbs_per_100g":    round(n.get("carbohydrates_100g", 0), 1),
                    "fat_per_100g":      round(n.get("fat_100g", 0), 1),
                    "serving_size":      product.get("serving_size", "100g"),
                }
        return None
    except Exception:
        return None

# ── Extract food name from user message using Llama ───────────────────────────
def extract_food_info(user_msg, api_key):
    """Ask Llama to extract food name and quantity from user message."""
    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://calbot.app",
                "X-Title": "CalBot",
            },
            json={
                "model": MODEL,
                "max_tokens": 100,
                "messages": [
                    {"role": "system", "content": """Extract the food item and quantity from the user message.
Reply ONLY with JSON in this exact format (no other text):
{"food": "<food name for database search>", "quantity": <number>, "unit": "<piece/gram/cup/bowl/slice>"}
If no quantity mentioned, use 1. Keep food name simple e.g. 'banana', 'roti', 'chicken breast'."""},
                    {"role": "user", "content": user_msg}
                ],
            },
            timeout=15,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
        # Clean markdown fences if any
        text = re.sub(r"```json|```", "", text).strip()
        return json.loads(text)
    except Exception:
        return None

# ── Estimate calories with Llama (fallback when DB has no result) ─────────────
SYSTEM_PROMPT_FALLBACK = """You are CalBot, a nutrition assistant. When the user mentions food:
1. Give a short friendly response (1-2 sentences).
2. ALWAYS end with this exact line (no markdown):
FOOD_LOG_JSON:{"name":"<food>","calories":<int>,"protein":<float>,"carbs":<float>,"fat":<float>}

Use your best knowledge for calorie estimates. For Indian foods use standard values:
roti/chapati ~120 kcal, paratha ~200 kcal, rice (1 cup cooked) ~200 kcal, dal (1 cup) ~150 kcal.
Be encouraging and concise!"""

def call_llama_fallback(user_msg, api_key, messages):
    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://calbot.app",
                "X-Title": "CalBot",
            },
            json={
                "model": MODEL,
                "max_tokens": 300,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT_FALLBACK}] + messages + [{"role": "user", "content": user_msg}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ Error: {e}"

# ── Main chat function ─────────────────────────────────────────────────────────
def call_openrouter(user_msg):
    api_key = st.session_state.api_key or SECRET_API_KEY
    if not api_key:
        st.session_state.messages.append({"role": "user", "content": user_msg})
        st.session_state.messages.append({"role": "assistant", "content": "⚠️ Please enter your OpenRouter API key in the sidebar first."})
        return

    st.session_state.messages.append({"role": "user", "content": user_msg})

    food_data = None
    source = None
    reply = ""

    # Step 1: Extract food + quantity using Llama
    extracted = extract_food_info(user_msg, api_key)

    if extracted and extracted.get("food"):
        food_name = extracted["food"]
        quantity  = extracted.get("quantity", 1)
        unit      = extracted.get("unit", "piece")

        # Step 2: Search Open Food Facts
        db_result = search_nutrition_db(food_name)

        if db_result:
            # Estimate grams based on unit/quantity
            grams_map = {
                "gram": quantity, "g": quantity,
                "kg": quantity * 1000,
                "cup": quantity * 240,
                "bowl": quantity * 200,
                "slice": quantity * 40,
                "piece": quantity * 100,
                "serving": quantity * 100,
            }
            grams = grams_map.get(unit.lower(), quantity * 100)

            factor = grams / 100
            cals    = round(db_result["calories_per_100g"] * factor)
            protein = round(db_result["protein_per_100g"]  * factor, 1)
            carbs   = round(db_result["carbs_per_100g"]    * factor, 1)
            fat     = round(db_result["fat_per_100g"]      * factor, 1)

            food_data = {
                "name":     f"{quantity} {food_name}",
                "calories": cals,
                "protein":  protein,
                "carbs":    carbs,
                "fat":      fat,
            }
            source = "db"

            reply = (
                f"✅ Found **{food_name}** in the nutrition database! "
                f"{''.join([f'{quantity} {unit}(s)' if unit != 'piece' else f'{quantity}'])} = "
                f"**{cals} kcal** | Protein: {protein}g | Carbs: {carbs}g | Fat: {fat}g. Logged! 🎯"
            )

    # Step 3: Fallback to Llama estimation if DB failed
    if not food_data:
        reply = call_llama_fallback(user_msg, api_key, st.session_state.messages[:-1])
        source = "estimate"

        if "FOOD_LOG_JSON:" in reply:
            try:
                json_str = reply.split("FOOD_LOG_JSON:")[1].strip().split("\n")[0]
                food_data = json.loads(json_str)
            except Exception:
                pass

        if not food_data:
            matches = re.findall(r'\{[^{}]*"calories"[^{}]*\}', reply)
            for m in matches:
                try:
                    food_data = json.loads(m)
                    break
                except Exception:
                    pass

        # Clean FOOD_LOG_JSON from display
        if "FOOD_LOG_JSON:" in reply:
            reply = reply.split("FOOD_LOG_JSON:")[0].strip()
        if food_data:
            reply += "\n\n*(Calorie estimate — not from database)*"

    # Log food
    if food_data and "calories" in food_data:
        food_data.setdefault("name", "Food item")
        food_data.setdefault("protein", 0)
        food_data.setdefault("carbs", 0)
        food_data.setdefault("fat", 0)
        food_data["time"]   = datetime.datetime.now().strftime("%I:%M %p")
        food_data["source"] = source
        st.session_state.food_log.append(food_data)

    st.session_state.messages.append({"role": "assistant", "content": reply})

# ── Helpers ────────────────────────────────────────────────────────────────────
def total_cals():
    return sum(f.get("calories", 0) for f in st.session_state.food_log)

def total_macro(macro):
    return sum(f.get(macro, 0) for f in st.session_state.food_log)

def pct(val, goal):
    return min(int(val / goal * 100), 100) if goal > 0 else 0

def bar_color(p):
    if p < 60: return "#5cb85c"
    if p < 90: return "#f0a500"
    return "#e05c5c"

# ── Load secret API key ────────────────────────────────────────────────────────
def get_secret_api_key():
    try:
        return st.secrets.get("OPENROUTER_API_KEY", "")
    except Exception:
        return ""

SECRET_API_KEY = get_secret_api_key()

# ── Session state ──────────────────────────────────────────────────────────────
for k, v in {
    "messages":   [],
    "food_log":   [],
    "daily_goal": 2000,
    "api_key":    SECRET_API_KEY,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Settings")

    if not SECRET_API_KEY:
        st.session_state.api_key = st.text_input(
            "OpenRouter API Key", type="password",
            placeholder="sk-or-v1-...",
            value=st.session_state.api_key,
        )
        if st.session_state.api_key:
            st.success("API key set ✓")
        else:
            st.info("Get a free key at [openrouter.ai](https://openrouter.ai/keys)")
    else:
        st.success("API key loaded ✓")

    st.markdown("---")
    st.session_state.daily_goal = st.number_input(
        "Daily Calorie Goal", min_value=800, max_value=5000,
        value=st.session_state.daily_goal, step=50,
    )

    st.markdown("---")
    st.markdown("**Data source**")
    st.markdown("🟢 Open Food Facts DB\n\n🟡 AI estimate (fallback)")

    st.markdown("---")
    if st.button("🗑️ Clear today's log"):
        st.session_state.food_log = []
        st.rerun()
    if st.button("💬 Reset chat"):
        st.session_state.messages = []
        st.rerun()

# ── Page ───────────────────────────────────────────────────────────────────────
st.markdown("## 🥗 CalBot — Daily Calorie Tracker")
st.markdown("<hr style='border:none;border-top:1px solid #e8e6df;margin:0 0 1.5rem'>", unsafe_allow_html=True)

left, right = st.columns([3, 2], gap="large")

# ── Chat ───────────────────────────────────────────────────────────────────────
with left:
    st.markdown('<div class="section-title">Chat with CalBot</div>', unsafe_allow_html=True)

    chat_box = st.container(height=420, border=False)
    with chat_box:
        if not st.session_state.messages:
            st.markdown('<div class="bubble-bot">👋 Hi! I\'m CalBot. Tell me what you\'ve eaten and I\'ll look up the exact calories from a nutrition database. Ask me anything!</div>', unsafe_allow_html=True)
        for msg in st.session_state.messages:
            content = msg["content"]
            if "FOOD_LOG_JSON:" in content:
                content = content.split("FOOD_LOG_JSON:")[0].strip()
            css = "bubble-user" if msg["role"] == "user" else "bubble-bot"
            st.markdown(f'<div class="{css}">{content}</div>', unsafe_allow_html=True)

    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "Message",
            placeholder="e.g. I had 2 rotis and dal…",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Send ➤", type="primary", use_container_width=True)

    if submitted and user_input.strip():
        with st.spinner("Looking up nutrition data…"):
            call_openrouter(user_input.strip())
        st.rerun()

# ── Dashboard ──────────────────────────────────────────────────────────────────
with right:
    cals   = total_cals()
    goal   = st.session_state.daily_goal
    remain = max(goal - cals, 0)
    p      = pct(cals, goal)
    color  = bar_color(p)

    c1, c2, c3 = st.columns(3)
    c1.markdown(f'<div class="metric-card"><div class="metric-label">Consumed</div><div class="metric-value" style="color:{color}">{cals}</div><div class="metric-sub">kcal</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card"><div class="metric-label">Remaining</div><div class="metric-value">{remain}</div><div class="metric-sub">kcal</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-card"><div class="metric-label">Goal</div><div class="metric-value">{goal}</div><div class="metric-sub">kcal</div></div>', unsafe_allow_html=True)

    st.markdown(f'<div class="prog-wrap"><div class="prog-fill" style="width:{p}%;background:{color}"></div></div>', unsafe_allow_html=True)
    st.caption(f"{p}% of daily goal")

    st.markdown('<div class="section-title">Macros today</div>', unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    m1.metric("Protein", f"{total_macro('protein'):.0f}g")
    m2.metric("Carbs",   f"{total_macro('carbs'):.0f}g")
    m3.metric("Fat",     f"{total_macro('fat'):.0f}g")

    st.markdown('<div class="section-title">Food log</div>', unsafe_allow_html=True)
    if not st.session_state.food_log:
        st.caption("No food logged yet. Tell CalBot what you've eaten!")
    else:
        for item in reversed(st.session_state.food_log):
            source_badge = '<span class="db-badge">DB</span>' if item.get("source") == "db" else '<span class="est-badge">EST</span>'
            st.markdown(
                f'<div class="food-row">'
                f'<span class="food-name">{item["name"]}{source_badge}</span>'
                f'<span style="font-size:11px;color:#aaa">{item.get("time","")}</span>'
                f'<span class="food-cal">{item["calories"]} kcal</span>'
                f'</div>',
                unsafe_allow_html=True
            )