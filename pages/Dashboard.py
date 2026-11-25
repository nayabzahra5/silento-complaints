import hmac
import time

import boto3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

REGION = "ap-south-1"
DATABASE = "silento"
OUTPUT = "s3://silento-data-lake/athena-results/"

# Palette taken from the Silento complaint page
TEAL_DARK = "#0F3D3A"
TEAL = "#1D5B55"
TEAL_LIGHT = "#7FB5A8"
AMBER = "#E8A33D"
CRIMSON = "#C8374B"
CREAM = "#F5EEE3"
SAND = "#E6DCCB"
INK = "#1B2A28"
MUTED = "#5E6F6B"
CARD = "#FFFDF8"
NOISE_SCALE = ["#2E8B6E", AMBER, CRIMSON]
SOURCE_COLOURS = [AMBER, TEAL, CRIMSON, TEAL_LIGHT, "#8C6A2F", "#B7C9C2", "#D9B26F"]

st.set_page_config(page_title="Silento - Lahore Noise Dashboard", page_icon="🔊",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Source+Sans+3:wght@400;600&display=swap');
.stApp {{ background: {CREAM}; }}
.stApp, .stApp p, .stApp span, .stApp label, .stApp li, .stApp div {{ font-family: 'Source Sans 3', sans-serif; color: {INK}; }}
h1, h2, h3, h4 {{ font-family: 'Space Grotesk', sans-serif !important; color: {TEAL_DARK} !important; }}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 1.5rem; max-width: 1200px; }}
.hero {{ background: linear-gradient(120deg, {TEAL_DARK} 0%, #145049 100%); border-radius: 18px;
        padding: 34px 40px 28px 40px; position: relative; overflow: hidden; margin-bottom: 18px; }}
.hero .brand {{ font-family: 'Space Grotesk', sans-serif; color: #fff !important; font-size: 1.7rem; font-weight: 700; margin: 0; }}
.hero .tag {{ color: #CFE5DE !important; font-size: 0.95rem; margin: 2px 0 14px 0; }}
.hero .title {{ font-family: 'Space Grotesk', sans-serif; color: {AMBER} !important; font-size: 2.5rem; font-weight: 700; line-height: 1.1; margin: 0 0 10px 0; }}
.hero .sub {{ color: #DDEEE8 !important; max-width: 560px; font-size: 1.05rem; margin: 0; }}
.hero svg {{ position: absolute; right: 30px; bottom: 0; opacity: .9; }}
.hero .wave {{ position: absolute; left: 0; right: 0; bottom: 0; height: 10px; background: {AMBER}; }}
.kpi {{ background: {CARD}; border-radius: 14px; padding: 16px 18px; border: 1px solid {SAND}; border-top: 5px solid {AMBER}; height: 100%; }}
.kpi .label {{ color: {MUTED} !important; font-size: .85rem; text-transform: uppercase; letter-spacing: .05em; margin: 0; }}
.kpi .value {{ font-family: 'Space Grotesk', sans-serif; color: {TEAL_DARK} !important; font-size: 2.1rem; font-weight: 700; margin: 2px 0 0 0; line-height: 1.15; }}
.kpi .note {{ color: {MUTED} !important; font-size: .85rem; margin: 0; }}
.kpi.red {{ border-top-color: {CRIMSON}; }} .kpi.teal {{ border-top-color: {TEAL}; }}
.card {{ background: {CARD}; border: 1px solid {SAND}; border-radius: 14px; padding: 14px 18px 6px 18px; }}
.rank {{ background: {CARD}; border: 1px solid {SAND}; border-left: 6px solid {CRIMSON}; border-radius: 12px; padding: 12px 16px; }}
.rank .n {{ font-family: 'Space Grotesk', sans-serif; color: {CRIMSON} !important; font-weight: 700; font-size: .9rem; margin: 0; }}
.rank .a {{ font-family: 'Space Grotesk', sans-serif; color: {TEAL_DARK} !important; font-weight: 700; font-size: 1.35rem; margin: 0; }}
.rank .d {{ color: {MUTED} !important; font-size: .9rem; margin: 0; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 6px; border-bottom: 2px solid {SAND}; }}
.stTabs [data-baseweb="tab"] {{ font-family: 'Space Grotesk', sans-serif; font-weight: 500; padding: 8px 16px; }}
.stTabs [aria-selected="true"] {{ color: {CRIMSON} !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ background-color: {CRIMSON} !important; }}
a[data-testid="stPageLink-NavLink"] {{ background: {AMBER}; border-radius: 10px; padding: 6px 14px; width: fit-content; }}
a[data-testid="stPageLink-NavLink"] p {{ color: {TEAL_DARK} !important; font-weight: 600; }}
.foot {{ color: {MUTED} !important; font-size: .82rem; margin-top: 18px; }}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- data (Athena)
@st.cache_resource
def athena_client():
    return boto3.client(
        "athena", region_name=REGION,
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
    )


@st.cache_data(ttl=600, show_spinner="Loading data...")
def query(sql):
    client = athena_client()
    qid = client.start_query_execution(
        QueryString=sql, QueryExecutionContext={"Database": DATABASE},
        ResultConfiguration={"OutputLocation": OUTPUT}, WorkGroup="primary",
    )["QueryExecutionId"]
    for _ in range(60):
        status = client.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
        if status["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    if status["State"] != "SUCCEEDED":
        raise RuntimeError(status.get("StateChangeReason", status["State"]))
    rows, header = [], None
    for page in client.get_paginator("get_query_results").paginate(QueryExecutionId=qid):
        for r in page["ResultSet"]["Rows"]:
            vals = [c.get("VarCharValue") for c in r["Data"]]
            if header is None:
                header = vals
            else:
                rows.append(vals)
    df = pd.DataFrame(rows, columns=header)
    for c in df.columns:
        try:
            df[c] = pd.to_numeric(df[c])
        except (ValueError, TypeError):
            pass
    return df


# ---------------------------------------------------------------- helpers
def style(fig, height=380, legend=False):
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Source Sans 3, sans-serif", color=INK, size=13),
        showlegend=legend, legend=dict(orientation="h", y=-0.2),
    )
    fig.update_xaxes(gridcolor=SAND, zeroline=False)
    fig.update_yaxes(gridcolor=SAND, zeroline=False)
    return fig


def show(fig):
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def kpi(col, label, value, note="", cls=""):
    col.markdown(f'<div class="kpi {cls}"><p class="label">{label}</p>'
                 f'<p class="value">{value}</p><p class="note">{note}</p></div>',
                 unsafe_allow_html=True)


def hero():
    bars = [10, 18, 30, 20, 44, 66, 50, 82, 58, 40, 62, 34, 24, 38, 18, 12]
    rects = "".join(
        f'<rect x="{10 + i * 14}" y="{50 - h / 2:.0f}" width="6" height="{h:.0f}" rx="3" fill="#7FB5A8"/>'
        for i, h in enumerate(bars))
    st.markdown(
        '<div class="hero">'
        '<p class="brand">Silento</p>'
        '<p class="tag">Predict the peaks, protect the peace.</p>'
        '<p class="title">Lahore Noise Dashboard</p>'
        '<p class="sub">Noise measurements and citizen complaints, cleaned and analysed '
        'automatically on AWS, so EPA teams can see where and when noise is happening.</p>'
        f'<svg width="250" height="100" viewBox="0 0 250 100">{rects}</svg>'
        '<div class="wave"></div></div>', unsafe_allow_html=True)


def noise_map(df):
    d = df.copy()
    d["size"] = d["points"].clip(lower=5) ** 0.5
    plot = getattr(px, "scatter_map", None) or px.scatter_mapbox
    fig = plot(d, lat="c_lat", lon="c_lon", color="avg_db", size="size", size_max=38,
               color_continuous_scale=NOISE_SCALE, range_color=(40, 90),
               hover_name="area",
               hover_data={"avg_db": ":.1f", "max_db": ":.1f", "points": True,
                           "complaints": True, "size": False, "c_lat": False, "c_lon": False},
               zoom=9.6, center={"lat": 31.50, "lon": 74.33})
    if hasattr(px, "scatter_map"):
        fig.update_layout(map_style="carto-positron")
    else:
        fig.update_layout(mapbox_style="carto-positron")
    fig.update_layout(coloraxis_colorbar=dict(title="dB", thickness=12, len=0.7))
    return style(fig, height=470)


def ranked_bar(scored):
    d = scored.sort_values("avg_db")
    fig = px.bar(d, x="avg_db", y="area", orientation="h", color="avg_db",
                 color_continuous_scale=NOISE_SCALE, range_color=(40, 90),
                 text="avg_db", labels={"avg_db": "Average noise (dB)", "area": ""})
    fig.update_traces(texttemplate="%{text:.1f}", textposition="outside", cliponaxis=False)
    fig.add_vline(x=55, line_dash="dot", line_color=TEAL,
                  annotation_text="55 dB residential daytime guideline", annotation_position="bottom right")
    fig.update_layout(coloraxis_showscale=False)
    return style(fig, height=470)


# ---------------------------------------------------------------- public view
def public_view():
    summary = query("SELECT * FROM area_summary")
    centres = query("SELECT * FROM area_lookup")
    hourly = query("SELECT area, hour, avg_db, points FROM area_noise_hourly")
    monthly = query("SELECT area, year_month, avg_db, points FROM area_noise_monthly")
    csrc = query("SELECT area, noise_source, severity, complaints FROM complaints_by_area_source")
    daily = query("SELECT CAST(received_date AS varchar) AS day, complaints, high_complaints "
                  "FROM complaints_daily ORDER BY 1")

    scored = summary.dropna(subset=["avg_db"]).merge(centres, on="area", how="left")
    total_pts = int(summary["points"].fillna(0).sum())
    city_avg = (scored["avg_db"] * scored["points"]).sum() / max(scored["points"].sum(), 1)
    n_complaints = int(summary["complaints"].fillna(0).sum())
    n_high = int(summary["high_complaints"].fillna(0).sum())
    top = scored.sort_values("hotspot_rank").iloc[0] if scored["hotspot_rank"].notna().any() else None

    c1, c2, c3, c4 = st.columns(4)
    kpi(c1, "Noise measurements", f"{total_pts:,}", "NoiseCapture points in Lahore")
    kpi(c2, "Average noise", f"{city_avg:.1f} dB", "weighted across all areas", "teal")
    kpi(c3, "Complaints received", f"{n_complaints}", f"{n_high} high severity", "red")
    if top is not None:
        kpi(c4, "Noisiest area", top["area"], f"{top['avg_db']:.1f} dB average")
    st.write("")

    t_where, t_when, t_comp = st.tabs(["📍 Where is it loudest?", "🕒 When is it loudest?", "📢 Complaints"])

    with t_where:
        a, b = st.columns([3, 2])
        with a:
            st.markdown("#### Noise map")
            show(noise_map(scored.dropna(subset=["c_lat"])))
        with b:
            st.markdown("#### Areas ranked by average noise")
            show(ranked_bar(scored))
        other = summary[summary["area"] == "Other Lahore"]
        if len(other):
            st.caption(f"{int(other['points'].iloc[0])} measurements are more than 6 km from every "
                       "named area, so they are grouped as 'Other Lahore' and not drawn on the map.")

    with t_when:
        a, b = st.columns(2)
        with a:
            st.markdown("#### Noise by hour of day")
            h = (hourly.assign(w=hourly["avg_db"] * hourly["points"]).groupby("hour")
                 .agg(w=("w", "sum"), n=("points", "sum")).reset_index())
            h["avg_db"] = h["w"] / h["n"]
            fig = px.area(h, x="hour", y="avg_db", labels={"avg_db": "Average noise (dB)", "hour": "Hour"})
            fig.update_traces(line_color=CRIMSON, fillcolor="rgba(200,55,75,0.18)")
            fig.update_xaxes(dtick=3)
            show(style(fig, 340))
        with b:
            st.markdown("#### Night vs overall (dB)")
            n = scored.dropna(subset=["night_avg_db"]).sort_values("avg_db", ascending=False)
            fig = go.Figure()
            fig.add_bar(x=n["area"], y=n["avg_db"], name="All day", marker_color=TEAL)
            fig.add_bar(x=n["area"], y=n["night_avg_db"], name="Night", marker_color=AMBER)
            fig.update_layout(barmode="group")
            show(style(fig, 340, legend=True))
        st.markdown("#### Area × hour heatmap")
        pv = hourly.pivot_table(index="area", columns="hour", values="avg_db")
        fig = px.imshow(pv, aspect="auto", color_continuous_scale=NOISE_SCALE, zmin=40, zmax=90,
                        labels=dict(x="Hour of day", y="", color="dB"))
        show(style(fig, 360))
        if monthly["year_month"].nunique() > 1:
            st.markdown("#### Monthly trend")
            m = (monthly.assign(w=monthly["avg_db"] * monthly["points"]).groupby("year_month")
                 .agg(w=("w", "sum"), n=("points", "sum")).reset_index())
            m["avg_db"] = m["w"] / m["n"]
            fig = px.line(m, x="year_month", y="avg_db", markers=True)
            fig.update_traces(line_color=TEAL)
            show(style(fig, 300))

    with t_comp:
        a, b = st.columns(2)
        with a:
            st.markdown("#### What do people complain about?")
            s = (csrc.assign(noise_source=csrc["noise_source"].fillna("Photo only"))
                 .groupby("noise_source")["complaints"].sum().reset_index())
            fig = px.pie(s, names="noise_source", values="complaints", hole=0.55,
                         color_discrete_sequence=SOURCE_COLOURS)
            fig.update_traces(textinfo="label+value", textposition="outside")
            show(style(fig, 360))
        with b:
            st.markdown("#### Complaints per day")
            fig = go.Figure()
            fig.add_bar(x=daily["day"], y=daily["complaints"] - daily["high_complaints"],
                        name="Other", marker_color=TEAL_LIGHT)
            fig.add_bar(x=daily["day"], y=daily["high_complaints"], name="High severity",
                        marker_color=CRIMSON)
            fig.update_layout(barmode="stack")
            show(style(fig, 360, legend=True))
        st.markdown("#### Complaints by area")
        ca = csrc.groupby(["area", "severity"])["complaints"].sum().reset_index()
        fig = px.bar(ca, x="area", y="complaints", color="severity",
                     color_discrete_map={"high": CRIMSON, "medium": AMBER, "low": TEAL_LIGHT},
                     category_orders={"severity": ["high", "medium", "low"]})
        show(style(fig, 320, legend=True))
        st.page_link("complaint_page.py", label="Report a noise complaint", icon="📢")


# ---------------------------------------------------------------- EPA view
def epa_view():
    summary = query("SELECT * FROM area_summary")
    csrc = query("SELECT area, noise_source, severity, complaints FROM complaints_by_area_source")
    ranked = summary.dropna(subset=["hotspot_rank"]).sort_values("hotspot_rank")

    st.markdown("#### Priority hotspots")
    cols = st.columns(3)
    for col, (_, r) in zip(cols, ranked.head(3).iterrows()):
        col.markdown(
            f'<div class="rank"><p class="n">HOTSPOT #{int(r["hotspot_rank"])}</p>'
            f'<p class="a">{r["area"]}</p>'
            f'<p class="d">{r["avg_db"]:.1f} dB average · {int(r["complaints"])} complaints '
            f'({int(r["high_complaints"])} high)</p></div>', unsafe_allow_html=True)
    st.write("")

    st.markdown("#### Full ranking")
    table = summary.sort_values("hotspot_rank", na_position="last").copy()
    table["loud_pct"] = table["loud_share"] * 100
    table = table.drop(columns=["loud_share"])
    st.dataframe(
        table, hide_index=True, use_container_width=True,
        column_config={
            "hotspot_rank": st.column_config.NumberColumn("Rank", format="%d"),
            "hotspot_score": st.column_config.ProgressColumn("Hotspot score", min_value=0, max_value=1,
                                                             format="%.2f"),
            "avg_db": st.column_config.NumberColumn("Avg dB", format="%.1f"),
            "max_db": st.column_config.NumberColumn("Max dB", format="%.1f"),
            "night_avg_db": st.column_config.NumberColumn("Night dB", format="%.1f"),
            "loud_pct": st.column_config.NumberColumn("Share of readings 70 dB+", format="%.0f%%"),
        })
    a, b = st.columns(2)
    a.download_button("⬇ Download hotspot ranking (CSV)", summary.to_csv(index=False),
                      "silento_hotspots.csv", "text/csv")
    b.download_button("⬇ Download complaints summary (CSV)", csrc.to_csv(index=False),
                      "silento_complaints.csv", "text/csv")

    st.markdown("#### Complaint sources by severity")
    d = csrc.assign(noise_source=csrc["noise_source"].fillna("Photo only"))
    fig = px.bar(d.groupby(["noise_source", "severity"])["complaints"].sum().reset_index(),
                 x="noise_source", y="complaints", color="severity",
                 color_discrete_map={"high": CRIMSON, "medium": AMBER, "low": TEAL_LIGHT},
                 category_orders={"severity": ["high", "medium", "low"]})
    show(style(fig, 340, legend=True))


def epa_gate():
    expected = st.secrets.get("EPA_PASSWORD", "")
    if st.session_state.get("epa_ok"):
        if st.button("Log out"):
            st.session_state["epa_ok"] = False
            st.rerun()
        epa_view()
        return
    st.markdown("#### EPA staff login")
    with st.form("epa_login"):
        pw = st.text_input("Password", type="password")
        go_ = st.form_submit_button("Log in")
    if go_:
        if expected and hmac.compare_digest(pw, expected):
            st.session_state["epa_ok"] = True
            st.rerun()
        else:
            st.error("Wrong password.")


# ---------------------------------------------------------------- page
hero()
try:
    tab_public, tab_epa = st.tabs(["📊 Public dashboard", "🛡️ EPA login"])
    with tab_public:
        public_view()
    with tab_epa:
        epa_gate()
except Exception as e:
    st.error(f"Could not load data: {e}")
st.markdown('<p class="foot">Data refreshes automatically when new complaints arrive. '
            'Noise levels: under 55 dB acceptable · 55-70 moderate · 70-85 loud · over 85 harmful.</p>',
            unsafe_allow_html=True)
