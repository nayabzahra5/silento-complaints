"""
Silento public complaint page (Streamlit).
Two ways to report: write it, or send visual evidence (photo).
Everything goes to the API, which saves the files as received in the S3 raw zone.

Secrets (Streamlit "Secrets" settings, never in the code):
  API_URL    = "https://xxxx.execute-api.ap-south-1.amazonaws.com/complaints"
  API_SECRET = "the same string you set on the Lambda"
"""
import base64

import requests
import streamlit as st

API_URL = st.secrets["API_URL"]
API_SECRET = st.secrets["API_SECRET"]
MAX_IMAGE_BYTES = 2 * 1024 * 1024

AREAS_EN = ["Gulberg", "DHA", "Johar Town", "Model Town", "Township", "Shahdara",
            "Iqbal Town", "Samanabad", "Walled City", "Cantt", "Wapda Town",
            "Bahria Town", "Kot Lakhpat", "Other"]
AREAS_UR = ["گلبرگ", "ڈی ایچ اے", "جوہر ٹاؤن", "ماڈل ٹاؤن", "ٹاؤن شپ", "شاہدرہ",
            "اقبال ٹاؤن", "سمن آباد", "اندرون شہر", "کینٹ", "واپڈا ٹاؤن",
            "بحریہ ٹاؤن", "کوٹ لکھپت", "دیگر"]
WHEN_EN = ["Right now", "Earlier today", "Every night", "All day"]
WHEN_UR = ["ابھی", "آج پہلے", "ہر رات", "سارا دن"]

TXT = {
    "en": {
        "tagline": "Predict the peaks, protect the peace.",
        "t1": "Report", "t2": "Noise", "t3": "in Your Area",
        "sub": "Help EPA teams understand where and when noise is happening.",
        "step1": "Choose a reporting method",
        "m_text": "Write a Report", "m_photo": "Visual Evidence",
        "step2": "Report details",
        "what": "What is happening?",
        "ph": "e.g. Loud music from a wedding hall after midnight",
        "photo": "Visual evidence of the source of noise (photo, max 2 MB)",
        "area": "Area", "area_ph": "Select area",
        "when": "When is it happening?",
        "submit": "Submit Report",
        "thanks": "Thank you for reporting. Every report helps make Lahore quieter.",
        "err_text": "Please describe the problem in a few words.",
        "err_photo": "Please add a photo.",
        "err_big": "The photo is too large. Please choose one under 2 MB.",
        "err_save": "Sorry, we could not save your report. Please try again.",
        "err_net": "Could not reach the server. Please try again later.",
        "ok": "Report received. ID:",
    },
    "ur": {
        "tagline": "شور کی پیش گوئی، سکون کی حفاظت۔",
        "t1": "اپنے علاقے میں", "t2": "شور", "t3": "کی شکایت کریں",
        "sub": "ای پی اے ٹیم کو بتائیں شور کہاں اور کب ہوتا ہے۔",
        "step1": "شکایت کا طریقہ چنیں",
        "m_text": "لکھیں", "m_photo": "بصری ثبوت",
        "step2": "شکایت کی تفصیل",
        "what": "کیا ہو رہا ہے؟",
        "ph": "مثلاً: آدھی رات کے بعد شادی ہال میں تیز آواز میں موسیقی",
        "photo": "شور کے ذریعے کا بصری ثبوت (تصویر، زیادہ سے زیادہ 2 MB)",
        "area": "علاقہ", "area_ph": "علاقہ منتخب کریں",
        "when": "شور کب ہوتا ہے؟",
        "submit": "شکایت بھیجیں",
        "thanks": "رپورٹ کرنے کا شکریہ۔ آپ کی ہر رپورٹ لاہور کو پرسکون بنانے میں مدد کرتی ہے۔",
        "err_text": "براہِ کرم مسئلہ چند الفاظ میں بیان کریں۔",
        "err_photo": "براہِ کرم تصویر شامل کریں۔",
        "err_big": "تصویر بہت بڑی ہے۔ 2 MB سے چھوٹی تصویر چنیں۔",
        "err_save": "معذرت، شکایت محفوظ نہیں ہو سکی۔ دوبارہ کوشش کریں۔",
        "err_net": "سرور سے رابطہ نہیں ہو سکا۔ بعد میں کوشش کریں۔",
        "ok": "شکایت موصول ہو گئی۔ نمبر:",
    },
}

