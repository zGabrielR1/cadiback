"""Fetch real official cover art for each catalog game.

Reads probes/provider-demos.json, visits each publisher's official game
page, extracts its og:image, downloads it into games/ and
web/public/games/, and records the local path in the JSON's "cover" field.
Titles that fail keep the generated SVG fallback.
"""

import json
import os
import re
import shutil
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "probes", "provider-demos.json")

PP = "https://www.pragmaticplay.com/en/games/{slug}/"
PP_SLUG = {
    "pp:gates-of-olympus": "gates-of-olympus",
    "pp:sweet-bonanza": "sweet-bonanza",
    "pp:sugar-rush": "sugar-rush",
    "pp:big-bass-bonanza": "big-bass-bonanza",
    "pp:starlight-princess": "starlight-princess",
    "pp:dog-house-megaways": "the-dog-house-megaways",
    "pp:wolf-gold": "wolf-gold",
    "pp:fruit-party": "fruit-party",
    "pp:big-bass-splash": "big-bass-splash",
    "pp:cleocatra": "cleocatra",
    "pp:wild-west-gold": "wild-west-gold",
    "pp:spaceman": "spaceman",
    "pp:roulette": "roulette",
    "pp:blackjack": "multihand-blackjack",
    "pp:baccarat": "baccarat",
}
PAGES = {
    "spribe:aviator": "https://spribe.co/games/aviator",
    "hs:rip-city-dice": "https://www.hacksawgaming.com/games/rip-city",
    "pgo:book-of-dead": "https://playngo.com/games/book-of-dead",
    "ev:lightning-roulette": "https://games.evolution.com/live-casino/live-roulette/lightning-roulette/",
    "ev:crazy-time": "https://games.evolution.com/live-casino/game-shows/crazy-time/",
    "pg:fortune-tiger": "https://www.pgsoft.com/en/games/110/",
    "pg:mahjong-ways": "https://www.pgsoft.com/en/games/50/",
}
for gid, slug in PP_SLUG.items():
    PAGES[gid] = PP.format(slug=slug)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


EV_THUMBNAIL_KEY = {
    "ev:lightning-roulette": "lightning_roulette",
    "ev:crazy-time": "crazy_time",
}


def pg_first_image(html_bytes: bytes, page: str) -> str | None:
    text = html_bytes.decode("utf-8", "ignore")
    m = re.search(r'"(/uploads/Games/Images/[^"]+\.(?:png|jpg|webp))"', text)
    if m:
        from urllib.parse import urlparse

        p = urlparse(page)
        return f"{p.scheme}://{p.netloc}{m.group(1)}"
    return None


def ev_thumbnail(html_bytes: bytes, key: str) -> str | None:
    text = html_bytes.decode("utf-8", "ignore")
    pat = re.compile(r"(https?://[^\"' ]*" + re.escape(key) + r"[^\"' ]*(?:web_imagery|thumbnail)[^\"' ]*1000x563[^\"' ]*\.jpg)")
    m = pat.search(text)
    if m:
        return m.group(1)
    return None


def og_image(html_bytes: bytes) -> str | None:
    text = html_bytes.decode("utf-8", "ignore")
    m = re.search(r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)', text)
    if not m:
        m = re.search(r'content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']', text)
    if not m:
        m = re.search(r'name=["\']twitter:image["\'][^>]*content=["\']([^"\']+)', text)
    return m.group(1) if m else None


def ext_of(content_type: str, url: str) -> str:
    path = url.split("?")[0].lower()
    for ext in (".webp", ".png", ".jpg", ".jpeg", ".gif"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    ct = content_type.lower()
    if "webp" in ct:
        return ".webp"
    if "png" in ct:
        return ".png"
    if "gif" in ct:
        return ".gif"
    return ".jpg"


def slug(game_id: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in game_id).strip("-")


def main() -> int:
    with open(SRC, encoding="utf-8") as f:
        data = json.load(f)
    out_root = os.path.join(ROOT, "games")
    out_web = os.path.join(ROOT, "web", "public", "games")
    os.makedirs(out_root, exist_ok=True)
    os.makedirs(out_web, exist_ok=True)
    ok, fail = 0, []
    for g in data["demos"]:
        page = PAGES.get(g["game_id"])
        if not page:
            fail.append((g["game_id"], "no page mapping"))
            continue
        try:
            html_bytes = fetch(page)
            if g["game_id"] in EV_THUMBNAIL_KEY:
                img_url = ev_thumbnail(html_bytes, EV_THUMBNAIL_KEY[g["game_id"]])
            elif g["game_id"].startswith("pg:"):
                img_url = pg_first_image(html_bytes, page)
            else:
                img_url = None
            if not img_url:
                img_url = og_image(html_bytes)
            if not img_url:
                fail.append((g["game_id"], "no og:image"))
                continue
            from urllib.parse import quote, urlparse

            if img_url.startswith("//"):
                img_url = "https:" + img_url
            elif img_url.startswith("/"):
                p = urlparse(page)
                img_url = f"{p.scheme}://{p.netloc}{img_url}"
            p = urlparse(img_url)
            img_url = f"{p.scheme}://{p.netloc}{quote(p.path)}" + (f"?{p.query}" if p.query else "")
            req = urllib.request.Request(img_url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                img = r.read()
                ext = ext_of(r.headers.get("Content-Type", ""), img_url)
            name = slug(g["game_id"]) + ext
            with open(os.path.join(out_root, name), "wb") as f:
                f.write(img)
            shutil.copyfile(os.path.join(out_root, name), os.path.join(out_web, name))
            g["cover"] = f"/games/{name}"
            print(f"OK  {g['game_id']} -> {name} ({len(img)}B)")
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append((g["game_id"], str(e)[:80]))
            print(f"FAIL {g['game_id']}: {e}")
    with open(SRC, "w", encoding="utf-8", newline="") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\n{ok} ok, {len(fail)} failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
