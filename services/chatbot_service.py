"""AI maintenance assistant — conversational engine.

Layers (checked in order, first match wins):

1. SAFETY      — dangerous situations (fire, fuel leak, burning smell, brake
                 failure, severe overheating) get stop-machine guidance.
2. FLOW        — guided troubleshooting dialogs (noise, overheating,
                 won't start, low power, smoke, warning light). The farmer's
                 answers are understood from conversation history, so short
                 replies like "grinding" continue the right flow.
3. EQUIPMENT   — questions about "my tractor/its health/risk" answer with the
                 farmer's OWN equipment data (never another user's) and explain
                 ML predictions in plain language.
4. KNOWLEDGE   — the curated maintenance knowledge base (phrasal retrieval).
5. FALLBACK    — a clarifying question instead of a random answer.

If ``LLM_API_KEY`` is configured, layers 3-5 are handed to the LLM together
with the conversation history + retrieved context (RAG), with a system prompt
that enforces farmer-friendly language, follow-up questions and safety rules.
The key lives only in the backend environment — never in frontend JavaScript.

Language support: ``answer()`` accepts ``language`` (en/kn/te/hi). Without an
LLM the answer notes that only English is available; with an LLM the system
prompt instructs it to reply in the selected language while keeping technical
terms in English.
"""
import json
import os
import re
import urllib.request
import urllib.error

from config import Config

DISCLAIMER = ("AI-generated guidance is for assistance. Always follow the equipment "
              "manufacturer's service instructions and consult a qualified technician "
              "for serious problems.")

_KB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base.json")

with open(_KB_PATH, "r", encoding="utf-8") as _fh:
    KNOWLEDGE_BASE = json.load(_fh)

QUICK_PROMPTS = [
    "🔧 Check my equipment",
    "⚠️ Why is my tractor at high risk?",
    "🛠️ What maintenance is due?",
    "🚜 My tractor is overheating",
    "📊 Explain my equipment health",
    "📅 Show upcoming maintenance",
]

LANGUAGES = {"en": "English", "kn": "Kannada", "te": "Telugu", "hi": "Hindi"}

# Shown when the LLM is configured but unreachable (never exposes internals).
OUTAGE_MESSAGE = ("I'm having trouble connecting to the AI assistant right "
                  "now. Please try again in a moment.")

_SCRIPT_RANGES = {"te": r"[\u0C00-\u0C7F]",   # Telugu
                  "kn": r"[\u0C80-\u0CFF]",   # Kannada
                  "hi": r"[\u0900-\u097F]"}   # Devanagari (Hindi)


def detect_language(text, fallback="en"):
    """Best-effort script detection; the LLM handles romanised/mixed input."""
    t = text or ""
    for code, pattern in _SCRIPT_RANGES.items():
        if re.search(pattern, t):
            return code
    return fallback

_STOPWORDS = {"the", "a", "an", "my", "is", "are", "do", "does", "did", "what",
              "why", "how", "when", "should", "i", "it", "of", "to", "for",
              "on", "with", "if", "in", "check", "please", "me", "you", "tractor",
              "system", "can", "have", "has"}


def _norm(text):
    return re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())


def _tokens(text):
    return {w for w in re.findall(r"[a-z0-9]+", _norm(text)) if w not in _STOPWORDS}


def retrieve(question):
    """Return the best knowledge-base entry (entry, score).

    Keywords are matched as intent phrases: a keyword like "oil change" also
    matches questions that rephrase it in any word order ("change the oil").
    """
    q = _norm(question)
    q_tokens = _tokens(question)
    q_words = set(q.split())
    best, best_score = None, 0.0
    for entry in KNOWLEDGE_BASE:
        score = 0.0
        for raw_kw in entry["keywords"]:
            kw = _norm(raw_kw).strip()
            words = kw.split()
            if len(words) > 1:
                if kw in q:
                    score += 6.0
                elif all(w in q_words for w in words):
                    score += 4.0
            else:
                if kw in q_tokens:
                    score += 3.0
                elif kw and kw in q:
                    score += 1.0
        if score > best_score:
            best, best_score = entry, score
    return best, best_score


