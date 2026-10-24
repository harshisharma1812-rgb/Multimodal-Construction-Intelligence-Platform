"""Multimodal Construction Intelligence Platform - Skill Wallet Capstone Project 1.
Run: streamlit run app.py   |   Deploy: push app.py + requirements.txt to GitHub -> Streamlit Community Cloud.
"""
import json
import re
import urllib.parse
from datetime import datetime

import streamlit as st
from PIL import Image

try:
    from google import genai
    from google.genai import types
except ImportError:  # app still runs in demo mode
    genai = None

MODEL = "gemini-2.5-flash"

st.set_page_config(page_title="Construction Intelligence Platform", page_icon="🏗️", layout="wide")

# ----------------------------------------------------------------------------- styling
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;600;800&family=Source+Serif+4:wght@400;600&display=swap');
:root{--ink:#1d2733;--steel:#3d5266;--concrete:#e9e7e2;--hi-vis:#f2c200;--ok:#2f7d4f;--warn:#c77d0a;--bad:#b3261e;}
html,body,[class*="css"]{font-family:'Source Serif 4',Georgia,serif;}
h1,h2,h3,.hero h1,.metric .v,.pill{font-family:'Archivo',sans-serif;}
.hero{background:var(--ink);color:#fff;padding:1.4rem 1.8rem;border-left:10px solid var(--hi-vis);border-radius:4px;margin-bottom:1rem;}
.hero h1{margin:0;font-size:1.8rem;font-weight:800;color:#fff;} .hero p{margin:.3rem 0 0;color:#c9d3dd;}
.metric{background:var(--concrete);border-radius:6px;padding:.9rem 1rem;border-bottom:4px solid var(--steel);}
.metric .l{font-size:.85rem;color:var(--steel);} .metric .v{font-size:1.7rem;font-weight:800;color:var(--ink);}
.pill{display:inline-block;padding:.15rem .7rem;border-radius:999px;font-size:.8rem;font-weight:600;color:#fff;}
.Low,.pass{background:var(--ok);} .Medium{background:var(--warn);} .High,.fail{background:var(--bad);} .Critical{background:#6d0f0a;}
.haz{border:1px solid #cfcac1;border-left:6px solid var(--steel);padding:.7rem .9rem;border-radius:4px;margin-bottom:.6rem;}
.alert{padding:1rem 1.2rem;border-radius:6px;background:#fff6d6;border-left:8px solid var(--hi-vis);margin-bottom:.6rem;}
.alert.red{background:#fdeceb;border-color:var(--bad);}
</style>""", unsafe_allow_html=True)


def metric(label, value):
    st.markdown(f'<div class="metric"><div class="l">{label}</div><div class="v">{value}</div></div>', unsafe_allow_html=True)


def pill(text, cls):
    return f'<span class="pill {cls}">{text}</span>'


# ----------------------------------------------------------------------------- Gemini layer
def get_client():
    key = st.session_state.get("api_key", "").strip()
    if not key or genai is None:
        return None
    try:
        return genai.Client(api_key=key)
    except Exception as e:  # invalid key format etc.
        st.sidebar.error(f"Client error: {e}")
        return None


def parse_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text)


def analyze_image(prompt, image, demo_payload):
    """Returns (result_dict, mode). Falls back to demo data on any failure."""
    client = get_client()
    if client is None:
        return demo_payload, "demo"
    try:
        resp = client.models.generate_content(
            model=MODEL, contents=[prompt, image],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2))
        return parse_json(resp.text), "live"
    except json.JSONDecodeError:
        st.warning("Model returned malformed JSON; showing demonstration output.")
    except Exception as e:
        st.warning(f"Gemini request failed ({type(e).__name__}: {e}). Showing demonstration output.")
    return demo_payload, "demo"


SAFETY_PROMPT = """You are a certified construction safety officer. Audit this site photo for worker PPE
compliance and site hazards under OSHA 1926 and relevant Indian Standards (IS 456 for concrete/formwork, NBC 2016 safety).
Check helmets, high-visibility vests, steel-toe boots, safety harnesses. If no workers are visible, mark items "Not Visible".
Return ONLY JSON with this schema:
{"safety_score": int 0-100, "overall_status": "Compliant|Needs Improvement|Non-Compliant|Critical",
 "summary": str,
 "ppe_detection": {"helmet": "Detected|Missing|Not Visible", "high_vis_vest": "...", "steel_toe_boots": "...", "safety_harness": "..."},
 "hazards": [{"hazard": str, "severity": "Low|Medium|High|Critical", "standard_reference": str, "remedy": str}]}"""

CRACK_PROMPT = """You are a structural engineer. Examine this concrete/wall surface photo. Classify the defect as exactly one of:
Hairline, Settlement, Structural Shear, Thermal Expansion, Spalling. Estimate crack width in mm (use any scale reference visible; state uncertainty).
Reference IS 456 / IS 13935 for repair guidance. Return ONLY JSON:
{"defect_type": str, "confidence": int 0-100, "estimated_width_mm": number, "pattern": str,
 "root_causes": [str], "recommended_repairs": [str], "urgency": "Monitor|Within 3 Months|Within 2 Weeks|Immediate",
 "structural_risk": "Low|Medium|High|Critical", "notes": str}"""

DEMO_SAFETY = {
    "safety_score": 62, "overall_status": "Needs Improvement",
    "summary": "DEMO DATA: Most workers wear helmets, but vests and harnesses are inconsistent at elevation.",
    "ppe_detection": {"helmet": "Detected", "high_vis_vest": "Missing", "steel_toe_boots": "Detected", "safety_harness": "Missing"},
    "hazards": [
        {"hazard": "Unprotected edge at upper slab", "severity": "Critical", "standard_reference": "OSHA 1926.501", "remedy": "Install guardrails and toe boards; enforce 100% harness tie-off."},
        {"hazard": "Loose scaffold planks", "severity": "High", "standard_reference": "OSHA 1926.451", "remedy": "Secure and inspect scaffolding daily by a competent person."},
        {"hazard": "Exposed rebar ends", "severity": "Medium", "standard_reference": "OSHA 1926.701(b)", "remedy": "Fit rebar caps on all protruding bars."},
        {"hazard": "Debris on walkway", "severity": "Low", "standard_reference": "OSHA 1926.25", "remedy": "Daily housekeeping and designated waste zones."}]}
DEMO_CRACK = {
    "defect_type": "Structural Shear", "confidence": 78, "estimated_width_mm": 2.5,
    "pattern": "DEMO DATA: Diagonal (~45°) crack near beam-column joint, widening toward the support.",
    "root_causes": ["Inadequate shear reinforcement / stirrup spacing", "Overloading beyond design live load", "Differential foundation movement"],
    "recommended_repairs": ["Epoxy injection (low-viscosity) for crack sealing", "Structural re-grouting with non-shrink cement grout", "Jacketing / FRP wrapping of affected member after structural audit"],
    "urgency": "Within 2 Weeks", "structural_risk": "High",
    "notes": "Install tell-tale gauges; consult a licensed structural engineer before repair."}

# ----------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("🏗️ Control Panel")
    st.text_input("Google Gemini API key", type="password", key="api_key",
                  help="Get a free key at aistudio.google.com. Kept in session memory only.")
    live = bool(st.session_state.get("api_key", "").strip()) and genai is not None
    st.markdown(pill("LIVE · Gemini" if live else "DEMO MODE", "pass" if live else "Medium"), unsafe_allow_html=True)
    if not live:
        st.caption("No key supplied: sample outputs are shown so every feature remains explorable.")
    st.divider()
    st.subheader("Architecture")
    st.markdown("""
- **UI:** Streamlit, custom CSS
- **Vision/LLM:** Gemini (`google-genai`), JSON-mode outputs
- **Estimator:** rule-based cost engine
- **Renders:** Pollinations AI (URL based)
- **State:** `st.session_state` only, no database
""")
    st.subheader("Modules")
    st.markdown("1. Safety & PPE audit\n2. Crack diagnostics\n3. Planning & valuation\n4. Weather-aware assistant")
    st.caption("Skill Wallet Capstone Project 1")

st.markdown('<div class="hero"><h1>Multimodal Construction Intelligence Platform</h1>'
            '<p>Photo-based safety audits, crack diagnostics, budget and valuation planning, and a weather-aware site assistant.</p></div>',
            unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["🦺 Safety & PPE Audit", "🧱 Crack Diagnostics", "📐 Planning & Valuation", "🌦️ Site Assistant"])

# ----------------------------------------------------------------------------- Tab 1
with tab1:
    st.subheader("Site Safety & PPE Audit")
    up = st.file_uploader("Upload a construction site photo", type=["jpg", "jpeg", "png"], key="safety_up")
    if up:
        try:
            img = Image.open(up).convert("RGB")
        except Exception:
            st.error("Could not read that image. Please upload a valid JPG or PNG.")
            img = None
        if img:
            c1, c2 = st.columns([1, 1.3])
            c1.image(img, caption=up.name, use_container_width=True)
            if c2.button("Run safety audit", type="primary"):
                with st.spinner("Analysing PPE and hazards..."):
                    st.session_state["safety"] = analyze_image(SAFETY_PROMPT, img, DEMO_SAFETY)
    if "safety" in st.session_state:
        r, mode = st.session_state["safety"]
        st.caption(f"Result source: {mode} analysis")
        score = int(r.get("safety_score", 0))
        status = r.get("overall_status", "Unknown")
        cls = "pass" if score >= 80 else "Medium" if score >= 60 else "High"
        hz = r.get("hazards", [])
        m = st.columns(4)
        with m[0]: metric("Safety score", f"{score}/100")
        with m[1]: metric("Status", status)
        with m[2]: metric("Hazards found", len(hz))
        with m[3]: metric("Critical / High", sum(h.get("severity") in ("Critical", "High") for h in hz))
        st.progress(min(max(score, 0), 100) / 100)
        st.markdown(pill(status, cls), unsafe_allow_html=True)
        st.write(r.get("summary", ""))
        st.markdown("##### PPE checklist")
        ppe = r.get("ppe_detection", {})
        cols = st.columns(max(len(ppe), 1))
        for col, (k, v) in zip(cols, ppe.items()):
            tone = "pass" if v == "Detected" else "fail" if v == "Missing" else "Medium"
            col.markdown(f"**{k.replace('_', ' ').title()}**<br>{pill(v, tone)}", unsafe_allow_html=True)
        st.markdown("##### Identified hazards")
        for h in sorted(hz, key=lambda x: ["Critical", "High", "Medium", "Low"].index(x.get("severity", "Low"))
                        if x.get("severity") in ("Critical", "High", "Medium", "Low") else 9):
            sev = h.get("severity", "Low")
            st.markdown(f'<div class="haz">{pill(sev, sev)} <b>{h.get("hazard","")}</b>'
                        f'<br><small>{h.get("standard_reference","")}</small><br>🔧 {h.get("remedy","")}</div>',
                        unsafe_allow_html=True)
        st.download_button("Download JSON report", json.dumps({**r, "generated": datetime.now().isoformat()}, indent=2),
                           "safety_report.json", "application/json")
    elif not up:
        st.info("Upload a site photo to begin. In demo mode you will see a sample audit.")

# ----------------------------------------------------------------------------- Tab 2
with tab2:
    st.subheader("Crack Diagnostics & Structural Integrity")
    up2 = st.file_uploader("Upload a concrete or wall surface photo", type=["jpg", "jpeg", "png"], key="crack_up")
    if up2:
        try:
            img2 = Image.open(up2).convert("RGB")
        except Exception:
            st.error("Could not read that image. Please upload a valid JPG or PNG.")
            img2 = None
        if img2:
            c1, c2 = st.columns([1, 1.3])
            c1.image(img2, caption=up2.name, use_container_width=True)
            if c2.button("Diagnose defect", type="primary"):
                with st.spinner("Classifying defect..."):
                    st.session_state["crack"] = analyze_image(CRACK_PROMPT, img2, DEMO_CRACK)
    if "crack" in st.session_state:
        r, mode = st.session_state["crack"]
        st.caption(f"Result source: {mode} analysis")
        risk = r.get("structural_risk", "Low")
        m = st.columns(4)
        with m[0]: metric("Defect type", r.get("defect_type", "-"))
        with m[1]: metric("Crack width", f'{r.get("estimated_width_mm", "-")} mm')
        with m[2]: metric("Confidence", f'{r.get("confidence", "-")}%')
        with m[3]: metric("Urgency", r.get("urgency", "-"))
        st.markdown(f'Structural risk: {pill(risk, risk if risk in ("Low","Medium","High","Critical") else "Medium")}', unsafe_allow_html=True)
        st.write(r.get("pattern", ""))
        a, b = st.columns(2)
        a.markdown("##### Probable root causes")
        for x in r.get("root_causes", []): a.markdown(f"- {x}")
        b.markdown("##### Recommended repairs")
        for x in r.get("recommended_repairs", []): b.markdown(f"- {x}")
        if r.get("notes"): st.info(r["notes"])
        st.download_button("Download JSON report", json.dumps(r, indent=2), "crack_report.json", "application/json")
    elif not up2:
        st.info("Upload a surface photo to begin.")

# ----------------------------------------------------------------------------- Tab 3
COST_PSF = {"Residential (RCC framed)": 1900, "Commercial Building": 2600, "Industrial Shed (PEB)": 1500,
            "Villa / Premium Residential": 3200, "Load-bearing Masonry": 1500}
TIER_MULT = {"Tier 1 (Mumbai, Delhi, Bengaluru)": 1.25, "Tier 2 (Indore, Pune, Jaipur)": 1.0, "Tier 3 (Smaller cities & towns)": 0.82}
MARKET_PSF = {"Tier 1": 9500, "Tier 2": 5200, "Tier 3": 2800}
STEEL_KG_PSF = {"Residential (RCC framed)": 4.0, "Commercial Building": 5.0, "Industrial Shed (PEB)": 7.0,
                "Villa / Premium Residential": 4.5, "Load-bearing Masonry": 2.0}
MILESTONES = [(10, "Site prep & foundation"), (30, "Plinth & substructure"), (55, "Superstructure (RCC frame)"),
              (75, "Masonry & services"), (90, "Finishing"), (100, "Handover")]


def inr(v):
    return f"₹{v/1e7:,.2f} Cr" if v >= 1e7 else f"₹{v/1e5:,.2f} Lakhs"


with tab3:
    st.subheader("Planning & Real Estate Valuation")
    c1, c2 = st.columns(2)
    stype = c1.selectbox("Structure type", list(COST_PSF))
    tier = c2.selectbox("Location tier", list(TIER_MULT))
    sqft = c1.number_input("Built-up area (sq ft)", 200, 500000, 1500, step=100)
    pct = c2.slider("Completion (%)", 0, 100, 40)

    budget = sqft * COST_PSF[stype] * TIER_MULT[tier]
    capex = budget * pct / 100
    tkey = tier.split(" (")[0]
    full_value = sqft * MARKET_PSF[tkey] * (1.15 if "Villa" in stype or "Commercial" in stype else 1.0)
    # Asset value recognises land/permits upfront and grows with completion
    asset_value = full_value * (0.30 + 0.70 * pct / 100) if pct < 100 else full_value
    steel_t = sqft * STEEL_KG_PSF[stype] / 1000
    cement_bags = sqft * 0.4 * (1.2 if "Commercial" in stype else 1.0)

    m = st.columns(4)
    with m[0]: metric("Total project budget", inr(budget))
    with m[1]: metric("CapEx incurred", inr(capex))
    with m[2]: metric("Current asset value", inr(asset_value))
    with m[3]: metric("Value at completion", inr(full_value))
    m = st.columns(3)
    with m[0]: metric("Steel required (total)", f"{steel_t:,.1f} tonnes")
    with m[1]: metric("Cement required (total)", f"{cement_bags:,.0f} bags")
    with m[2]: metric("Cement still to procure", f"{cement_bags*(100-pct)/100:,.0f} bags")
    nxt = next((n for p, n in MILESTONES if pct < p), "Handover")
    st.markdown(f"##### Milestone progress · next: **{nxt}**")
    st.progress(pct / 100)
    st.caption("Estimates use indicative 2025-26 Indian benchmark rates; replace with local quotations for bidding.")

    st.markdown("##### Conceptual 3D rendering")
    style = st.selectbox("Rendering style", ["photorealistic exterior", "architectural blueprint isometric", "twilight render"])
    prompt = (f"3D architectural {style} of a {stype.lower()} building, {int(sqft)} sq ft, Indian architecture, "
              f"{'under construction, scaffolding' if pct < 100 else 'completed'}, {pct}% complete, high detail")
    st.text_area("Generated prompt", prompt, height=70, disabled=True)
    if st.button("Generate concept render"):
        url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt) + "?width=1024&height=640&nologo=true"
        st.image(url, caption="Pollinations AI concept (illustrative only)", use_container_width=True)

# ----------------------------------------------------------------------------- Tab 4
WEATHER = {
    "Normal": ("ok", ["Standard operations permitted.", "Hold the daily toolbox talk and PPE check.",
                      "Maintain normal curing: cover slabs and keep damp for 7+ days (IS 456 cl. 13.5)."]),
    "High Wind": ("red", ["Suspend crane and hoisting operations when sustained winds exceed ~35 km/h (per manufacturer limits).",
                          "Secure scaffolding sheets, formwork, and loose materials; stop work at height.",
                          "Barricade drop zones and keep personnel clear of tall structures."]),
    "Heavy Rain": ("red", ["Electrical hazard: de-energise temporary supplies, use ELCB/RCD-protected circuits and IP-rated connectors.",
                           "Cover fresh concrete with tarpaulin; avoid pouring, and check slump and water-cement ratio for any later pour.",
                           "Inspect trench shoring and excavations for collapse risk; pump out water; slip-resistant walkways."]),
    "Extreme Heat": ("alert", ["Mandate hydration breaks (about 5 min per hour above 38°C) and shaded rest areas; watch for heat stroke.",
                               "Concrete curing: pour early morning or night, use chilled water or ice, keep concrete temperature under 35°C, wet-cure with hessian for 10+ days.",
                               "Reschedule heavy labour away from 12:00-16:00."]),
}

DEMO_REPLIES = [
    (("curing", "cure"), "Keep concrete continuously moist for at least 7 days (10+ for blended cements or hot weather) per IS 456 cl. 13.5."),
    (("slump",), "Typical slump: 25-75 mm for footings and beams with vibration, 100-150 mm for pumped concrete. Never add water on site to raise slump."),
    (("cover",), "Nominal cover per IS 456 Table 16: 20 mm slabs, 25 mm beams, 40 mm columns and 50 mm footings (mild exposure)."),
    (("harness", "height", "scaffold"), "Use full-body harnesses tied to a certified anchor above shoulder height for work above 1.8 m (OSHA 1926.501)."),
    (("cement", "grade", "m25", "m20"), "M20 is the minimum for RCC under IS 456; M25 or higher is recommended for moderate or worse exposure."),
]

with tab4:
    st.subheader("Daily Site Assistant & Weather-Aware Advisory")
    wx = st.radio("Today's site conditions", list(WEATHER), horizontal=True)
    kind, items = WEATHER[wx]
    st.markdown(f'<div class="alert {"red" if kind == "red" else ""}"><b>{wx} advisory</b><br>' +
                "<br>".join("• " + i for i in items) + "</div>", unsafe_allow_html=True)

    st.markdown("##### Engineering assistant")
    st.session_state.setdefault("chat", [])
    for msg in st.session_state["chat"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    if q := st.chat_input("Ask about concrete, safety, scheduling, materials..."):
        st.session_state["chat"].append({"role": "user", "content": q})
        with st.chat_message("user"):
            st.markdown(q)
        reply = None
        client = get_client()
        if client:
            try:
                sys_p = ("You are a senior site engineer for Indian construction projects. Be concise, practical, cite IS codes "
                         f"and OSHA where relevant, and flag safety risks. Current weather condition on site: {wx}.")
                contents = [types.Content(role="user" if m["role"] == "user" else "model",
                                          parts=[types.Part(text=m["content"])]) for m in st.session_state["chat"]]
                resp = client.models.generate_content(model=MODEL, contents=contents,
                                                      config=types.GenerateContentConfig(system_instruction=sys_p))
                reply = resp.text
            except Exception as e:
                reply = f"⚠️ Gemini request failed ({type(e).__name__}). Using offline guidance instead.\n\n"
        if reply is None or reply.startswith("⚠️"):
            ql = q.lower()
            offline = next((r for keys, r in DEMO_REPLIES if any(k in ql for k in keys)),
                           f"(Demo mode) Current condition is **{wx}**: " + items[0] + " Add a Gemini API key for full answers.")
            reply = (reply or "") + offline
        st.session_state["chat"].append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)
    if st.session_state["chat"] and st.button("Clear conversation"):
        st.session_state["chat"] = []
        st.rerun()
