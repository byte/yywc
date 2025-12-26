from __future__ import annotations

import html
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from .analyze import Summary, summarize
from .export_reader import Dataset


@dataclass(frozen=True)
class Report:
    summary: Summary
    html: str


def _h(text: str) -> str:
    return html.escape(text, quote=True)


def _render_kv(title: str, value: str) -> str:
    return f"<div class='kv'><div class='k'>{_h(title)}</div><div class='v'>{_h(value)}</div></div>"


def _render_table(title: str, rows: list[tuple[str, int]]) -> str:
    trs = "\n".join(f"<tr><td>{_h(k)}</td><td class='num'>{v}</td></tr>" for k, v in rows)
    return f"""
    <section class="card">
      <h2>{_h(title)}</h2>
      <table>
        <tbody>
          {trs}
        </tbody>
      </table>
    </section>
    """


def _render_bar_chart(title: str, series: dict[str, int]) -> str:
    labels = list(series.keys())
    values = list(series.values())
    payload = {"labels": labels, "values": values}
    chart_id = f"chart_{abs(hash(title))}"
    return f"""
    <section class="card">
      <h2>{_h(title)}</h2>
      <div class="chart" id="{_h(chart_id)}" data-series='{_h(json.dumps(payload, ensure_ascii=False))}'></div>
    </section>
    """


def build_report(dataset: Dataset, *, year: int | None, redact: bool, max_excerpts: int) -> Report:
    summary = summarize(dataset, year=year, redact=redact, max_excerpts=max_excerpts)
    generated_at = datetime.now(tz=timezone.utc).isoformat()
    year_label = str(year) if year is not None else "All time"
    data_json = json.dumps(asdict(summary), ensure_ascii=False)
    # Don't HTML-escape JSON inside a <script> tag: script bodies are raw text,
    # so entities like &quot; are not decoded and JSON.parse() will fail.
    # Minimal hardening to avoid prematurely closing the script tag.
    data_json_script = data_json.replace("</", "<\\/")

    fun_facts_html = ""
    if summary.fun_facts:
        items = "".join(f"<li>{_h(item)}</li>" for item in summary.fun_facts[:8])
        fun_facts_html = f"<ul class='facts'>{items}</ul>"

    excerpts_html = ""
    if summary.excerpts:
        items = []
        for ex in summary.excerpts:
            items.append(
                f"<div class='excerpt'><div class='meta'>{_h(ex.created_at_iso)} · {_h(ex.role)} · {_h(ex.title)}</div>"
                f"<pre>{_h(ex.text)}</pre></div>"
            )
        excerpts_html = f"""
        <section class="card">
          <h2>Excerpts</h2>
          {''.join(items)}
        </section>
        """

    html_out = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Your Year With Chat — Year in Review ({_h(year_label)})</title>
  <style>
    :root {{
      --bg: #0b1020;
      --card: #121a33;
      --muted: #9fb0d0;
      --text: #e9efff;
      --accent: #7dd3fc;
      --accent2: #a7f3d0;
      --border: rgba(255,255,255,0.10);
      --shadow: rgba(0,0,0,0.30);
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      --sans: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji";
    }}
    body {{
      margin: 0;
      background: radial-gradient(1200px 700px at 20% 0%, rgba(125,211,252,0.22), transparent 60%),
                  radial-gradient(900px 600px at 90% 20%, rgba(167,243,208,0.18), transparent 55%),
                  var(--bg);
      color: var(--text);
      font-family: var(--sans);
    }}
    header {{
      padding: 28px 18px 12px;
      max-width: 1100px;
      margin: 0 auto;
    }}
    h1 {{
      margin: 0 0 8px 0;
      font-size: 24px;
      letter-spacing: 0.2px;
    }}
    .subtitle {{
      color: var(--muted);
      font-size: 14px;
    }}
    main {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 12px 18px 40px;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }}
    @media (max-width: 900px) {{
      main {{ grid-template-columns: 1fr; }}
    }}
    .card {{
      background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px 14px 12px;
      box-shadow: 0 10px 35px var(--shadow);
      overflow: hidden;
    }}
    .kvs {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
    }}
    @media (max-width: 900px) {{
      .kvs {{ grid-template-columns: repeat(2, 1fr); }}
    }}
    .kv {{
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px 10px 8px;
      background: rgba(0,0,0,0.10);
    }}
    .k {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }}
    .v {{
      font-size: 18px;
      font-weight: 650;
    }}
    h2 {{
      margin: 0 0 10px 0;
      font-size: 15px;
      color: var(--text);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    td {{
      padding: 8px 6px;
      border-top: 1px solid var(--border);
      vertical-align: top;
    }}
    td.num {{
      text-align: right;
      font-variant-numeric: tabular-nums;
      color: var(--accent2);
      white-space: nowrap;
    }}
    .chart {{
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px;
      background: rgba(0,0,0,0.10);
    }}
    .bars {{
      display: grid;
      gap: 6px;
    }}
    .bar {{
      display: grid;
      grid-template-columns: 120px 1fr 70px;
      align-items: center;
      gap: 10px;
      font-size: 12px;
      color: var(--muted);
    }}
    .bar .label {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .bar .track {{
      height: 10px;
      border-radius: 999px;
      background: rgba(255,255,255,0.08);
      position: relative;
      overflow: hidden;
    }}
    .bar .fill {{
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--accent), var(--accent2));
      width: 0%;
    }}
    .bar .value {{
      text-align: right;
      font-variant-numeric: tabular-nums;
      color: var(--text);
    }}
    .excerpt .meta {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }}
    .facts {{
      margin: 0;
      padding-left: 18px;
      color: rgba(233,239,255,0.85);
      font-size: 13px;
    }}
    .facts li {{
      margin: 6px 0;
    }}
    .shareRow {{
      display: grid;
      grid-template-columns: 1fr 420px;
      gap: 14px;
      align-items: start;
    }}
    @media (max-width: 900px) {{
      .shareRow {{ grid-template-columns: 1fr; }}
    }}
    .shareImg {{
      width: 100%;
      border-radius: 14px;
      border: 1px solid var(--border);
      background: rgba(0,0,0,0.10);
    }}
    .linkRow {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 4px 0 10px 0;
    }}
    .pill {{
      display: inline-block;
      padding: 8px 10px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: rgba(0,0,0,0.14);
      color: var(--text);
      font-size: 13px;
      text-decoration: none;
    }}
    .pill:hover {{
      border-color: rgba(255,255,255,0.22);
    }}
    .calendar {{
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 12px;
      align-items: start;
    }}
    .calLegend {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
    }}
    .calGrid {{
      display: grid;
      grid-auto-flow: column;
      grid-auto-columns: 12px;
      grid-template-rows: repeat(7, 12px);
      gap: 3px;
      padding: 10px;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: rgba(0,0,0,0.10);
      overflow: auto;
    }}
    .cell {{
      width: 12px;
      height: 12px;
      border-radius: 3px;
      background: rgba(255,255,255,0.06);
    }}
    .cell[data-lvl="1"] {{ background: rgba(125,211,252,0.22); }}
    .cell[data-lvl="2"] {{ background: rgba(125,211,252,0.35); }}
    .cell[data-lvl="3"] {{ background: rgba(167,243,208,0.42); }}
    .cell[data-lvl="4"] {{ background: rgba(167,243,208,0.62); }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: var(--mono);
      font-size: 12px;
      line-height: 1.35;
      padding: 10px;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: rgba(0,0,0,0.12);
    }}
    footer {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 0 18px 24px;
      color: var(--muted);
      font-size: 12px;
    }}
  </style>