# ---------------------------------------------------------------------- #
#  Safety layer
# ---------------------------------------------------------------------- #
_DANGEROUS = [
    ("fire", "🔥"), ("flames", "🔥"), ("on fire", "🔥"), ("catch fire", "🔥"),
    ("smoke coming", "🔥"), ("smoke from", "🔥"), ("is smoking", "🔥"),
    ("burning smell", "🔥"), ("burnt smell", "🔥"), ("burning", "🔥"),
    ("burnt wiring", "🔥"), ("short circuit", "⚡"), ("electric shock", "⚡"),
    ("sparks", "⚡"),
    ("fuel leak", "⛽"), ("leaking fuel", "⛽"), ("petrol leak", "⛽"),
    ("diesel leak", "⛽"), ("gas leak", "⛽"),
    ("brake fail", "🛑"), ("brakes not working", "🛑"), ("no brakes", "🛑"),
]

_SAFETY_REPLY = (
    "⚠️ **Stop using the machine now and keep people clear.** This can be a "
    "dangerous situation.\n\n"
    "**Do this immediately**\n"
    "• Turn the engine off and remove the key\n"
    "• Move away from the machine — do not check while it is running\n"
    "• For fire or burning smell: do not open hot parts; use an extinguisher "
    "only if it is safe to do so\n"
    "• For a fuel leak: keep away from any flame, spark or phone near the leak\n\n"
    "**Do NOT try to repair this yourself.** Please contact a qualified "
    "technician before the machine is used again."
)


def _is_dangerous(text):
    t = _norm(text)
    for phrase, _ic in _DANGEROUS:
        if phrase in t:
            return True
    # very hot engine + running = dangerous
    if ("overheat" in t or "too hot" in t) and ("smoke" in t or "steam" in t):
        return True
    return False


