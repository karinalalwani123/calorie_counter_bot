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
    div[data-testid="stButton"] > button[kind="primary"] {
        background: #1a1a1a !important; color: white !important; border: none !important;
        border-radius: 12px !important; font-weight: 500 !important; width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# ── Models ─────────────────────────────────────────────────────────────────────
MODELS = {
    "Llama 3.3 70B (free)":           "meta-llama/llama-3.3-70b-instruct",
    "Mistral Small 3.1 (free)":       "mistralai/mistral-small-3.1-24b-instruct:free",
}

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """You are CalBot, a friendly nutrition assistant embedded in a calorie-tracking app.

Your job:
1. Help users log food. When they mention eating something, extract nutritional data and respond with a JSON block (even if approximate).
2. Answer nutrition questions, give meal suggestions, and motivate healthy habits.
3. Be concise and warm — one short paragraph + data if needed.

When logging food, ALWAYS include this JSON block at the end of your reply (no markdown fences):
FOOD_LOG_JSON:{"name":"<food>","calories":<int>,"protein":<float>,"carbs":<float>,"fat":<float>}

For questions that don't involve logging, skip the JSON block.
Use reasonable average values when exact data is unknown. Be encouraging!"""

# ── Load API key from st.secrets (deployment) or session state (local) ────────
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
    "api_key":    SECRET_API_KEY,  # pre-filled from secrets if available
    "model":      "meta-llama/llama-3.3-70b-instruct",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── API call ───────────────────────────────────────────────────────────────────
def call_openrouter(user_msg):
    api_key = st.session_state.api_key or SECRET_API_KEY
    if not api_key:
        st.session_state.messages.append({"role": "user", "content": user_msg})
        st.session_state.messages.append({"role": "assistant", "content": "⚠️ Please enter your OpenRouter API key in the sidebar first."})
        return

    st.session_state.messages.append({"role": "user", "content": user_msg})

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
                "model": st.session_state.model,
                "max_tokens": 600,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + st.session_state.messages,
            },
            timeout=30,
        )
        resp.raise_for_status()
        reply = resp.json()["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response else "?"
        if code == 401:
            reply = "⚠️ Invalid API key — please check your OpenRouter key in the sidebar."
        elif code == 402:
            reply = "⚠️ Insufficient OpenRouter credits — please top up your account."
        else:
            reply = f"⚠️ API error {code}. Please try again."
    except Exception as e:
        reply = f"⚠️ Connection error: {e}"

    # Parse food JSON — try FOOD_LOG_JSON: tag first
    food_data = None
    if "FOOD_LOG_JSON:" in reply:
        try:
            json_str = reply.split("FOOD_LOG_JSON:")[1].strip().split("\n")[0]
            food_data = json.loads(json_str)
        except Exception:
            pass

    # Fallback: find any {...} block containing "calories"
    if not food_data:
        matches = re.findall(r'\{[^{}]*"calories"[^{}]*\}', reply)
        for m in matches:
            try:
                food_data = json.loads(m)
                break
            except Exception:
                pass

    if food_data and "calories" in food_data:
        food_data.setdefault("name", "Food item")
        food_data.setdefault("protein", 0)
        food_data.setdefault("carbs", 0)
        food_data.setdefault("fat", 0)
        food_data["time"] = datetime.datetime.now().strftime("%I:%M %p")
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

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Settings")

    # Only show API key input if no secret key is configured
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
        st.success("API key loaded from secrets ✓")

    st.markdown("---")
    model_label = st.selectbox(
        "Model",
        options=list(MODELS.keys()),
        index=list(MODELS.values()).index(st.session_state.model)
              if st.session_state.model in MODELS.values() else 1,
    )
    st.session_state.model = MODELS[model_label]

    st.markdown("---")
    st.session_state.daily_goal = st.number_input(
        "Daily Calorie Goal", min_value=800, max_value=5000,
        value=st.session_state.daily_goal, step=50,
    )

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
            st.markdown('<div class="bubble-bot">👋 Hi! I\'m CalBot. Tell me what you\'ve eaten and I\'ll log the calories. Ask me anything about nutrition!</div>', unsafe_allow_html=True)
        for msg in st.session_state.messages:
            content = msg["content"]
            if "FOOD_LOG_JSON:" in content:
                content = content.split("FOOD_LOG_JSON:")[0].strip()
            css = "bubble-user" if msg["role"] == "user" else "bubble-bot"
            st.markdown(f'<div class="{css}">{content}</div>', unsafe_allow_html=True)

    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "Message",
            placeholder="e.g. I had 2 scrambled eggs and toast…",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Send ➤", type="primary", use_container_width=True)

    if submitted and user_input.strip():
        with st.spinner("CalBot is thinking…"):
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
            st.markdown(
                f'<div class="food-row">'
                f'<span class="food-name">{item["name"]}</span>'
                f'<span style="font-size:11px;color:#aaa">{item.get("time","")}</span>'
                f'<span class="food-cal">{item["calories"]} kcal</span>'
                f'</div>',
                unsafe_allow_html=True
            )