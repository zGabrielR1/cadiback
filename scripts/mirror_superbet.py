"""Mirror the captured Superbet block-landing page with its assets.

Reads examples/superbet/live-jogos.html, downloads every absolute
src/href it references into examples/superbet/assets/<host>/<name>,
and rewrites the HTML into an offline copy at
examples/superbet/jogos.offline.html. The original fetch is kept at
examples/superbet/jogos.live.html.
"""

import os
import pathlib
import re
import urllib.parse
import urllib.request

TARGET = "https://superbet.bet.br/jogos"
OUT = pathlib.Path("examples/superbet")
SRC = OUT / "live-jogos.html"


def main() -> None:
    html = SRC.read_text(encoding="utf-8")
    urls = set()
    for m in re.finditer(r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)["\']', html):
        urls.add(m.group(1))
    mapping = {}
    for u in sorted(urls):
        p = urllib.parse.urlparse(u)
        name = os.path.basename(p.path.rstrip("/")) or "index"
        if "." not in name:
            name += ".bin"
        dest = OUT / "assets" / p.netloc / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            dest.write_bytes(data)
            mapping[u] = str(dest.relative_to(OUT)).replace("\\", "/")
            print("OK ", len(data), "B", u[:80])
        except Exception as exc:  # noqa: BLE001
            print("FAIL", u[:80], str(exc)[:60])
    for u, local in mapping.items():
        html = html.replace(u, local)
    SRC.rename(OUT / "jogos.live.html")
    (OUT / "jogos.offline.html").write_text(html, encoding="utf-8")
    print("mirrored", len(mapping), "assets; offline at examples/superbet/jogos.offline.html")


if __name__ == "__main__":
    main()
