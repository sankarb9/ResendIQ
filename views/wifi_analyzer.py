"""Wi-Fi Stability & Dead-Zone Analyzer page (measurement)."""
import io
import sys
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import _ui
from resendiq.wifi import core, db, floorplan

try:  # optional: click-to-place on the floor plan (falls back to sliders)
    from streamlit_image_coordinates import streamlit_image_coordinates as img_click
except ImportError:
    img_click = None

db.init()
COLORS = {"Stable": "#2e9e5b", "Fair": "#e0b400", "Unstable": "#e8781a", "Potential Dead Zone": "#d64545"}
USE_COLORS = {"Usable": "#2e9e5b", "Degraded": "#e8781a", "Unusable": "#d64545"}
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
fmt = lambda v, u="": "—" if v is None or pd.isna(v) else f"{v}{u}"


def loc_stats(df):
    """Per-location mean ± std and 95% CI of the score across repeated runs."""
    rows = []
    for loc, g in df.groupby("location"):
        m, sd, ci = core.mean_ci(g["score"].tolist())
        rows.append(dict(location=loc, runs=len(g), score=m, std=sd, ci95=ci,
                         avg_ms=round(g["avg_ms"].mean(), 1), loss_pct=round(g["loss_pct"].mean(), 1),
                         dns_ms=round(g["dns_ms"].mean(), 1), http_ms=round(g["http_ms"].mean(), 1),
                         latest_status=g["status"].iloc[-1]))
    return pd.DataFrame(rows)


def targets_from(gw, ext):
    t = {}
    if gw.strip():
        t["gateway"] = gw.strip()
    if ext.strip():
        t["external"] = ext.strip()
    return t


_ui.apply()
_ui.hero("📶 Wi-Fi Stability & Dead-Zone Analyzer", "Measure latency, loss, jitter, DNS and HTTP at each spot, then find the dead zones.")

with st.sidebar:
    st.header("Test settings")
    location = st.text_input("Location name", placeholder="e.g. Room A / Hostel corridor")
    duration = st.slider("Duration (seconds)", 10, 120, 30, step=5)
    band = st.selectbox("Wi-Fi band you're connected to", ["Unknown", "2.4 GHz", "5 GHz", "6 GHz"])
    do_app = st.checkbox("Include DNS + HTTP checks", value=True)
    gateway = st.text_input("Gateway (auto-detected)", core.get_default_gateway() or "")
    external = st.text_input("External target", "8.8.8.8")
    run = st.button("▶ Run measurement", type="primary", disabled=not location.strip())
    st.caption("Stay in one spot during the test. Repeat at each location.")

tab_run, tab_cmp, tab_fp, tab_rep, tab_mon = st.tabs(
    ["Run test", "Compare locations", "Floor plan", "Report", "Monitor & trends"])