</head>
<body>
  <header>
    <h1>Your Year With Chat — Year in Review ({_h(year_label)})</h1>
    <div class="subtitle">Generated locally · { _h(generated_at) } · No network required</div>
  </header>
  <main>
    <section class="card" style="grid-column: 1 / -1;">
      <h2>Share Card</h2>
      <div class="shareRow">
        <div>
          <div class="linkRow">
            <a class="pill" href="share.svg" download>Download share.svg</a>
            <a class="pill" href="summary.json" download>Download summary.json</a>
          </div>
          <div class="subtitle" style="margin: 0 0 10px 0;">
            This is a single image file you can post. For PNG conversion, see the tip at the bottom of the page.
          </div>
          {fun_facts_html}
        </div>
        <div>
          <img class="shareImg" src="share.svg" alt="Share card" />
        </div>
      </div>
    </section>

    <section class="card" style="grid-column: 1 / -1;">
      <h2>Highlights</h2>
      <div class="kvs">
        {_render_kv("Conversations", str(summary.total_conversations))}
        {_render_kv("Messages", str(summary.total_messages))}
        {_render_kv("User Messages", str(summary.total_user_messages))}
        {_render_kv("Assistant Messages", str(summary.total_assistant_messages))}
        {_render_kv("Words (approx.)", str(summary.total_words))}
        {_render_kv("Words / Message", f"{summary.words_per_message:.1f}")}
        {_render_kv("Active Days", str(summary.active_days))}
        {_render_kv("Longest Streak (days)", str(summary.longest_streak_days))}
        {_render_kv("Busiest Day", summary.busiest_day_local or "—")}
        {_render_kv("Peak Hour (local)", f"{summary.busiest_hour_local:02d}:00" if summary.busiest_hour_local is not None else "—")}
        {_render_kv("Unique Models", str(len(summary.top_models)))}
        {_render_kv("Top Word", summary.top_words[0][0] if summary.top_words else "—")}
      </div>
    </section>

    <section class="card" style="grid-column: 1 / -1;">
      <h2>Calendar Heatmap (local time)</h2>
      <div class="calendar">
        <div class="calLegend">
          <div>Each square is a day.</div>
          <div>Darker = more messages.</div>
          <div id="calRange" style="margin-top:8px;"></div>
        </div>
        <div id="calGrid" class="calGrid" aria-label="Calendar heatmap"></div>
      </div>
    </section>

    {_render_bar_chart("Messages by Month", summary.messages_by_month)}
    {_render_bar_chart("Messages by Weekday", summary.messages_by_weekday)}
    {_render_bar_chart("Messages by Hour (local)", summary.messages_by_hour_local)}

    {_render_table("Top Words", summary.top_words[:15])}
    {_render_table("Top Bigrams", summary.top_bigrams[:15])}
    {_render_table("Top Conversation Titles (by message count)", summary.top_titles[:15])}
    {_render_table("Models (from metadata)", summary.top_models[:10])}
    {_render_table("Longest Conversations (by message count)", summary.longest_conversations[:10])}

    {excerpts_html}
  </main>

  <footer>
    <div>Tip: rerun with <span style="font-family: var(--mono);">--year YYYY</span> or <span style="font-family: var(--mono);">--redact</span> for shareable reports. PNG on macOS: <span style="font-family: var(--mono);">qlmanage -t -s 1200 -o . share.svg</span></div>
  </footer>

  <script id="summary" type="application/json">{data_json_script}</script>
  <script>
    (function() {{
      const summary = JSON.parse(document.getElementById('summary').textContent);

      function render(el) {{
        const data = JSON.parse(el.dataset.series);
        const labels = data.labels || [];
        const values = data.values || [];
        const max = Math.max(1, ...values);
        const bars = document.createElement('div');
        bars.className = 'bars';
        for (let i = 0; i < labels.length; i++) {{
          const row = document.createElement('div');
          row.className = 'bar';
          const label = document.createElement('div');
          label.className = 'label';
          label.textContent = labels[i];
          const track = document.createElement('div');
          track.className = 'track';
          const fill = document.createElement('div');
          fill.className = 'fill';
          fill.style.width = ((values[i] / max) * 100).toFixed(2) + '%';
          track.appendChild(fill);
          const value = document.createElement('div');
          value.className = 'value';
          value.textContent = values[i];
          row.appendChild(label);
          row.appendChild(track);
          row.appendChild(value);
          bars.appendChild(row);
        }}
        el.innerHTML = '';
        el.appendChild(bars);
      }}
      document.querySelectorAll('.chart').forEach(render);

      function renderCalendar() {{
        const counts = summary.messages_by_day_local || {{}};
        const keys = Object.keys(counts).sort();
        const calGrid = document.getElementById('calGrid');
        const calRange = document.getElementById('calRange');
        if (!calGrid) return;

        let start;
        let end;
        if (summary.year) {{
          start = new Date(summary.year, 0, 1);
          end = new Date(summary.year, 11, 31);
        }} else if (keys.length) {{
          end = new Date(keys[keys.length - 1]);
          start = new Date(end);
          start.setDate(start.getDate() - 364);
        }} else {{
          start = new Date();
          end = new Date();
        }}

        const startIso = start.toISOString().slice(0, 10);
        const endIso = end.toISOString().slice(0, 10);
        if (calRange) calRange.textContent = startIso + " \u2192 " + endIso;

        const values = keys.map(k => counts[k] || 0);
        const max = Math.max(0, ...values);
        function level(v) {{
          if (max <= 0 || v <= 0) return 0;
          const r = v / max;
          if (r < 0.25) return 1;
          if (r < 0.50) return 2;
          if (r < 0.75) return 3;
          return 4;
        }}

        // Align to Monday column start
        const d0 = new Date(start);
        const day = (d0.getDay() + 6) % 7; // 0=Mon ... 6=Sun
        d0.setDate(d0.getDate() - day);

        calGrid.innerHTML = '';
        for (let d = new Date(d0); d <= end; d.setDate(d.getDate() + 1)) {{
          const iso = d.toISOString().slice(0, 10);
          const v = counts[iso] || 0;
          const cell = document.createElement('div');
          cell.className = 'cell';
          cell.dataset.lvl = level(v);
          cell.title = iso + ": " + v + " messages";
          calGrid.appendChild(cell);
        }}
      }}

      renderCalendar();
    }})();
  </script>
</body>
</html>
"""
    return Report(summary=summary, html=html_out)