# ---------------------------------------------------------------------- #
#  Guided troubleshooting flows
# ---------------------------------------------------------------------- #
# Each flow: trigger keywords -> sequence of steps. A step asks a question;
# the farmer's next message answers it (matched by keyword sets).
FLOWS = {
    "noise": {
        "triggers": ["noise", "sound", "grinding", "clicking", "knocking",
                     "squealing", "squeaking", "rattling", "whining"],
        "intro": ("Okay, I can help you identify the possible cause. "
                  "**What type of noise are you hearing** — grinding, clicking, "
                  "knocking, or squealing?"),
        "steps": [
            {"key": "type", "question": None,   # question == intro
             "options": {"grinding": "grinding", "clicking": "clicking",
                         "knocking": "knocking", "squealing": "squealing",
                         "squeaking": "squealing", "rattling": "knocking",
                         "whining": "squealing", "rotavator": "rotavator",
                         "rotavate": "rotavator", "tiller": "rotavator",
                         "rotor": "rotavator", "cultivator": "rotavator"},
             "answers": {
                 "rotavator": ("A noise that appears **only while using the "
                               "rotavator** usually comes from the power "
                               "take-off (PTO) driveline or the gearbox — not "
                               "the engine itself.\n\n"
                               "**Possible causes**\n"
                               "• Worn or dry PTO universal joints\n"
                               "• PTO shaft guard rubbing against the shaft\n"
                               "• Gearbox bearing wear, or low gearbox oil\n"
                               "• Implement not mounted level, or blades hitting hard soil/rocks\n\n"
                               "**What you can safely check** (engine off, PTO disconnected)\n"
                               "• Spin the PTO shaft by hand — roughness or play in the joints\n"
                               "• Guard clearance along the whole shaft\n"
                               "• Gearbox oil level and metal filings on the dipstick\n\n"
                               "**Recommended action** — a light clicking under load "
                               "can be watched, but metallic grinding means stop and "
                               "have the gearbox/PTO inspected by a technician before "
                               "more rotavator work."),
             },
             "next": ("Got it — a {answer} noise usually points to bearings, "
                      "gears or another moving part.\n\n"
                      "**Where is the noise coming from** — the engine, the "
                      "gearbox/transmission, or the wheels?")},
            {"key": "location",
             "question": ("Where is the noise coming from — the engine, the "
                          "gearbox/transmission, or the wheels?"),
             "options": {"engine": "engine", "gearbox": "gearbox",
                         "transmission": "gearbox", "gear": "gearbox",
                         "wheel": "wheels", "wheels": "wheels",
                         "axle": "wheels", "front": "wheels", "rear": "wheels"},
             "answers": {
                 "engine": ("Engine noises often relate to belts, pulleys, the "
                            "valve train or a tired bearing.\n\n"
                            "**What you can safely check**\n"
                            "• Does the noise change with engine speed?\n"
                            "• Any visible damage or looseness on belts/pulleys (engine off)\n"
                            "• Oil level and condition\n\n"
                            "**Recommended action** — avoid heavy work until it is "
                            "inspected; engine-internal noises need a technician."),
                 "gearbox": ("Gearbox/transmission noises usually mean gear or "
                             "bearing wear — especially if it happens in a "
                             "particular gear.\n\n"
                             "**What you can safely check**\n"
                             "• Does it happen only in certain gears?\n"
                             "• Transmission oil level and condition\n\n"
                             "**Recommended action** — use light gears only and "
                             "have the transmission checked soon; continuing heavy "
                             "work can turn a repair into a replacement."),
                 "wheels": ("Wheel-area noises often come from wheel bearings, "
                            "axles or something caught around the wheel.\n\n"
                            "**What you can safely check**\n"
                            "• Any debris or wire wrapped around the axle (engine off)\n"
                            "• Loose wheel nuts\n\n"
                            "**Recommended action** — a wheel bearing failure can "
                            "be unsafe: have it inspected before any road or field "
                            "work."),
             },
             "next": None},
        ],
    },
    "overheat": {
        "triggers": ["overheat", "overheating", "too hot", "temperature high",
                     "running hot", "hot engine"],
        "intro": ("Let's check it step by step. **Is the coolant level low, is the "
                  "radiator blocked with dust or debris, is the cooling fan working, "
                  "and does it overheat only during heavy work?**\n\nYou can answer "
                  "in one line — for example: \"coolant ok, radiator dusty, fan ok, "
                  "only when ploughing\"."),
        "steps": [
            {"key": "detail", "options": {}, "answers": {}, "next": None},
        ],
    },
    "nostart": {
        "triggers": ["not start", "doesnt start", "won't start", "wont start",
                     "no start", "starting problem", "cranks but", "not starting"],
        "intro": ("Got it. **What happens when you try to start it?**\n\n"
                  "• Nothing at all / no lights\n"
                  "• Clicks but the engine does not turn\n"
                  "• Engine turns over but does not fire\n"
                  "• Starts then stops quickly"),
        "steps": [
            {"key": "detail", "options": {}, "answers": {}, "next": None},
        ],
    },
    "lowpower": {
        "triggers": ["low power", "no power", "losing power", "weak", "underpowered",
                     "not pulling", "struggles"],
        "intro": ("Let's narrow it down. **Does the loss of power happen under load "
                  "(ploughing, hauling), at all times, or together with black smoke "
                  "or strange noises?**"),
        "steps": [
            {"key": "detail", "options": {}, "answers": {}, "next": None},
        ],
    },
    "smoke": {
        "triggers": ["black smoke", "white smoke", "blue smoke", "exhaust smoke",
                     "smoke from the exhaust", "smoke from exhaust", "puffing smoke"],
        "intro": ("**What colour is the smoke** — black, white, or blue? "
                  "That tells us a lot."),
        "steps": [
            {"key": "colour",
             "options": {"black": "black", "white": "white", "blue": "blue"},
             "answers": {
                 "black": ("**Black smoke** usually means incomplete fuel burning — "
                           "too much fuel or not enough air.\n\n"
                           "**Possible causes**\n"
                           "• Dirty air filter\n"
                           "• Over-fueling / heavy load lugging the engine\n"
                           "• Injector issues\n\n"
                           "**What you can safely check** — the air filter for dust "
                           "clogging (very common in field work).\n\n"
                           "**Recommended action** — clean or replace the air filter; "
                           "if it persists, have the injectors checked."),
                 "white": ("**White smoke** that persists usually means unburnt "
                           "fuel or coolant entering the combustion chamber.\n\n"
                           "**Possible causes**\n"
                           "• Cold engine (normal for a minute)\n"
                           "• Head-gasket / coolant leak (if it keeps smoking)\n\n"
                           "**What you can safely check** — coolant level, and "
                           "whether the smoke is only during cold start.\n\n"
                           "**Recommended action** — continuous white smoke with "
                           "coolant loss needs a technician soon; stop heavy use."),
                 "blue": ("**Blue smoke** means engine oil is being burnt.\n\n"
                          "**Possible causes**\n"
                          "• Worn rings or valve seals (common in older machines)\n"
                          "• Too much oil in the sump\n\n"
                          "**What you can safely check** — the oil level; is it above "
                          "the maximum mark?\n\n"
                          "**Recommended action** — correct the oil level if overfull; "
                          "otherwise plan a technician visit — it worsens slowly over "
                          "time."),
             },
             "next": None},
        ],
    },
    "warning": {
        "triggers": ["warning light", "warning lamp", "dash light", "check light",
                     "indicator light", "beeping"],
        "intro": ("**Which warning is showing** — oil pressure, coolant "
                  "temperature, battery/charging, or something else? If you can, "
                  "tell me the symbol or colour."),
        "steps": [
            {"key": "detail", "options": {}, "answers": {}, "next": None},
        ],
    },
}