# ---------------- Run test ----------------
with tab_run:
    if run:
        targets = targets_from(gateway, external)
        if not targets:
            st.error("Enter a gateway or an external target.")
        else:
            bar = st.progress(0.0, text=f"Measuring at '{location}'…")
            samples = core.run_session(targets, duration, 0.5, lambda p: bar.progress(p))
            result = core.evaluate(samples)
            if do_app:
                bar.progress(1.0, text="Running DNS + HTTP checks…")
                result["app"] = core.app_checks()
            bar.empty()
            db.save_session(location.strip(), duration, result, samples, band)
            st.session_state["last"] = (location.strip(), result, samples)

    if "last" not in st.session_state:
        st.info("Enter a location in the sidebar and press **Run measurement**.")
    else:
        loc, res, samples = st.session_state["last"]
        p, a = res["primary"], res.get("app")
        st.subheader(loc)
        k = st.columns([2, 3])
        with k[0]:
            _ui.kpi("Stability score", f"{p['score']}/100", p["status"], COLORS[p["status"]])
        with k[1]:
            st.progress(min(max(p["score"], 0), 100) / 100)
            st.write(res["diagnosis"])
        st.markdown("")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Avg latency", fmt(p["avg"], " ms"))
        c2.metric("Packet loss", fmt(p["loss"], " %"))
        c3.metric("Jitter", fmt(p["jitter"], " ms"))
        c4.metric("Max RTT", fmt(p["max"], " ms"))
        c5.metric("Reachability", p["reachability"])
        if a:
            st.markdown(f"**Usability:** {_ui.pill(a['usability'], USE_COLORS[a['usability']])}"
                        f" &nbsp;|&nbsp; DNS {fmt(a['dns_ms'], ' ms')} ({a['dns_fail']} failed)"
                        f" &nbsp;|&nbsp; HTTP {fmt(a['http_ms'], ' ms')} ({a['http_fail']} failed)",
                        unsafe_allow_html=True)
            st.caption("Pings can succeed while DNS/HTTP are slow or failing: this separates "
                       "“connected” from “actually usable”.")
        st.caption(f"Primary metrics measured against the **{res['basis']}**. Gaps in the chart = lost packets.")
        df = pd.DataFrame(samples)
        df.insert(0, "time (s)", [i * 0.5 for i in range(len(df))])
        fig = px.line(df, x="time (s)", y=[c for c in df.columns if c != "time (s)"], markers=True,
                      labels={"value": "RTT (ms)", "variable": "target"})
        st.plotly_chart(fig, width="stretch")
        with st.expander("Per-target details"):
            st.dataframe(pd.DataFrame(res["metrics"]).T)

# ---------------- shared data ----------------
sessions = db.load_sessions()
stats = loc_stats(sessions) if not sessions.empty else pd.DataFrame()

# ---------------- Compare (statistics) ----------------
with tab_cmp:
    if sessions.empty:
        st.info("No results yet. Run a measurement first.")
    else:
        st.subheader("Stability score by location (mean ± 95% CI over repeated runs)")
        fig = px.bar(stats, x="location", y="score", error_y="ci95", color="latest_status",
                     color_discrete_map=COLORS, range_y=[0, 100], text="score")
        st.plotly_chart(fig, width="stretch")
        st.caption("Error bars need ≥ 2 runs per location. Non-overlapping bars suggest a real difference "
                   "between locations; overlapping bars suggest the difference may be run-to-run noise.")
        st.dataframe(stats, width="stretch", hide_index=True)

        known = sessions[sessions["band"].notna() & (sessions["band"] != "Unknown")]
        if known["band"].nunique() >= 2:
            st.subheader("2.4 GHz vs 5 GHz")
            g = known.groupby(["location", "band"], as_index=False)["score"].mean().round(1)
            st.plotly_chart(px.bar(g, x="location", y="score", color="band", barmode="group",
                                   range_y=[0, 100]), width="stretch")
        with st.expander("Run-to-run spread (box plot)"):
            st.plotly_chart(px.box(sessions, x="location", y="score", points="all", range_y=[0, 100]),
                            width="stretch")
        with st.expander("All sessions (history)"):
            st.dataframe(sessions.drop(columns=["details"]), width="stretch", hide_index=True)
        if st.button("🗑 Clear all measurements"):
            db.clear_all()
            st.rerun()

