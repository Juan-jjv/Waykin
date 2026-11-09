# Real phone over HTTPS

Location sharing and encryption only work over `https://`, so a phone needs a tunnel to your laptop.

1. Install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/).
2. Start the app as in the README, then in a second terminal:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
3. Open the `https://….trycloudflare.com` address it prints on the phone and allow location.
4. Start a walk on the phone, and open its share link on the laptop to follow along.

If the tunnel drops, run it again. The address changes, so share the new link.
