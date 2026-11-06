"""Read-only deployment checks plus an OAuth authorization start (no login)."""
import json
import urllib.request
import urllib.error
from urllib.parse import urlparse, parse_qs


def check(host):
    with urllib.request.urlopen(host, timeout=45) as response:
        assert response.status == 200
    try:
        urllib.request.urlopen(host + "/api/player", timeout=45)
        raise AssertionError("Guest player route must require authentication")
    except urllib.error.HTTPError as error:
        assert error.code == 401, error.code
    for path in ("/api/betterauth/providers", "/api/health"):
        with urllib.request.urlopen(host + path, timeout=45) as response:
            data = json.load(response)
            print(host, path, response.status,
                  data if path.endswith("providers") else data.get("betterauth"))
    payload = {"provider": "twitter", "callbackURL": host + "/api/betterauth/bridge?return=" + host}
    request = urllib.request.Request(host + "/api/betterauth/sign-in/social",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "Origin": host})
    with urllib.request.urlopen(request, timeout=45) as response:
        data = json.load(response)
        url = urlparse(data["url"])
        params = parse_qs(url.query)
        print("OAuth start:", response.status, url.netloc, {
            name: params.get(name) for name in ("redirect_uri", "scope", "code_challenge_method")})
        assert url.netloc == "x.com"
        assert params["redirect_uri"] == [host + "/api/betterauth/callback/twitter"]
        assert set(params["scope"][0].split()) == {"tweet.read", "users.read", "offline.access"}
        assert params["code_challenge_method"] == ["S256"]


if __name__ == "__main__":
    for host in ("https://cadiback.onrender.com", "https://cadiback-web.vercel.app"):
        check(host)