# ---------------- Floor plan ----------------
with tab_fp:
    up = st.file_uploader("Upload a floor-plan image (PNG/JPG)", type=["png", "jpg", "jpeg"])
    stored = db.load_floorplan()
    if up is not None and up.getvalue() != stored:
        db.save_floorplan(up.name, up.getvalue())
        stored = up.getvalue()
        st.session_state.pop("pending", None)
        st.success("Floor plan saved (previous positions were cleared).")
    if stored is None:
        st.info("Upload a floor plan (a phone photo or a sketch works) to start.")
    elif sessions.empty:
        st.info("Run some measurements first, then place each location on the plan.")
    else:
        img = Image.open(io.BytesIO(stored)).convert("RGB")
        img.thumbnail((900, 900))
        coords, means = db.load_coords(), sessions.groupby("location")["score"].mean().to_dict()
        router = coords.get("__router__")
        pts = [(l, x, y, means[l]) for l, (x, y) in coords.items() if l in means]
        pick = st.selectbox("Place on plan", ["📶 Router / access point"] + sorted(means))
        key = "__router__" if pick.startswith("📶") else pick
        st.caption("Click where this spot is on the plan, then press **Save position**.")
        surface = floorplan.render(img, pts, router, heat=False)
        if img_click:
            c = img_click(surface, key="fp_click")
            if c and c.get("unix_time") != st.session_state.get("seen_click"):
                st.session_state["seen_click"] = c.get("unix_time")
                st.session_state["pending"] = (c["x"] / c["width"], c["y"] / c["height"])
        else:
            st.image(surface)
            st.session_state["pending"] = (st.slider("X (%)", 0, 100, 50) / 100, st.slider("Y (%)", 0, 100, 50) / 100)
            st.caption("Install `streamlit-image-coordinates` for click-to-place.")
        pend = st.session_state.get("pending")
        if pend and st.button(f"💾 Save position for: {pick}"):
            db.save_coord(key, *pend)
            st.session_state.pop("pending", None)
            st.rerun()
        st.subheader("Coverage heatmap")
        if len(pts) >= 2:
            heat = floorplan.render(img, pts, router)
            st.image(heat, caption="Green = stable, red = dead zone. Colours between measured points are "
                                   "interpolated estimates (inverse-distance weighting), not measurements.")
            buf = io.BytesIO()
            heat.save(buf, "PNG")
            st.download_button("⬇ Heatmap (.png)", buf.getvalue(), "wifi_heatmap.png", "image/png")
        else:
            st.info(f"Place at least 2 measured locations ({len(pts)} placed so far).")

# ---------------- Report ----------------
with tab_rep:
    if sessions.empty:
        st.info("No data to report yet.")
    else:
        latest_rows = sessions.groupby("location").tail(1)
        counts = latest_rows["status"].value_counts()
        by_loc = sessions.groupby("location")["score"].mean()
        dead = latest_rows.loc[latest_rows["status"] == "Potential Dead Zone", "location"].tolist()
        ci_lines = "\n".join(
            f"  - {r.location}: {r.score} ± {fmt(r.ci95)} (n={r.runs})" for r in stats.itertuples())
        use = sessions["usability"].value_counts()
        trend = db.load_trend()
        worst_hr = ""
        if not trend.empty:
            hr = trend.groupby(trend["created_at"].dt.hour)["score"].mean()
            worst_hr = f"\n- **Worst time of day:** {hr.idxmin():02d}:00 (mean score {hr.min():.1f}/100)"
        report = f"""# Wi-Fi Network-Quality Report

- **Locations tested:** {sessions['location'].nunique()} ({len(sessions)} sessions)
- **Stable:** {counts.get('Stable', 0)} | **Fair:** {counts.get('Fair', 0)} | **Unstable:** {counts.get('Unstable', 0)} | **Potential dead zones:** {counts.get('Potential Dead Zone', 0)}
- **Potential dead zones:** {', '.join(dead) if dead else 'none detected'}
- **Average latency (all sessions):** {fmt(round(sessions['avg_ms'].mean(), 1), ' ms')}
- **Average packet loss (all sessions):** {round(sessions['loss_pct'].mean(), 1)} %
- **Most unstable location:** {by_loc.idxmin()} (mean score {by_loc.min():.1f}/100)
- **Application-layer usability:** Usable {use.get('Usable', 0)} | Degraded {use.get('Degraded', 0)} | Unusable {use.get('Unusable', 0)}{worst_hr}
- **Mean score ± 95% CI per location:**
{ci_lines}

*Classification uses project-defined thresholds: {core.T}*
"""
        st.markdown(report)
        d1, d2 = st.columns(2)
        d1.download_button("⬇ Report (.md)", report, "wifi_report.md")
        d2.download_button("⬇ Sessions (.csv)", sessions.drop(columns=["details"]).to_csv(index=False),
                           "wifi_sessions.csv")