st.set_page_config(page_title="Silento: Report Noise", layout="centered")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Space+Grotesk:wght@700&family=Noto+Nastaliq+Urdu:wght@400;600&display=swap');
#MainMenu, footer, header {visibility: hidden;}
.stApp {background: #F6EFE3;}
.block-container {max-width: 430px; padding: 0 0 2rem 0;}
html, body, [class*="css"] {font-family: 'Inter', 'Noto Nastaliq Urdu', sans-serif;}
.hero {background:#0F3D3A; color:#fff; padding:18px 20px 0 20px; position:relative; overflow:hidden;}
.hero .logo {font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:24px;}
.hero .tag {color:#CFE3DF; font-size:11px;}
.hero h1 {color:#fff; font-family:'Space Grotesk','Noto Nastaliq Urdu',sans-serif; font-size:32px; line-height:1.15; max-width:250px; margin:14px 0 6px 0; padding:0;}
.hero h1 span {color:#E8A33D;}
.hero p {color:#CFE3DF; font-size:14px; max-width:230px; margin:0;}
.hero svg {display:block; margin:-84px -20px 0 -20px; width:calc(100% + 40px); position:relative; z-index:0;}
.hero .txt {position:relative; z-index:2;}
.pad {padding: 0 20px;}
h3.step {font-size:18px; color:#1B2B2A; margin:18px 0 6px 0;}
.thanks {color:#2F4A47; font-size:13px; text-align:center; margin-top:10px;}
div[data-testid="stForm"] {background:#fff; border:2px solid #EADFC9; border-radius:20px; padding:16px;}
div.stButton > button, div[data-testid="stFormSubmitButton"] > button {
  background:#E8A33D; color:#1B2B2A; font-weight:700; font-size:18px; border:0;
  border-radius:16px; min-height:56px; width:100%;}
div[data-testid="stFormSubmitButton"] > button:hover {background:#d99428; color:#1B2B2A;}
.rtl {direction: rtl; text-align: right; font-family:'Noto Nastaliq Urdu',serif;}
</style>
""",
    unsafe_allow_html=True,
)

lang_label = st.radio("Language", ["English", "اردو"], horizontal=True,
                      label_visibility="collapsed")
lang = "ur" if lang_label == "اردو" else "en"
T = TXT[lang]
AREAS = AREAS_UR if lang == "ur" else AREAS_EN
WHENS = WHEN_UR if lang == "ur" else WHEN_EN
rtl = " class='rtl'" if lang == "ur" else ""

HERO_SVG = """
<svg viewBox="0 0 390 200" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
<g fill="none" stroke="#E8A33D" stroke-width="2">
<circle cx="318" cy="84" r="30" opacity=".6"/><circle cx="318" cy="84" r="56" opacity=".4"/>
<circle cx="318" cy="84" r="84" opacity=".24"/><circle cx="318" cy="84" r="114" opacity=".12"/></g>
<g stroke="#9CC3BB" stroke-width="3" stroke-linecap="round" opacity=".8" fill="none">
<path d="M150 84v6M158 76v22M166 66v42M174 74v26M182 56v58M190 70v30M198 48v74M206 62v46M214 72v26M222 54v62M230 68v34M238 76v18M246 62v40M254 72v22M262 80v10"/></g>
<g fill="#1B5A54"><path d="M4 176v-34h120v34Z"/>
<path d="M40 142v-18c0-16 10-20 24-34 14 14 24 18 24 34v18Z"/><rect x="63" y="78" width="2" height="14"/>
<path d="M4 142v-12c0-9 5-11 12-18 7 7 12 9 12 18v12Z"/><path d="M100 142v-12c0-9 5-11 12-18 7 7 12 9 12 18v12Z"/>
<rect x="0" y="98" width="7" height="78"/><path d="M-2 98h11l-5.5-10Z"/>
<rect x="121" y="98" width="7" height="78"/><path d="M119 98h11l-5.5-10Z"/>
<path d="M150 176v-26h8v-8h8v8h8v26Z"/><path d="M200 176v-18c0-8 5-10 10-16 5 6 10 8 10 16v18Z"/>
<path d="M236 176v-28h10v-6h8v6h10v28Z"/></g>
<g fill="#F6EFE3" opacity=".9"><path d="M52 176v-10c0-6 5-8 12-8s12 2 12 8v10Z"/>
<path d="M8 176v-8c0-5 4-6 8-6s8 1 8 6v8Z"/><path d="M100 176v-8c0-5 4-6 8-6s8 1 8 6v8Z"/></g>
<g fill="#0A2B29"><path d="M309 176l3-118h12l3 118Z"/><path d="M306 60h24l-12-22Z"/>
<path d="M314 38h8l-4-28Z"/><circle cx="318" cy="8" r="3"/><path d="M284 182l12-14h44l12 14Z"/>
<path d="M296 168l8-14h28l8 14Z"/></g>
<g stroke="#1B5A54" stroke-width="2"><path d="M310 94h16M311 124h14M310 152h16"/></g>
<path d="M0 168C70 150 120 188 200 170S330 150 390 166V200H0Z" fill="#E8A33D"/>
<path d="M0 180C70 162 120 200 200 182S330 162 390 178V200H0Z" fill="#F6EFE3"/>
</svg>
"""

st.markdown(
    f"""
<div class="hero"{rtl}>
  <div class="txt">
    <div class="logo">Silento</div>
    <div class="tag">{T['tagline']}</div>
    <h1>{T['t1']} <span>{T['t2']}</span> {T['t3']}</h1>
    <p>{T['sub']}</p>
  </div>
  {HERO_SVG}
</div>
""",
    unsafe_allow_html=True,
)

st.markdown("<div class='pad'>", unsafe_allow_html=True)
st.markdown(f"<h3 class='step'{rtl}>{T['step1']}</h3>", unsafe_allow_html=True)
method = st.radio("method", ["text", "photo"], horizontal=True,
                  format_func=lambda k: T["m_" + k], label_visibility="collapsed")
st.markdown(f"<h3 class='step'{rtl}>{T['step2']}</h3>", unsafe_allow_html=True)

with st.form("complaint_form", clear_on_submit=True):
    text = ""
    photo = None
    if method == "text":
        text = st.text_area(T["what"], placeholder=T["ph"], max_chars=200)
    else:
        photo = st.file_uploader(T["photo"], type=["jpg", "jpeg", "png", "webp"])
    c1, c2 = st.columns(2)
    area_i = c1.selectbox(T["area"], range(len(AREAS)), index=None,
                          format_func=lambda i: AREAS[i], placeholder=T["area_ph"])
    when_i = c2.selectbox(T["when"], range(len(WHENS)), index=0,
                          format_func=lambda i: WHENS[i])
    submitted = st.form_submit_button(T["submit"])

if submitted:
    payload = {
        "area": AREAS_EN[area_i] if area_i is not None else "",
        "when": WHEN_EN[when_i],
        "lang": lang,
    }
    problem = None
    if method == "text":
        if len(text.strip()) < 5:
            problem = T["err_text"]
        payload["text"] = text.strip()
    else:
        if photo is None:
            problem = T["err_photo"]
        else:
            data = photo.getvalue()
            if len(data) > MAX_IMAGE_BYTES:
                problem = T["err_big"]
            else:
                payload["image_base64"] = base64.b64encode(data).decode("ascii")
                payload["image_type"] = photo.type or "image/jpeg"
    if problem:
        st.error(problem)
    else:
        try:
            resp = requests.post(API_URL, json=payload,
                                 headers={"x-api-secret": API_SECRET}, timeout=20)
            if resp.status_code == 200:
                st.success(f"{T['ok']} {resp.json().get('complaint_id', '')}")
            else:
                st.error(T["err_save"])
        except requests.RequestException:
            st.error(T["err_net"])

st.markdown(f"<p class='thanks'{rtl}>{T['thanks']}</p></div>", unsafe_allow_html=True)