def _detect_flow(text):
    t = _norm(text)
    for flow_id, flow in FLOWS.items():
        for trig in flow["triggers"]:
            if trig in t:
                return flow_id
    return None


def _advance_flow(history, question):
    """Continue an active flow from conversation history.

    ``history`` is a list of {role, content} (oldest first). Returns a reply
    string or None when no flow is active.
    """
    # Find the most recent bot question that belongs to a flow.
    last_bot, last_user = None, None
    for turn in reversed(history):
        if last_bot is None and turn.get("role") == "assistant":
            last_bot = turn.get("content") or ""
        if last_bot is not None and turn.get("role") == "user" and turn is not history[-1]:
            last_user = turn.get("content") or ""
            break
    if not last_bot:
        return None

    q = _norm(last_bot)
    ans = (question or "").strip()
    a_norm = _norm(ans)

    for flow_id, flow in FLOWS.items():
        # Step 1: the flow intro is pending (bot asked the intro question).
        if flow["intro"].split(".")[0][:40].lower() in q or \
           any(trig in q for trig in flow["triggers"] if len(trig) > 6 and trig in q):
            pass
        steps = flow["steps"]
        for i, step in enumerate(steps):
            marker = (step.get("question") or flow["intro"])
            # crude-but-robust: does the last bot question match this step?
            if _step_matches(last_bot, marker, flow_id):
                # Interpret the farmer's answer.
                for word, canon in step.get("options", {}).items():
                    if word in a_norm:
                        ans = canon
                        break
                if step.get("answers", {}).get(a_norm if a_norm in ("black", "white", "blue")
                                               else _canonical(a_norm, step)):
                    pass
                answer_key = _canonical(a_norm, step)
                if answer_key and answer_key in step.get("answers", {}):
                    return step["answers"][answer_key]
                if i + 1 < len(steps):
                    nxt = steps[i + 1]
                    return (nxt.get("question") or flow["intro"]).format(answer=ans.lower())
                return _detail_answer(flow_id, ans, last_user)
    return None


def _canonical(a_norm, step):
    for word, canon in step.get("options", {}).items():
        if word in a_norm:
            return canon
    return a_norm


def _step_matches(last_bot, marker, flow_id):
    """Match the bot's last question to a flow step by distinctive words."""
    marker_words = {w for w in _tokens(marker) if len(w) > 4}
    bot_words = set(_tokens(last_bot))
    if not marker_words:
        return False
    overlap = marker_words & bot_words
    return len(overlap) >= min(2, len(marker_words))