# ---------------- Monitor & trends (last: its loop blocks the script while running) ----------------
with tab_mon:
    st.subheader("Continuous monitoring")
    a1, a2, a3, a4, a5 = st.columns(5)
    mloc = a1.text_input("Monitored location", value=location.strip() or "Monitor spot")
    probe = a2.slider("Probe length (s)", 5, 30, 10)
    gap = a3.slider("Wait between probes (s)", 0, 300, 30)
    minutes = a4.slider("Total time (min)", 1, 240, 5)
    thresh = a5.slider("Alert if score below", 10, 90, 60)
    b1, b2 = st.columns([1, 6])
    start = b1.button("▶ Start", type="primary")
    b2.button("⏹ Stop")  # any widget interaction reruns the script, which ends the loop
    st.caption("Keep this tab open and the laptop awake. Each cycle is logged; alerts fire when the score drops "
               "below the threshold or the location turns into a potential dead zone.")
    alert_box, chart_slot = st.empty(), st.empty()

    def live_chart(n):
        m = db.load_monitor(mloc)
        if m.empty:
            return
        fig = px.line(m, x="created_at", y="score", markers=True, range_y=[0, 100],
                      title=f"Stability score over time — {mloc}")
        fig.add_hline(y=thresh, line_dash="dash", line_color="#d64545", annotation_text="alert threshold")
        chart_slot.plotly_chart(fig, width="stretch", key=f"live_{n}")

    live_chart(0)
    if start:
        targets, end, n = targets_from(gateway, external), time.time() + minutes * 60, 0
        if not targets:
            st.error("Enter a gateway or an external target in the sidebar.")
        while targets and time.time() < end:
            n += 1
            p = core.evaluate(core.run_session(targets, probe, 0.5))["primary"]
            alert = p["score"] < thresh or p["status"] == "Potential Dead Zone"
            db.save_monitor(mloc, p, alert)
            if alert:
                msg = f"⚠ {time.strftime('%H:%M:%S')} — {mloc}: {p['status']} (score {p['score']})"
                alert_box.warning(msg)
                st.toast(msg)
            live_chart(n)
            for _ in range(gap):
                if time.time() >= end:
                    break
                time.sleep(1)
        st.success("Monitoring finished.")

    mon = db.load_monitor()
    if not mon.empty and mon["alert"].sum():
        with st.expander(f"Alert log ({int(mon['alert'].sum())})"):
            st.dataframe(mon[mon["alert"] == 1][["created_at", "location", "score", "status"]],
                         width="stretch", hide_index=True)

    st.subheader("Trends by time of day")
    trend = db.load_trend()
    if trend.empty:
        st.info("Run tests or monitoring to see trends.")
    else:
        pick = st.multiselect("Locations", sorted(trend["location"].unique()),
                              default=sorted(trend["location"].unique()))
        t = trend[trend["location"].isin(pick)].copy()
        if not t.empty:
            t["hour"], t["weekday"] = t["created_at"].dt.hour, t["created_at"].dt.day_name()
            hr = t.groupby("hour").agg(score=("score", "mean"), avg_ms=("avg_ms", "mean"),
                                       loss_pct=("loss_pct", "mean"), n=("score", "size")).round(1).reset_index()
            st.write(f"**Worst hour:** {int(hr.loc[hr['score'].idxmin(), 'hour']):02d}:00 "
                     f"(mean score {hr['score'].min()}) — {int(hr['n'].sum())} measurements analysed.")
            st.plotly_chart(px.bar(hr, x="hour", y="score", text="n", range_y=[0, 100],
                                   title="Mean score by hour of day (label = #measurements)"),
                            width="stretch")
            st.plotly_chart(px.density_heatmap(t, x="hour", y="weekday", z="score", histfunc="avg",
                                               color_continuous_scale="RdYlGn", range_color=[0, 100],
                                               category_orders={"weekday": DAYS},
                                               title="Mean score: weekday × hour"), width="stretch")
            st.plotly_chart(px.scatter(t, x="created_at", y="score", color="location", range_y=[0, 100],
                                       title="All measurements over time"), width="stretch")
