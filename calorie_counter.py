import streamlit as st
import requests
import json
import re
import os
from datetime import date, datetime

# ── Persistence ────────────────────────────────────────────────────────────────
DATA_FILE = os.path.join(os.path.dirname(__file__), "calorie_log.json")

def load_log():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f: return json.load(f)
        except: pass
    return {}

def save_log(log):
    with open(DATA_FILE, "w") as f: json.dump(log, f, indent=2)

def today_key(): return date.today().isoformat()

def get_today(log):
    k = today_key()
    if k not in log:
        log[k] = {"cal":0,"protein":0.0,"carbs":0.0,"fat":0.0,"entries":[]}
    return log[k]

def add_entry(log, nutrition, query):
    t = get_today(log)
    t["cal"]     += nutrition.get("total_calories", 0)
    t["protein"] += nutrition.get("total_protein_g", 0.0)
    t["carbs"]   += nutrition.get("total_carbs_g", 0.0)
    t["fat"]     += nutrition.get("total_fat_g", 0.0)
    t["entries"].append({
        "time": datetime.now().strftime("%H:%M"),
        "query": query,
        "cal": nutrition.get("total_calories", 0),
        "protein": nutrition.get("total_protein_g", 0.0),
        "carbs": nutrition.get("total_carbs_g", 0.0),
        "fat": nutrition.get("total_fat_g", 0.0),
        "items": nutrition.get("items", []),
    })
    save_log(log)

def reset_today(log):
    log[today_key()] = {"cal":0,"protein":0.0,"carbs":0.0,"fat":0.0,"entries":[]}
    save_log(log)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Nourish · CalorieBot", page_icon="🌿", layout="wide", initial_sidebar_state="expanded")

# ── Design System ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;1,400&family=Outfit:wght@300;400;500;600&display=swap');

:root {
  --cream:    #faf7f2;
  --warm0:    #f5efe6;
  --warm1:    #ede4d5;
  --warm2:    #d9cab4;
  --bark:     #8b6f47;
  --bark2:    #6b5235;
  --forest:   #3d6b4f;
  --forest2:  #2d5040;
  --forest-l: #e8f2ec;
  --rust:     #c4622d;
  --rust-l:   #fbeee7;
  --gold:     #c89b3c;
  --gold-l:   #fdf5e4;
  --plum:     #7c4f8e;
  --plum-l:   #f3ecf7;
  --text:     #2c2016;
  --text2:    #6b5a45;
  --text3:    #a08c72;
  --border:   #e0d5c5;
  --shadow:   rgba(139,111,71,.10);
}

html,body,[class*="css"]{
  background: var(--cream) !important;
  color: var(--text) !important;
  font-family: 'Outfit', sans-serif !important;
}
header[data-testid="stHeader"]{display:none!important}
.block-container{padding:2rem 2.5rem 5rem!important; max-width:980px}
footer{display:none!important}

/* ── Sidebar ── */
section[data-testid="stSidebar"]{
  background: var(--warm0) !important;
  border-right: 1.5px solid var(--border) !important;
}
section[data-testid="stSidebar"] .block-container{padding:1.5rem 1.2rem!important}

/* ── Sidebar logo ── */
.sb-logo{
  font-family:'Playfair Display',serif;
  font-size:1.35rem;
  color:var(--forest2);
  display:flex; align-items:center; gap:8px;
  margin-bottom:1.2rem;
}
.sb-logo .leaf{font-size:1.6rem}

