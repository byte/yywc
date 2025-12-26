from __future__ import annotations

import html
from datetime import date, timedelta

from .analyze import Summary


def _h(text: str) -> str:
    return html.escape(text, quote=True)


def _fmt_int(value: int) -> str:
    return f"{value:,}"


def _fmt_float(value: float) -> str:
    if value >= 100:
        return f"{value:,.0f}"
    return f"{value:,.1f}"


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    if max_len <= 1:
        return "…"
    return text[: max_len - 1] + "…"


# Premium color palette
COLORS = {
    "bg_dark": "#0a0e1a",
    "bg_mid": "#0f1628",
    "accent_cyan": "#22d3ee",
    "accent_emerald": "#34d399",
    "accent_violet": "#a78bfa",
    "accent_rose": "#fb7185",
    "text_primary": "#f1f5f9",
    "text_secondary": "#94a3b8",
    "text_muted": "#64748b",
    "surface": "#1e293b",
    "border": "#334155",
}


def _heat_color(level: int) -> str:
    """Return a single color with baked-in opacity for each heat level."""
    if level <= 0:
        return "#1e293b"  # Empty/surface
    if level == 1:
        return "#164e63"  # Cyan-900
    if level == 2:
        return "#0e7490"  # Cyan-700
    if level == 3:
        return "#06b6d4"  # Cyan-500
    return "#22d3ee"  # Cyan-400 (brightest)


def _heat_level(value: int, max_value: int) -> int:
    if max_value <= 0 or value <= 0:
        return 0
    r = value / max_value
    if r < 0.25:
        return 1
    if r < 0.50:
        return 2
    if r < 0.75:
        return 3
    return 4


def _month_name(month: int) -> str:
    return ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][month - 1]


def _panel(x: int, y: int, w: int, h: int, title: str = "", *, corner: int = 20) -> str:
    panel = f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='{corner}' fill='{COLORS['surface']}' fill-opacity='0.5'/>"
    if title:
        panel += f"<text class='sectionTitle' x='{x + 24}' y='{y + 32}'>{_h(title)}</text>"
    return panel


def _models_panel_svg(*, x: int, y: int, w: int, items: list[tuple[str, int]], max_items: int) -> str:
    items = items[:max_items]
    if not items:
        return f"<text class='bodyMuted' x='{x}' y='{y + 40}'>No model data in export</text>"
    max_value = max((int(v) for _, v in items), default=1) or 1

    cols = 2
    rows_per_col = 5
    max_display = cols * rows_per_col
    items = items[:max_display]
    half = (len(items) + 1) // 2
    col_w = (w - 32) // cols
    row_h = 28
    bar_w = min(160, col_w - 200)
    bar_h = 6

    out: list[str] = []
    for idx, (name, value) in enumerate(items):
        col = 0 if idx < half else 1
        row = idx if col == 0 else idx - half
        x0 = x + col * col_w
        y0 = y + 36 + row * row_h

        value_i = int(value)
        fill_w = max(4, int(round((value_i / max_value) * bar_w)))

        # Model name
        out.append(f"<text class='modelName' x='{x0}' y='{y0}'>{_h(_truncate(name, 18))}</text>")
        # Background bar
        bar_x = x0 + 120
        out.append(f"<rect x='{bar_x}' y='{y0 - 5}' width='{bar_w}' height='{bar_h}' rx='{bar_h // 2}' fill='{COLORS['border']}' fill-opacity='0.4'/>")
        # Fill bar with gradient effect
        out.append(f"<rect x='{bar_x}' y='{y0 - 5}' width='{fill_w}' height='{bar_h}' rx='{bar_h // 2}' fill='url(#barGradient)'/>")
        # Count
        out.append(f"<text class='modelCount' x='{bar_x + bar_w + 10}' y='{y0}'>{_fmt_int(value_i)}</text>")

    return "\n".join(out)


