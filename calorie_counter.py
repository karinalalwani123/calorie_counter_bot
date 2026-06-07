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
    .usda-badge { font-size: 10px; background: #e3f2fd; color: #1565c0; border-radius: 99px; padding: 1px 7px; margin-left: 6px; font-weight: 500; }
    .off-badge  { font-size: 10px; background: #e8f5e9; color: #2e7d32; border-radius: 99px; padding: 1px 7px; margin-left: 6px; font-weight: 500; }
    .est-badge  { font-size: 10px; background: #fff3e0; color: #e65100; border-radius: 99px; padding: 1px 7px; margin-left: 6px; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL          = "meta-llama/llama-3.3-70b-instruct"
USDA_BASE      = "https://api.nal.usda.gov/fdc/v1"
USDA_KEY       = "DEMO_KEY"  # Free, no signup needed. Rate limit: 30 req/hr
OFF_BASE       = "https://world.openfoodfacts.org/cgi/search.pl"

# ── USDA FoodData Central ──────────────────────────────────────────────────────
def search_usda(query):
    try:
        resp = requests.get(
            f"{USDA_BASE}/foods/search",
            params={"query": query, "pageSize": 5, "api_key": USDA_KEY},
            timeout=8,
        )
        foods = resp.json().get("foods", [])
        for food in foods:
            nutrients = {n["nutrientName"]: n["value"] for n in food.get("foodNutrients", [])}
            cal = nutrients.get("Energy", nutrients.get("Energy (Atwater General Factors)", 0))
            pro = nutrients.get("Protein", 0)
            carb = nutrients.get("Carbohydrate, by difference", 0)
            fat = nutrients.get("Total lipid (fat)", 0)
            if cal > 0:
                return {
                    "name":             food.get("description", query),
                    "calories_per_100g": round(cal, 1),
                    "protein_per_100g":  round(pro, 1),
                    "carbs_per_100g":    round(carb, 1),
                    "fat_per_100g":      round(fat, 1),
                    "source": "usda",
                }
        return None
    except Exception:
        return None

# ── Open Food Facts ────────────────────────────────────────────────────────────
def search_off(query):
    try:
        resp = requests.get(
            OFF_BASE,
            params={
                "search_terms": query, "search_simple": 1,
                "action": "process", "json": 1,
                "page_size": 8,
                "fields": "product_name,nutriments",
            },
            timeout=8,
        )
        for product in resp.json().get("products", []):
            n = product.get("nutriments", {})
            cal = n.get("energy-kcal_100g", 0)
            pro = n.get("proteins_100g", 0)
            carb = n.get("carbohydrates_100g", 0)
            fat = n.get("fat_100g", 0)
            if cal > 0:
                return {
                    "name":             product.get("product_name", query),
                    "calories_per_100g": round(cal, 1),
                    "protein_per_100g":  round(pro, 1),
                    "carbs_per_100g":    round(carb, 1),
                    "fat_per_100g":      round(fat, 1),
                    "source": "off",
                }
        return None
    except Exception:
        return None

# ── Unified DB search: USDA first, then OFF ────────────────────────────────────
# Indian prepared dishes — USDA only has raw ingredients, so skip DB and use Llama reasoning
INDIAN_DISHES = {
    "poha", "upma", "idli", "dosa", "sabudana", "khichdi", "biryani",
    "pulao", "paratha", "halwa", "kheer", "pav bhaji", "pav",
    "chole", "rajma", "dal makhani", "palak paneer", "paneer butter masala",
    "butter chicken", "chicken curry", "mutton curry", "sambar", "rasam",
    "vada", "medu vada", "uttapam", "dhokla", "thepla", "kadhi",
    "aloo gobi", "baingan", "bhindi", "sabzi", "curry", "korma",
    "lassi", "chai", "masala chai", "shrikhand", "raita",
}

def is_indian_dish(query):
    q = query.lower()
    return any(dish in q for dish in INDIAN_DISHES)

def search_nutrition(query):
    # Skip DB for Indian prepared dishes — raw ingredient data would be inaccurate
    if is_indian_dish(query):
        return None
    result = search_usda(query)
    if result:
        return result
    return search_off(query)

# ── Convert quantity+unit to grams ────────────────────────────────────────────
def to_grams(quantity, unit):
    unit = unit.lower().strip()
    mapping = {
        "gram": 1, "grams": 1, "g": 1,
        "kg": 1000, "kilogram": 1000,
        "cup": 240, "cups": 240,
        "bowl": 300, "bowls": 300,
        "plate": 350, "plates": 350,  # prepared Indian plate ~350g
        "slice": 40, "slices": 40,
        "piece": 100, "pieces": 100,
        "serving": 200,
        "tablespoon": 15, "tbsp": 15,
        "teaspoon": 5, "tsp": 5,
        "glass": 250, "glasses": 250,
        "ml": 1, "liter": 1000, "l": 1000,
        "oz": 28, "lb": 454,
        "handful": 30,
        "roti": 40, "chapati": 40,
        "paratha": 80,
    }
    return quantity * mapping.get(unit, 100)

# ── Extract all food items from message via Llama ─────────────────────────────
def extract_foods(user_msg, api_key):
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
                "max_tokens": 250,
                "messages": [
                    {"role": "system", "content": """Extract ALL food items and quantities from the user message.
Reply ONLY with a JSON array, no other text, no markdown fences.
Format: [{"food": "<simple searchable name>", "quantity": <number>, "unit": "<gram/cup/bowl/plate/piece/roti/paratha/slice/glass/tbsp>"}]

Rules:
- Split combined meals into individual items
- Use simple English names good for database search
- For Indian foods use transliterated names: "roti", "dal", "palak paneer", "sabudana khichdi"
- If no quantity mentioned use 1
- Guess unit sensibly: liquids=glass/cup, Indian breads=roti/paratha, rice/dal=cup, curries=cup

Examples:
"2 rotis with palak paneer" -> [{"food":"roti","quantity":2,"unit":"roti"},{"food":"palak paneer","quantity":1,"unit":"cup"}]
"sabudana khichdi plate" -> [{"food":"sabudana khichdi","quantity":1,"unit":"plate"}]
"3 eggs and milk" -> [{"food":"egg","quantity":3,"unit":"piece"},{"food":"milk","quantity":1,"unit":"glass"}]"""},
                    {"role": "user", "content": user_msg}
                ],
            },
            timeout=15,
        )
        resp.raise_for_status()
        text = re.sub(r"```json|```", "", resp.json()["choices"][0]["message"]["content"]).strip()
        return json.loads(text)
    except Exception:
        return None

# ── Llama fallback: estimate from ingredients knowledge ───────────────────────
def llama_estimate(items, api_key):
    """Ask Llama to estimate calories by reasoning from ingredients — no hardcoded values."""
    items_str = ", ".join(f"{i['quantity']} {i['unit']} of {i['food']}" for i in items)
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
                "max_tokens": 500,
                "messages": [
                    {"role": "system", "content": """You are a nutrition expert. For each food item given:
1. Think about its typical ingredients and cooking method
2. Estimate accurate calories and macros based on that reasoning
3. Output one line per food item in this exact format (no markdown, no extra text):
FOOD_LOG_JSON:{"name":"<food name>","calories":<int>,"protein":<float>,"carbs":<float>,"fat":<float>}

Be accurate. Reason from ingredients — do not guess randomly.
For Indian foods, consider typical preparation: oil/ghee used, main ingredients, portion size.
After all JSON lines, add one short friendly sentence."""},
                    {"role": "user", "content": f"Estimate nutrition for: {items_str}"}
                ],
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ Error: {e}"

# ── General chat (non-food questions) ─────────────────────────────────────────
def llama_chat(user_msg, api_key, history):
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
                "messages": [
                    {"role": "system", "content": "You are CalBot, a friendly nutrition assistant. Answer nutrition questions concisely. If the user mentions food they ate, remind them to log it."}
                ] + history + [{"role": "user", "content": user_msg}],
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ Error: {e}"

# ── Main chat handler ──────────────────────────────────────────────────────────
def call_openrouter(user_msg):
    api_key = st.session_state.api_key or SECRET_API_KEY
    if not api_key:
        st.session_state.messages.append({"role": "user", "content": user_msg})
        st.session_state.messages.append({"role": "assistant", "content": "⚠️ Please enter your OpenRouter API key in the sidebar first."})
        return

    st.session_state.messages.append({"role": "user", "content": user_msg})

    # Step 1: Extract food items
    foods = extract_foods(user_msg, api_key)

    if not foods:
        # Not a food message — general chat
        reply = llama_chat(user_msg, api_key, st.session_state.messages[:-1])
        st.session_state.messages.append({"role": "assistant", "content": reply})
        return

    logged_items  = []
    db_lines      = []
    missed_items  = []

    # Step 2: Look up each food in USDA → OFF
    for item in foods:
        food  = item.get("food", "")
        qty   = item.get("quantity", 1)
        unit  = item.get("unit", "piece")
        grams = to_grams(qty, unit)

        db = search_nutrition(food)
        if db:
            factor = grams / 100
            entry  = {
                "name":     f"{qty} {food}",
                "calories": round(db["calories_per_100g"] * factor),
                "protein":  round(db["protein_per_100g"]  * factor, 1),
                "carbs":    round(db["carbs_per_100g"]    * factor, 1),
                "fat":      round(db["fat_per_100g"]      * factor, 1),
                "time":     datetime.datetime.now().strftime("%I:%M %p"),
                "source":   db["source"],
            }
            logged_items.append(entry)
            src_label = "USDA" if db["source"] == "usda" else "OFF"
            db_lines.append(f"• {qty} {food} → **{entry['calories']} kcal** [{src_label}]")
        else:
            missed_items.append(item)

    # Step 3: Llama estimates for items not in any DB
    est_lines = []
    if missed_items:
        llama_reply = llama_estimate(missed_items, api_key)
        for line in llama_reply.split("\n"):
            if "FOOD_LOG_JSON:" in line:
                try:
                    fd = json.loads(line.split("FOOD_LOG_JSON:")[1].strip())
                    fd["time"]   = datetime.datetime.now().strftime("%I:%M %p")
                    fd["source"] = "estimate"
                    fd.setdefault("protein", 0)
                    fd.setdefault("carbs", 0)
                    fd.setdefault("fat", 0)
                    logged_items.append(fd)
                    est_lines.append(f"• {fd['name']} → **{fd['calories']} kcal** [AI estimate]")
                except Exception:
                    pass

    # Save to food log
    for entry in logged_items:
        st.session_state.food_log.append(entry)

    # Build a natural, conversational reply
    if logged_items:
        lines = []
        for e in logged_items:
            lines.append(f"{e['name'].title()} — {e['calories']} kcal | Protein: {e['protein']}g | Carbs: {e['carbs']}g | Fat: {e['fat']}g")

        if len(logged_items) == 1:
            item = logged_items[0]
            reply = (
                f"Logged! Here's the nutrition breakdown for {item['name'].title()}:\n\n"
                + "\n".join(lines)
            )
        else:
            total_cal  = sum(e["calories"] for e in logged_items)
            total_pro  = round(sum(e["protein"] for e in logged_items), 1)
            total_carb = round(sum(e["carbs"]   for e in logged_items), 1)
            total_fat  = round(sum(e["fat"]     for e in logged_items), 1)
            reply = (
                f"Logged! Here's the nutrition breakdown for your meal:\n\n"
                + "\n".join(lines)
                + f"\n\nMeal Total — {total_cal} kcal | Protein: {total_pro}g | Carbs: {total_carb}g | Fat: {total_fat}g"
            )
    else:
        reply = "I couldn't identify the food item. Could you describe it a bit more specifically?"

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

def get_secret_api_key():
    try:
        return st.secrets.get("OPENROUTER_API_KEY", "")
    except Exception:
        return ""

SECRET_API_KEY = get_secret_api_key()

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
    st.markdown("**Data source legend**")
    st.markdown("🔵 **USDA** = US Dept. of Agriculture\n\n🟢 **OFF** = Open Food Facts\n\n🟡 **EST** = AI ingredient reasoning")

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

with left:
    st.markdown('<div class="section-title">Chat with CalBot</div>', unsafe_allow_html=True)

    chat_box = st.container(height=420, border=False)
    with chat_box:
        if not st.session_state.messages:
            st.markdown('<div class="bubble-bot">👋 Hi! I\'m CalBot. Tell me what you\'ve eaten and I\'ll look up accurate calories from USDA & Open Food Facts databases. For Indian dishes, I\'ll reason from ingredients!</div>', unsafe_allow_html=True)
        for msg in st.session_state.messages:
            content = msg["content"]
            content = re.sub(r"FOOD_LOG_JSON:\{.*?\}", "", content).strip()
            css = "bubble-user" if msg["role"] == "user" else "bubble-bot"
            st.markdown(f'<div class="{css}">{content}</div>', unsafe_allow_html=True)

    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "Message",
            placeholder="e.g. 2 rotis with palak paneer and lassi…",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Send ➤", type="primary", use_container_width=True)

    if submitted and user_input.strip():
        with st.spinner("Fetching nutrition data…"):
            call_openrouter(user_input.strip())
        st.rerun()

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
            src = item.get("source", "estimate")
            if src == "usda":
                badge = '<span class="usda-badge">USDA</span>'
            elif src == "off":
                badge = '<span class="off-badge">OFF</span>'
            else:
                badge = '<span class="est-badge">EST</span>'
            st.markdown(
                f'<div class="food-row">'
                f'<span class="food-name">{item["name"]}{badge}</span>'
                f'<span style="font-size:11px;color:#aaa">{item.get("time","")}</span>'
                f'<span class="food-cal">{item["calories"]} kcal</span>'
                f'</div>',
                unsafe_allow_html=True
            )