/* ── Macro ring card ── */
.ring-card{
  background:#fff;
  border:1.5px solid var(--border);
  border-radius:20px;
  padding:1.1rem 1rem 1rem;
  margin-bottom:.9rem;
  text-align:center;
  box-shadow:0 2px 12px var(--shadow);
}
.ring-card .big-cal{
  font-family:'Playfair Display',serif;
  font-size:2.6rem;
  color:var(--forest2);
  line-height:1;
  margin-bottom:.1rem;
}
.ring-card .cal-label{font-size:.72rem;color:var(--text3);letter-spacing:.08em;text-transform:uppercase;margin-bottom:.9rem}
.macro-pills{display:flex;gap:.4rem;justify-content:center;flex-wrap:wrap}
.mp{
  padding:.25rem .7rem;
  border-radius:30px;
  font-size:.72rem;
  font-weight:600;
}
.mp-p{background:var(--forest-l);color:var(--forest2)}
.mp-c{background:var(--gold-l);color:#8a6520}
.mp-f{background:var(--plum-l);color:var(--plum)}

/* ── Sidebar meal entries ── */
.sb-section{font-size:.68rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--text3);margin:.9rem 0 .4rem}
.sb-entry{
  display:flex; align-items:center; gap:.5rem;
  background:#fff; border:1px solid var(--border);
  border-radius:12px; padding:.45rem .7rem;
  margin-bottom:.35rem; font-size:.78rem;
}
.sb-entry .se-dot{
  width:8px;height:8px;border-radius:50%;
  background:var(--forest);flex-shrink:0;
}
.sb-entry .se-name{flex:1;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sb-entry .se-cal{color:var(--rust);font-weight:600;font-size:.8rem;flex-shrink:0}
.sb-entry .se-time{color:var(--text3);font-size:.68rem;flex-shrink:0}

/* ── Example pills ── */
.sb-section-ex{font-size:.68rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--text3);margin:.9rem 0 .4rem}

/* ── Sidebar buttons ── */
.stButton>button{
  background:var(--forest)!important; color:#fff!important;
  border:none!important; border-radius:10px!important;
  font-weight:500!important; font-family:'Outfit',sans-serif!important;
  font-size:.82rem!important; padding:.4rem .9rem!important;
  transition:background .2s!important;
}
.stButton>button:hover{background:var(--forest2)!important}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"]{
  background:var(--warm1)!important;
  border-radius:12px!important; padding:4px!important;
  gap:4px!important; border:none!important;
}
.stTabs [data-baseweb="tab"]{
  border-radius:9px!important; font-family:'Outfit',sans-serif!important;
  font-size:.88rem!important; font-weight:500!important;
  color:var(--text2)!important; padding:.4rem 1.2rem!important;
  background:transparent!important; border:none!important;
}
.stTabs [aria-selected="true"]{
  background:#fff!important; color:var(--forest2)!important;
  box-shadow:0 1px 4px var(--shadow)!important;
}
.stTabs [data-baseweb="tab-border"]{display:none!important}
.stTabs [data-baseweb="tab-panel"]{padding-top:1.2rem!important}