def _detail_answer(flow_id, ans, last_user):
    """Free-text answers for overheating / won't-start / low-power / warning."""
    a = _norm(ans)
    if flow_id == "overheat":
        checks = []
        if "coolant" in a or "water" in a:
            checks.append("coolant: " + ("**low — top it up (cold engine only)**" if any(
                w in a for w in ("low", "less", "down")) else "appears okay"))
        if "dust" in a or "block" in a or "debris" in a or "dirty" in a:
            checks.append("radiator: **dusty/blocked — clean the fins and screen gently**")
        if "fan" in a:
            checks.append("fan: " + ("**not working — check the fuse/belt with the engine off**"
                                     if any(w in a for w in ("not", "no", "never")) else "working"))
        if "load" in a or "work" in a or "plough" in a or "only" in a:
            checks.append("pattern: mostly under heavy load — reduce load and use a lower gear")
        reply = ("Thanks — that helps a lot.\n\n**What this means**\n"
                 + ("\n".join(f"• {c}" for c in checks) if checks else
                    "• Most overheating in tractors comes from coolant level, a "
                    "dust-blocked radiator, or a lazy belt-driven fan"))
        reply += ("\n\n**What you can safely check** (engine off, cold)\n"
                  "• Coolant level in the overflow bottle\n"
                  "• Radiator fins and screen for dust/chaff\n"
                  "• Fan belt tension and condition\n\n"
                  "**Recommended action** — clean the cooling system and re-check "
                  "the temperature. **If it still overheats, stop operating and "
                  "have a technician look at the water pump and thermostat.** "
                  "Running hot can crack the head — not worth the risk.")
        return reply
    if flow_id == "nostart":
        if "click" in a or "nothing" in a or "no light" in a or "dead" in a:
            return ("A click (or nothing) with a slow-cranking starter usually "
                    "points to the **battery or starter connections**.\n\n"
                    "**What you can safely check**\n"
                    "• Battery terminals: tight and not corroded\n"
                    "• Battery voltage (should be ~12.5 V resting; your operator "
                    "panel also shows it)\n"
                    "• Earth/ground strap condition\n\n"
                    "**Recommended action** — charge the battery and clean the "
                    "terminals. If it still only clicks, the starter solenoid "
                    "needs a technician.")
        if "turn" in a or "crank" in a or "fire" in a or "not start" in a:
            return ("If the engine turns over but will not fire, the usual suspects "
                    "are **fuel supply, air in the fuel line, or glow plugs (cold "
                    "weather)**.\n\n"
                    "**What you can safely check**\n"
                    "• Fuel level and fuel shut-off valve open\n"
                    "• Water separator for water/dirt (bleed if trained)\n"
                    "• Fuel filter age\n\n"
                    "**Recommended action** — if bleeding the fuel system is not "
                    "something you have done before, ask a technician — modern "
                    "diesel injection does not like amateur bleeding.")
        return ("Thanks. Starting problems usually sit in one of three areas: "
                "**battery/starter, fuel supply, or safety switches** (seat, "
                "clutch, PTO). Tell me a bit more — what exactly happens when "
                "you turn the key?")
    if flow_id == "lowpower":
        return ("Power loss under load most often comes down to **air, fuel or "
                "hydraulics**.\n\n"
                "**What you can safely check**\n"
                "• Air filter (dust is the #1 cause in the field)\n"
                "• Fuel filter and water separator\n"
                "• Tyre pressure / implement adjustment (apparent power loss)\n\n"
                "**Recommended action** — start with the air and fuel filters; "
                "if power is still low, a compression/injector check by a "
                "technician is the next step.")
    if flow_id == "warning":
        return ("Warning lights are the machine protecting itself — please don't "
                "ignore them.\n\n"
                "**Safe rule**\n"
                "• **Red light** → stop the engine as soon as it is safe\n"
                "• **Yellow/amber** → plan service soon, avoid heavy work\n\n"
                "Tell me which symbol it is (oil can, thermometer, battery, "
                "engine) and I'll explain what it means and what to check first.")
    return None


# ---------------------------------------------------------------------- #
#  Equipment context (farmer's own data only)
# ---------------------------------------------------------------------- #
# Clarifying question in the farmer's language (rule-mode fallback; with an
# LLM configured the model replies in the detected language itself).
_CLARIFY_I18N = {
    "te": ("మీకు సరైన సహాయం అందించడానికి కొన్ని వివరాలు కావాలి.\n\n"
           "• ఏ యంత్రం గురించి మాట్లాడుతున్నారు — మరియు అందులో ఏమి జరుగుతోంది?\n"
           "• ఇది నిర్వహణ, విచిత్రమైన ప్రవర్తన, లేదా AI సూచన గురించా?\n\n"
           "ఉదాహరణ: \"నా ట్రాక్టర్ ఎక్కువ వేడెక్కుతోంది\"."),
    "hi": ("सही मदद के लिए मुझे थोड़ी जानकारी चाहिए।\n\n"
           "• आप किस मशीन के बारे में पूछ रहे हैं — और उसमें क्या हो रहा है?\n"
           "• यह रखरखाव, अजीब व्यवहार, या AI अनुमान के बारे में है?\n\n"
           "उदाहरण: \"मेरा ट्रैक्टर बहुत गर्म हो रहा है\"."),
    "kn": ("ಸರಿಯಾದ ಸಹಾಯಕ್ಕಾಗಿ ಸ್ವಲ್ಪ ಮಾಹಿತಿ ಬೇಕು.\n\n"
           "• ಯಾವ ಯಂತ್ರದ ಬಗ್ಗೆ ಮಾತನಾಡುತ್ತಿದ್ದೀರಿ — ಮತ್ತು ಅದರಲ್ಲಿ ಏನಾಗುತ್ತಿದೆ?\n"
           "• ಇದು ನಿರ್ವಹಣೆ, ವಿಚಿತ್ರ ವರ್ತನೆ, ಅಥವಾ AI ಸೂಚನೆಯ ಬಗ್ಗೆಯಾ?\n\n"
           "ಉದಾಹರಣೆ: \"ನನ್ನ ಟ್ರ್ಯಾಕ್ಟರ್ ಜಾಸ್ತಿ ಬಿಸಿಯಾಗುತ್ತಿದೆ\"."),
}


