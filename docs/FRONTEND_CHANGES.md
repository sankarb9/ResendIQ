# Frontend changes

- **Theme & shared helpers:** `.streamlit/config.toml`, `views/_ui.py` (hero, cards, KPI tiles, pills, Plotly template, colour maps).
- **Overview:** live KPI strip from the SQLite data, page cards, demo checklist.
- **Live Terminal Mode:** run a real UDP transfer from the browser (`resendiq/live_runner.py`), colour-coded auto-scrolling log, result KPIs, log download, port-busy check, generated two-terminal commands.
- **ARQ Simulator:** tabs instead of sidebar radio, channel presets (Clean / Typical Wi-Fi / Weak signal / Near dead zone), KPI tiles, per-packet timeline with event colours, event filter, comparison summary + side-by-side charts, history clear button.
- **Wi-Fi Analyzer / Measured -> ARQ:** shared hero, score tile + progress bar, usability pill, consistent protocol colours.
- **Tests:** smoke test now covers the Live Terminal page and a simulator run; `tests/test_live_runner.py` covers parsing, commands and a real lossless UDP transfer.