/* ── Hero ── */
.hero{
  background: linear-gradient(135deg, #2d5040 0%, #3d6b4f 55%, #4a7a5c 100%);
  border-radius:24px; padding:2.2rem 2.8rem 2rem;
  margin-bottom:1.6rem; position:relative; overflow:hidden;
}
.hero::after{
  content:"🌿";font-size:8rem;position:absolute;
  right:-1rem;top:-1rem;opacity:.12;filter:blur(1px);
  pointer-events:none;
}
.hero-tag{
  display:inline-flex; align-items:center; gap:6px;
  background:rgba(255,255,255,.15); border:1px solid rgba(255,255,255,.25);
  color:rgba(255,255,255,.9); font-size:.72rem; font-weight:500;
  padding:.2rem .75rem; border-radius:30px; letter-spacing:.06em;
  margin-bottom:.7rem;
}
.hero h1{
  font-family:'Playfair Display',serif;
  font-size:2.6rem; color:#fff; margin:0 0 .35rem; line-height:1.15;
}
.hero h1 em{font-style:italic;color:#a8d5b5}
.hero p{color:rgba(255,255,255,.72);margin:0;font-size:.95rem;max-width:520px}

/* ── Chat bubbles ── */
.bubble{
  max-width:86%; border-radius:18px;
  padding:1rem 1.2rem; font-size:.92rem; line-height:1.65;
  animation:popIn .2s cubic-bezier(.34,1.56,.64,1);
}
@keyframes popIn{from{opacity:0;transform:scale(.96) translateY(6px)}to{opacity:1;transform:scale(1) translateY(0)}}

.bubble-user{
  align-self:flex-end;
  background:linear-gradient(135deg,var(--forest) 0%,var(--forest2) 100%);
  color:#fff; border-bottom-right-radius:5px;
  box-shadow:0 3px 12px rgba(45,80,64,.25);
}
.bubble-bot{
  align-self:flex-start;
  background:#fff; color:var(--text);
  border:1.5px solid var(--border);
  border-bottom-left-radius:5px;
  box-shadow:0 2px 10px var(--shadow);
}
.bot-tag{
  display:flex; align-items:center; gap:6px;
  font-size:.68rem; font-weight:600; letter-spacing:.1em;
  text-transform:uppercase; color:var(--forest);
  margin-bottom:.45rem;
}
.bot-tag::before{
  content:""; display:block; width:6px;height:6px;
  border-radius:50%; background:var(--forest);
}

/* ── Nutrition card ── */
.nut-card{
  background:var(--warm0); border:1.5px solid var(--border);
  border-radius:14px; overflow:hidden; margin-top:.8rem;
}
.nut-card-header{
  display:flex; justify-content:space-between; align-items:center;
  padding:.55rem 1rem; background:var(--warm1);
  border-bottom:1px solid var(--border);
}
.nut-card-header span{font-size:.72rem;font-weight:600;color:var(--text2);text-transform:uppercase;letter-spacing:.07em}
.nut-card-header .total-badge{
  background:var(--forest); color:#fff;
  font-size:.8rem; font-weight:600; padding:.15rem .65rem;
  border-radius:30px;
}
.nut-table{width:100%;border-collapse:collapse;font-size:.83rem}
.nut-table th{
  color:var(--text3); font-weight:500; text-align:left;
  padding:.4rem .8rem; font-size:.72rem; text-transform:uppercase; letter-spacing:.06em;
  border-bottom:1px solid var(--border); background:var(--warm0);
}
.nut-table th:not(:first-child){text-align:right}
.nut-table td{padding:.4rem .8rem; border-bottom:1px solid var(--border); color:var(--text2)}
.nut-table td:not(:first-child){text-align:right;color:var(--text3)}
.nut-table td:first-child{color:var(--text);font-weight:500}
.nut-table tr:last-child td{border-bottom:none}
.nut-total td{background:var(--forest-l)!important; color:var(--forest2)!important; font-weight:600!important}
.nut-total td:not(:first-child){color:var(--forest)!important}
.nut-tip{
  padding:.5rem .9rem; font-size:.78rem; color:var(--bark);
  background:var(--gold-l); border-top:1px solid #e8d9b0;
  display:flex; align-items:flex-start; gap:.4rem;
}
.nut-tip::before{content:"✦"; color:var(--gold); flex-shrink:0; margin-top:1px}

/* ── Input ── */
.stTextInput>div>div>input{
  background:#fff!important; border:1.5px solid var(--border)!important;
  border-radius:14px!important; color:var(--text)!important;
  font-size:.93rem!important; font-family:'Outfit',sans-serif!important;
  padding:.7rem 1.1rem!important; box-shadow:0 1px 4px var(--shadow)!important;
}
.stTextInput>div>div>input:focus{
  border-color:var(--forest)!important;
  box-shadow:0 0 0 3px rgba(61,107,79,.12)!important;
}
.stTextInput>div>div>input::placeholder{color:var(--text3)!important}

/* ── Send button ── */
div[data-testid="column"]:last-child .stButton>button{
  background:var(--rust)!important;
  box-shadow:0 3px 10px rgba(196,98,45,.3)!important;
  border-radius:14px!important;
  padding:.7rem 1.3rem!important;
  font-size:.9rem!important;
}
div[data-testid="column"]:last-child .stButton>button:hover{
  background:#a8521f!important;
}

/* ── History ── */
.hist-card{
  background:#fff; border:1.5px solid var(--border);
  border-radius:20px; padding:1.1rem 1.3rem;
  margin-bottom:1rem; box-shadow:0 2px 8px var(--shadow);
}
.hist-date{
  font-family:'Playfair Display',serif; font-size:1.05rem;
  color:var(--bark2); margin-bottom:.6rem;
  display:flex; justify-content:space-between; align-items:center;
}
.hist-date .today-tag{
  font-family:'Outfit',sans-serif; font-size:.68rem; font-weight:600;
  background:var(--forest); color:#fff;
  padding:.15rem .65rem; border-radius:30px; letter-spacing:.05em;
}
.hist-macros{display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:.8rem}
.hm{padding:.25rem .8rem;border-radius:30px;font-size:.76rem;font-weight:600}
.hm-cal{background:var(--rust-l);color:var(--rust)}
.hm-p{background:var(--forest-l);color:var(--forest2)}
.hm-c{background:var(--gold-l);color:#8a6520}
.hm-f{background:var(--plum-l);color:var(--plum)}
.hist-entry{
  display:flex; align-items:center; gap:.75rem;
  padding:.5rem .7rem; border-radius:10px;
  background:var(--warm0); margin-bottom:.35rem;
  border:1px solid var(--border);
}
.he-icon{font-size:1.1rem;flex-shrink:0}
.he-body{flex:1;min-width:0}
.he-name{font-size:.85rem;font-weight:500;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.he-meta{font-size:.72rem;color:var(--text3);margin-top:1px}
.he-cal{font-size:.85rem;font-weight:600;color:var(--rust);flex-shrink:0}

/* ── Expander overrides ── */
details summary{color:var(--text2)!important;font-size:.83rem!important}
details[open] summary{color:var(--forest)!important}

/* ── Spinner ── */
div[data-testid="stSpinner"] p{color:var(--forest)!important;font-family:'Outfit',sans-serif!important}

/* ── Disclaimer ── */
.disclaimer{color:var(--text3);font-size:.72rem;border-top:1px solid var(--border);padding-top:.7rem;margin-top:1rem;line-height:1.5}

/* ── Download button ── */
.stDownloadButton>button{
  background:transparent!important; color:var(--bark)!important;
  border:1.5px solid var(--border)!important; border-radius:10px!important;
  font-size:.8rem!important; padding:.4rem .9rem!important;
}
.stDownloadButton>button:hover{background:var(--warm1)!important}

/* ── Scrollbar ── */
::-webkit-scrollbar{width:5px}
::-webkit-scrollbar-track{background:var(--warm0)}
::-webkit-scrollbar-thumb{background:var(--warm2);border-radius:10px}
</style>
""", unsafe_allow_html=True)

# ── LLM ───────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Nourish, a precise nutritional assistant powered by evidence-based food databases.

For EVERY food or meal query, respond with:
1. One warm, friendly intro sentence.
2. A JSON block (inside ```json ... ```) with this exact schema:
   {
     "items": [{"name":"Food name","qty":"portion","calories":123,"protein_g":10.2,"carbs_g":20.1,"fat_g":5.3}],
     "total_calories":123,"total_protein_g":10.2,"total_carbs_g":20.1,"total_fat_g":5.3,
     "notes":"brief tip"
   }
3. One brief, encouraging concluding tip.

Use USDA/NIH nutritional values. For general nutrition questions, answer conversationally without JSON."""

def call_ollama(messages, model):
    try:
        with requests.post("http://localhost:11434/api/chat",
            json={"model":model,"messages":messages,"stream":True},
            stream=True, timeout=120) as r:
            if r.status_code != 200:
                yield f"❌ Ollama error {r.status_code}"; return
            for line in r.iter_lines():
                if line:
                    chunk = json.loads(line)
                    t = chunk.get("message",{}).get("content","")
                    if t: yield t
                    if chunk.get("done"): break
    except requests.exceptions.ConnectionError:
        yield "❌ **Can't reach Ollama.** Run `ollama serve` then `ollama pull llama3.2`"

def parse_nutrition(text):
    m = re.search(r"```json\s*([\s\S]*?)```", text)
    raw = m.group(1) if m else None
    if not raw:
        m2 = re.search(r"\{[\s\S]*\"items\"[\s\S]*\}", text)
        raw = m2.group(0) if m2 else None
    if not raw: return None
    try: return json.loads(raw)
    except: return None

FOOD_ICONS = ["🥗","🍱","🥘","🍲","🥙","🫕","🍛","🥣","🍜","🥚","🍗","🥩","🫙","🥦","🍚"]

def render_nutrition_card(data, query=""):
    rows = ""
    for item in data.get("items", []):
        rows += f"""<tr>
          <td>{item['name']}</td>
          <td>{item.get('qty','—')}</td>
          <td>{item['calories']}</td>
          <td>{item.get('protein_g','—')}g</td>
          <td>{item.get('carbs_g','—')}g</td>
          <td>{item.get('fat_g','—')}g</td></tr>"""
    rows += f"""<tr class="nut-total">
      <td colspan="2">Total</td>
      <td>{data.get('total_calories','—')}</td>
      <td>{data.get('total_protein_g','—')}g</td>
      <td>{data.get('total_carbs_g','—')}g</td>
      <td>{data.get('total_fat_g','—')}g</td></tr>"""
    return f"""<div class="nut-card">
      <div class="nut-card-header">
        <span>Nutrition breakdown</span>
        <span class="total-badge">{data.get('total_calories','?')} kcal</span>
      </div>
      <table class="nut-table">
        <thead><tr>
          <th>Food</th><th>Portion</th>
          <th>Kcal</th><th>Protein</th><th>Carbs</th><th>Fat</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
      <div class="nut-tip">{data.get('notes','')}</div>
    </div>"""

# ── State ─────────────────────────────────────────────────────────────────────
if "log" not in st.session_state: st.session_state.log = load_log()
if "messages" not in st.session_state: st.session_state.messages = []
log = st.session_state.log
today_data = get_today(log)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sb-logo"><span class="leaf">🌿</span> Nourish</div>', unsafe_allow_html=True)

    model = st.text_input("Model", value="llama3.2", label_visibility="collapsed",
                          placeholder="Ollama model (e.g. llama3.2)")

    # Macro ring card
    st.markdown(f"""
    <div class="ring-card">
      <div class="big-cal">{int(today_data['cal'])}</div>
      <div class="cal-label">kcal · {date.today().strftime('%d %b')}</div>
      <div class="macro-pills">
        <div class="mp mp-p">P {today_data['protein']:.1f}g</div>
        <div class="mp mp-c">C {today_data['carbs']:.1f}g</div>
        <div class="mp mp-f">F {today_data['fat']:.1f}g</div>
      </div>
    </div>""", unsafe_allow_html=True)

    entries = today_data.get("entries", [])
    if entries:
        st.markdown('<div class="sb-section">Today\'s meals</div>', unsafe_allow_html=True)
        for e in reversed(entries[-5:]):
            icon = FOOD_ICONS[hash(e['query']) % len(FOOD_ICONS)]
            st.markdown(f"""
            <div class="sb-entry">
              <div class="se-dot"></div>
              <div class="se-name">{e['query']}</div>
              <div class="se-cal">{int(e['cal'])}</div>
              <div class="se-time">{e['time']}</div>
            </div>""", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("↺ Reset", use_container_width=True):
            reset_today(log); st.session_state.messages = []; st.rerun()
    with c2:
        st.download_button("↓ Export", json.dumps(log, indent=2),
                           "nourish_log.json", use_container_width=True)

    st.markdown('<div class="sb-section-ex">Try asking</div>', unsafe_allow_html=True)
    examples = ["Masala dosa with sambar","2 eggs scrambled with toast",
                "Dal rice with ghee","200g grilled chicken","Big Mac large meal"]
    for ex in examples:
        if st.button(ex, key=ex, use_container_width=True):
            st.session_state["prefill"] = ex; st.rerun()

    st.markdown('<div class="disclaimer">📁 Saved to nourish_log.json · Values are estimates. Not medical advice.</div>',
                unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_chat, tab_history = st.tabs(["  💬  Chat  ", "  📖  History  "])

# ════════════════════════════════════════════════════════════════
# CHAT
# ════════════════════════════════════════════════════════════════
with tab_chat:
    st.markdown("""
    <div class="hero">
      <div class="hero-tag">🌿 AI-Powered · Auto-saved</div>
      <h1>Know what you <em>eat.</em></h1>
      <p>Ask about any meal, ingredient, or recipe and get an instant breakdown of calories and macros.</p>
    </div>""", unsafe_allow_html=True)

    for msg in st.session_state.messages:
        role    = msg.get("role", "user")
        display = msg.get("display") or msg.get("content", "")
        if role == "user":
            st.markdown(f'<div class="bubble bubble-user">{display}</div>', unsafe_allow_html=True)
        else:
            html = msg.get("html") or display
            st.markdown(f'<div class="bubble bubble-bot"><div class="bot-tag">Nourish AI</div>{html}</div>', unsafe_allow_html=True)

    prefill = st.session_state.pop("prefill", "")
    c1, c2 = st.columns([5, 1])
    with c1:
        user_input = st.text_input("food", value=prefill,
            placeholder="What did you eat? e.g. 'paneer butter masala, 1 roti'",
            label_visibility="collapsed", key="user_input")
    with c2:
        send = st.button("Send ↗", use_container_width=True)

    if (send or prefill) and user_input.strip():
        query = user_input.strip()
        st.session_state.messages.append({"role":"user","display":query})
        st.markdown(f'<div class="bubble bubble-user">{query}</div>', unsafe_allow_html=True)

        api_msgs = [{"role":"system","content":SYSTEM_PROMPT}]
        for m in st.session_state.messages[:-1]:
            api_msgs.append({"role": m.get("role","user"), "content": m.get("display") or m.get("content", "")})
        api_msgs.append({"role":"user","content":query})

        placeholder = st.empty()
        full = ""
        with st.spinner("Analysing nutrition…"):
            for token in call_ollama(api_msgs, model):
                full += token
                placeholder.markdown(
                    f'<div class="bubble bubble-bot"><div class="bot-tag">Nourish AI</div>{full}▌</div>',
                    unsafe_allow_html=True)

        nutrition = parse_nutrition(full)
        clean = re.sub(r"```json[\s\S]*?```", "", full).strip()

        if nutrition:
            card = render_nutrition_card(nutrition, query)
            final_html = f"{clean}<br>{card}"
            add_entry(log, nutrition, query)
            today_data = get_today(log)
        else:
            final_html = clean

        placeholder.markdown(
            f'<div class="bubble bubble-bot"><div class="bot-tag">Nourish AI</div>{final_html}</div>',
            unsafe_allow_html=True)
        st.session_state.messages.append({"role":"assistant","display":full,"html":final_html})
        st.rerun()

# ════════════════════════════════════════════════════════════════
# HISTORY
# ════════════════════════════════════════════════════════════════
with tab_history:
    st.markdown("<br>", unsafe_allow_html=True)
    if not log:
        st.markdown("""<div style="text-align:center;padding:3rem 0;color:var(--text3)">
          <div style="font-size:3rem;margin-bottom:.5rem">🌱</div>
          <div style="font-size:1rem;font-family:'Playfair Display',serif;color:var(--bark)">Your food journal is empty</div>
          <div style="font-size:.85rem;margin-top:.3rem">Start logging meals in the Chat tab</div>
        </div>""", unsafe_allow_html=True)
    else:
        for day_key in sorted(log.keys(), reverse=True):
            day = log[day_key]
            entries = day.get("entries", [])
            is_today = day_key == today_key()
            try: label = datetime.fromisoformat(day_key).strftime("%A, %d %B %Y")
            except: label = day_key

            today_tag = '<span class="today-tag">TODAY</span>' if is_today else ""
            st.markdown(f"""
            <div class="hist-card">
              <div class="hist-date">{label} {today_tag}</div>
              <div class="hist-macros">
                <span class="hm hm-cal">{int(day['cal'])} kcal</span>
                <span class="hm hm-p">P {day['protein']:.1f}g</span>
                <span class="hm hm-c">C {day['carbs']:.1f}g</span>
                <span class="hm hm-f">F {day['fat']:.1f}g</span>
              </div>
              {''.join(f"""<div class="hist-entry">
                <div class="he-icon">{FOOD_ICONS[hash(e['query']) % len(FOOD_ICONS)]}</div>
                <div class="he-body">
                  <div class="he-name">{e['query']}</div>
                  <div class="he-meta">{e['time']} · P {e['protein']:.1f}g · C {e['carbs']:.1f}g · F {e['fat']:.1f}g</div>
                </div>
                <div class="he-cal">{int(e['cal'])} kcal</div>
              </div>""" for e in entries) if entries else '<div style="color:var(--text3);font-size:.83rem;padding:.3rem 0">No entries</div>'}
            </div>""", unsafe_allow_html=True)

            if entries:
                for e in entries:
                    if e.get("items"):
                        with st.expander(f"↳ Breakdown: {e['query']}", expanded=False):
                            for item in e["items"]:
                                st.markdown(
                                    f"**{item['name']}** ({item.get('qty','')}) — "
                                    f"`{item.get('calories','?')} kcal` · "
                                    f"P `{item.get('protein_g','?')}g` · "
                                    f"C `{item.get('carbs_g','?')}g` · "
                                    f"F `{item.get('fat_g','?')}g`")