def _clarify_text(language="en"):
    return _CLARIFY_I18N.get(language) or (
        "I want to make sure I help with the right thing. "
        "Could you tell me a little more?\n\n"
        "• Which machine is it — and what is happening?\n"
        "• Is it about maintenance, a strange behaviour, or one "
        "of the AI predictions?\n\n"
        "For example: \"my tractor is overheating\", \"when "
        "should I change the oil\", or \"explain the high risk "
        "on my harvester\".")


# Vague problem reports — the farmer hasn't said which machine or what happens.
_PROBLEM_WORDS = ("not working", "isn't working", "dont work", "don't work",
                  "doesn't work", "stopped working", "stopped running",
                  "broken", "problem", "issue", "trouble", "acting up",
                  "malfunction", "fails", "failed", "failure",
                  "something wrong", "not responding", "stuck", "won't go",
                  "wont go", "hanging", "vibrating badly")


def _health_score(equip):
    """Simple 0-100 health indicator from status (explanatory, not an ML output)."""
    return {"Healthy": 95, "Maintenance Due": 70, "Warning": 55, "High Risk": 35,
            "Critical": 20}.get(equip.get("status"), 70)


def _equipment_context(db, user_id, equipment_id):
    if not db or not user_id:
        return None
    equipment = db.list_equipment(user_id)
    if not equipment:
        return None
    chosen = None
    if equipment_id:
        chosen = next((e for e in equipment if e["equipment_id"] == equipment_id), None)
    lines = []
    profile = db.get_profile(user_id) or {}
    farm = profile.get("farm_name") or "the farm"
    lines.append(f"Farm: {farm}")
    for e in equipment:
        mark = " (the machine being asked about)" if chosen and e["equipment_id"] == chosen["equipment_id"] else ""
        lines.append(f"Equipment: {e['equipment_name']} — {e['equipment_type']} "
                     f"{e['brand']} {e['model']} ({e['year']}), status {e['status']}, "
                     f"risk {e.get('risk_level') or 'unknown'}{mark}")
    if chosen:
        pred = db.latest_prediction(user_id, equipment_id)
        if pred:
            src = "demo prediction" if pred.get("is_demo") else "ML model prediction"
            lines.append(f"Latest prediction for {chosen['equipment_name']}: "
                         f"{pred['condition']} condition, {pred['risk_level']} risk, "
                         f"{pred['probability']}% probability ({src}). "
                         f"Recommendation: {pred.get('recommendation', '')}")
        maint = db.list_maintenance(user_id)
        last = next((m for m in maint if m.get("equipment_id") == equipment_id), None)
        if last:
            lines.append(f"Last service: {last.get('service_date')} "
                         f"({last.get('service_type')})")
    return "\n".join(lines)


def _explain_prediction_text(result):
    """Plain-language explanation of a prediction result dict."""
    risk = (result.get("risk_level") or "Low").lower()
    prob = result.get("probability")
    cond = result.get("condition", "Normal")
    if cond == "Normal" or risk == "low":
        return (f"Good news — the system sees a **normal operating pattern** "
                f"({prob}% deviation). This does not guarantee there are no "
                f"issues, but nothing abnormal was detected in the data.")
    return (f"The system estimates a **{prob}% chance of an abnormal operating "
            f"condition**. This does not mean the machine will definitely fail — "
            f"it means the operating pattern differs enough from normal that an "
            f"inspection is worthwhile.\n\n"
            f"**Recommended action:** {result.get('recommendation', 'schedule an inspection')}\n"
            f"**Priority:** {'book a technician soon' if risk in ('high', 'critical') else 'plan service in the coming days'}")