def _mini_bar_chart(
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    title: str,
    labels: list[str],
    values: list[int],
    gradient_id: str = "barGradient",
    label_mode: str = "sparse",
) -> str:
    values = (values + [0] * len(labels))[: len(labels)]
    max_value = max(1, max(values)) if values else 1
    n = len(labels)
    pad = 16
    inner_w = width - pad * 2
    inner_h = height - 24
    bar_gap = 4 if n <= 12 else 2
    bar_w = max(4, (inner_w - (n - 1) * bar_gap) // n)

    out: list[str] = []
    out.append(f"<text class='chartTitle' x='{x}' y='{y - 10}'>{_h(title)}</text>")

    for i, v in enumerate(values):
        bx = x + pad + i * (bar_w + bar_gap)
        bar_h = max(2, int(round((v / max_value) * inner_h)))
        by = y + height - 12 - bar_h
        out.append(f"<rect x='{bx}' y='{by}' width='{bar_w}' height='{bar_h}' rx='{min(4, bar_w // 2)}' fill='url(#{gradient_id})'/>")

    if label_mode == "months":
        for i, lab in enumerate(labels):
            tx = x + pad + i * (bar_w + bar_gap) + bar_w / 2
            out.append(f"<text class='axisLabel' x='{tx:.1f}' y='{y + height + 4}' text-anchor='middle'>{_h(lab[:1])}</text>")
    elif label_mode == "sparse":
        step = max(1, n // 4)
        for i in range(0, n, step):
            tx = x + pad + i * (bar_w + bar_gap) + bar_w / 2
            out.append(f"<text class='axisLabel' x='{tx:.1f}' y='{y + height + 4}' text-anchor='middle'>{_h(labels[i])}</text>")

    return "\n".join(out)


def _hour_chart_svg(*, x: int, y: int, width: int, height: int, values: list[int]) -> str:
    if len(values) != 24:
        values = (values + [0] * 24)[:24]
    max_value = max(1, max(values))
    pad = 16
    inner_w = width - pad * 2
    inner_h = height - 24
    bar_gap = 2
    bar_w = max(4, (inner_w - 23 * bar_gap) // 24)

    out: list[str] = []
    out.append(f"<text class='chartTitle' x='{x}' y='{y - 10}'>Activity by hour</text>")

    for h in range(24):
        bx = x + pad + h * (bar_w + bar_gap)
        bar_h = max(2, int(round((values[h] / max_value) * inner_h)))
        by = y + height - 12 - bar_h
        out.append(f"<rect x='{bx}' y='{by}' width='{bar_w}' height='{bar_h}' rx='3' fill='url(#emeraldGradient)'/>")

    for tick in (0, 6, 12, 18, 23):
        tx = x + pad + tick * (bar_w + bar_gap) + bar_w / 2
        out.append(f"<text class='axisLabel' x='{tx:.1f}' y='{y + height + 4}' text-anchor='middle'>{tick}</text>")

    return "\n".join(out)


def _stat_card(x: int, y: int, w: int, h: int, label: str, value: str, icon_color: str) -> str:
    """Render a single stat card with glow effect."""
    return f"""<g transform="translate({x}, {y})">
      <rect width="{w}" height="{h}" rx="16" fill="{COLORS['surface']}" fill-opacity="0.6"/>
      <circle cx="24" cy="24" r="6" fill="{icon_color}" fill-opacity="0.8"/>
      <text class="statLabel" x="24" y="{h - 20}">{_h(label)}</text>
      <text class="statValue" x="24" y="{h - 42}">{_h(value)}</text>
    </g>"""


def build_share_svg(summary: Summary, *, year_label: str) -> str:
    # Highlights data
    highlights = [
        ("Total Messages", _fmt_int(summary.total_messages), COLORS["accent_cyan"]),
        ("Active Days", _fmt_int(summary.active_days), COLORS["accent_emerald"]),
        ("Longest Streak", f"{_fmt_int(summary.longest_streak_days)} days", COLORS["accent_violet"]),
        ("Words/Message", _fmt_float(summary.words_per_message), COLORS["accent_rose"]),
    ]

    # Heatmap data
    day_counts = {k: int(v) for k, v in (summary.messages_by_day_local or {}).items()}
    if summary.year:
        start = date(summary.year, 1, 1)
        end = date(summary.year, 12, 31)
    else:
        end = max((date.fromisoformat(k) for k in day_counts.keys()), default=date.today())
        start = end - timedelta(days=364)

    start_monday = start - timedelta(days=start.weekday())
    max_day = max(day_counts.values(), default=0)

    # Heatmap geometry - larger cells, better positioned
    cell = 12
    gap = 2
    heat_x0 = 80
    heat_y0 = 310

    heat_rects: list[str] = []
    total_days = (end - start_monday).days + 1
    for i in range(total_days):
        d = start_monday + timedelta(days=i)
        week = (d - start_monday).days // 7
        weekday = d.weekday()
        x = heat_x0 + week * (cell + gap)
        y = heat_y0 + weekday * (cell + gap)
        lvl = _heat_level(day_counts.get(d.isoformat(), 0), max_day)
        color = _heat_color(lvl)
        heat_rects.append(f"<rect x='{x}' y='{y}' width='{cell}' height='{cell}' rx='3' fill='{color}'/>")

    # Month labels above heatmap - calculate actual positions based on first day of each month
    month_labels_svg: list[str] = []
    for m in range(1, 13):
        first_of_month = date(summary.year or start.year, m, 1)
        if first_of_month < start_monday:
            week_num = 0
        else:
            week_num = (first_of_month - start_monday).days // 7
        month_x = heat_x0 + week_num * (cell + gap)
        month_labels_svg.append(f"<text class='axisLabel' x='{month_x}' y='{heat_y0 - 10}'>{_month_name(m)}</text>")

    # Weekday labels
    weekday_labels = ["Mon", "", "Wed", "", "Fri", "", "Sun"]
    weekday_svg = [
        f"<text class='axisLabel' x='{heat_x0 - 8}' y='{heat_y0 + i * (cell + gap) + 9}' text-anchor='end'>{lab}</text>"
        for i, lab in enumerate(weekday_labels) if lab
    ]

    # Legend
    legend_x = heat_x0
    legend_y = heat_y0 + 7 * (cell + gap) + 16
    legend = [f"<text class='axisLabel' x='{legend_x}' y='{legend_y + 10}'>Less</text>"]
    for i in range(5):
        legend.append(f"<rect x='{legend_x + 32 + i * 18}' y='{legend_y}' width='14' height='14' rx='3' fill='{_heat_color(i)}'/>")
    legend.append(f"<text class='axisLabel' x='{legend_x + 32 + 5 * 18 + 8}' y='{legend_y + 10}'>More</text>")

    # Charts data
    month_chart_labels = [_month_name(m) for m in range(1, 13)]
    month_values = [0] * 12
    if summary.year:
        for key, v in (summary.messages_by_month or {}).items():
            if not (isinstance(key, str) and len(key) >= 7):
                continue
            try:
                yr = int(key[:4])
                mo = int(key[5:7])
            except ValueError:
                continue
            if yr == summary.year and 1 <= mo <= 12:
                month_values[mo - 1] = int(v)

    weekday_chart_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday_values = [int((summary.messages_by_weekday or {}).get(k, 0)) for k in weekday_chart_labels]
    hour_values = [int((summary.messages_by_hour_local or {}).get(str(h), 0)) for h in range(24)]

    # Models data
    model_items = [(name, int(count)) for name, count in (summary.top_models or [])]

    # Canvas dimensions
    W, H = 1200, 900
    pad = 48

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Your Year With Chat - {year_label}">
  <defs>
    <!-- Background gradient -->
    <linearGradient id="bgGradient" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{COLORS['bg_dark']}"/>
      <stop offset="50%" stop-color="{COLORS['bg_mid']}"/>
      <stop offset="100%" stop-color="{COLORS['bg_dark']}"/>
    </linearGradient>

    <!-- Ambient glow effects -->
    <radialGradient id="glowCyan" cx="15%" cy="20%" r="50%">
      <stop offset="0%" stop-color="{COLORS['accent_cyan']}" stop-opacity="0.15"/>
      <stop offset="100%" stop-color="{COLORS['accent_cyan']}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glowEmerald" cx="85%" cy="80%" r="50%">
      <stop offset="0%" stop-color="{COLORS['accent_emerald']}" stop-opacity="0.12"/>
      <stop offset="100%" stop-color="{COLORS['accent_emerald']}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glowViolet" cx="90%" cy="15%" r="40%">
      <stop offset="0%" stop-color="{COLORS['accent_violet']}" stop-opacity="0.10"/>
      <stop offset="100%" stop-color="{COLORS['accent_violet']}" stop-opacity="0"/>
    </radialGradient>

    <!-- Bar chart gradients -->
    <linearGradient id="barGradient" x1="0" y1="1" x2="0" y2="0">
      <stop offset="0%" stop-color="{COLORS['accent_cyan']}" stop-opacity="0.6"/>
      <stop offset="100%" stop-color="{COLORS['accent_cyan']}" stop-opacity="1"/>
    </linearGradient>
    <linearGradient id="emeraldGradient" x1="0" y1="1" x2="0" y2="0">
      <stop offset="0%" stop-color="{COLORS['accent_emerald']}" stop-opacity="0.6"/>
      <stop offset="100%" stop-color="{COLORS['accent_emerald']}" stop-opacity="1"/>
    </linearGradient>
    <linearGradient id="violetGradient" x1="0" y1="1" x2="0" y2="0">
      <stop offset="0%" stop-color="{COLORS['accent_violet']}" stop-opacity="0.6"/>
      <stop offset="100%" stop-color="{COLORS['accent_violet']}" stop-opacity="1"/>
    </linearGradient>


    <style>
      .title {{ font-family: 'SF Pro Display', system-ui, -apple-system, sans-serif; font-size: 42px; font-weight: 700; fill: {COLORS['text_primary']}; }}
      .subtitle {{ font-family: 'SF Pro Display', system-ui, -apple-system, sans-serif; font-size: 18px; font-weight: 500; fill: {COLORS['text_secondary']}; }}
      .badge {{ font-family: 'SF Pro Display', system-ui, -apple-system, sans-serif; font-size: 13px; font-weight: 700; fill: {COLORS['bg_dark']}; text-transform: uppercase; letter-spacing: 0.5px; }}
      .sectionTitle {{ font-family: 'SF Pro Display', system-ui, -apple-system, sans-serif; font-size: 14px; font-weight: 600; fill: {COLORS['text_secondary']}; text-transform: uppercase; letter-spacing: 1px; }}
      .statLabel {{ font-family: 'SF Pro Display', system-ui, -apple-system, sans-serif; font-size: 12px; font-weight: 500; fill: {COLORS['text_muted']}; }}
      .statValue {{ font-family: 'SF Pro Display', system-ui, -apple-system, sans-serif; font-size: 32px; font-weight: 700; fill: {COLORS['text_primary']}; }}
      .chartTitle {{ font-family: 'SF Pro Display', system-ui, -apple-system, sans-serif; font-size: 13px; font-weight: 600; fill: {COLORS['text_secondary']}; }}
      .axisLabel {{ font-family: 'SF Pro Text', system-ui, -apple-system, sans-serif; font-size: 10px; font-weight: 500; fill: {COLORS['text_muted']}; }}
      .modelName {{ font-family: 'SF Pro Text', system-ui, -apple-system, sans-serif; font-size: 13px; font-weight: 500; fill: {COLORS['text_primary']}; }}
      .modelCount {{ font-family: 'SF Mono', ui-monospace, monospace; font-size: 12px; font-weight: 600; fill: {COLORS['accent_emerald']}; }}
      .footer {{ font-family: 'SF Mono', ui-monospace, monospace; font-size: 11px; font-weight: 500; fill: {COLORS['text_muted']}; }}
      .bodyMuted {{ font-family: 'SF Pro Text', system-ui, -apple-system, sans-serif; font-size: 13px; fill: {COLORS['text_muted']}; }}
    </style>
  </defs>

  <!-- Background -->
  <rect width="{W}" height="{H}" fill="url(#bgGradient)"/>
  <rect width="{W}" height="{H}" fill="url(#glowCyan)"/>
  <rect width="{W}" height="{H}" fill="url(#glowEmerald)"/>
  <rect width="{W}" height="{H}" fill="url(#glowViolet)"/>

  <!-- Main card container -->
  <rect x="{pad}" y="{pad}" width="{W - pad * 2}" height="{H - pad * 2}" rx="24" fill="{COLORS['surface']}" fill-opacity="0.3" stroke="{COLORS['border']}" stroke-opacity="0.3"/>

  <!-- Header -->
  <g transform="translate({pad + 32}, {pad + 48})">
    <text class="title" x="0" y="0">Your Year With Chat</text>
    <text class="subtitle" x="0" y="32">{year_label} Wrapped</text>
  </g>


  <!-- Stats Row -->
  <g transform="translate({pad + 32}, 150)">
    {_stat_card(0, 0, 250, 90, highlights[0][0], highlights[0][1], highlights[0][2])}
    {_stat_card(266, 0, 250, 90, highlights[1][0], highlights[1][1], highlights[1][2])}
    {_stat_card(532, 0, 250, 90, highlights[2][0], highlights[2][1], highlights[2][2])}
    {_stat_card(798, 0, 250, 90, highlights[3][0], highlights[3][1], highlights[3][2])}
  </g>

  <!-- Heatmap Section -->
  <text class="sectionTitle" x="{pad + 32}" y="268">Activity Heatmap</text>
  <text class="axisLabel" x="{W - pad - 32}" y="268" text-anchor="end">{start.strftime('%b %d')} - {end.strftime('%b %d, %Y')}</text>
  {''.join(month_labels_svg)}
  {''.join(weekday_svg)}
  {''.join(heat_rects)}
  {''.join(legend)}

  <!-- Models Section -->
  <text class="sectionTitle" x="{pad + 32}" y="490">Top Models</text>
  {_models_panel_svg(x=pad + 32, y=490, w=W - pad * 2 - 64, items=model_items, max_items=10)}

  <!-- Charts Section -->
  <g transform="translate({pad + 32}, 680)">
    <text class="sectionTitle" x="0" y="0">Activity Breakdown</text>
  </g>
  <g>
    {_mini_bar_chart(x=pad + 32, y=700, width=340, height=110, title="By Month", labels=month_chart_labels, values=month_values, gradient_id="barGradient", label_mode="months")}
    {_mini_bar_chart(x=pad + 400, y=700, width=280, height=110, title="By Weekday", labels=weekday_chart_labels, values=weekday_values, gradient_id="violetGradient", label_mode="sparse")}
    {_hour_chart_svg(x=pad + 708, y=700, width=396, height=110, values=hour_values)}
  </g>

  <!-- Footer -->
  <text class="footer" x="{W // 2}" y="{H - 32}" text-anchor="middle">Generated with YYWC  •  Privacy-first  •  Offline analysis</text>
</svg>
"""
