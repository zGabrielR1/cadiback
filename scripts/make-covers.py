"""Generate per-game cover art (SVG) for the casino lobby.

Replaces emoji tiles with title-styled cover images, mimicking real
betting-site game thumbnails. Output: /games/*.svg at repo root (fallback
server) and web/public/games/*.svg (Next export).
"""

import json
import os
import shutil
import html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "probes", "provider-demos.json")

PROVIDER_COLORS = {
    "pragmatic_play": ("#451a03", "#f59e0b", "#fde68a"),
    "spribe": ("#052e16", "#22c55e", "#bbf7d0"),
    "hacksaw": ("#3b0764", "#a855f7", "#e9d5ff"),
    "playngo": ("#450a0a", "#ef4444", "#fecaca"),
    "evolution": ("#082f49", "#0ea5e9", "#bae6fd"),
    "pg_soft": ("#422006", "#eab308", "#fef08a"),
    "demo_studio": ("#14532d", "#10b981", "#a7f3d0"),
}
DEFAULT_COLORS = ("#27272a", "#71717a", "#d4d4d8")

DEMO_GAMES = [
    {"game_id": "demo:neon-gems", "provider": "demo_studio", "title": "Neon Gems"},
    {"game_id": "demo:fortune-ledger", "provider": "demo_studio", "title": "Fortune Ledger"},
    {"game_id": "demo:royale-roulette", "provider": "demo_studio", "title": "Royale Roulette"},
    {"game_id": "demo:crash-nitro", "provider": "demo_studio", "title": "Crash Nitro"},
    {"game_id": "demo:plinko-drops", "provider": "demo_studio", "title": "Plinko Drops"},
    {"game_id": "demo:minas", "provider": "demo_studio", "title": "Minas"},
    {"game_id": "demo:dados", "provider": "demo_studio", "title": "Dados Relâmpago"},
    {"game_id": "demo:keno", "provider": "demo_studio", "title": "Keno Relâmpago"},
]


def slug(game_id: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in game_id).strip("-")


def cover(game: dict) -> str:
    c1, c2, c3 = PROVIDER_COLORS.get(game.get("provider", ""), DEFAULT_COLORS)
    title = html.escape(game["title"])
    words = title.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if len(trial) > 12 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    tspans = "".join(
        f'<tspan x="200" dy="{0 if i == 0 else 44}">{line}</tspan>'
        for i, line in enumerate(lines)
    )
    start_y = 200 - (len(lines) - 1) * 22
    provider = html.escape((game.get("provider") or "").replace("_", " ").upper())
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{c1}"/>
      <stop offset="0.6" stop-color="{c2}"/>
      <stop offset="1" stop-color="{c3}"/>
    </linearGradient>
  </defs>
  <rect width="400" height="300" fill="url(#g)"/>
  <circle cx="330" cy="60" r="90" fill="#ffffff" opacity="0.08"/>
  <circle cx="60" cy="250" r="70" fill="#000000" opacity="0.12"/>
  <text y="{start_y}" text-anchor="middle" font-family="Arial Black, Arial, sans-serif" font-weight="900" font-size="38" fill="#ffffff" stroke="{c1}" stroke-width="1.5" paint-order="stroke">{tspans}</text>
  <text x="200" y="272" text-anchor="middle" font-family="Arial, sans-serif" font-weight="700" font-size="13" letter-spacing="3" fill="#ffffff" opacity="0.85">{provider}</text>
</svg>
"""


def main() -> None:
    with open(SRC, encoding="utf-8") as f:
        games = json.load(f)["demos"] + DEMO_GAMES
    out_root = os.path.join(ROOT, "games")
    out_web = os.path.join(ROOT, "web", "public", "games")
    for out in (out_root, out_web):
        os.makedirs(out, exist_ok=True)
    for g in games:
        name = slug(g["game_id"]) + ".svg"
        data = cover(g)
        with open(os.path.join(out_root, name), "w", encoding="utf-8", newline="") as f:
            f.write(data)
        shutil.copyfile(os.path.join(out_root, name), os.path.join(out_web, name))
    print(f"wrote {len(games)} covers to games/ and web/public/games/")


if __name__ == "__main__":
    main()