# ---------------------------------------------------------------------- #
#  LLM integration (optional, key stays in backend env)
# ---------------------------------------------------------------------- #
def _ask_llm(question, context, history, kb_answer, language="en"):
    """Call the configured OpenAI-compatible LLM. Returns reply text or None."""
    if not Config.LLM_API_KEY:
        return None
    lang_name = LANGUAGES.get(language, "English")
    system = (
        "You are AgriCare, a conversational AI assistant for farmers and farm "
        "equipment (tractors, harvesters, rotavators, cultivators, seed drills, "
        "ploughs, sprayers, pumps, threshers and similar machines). You talk "
        "like a modern AI assistant — natural, warm and practical — never like "
        "a keyword FAQ bot.\n"
        "\nHOW TO ANSWER\n"
        "- Understand the meaning and intent of the message, including informal "
        "wording and small spelling mistakes; never require exact keywords.\n"
        "- Use the conversation history. Resolve references like \"it\", \"the "
        "same noise\" or short follow-ups (\"only when I use the rotavator\") "
        "from earlier messages. Never ask the farmer to repeat what they "
        "already told you.\n"
        "- If important information is missing, ask ONE short clarifying "
        "question instead of guessing. Never invent details.\n"
        "- For a problem report, do NOT give a definite diagnosis. Explain "
        "possible causes in simple words, give safe basic checks the farmer "
        "can do, and say when a qualified technician should inspect the "
        "machine. Present uncertainty honestly (\"could be\", \"usually\").\n"
        "- Dangerous situations (fire, smoke suggesting fire, fuel leak, major "
        "oil leak, burning smell, brake failure, severe overheating): tell the "
        "farmer to stop the machine, keep people clear and get qualified "
        "professional help. Never give unsafe instructions.\n"
        "- This system has NO IoT sensors. Never suggest sensor readings (RPM, "
        "oil-pressure, temperature or vibration sensors); base advice on "
        "symptoms, basic checks and the farm context provided.\n"
        "- When equipment context is provided, use it (machine, status, risk, "
        "latest prediction, last service) and speak only about THIS farmer's "
        "machines. Never mention or expose any other farmer's data.\n"
        "- Explain AI predictions as estimates, never guarantees; never predict "
        "a failure date.\n"
        "- Be concise: usually under 160 words, short paragraphs or a few "
        "bullets. Ask a follow-up question when it helps. Greet only at the "
        "start of a conversation, and never repeat the same answer twice.\n"
        "\nLANGUAGE\n"
        "- Detect the language of the farmer's latest message: English, "
        "Telugu, or a mix of Telugu and English. Reply in the same language "
        "and script: Telugu in Telugu script, English in English. For a mix, "
        "reply in the dominant language and keep technical part names in "
        f"English. Preferred-language hint ({lang_name}): use it only when "
        "the message language is unclear."
    )
    messages = [{"role": "system", "content": system}]
    for turn in (history or [])[-10:]:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        content = (turn.get("content") or "")[:800]
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user",
                     "content": f"Knowledge-base reference (may be empty):\n{kb_answer or '—'}\n\n"
                                f"Farmer's equipment context:\n{context or '—'}\n\n"
                                f"Farmer says: {question}"})
    payload = json.dumps({
        "model": Config.LLM_MODEL,
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0.6,
    }).encode("utf-8")
    req = urllib.request.Request(
        Config.LLM_API_URL, data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {Config.LLM_API_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        reply = data["choices"][0]["message"]["content"].strip()
        return reply or None
    except Exception:                                    # noqa: BLE001
        return None


# ---------------------------------------------------------------------- #
#  Main entry point
# ---------------------------------------------------------------------- #
def _rule_answer(question, context, entry, score, history, language="en",
                 user_id=None, db=None, equipment_id=None):
    """Deterministic assistant layers (demo mode / LLM outage fallback)."""
    # 1) Safety first.
    if _is_dangerous(question) or any(_is_dangerous(t.get("content") or "")
                                      for t in (history or [])[-2:]
                                      if t.get("role") == "user"):
        return {"answer": _SAFETY_REPLY + f"\n\n{DISCLAIMER}",
                "source": "safety", "suggestions": [], "language": language}

    # 2) Continue an active troubleshooting flow.
    flow_reply = _advance_flow(history or [], question)
    if flow_reply:
        return {"answer": f"{flow_reply}\n\n{DISCLAIMER}",
                "source": "troubleshooting", "suggestions": [], "language": language}

    # 3) New flow? ("my tractor is making a strange noise")
    flow_id = _detect_flow(question)
    if flow_id and not any(w in _norm(question) for w in
                           ("what", "why", "how", "when", "meaning")):
        return {"answer": f"{FLOWS[flow_id]['intro']}\n\n{DISCLAIMER}",
                "source": "troubleshooting", "suggestions": [], "language": language}

    # 4) Equipment-specific questions answered from the farmer's own data.
    eq_words = ("how is my", "health", "condition of my", "my tractor", "my machine",
                "high risk", "why.*risk", "explain.*prediction", "equipment status",
                "check my equipment")
    about_equipment = any(re.search(w, _norm(question)) for w in eq_words)
    # A vague problem report ("my machine is not working") needs clarification
    # first — which machine, and what happens — never a data dump or a guess.
    if (any(w in _norm(question) for w in _PROBLEM_WORDS)
            and not _detect_flow(question)):
        return {"answer": f"{_clarify_text(language)}\n\n{DISCLAIMER}",
                "source": "clarify", "suggestions": QUICK_PROMPTS[:3],
                "language": language}
    if about_equipment and context:
        latest = None
        if equipment_id and db:
            latest = db.latest_prediction(user_id, equipment_id)
        if latest:
            explanation = _explain_prediction_text(latest)
            body = (f"Here is what the system knows about your machine:\n\n{context}\n\n"
                    f"**What the prediction means**\n{explanation}")
        else:
            body = (f"Here is the current picture of your equipment:\n\n{context}\n\n"
                    f"Run a prediction on the Predictive Maintenance page to see "
                    f"the AI risk estimate for this machine.")
        return {"answer": f"{body}\n\n{DISCLAIMER}",
                "source": "equipment-context", "suggestions": [], "language": language}

    # 5) Knowledge base.
    kb_answer = entry["answer"] if entry else None
    if not entry or score < 3:
        # Unclear question — ask a clarifying follow-up instead of guessing.
        return {"answer": f"{_clarify_text(language)}\n\n{DISCLAIMER}",
                "source": "clarify", "suggestions": QUICK_PROMPTS[:3],
                "language": language}

    final = (f"{kb_answer}\n\n**Was this about a specific machine?** "
             f"Select it above and ask again — I can use its health "
             f"data and predictions." if not context else kb_answer)
    if context:
        final = f"{context}\n\n{final}"

    return {"answer": f"{final}\n\n{DISCLAIMER}",
            "source": "knowledge-base",
            "matched": entry["id"],
            "suggestions": [], "language": language}


def answer(question, equipment_id=None, user_id=None, db=None,
           history=None, language="en"):
    """Produce a conversational answer for the farmer's question.

    ``history``: list of {role, content} turns (oldest first) from MySQL
    (chat_messages) for THIS conversation — used as LLM context and by the
    rule-based fallback flows.

    With ``LLM_API_KEY`` configured the LLM is the primary engine (context,
    history and a knowledge-base reference are passed to it — RAG) and the
    rule layers below only serve as an outage fallback. Returns
    {answer, source, suggestions, language}.
    """
    question = (question or "").strip()
    if not question:
        return {"answer": "Please type a question about your equipment, "
                          "maintenance or AI predictions.",
                "source": "system", "suggestions": [], "language": language}

    # Understand the language from the message itself (Telugu / Kannada /
    # Hindi scripts are detected; romanised or mixed input is handled by the
    # LLM, which mirrors the farmer's language).
    language = detect_language(question, fallback=(language or "en"))

    context = _equipment_context(db, user_id, equipment_id)
    entry, score = retrieve(question)
    kb_ref = entry["answer"] if entry and score >= 3 else None

    if Config.LLM_API_KEY:
        llm = _ask_llm(question, context, history, kb_ref, language)
        if llm:
            return {"answer": llm, "source": "llm",
                    "suggestions": [], "language": language}
        # LLM unavailable → friendly message, but still try the rule layers
        # so obvious questions keep working during a temporary outage.
        fallback = _rule_answer(question, context, entry, score, history,
                                language, user_id, db, equipment_id)
        if fallback and fallback.get("source") in ("safety", "troubleshooting"):
            return fallback
        return {"answer": OUTAGE_MESSAGE,
                "source": "outage", "suggestions": [], "language": language}

    # No LLM configured — deterministic assistant (demo mode).
    return _rule_answer(question, context, entry, score, history,
                        language, user_id, db, equipment_id)
