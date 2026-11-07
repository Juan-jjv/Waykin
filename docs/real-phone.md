# Real phone over HTTPS

Geolocation and WebCrypto need a secure context, so the phone must load the app over `https://`.

1. Install `cloudflared` (preferred) or `ngrok` on the demo laptop.
2. Start `make demo` in one terminal, then `make tunnel` in another (`cloudflared tunnel --url http://localhost:8000`).
   `make tunnel` refuses to run with `EXPOSURE_SOURCE=eps` unless `ALLOW_PUBLIC_EPS=1` (team lead only).
3. Open the printed `https://….trycloudflare.com` URL on the phone; allow location.
4. FastAPI serves the built frontend, so it's one origin: the relay uses `wss://` on the same host.
5. Start a walk on the phone, open the share link on the laptop (family view).
6. If the tunnel drops, re-run `make tunnel`: the URL changes, so re-share the link.
7. Test with C1 before H44. C4 and S2 decide at H44 whether the live demo includes this segment.
