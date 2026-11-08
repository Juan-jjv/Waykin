### ⚠️ DISCLAIMER: COMMIT HISTORY DOES NOT REFLECT WHO DID THE WORK

**OUR WHOLE TEAM CODED TOGETHER IN ONE VS CODE LIVE SHARE SESSION. BECAUSE OF THAT, ONLY ONE PERSON (THE SESSION HOST) MADE GIT COMMITS. THE COMMIT HISTORY AND GITHUB CONTRIBUTOR STATS ARE NOT REFLECTIVE OF THE WORK EACH TEAMMATE DID.** EVERY TEAMMATE WROTE CODE FOR THIS PROJECT. 

## Run the demo
Needs Python 3.11+ and Node 20+. Demo mode is on by default (set `DEMO_MODE=0` for anything that isn't a demo).

1. Install: `pip install -e "backend[dev,build]"` and `cd frontend && npm ci`.
2. Unpack the Edmonton data committed in `data-split/` (about a minute; again after any pull that changes it):
   `python -m scripts.data.snapshot restore` from `backend/`. See [data-split/README.md](data-split/README.md),
   including how to send newer EPS reports or map data.
3. Start the backend from `backend/` with `EXPOSURE_SOURCE=eps`, and the frontend with `npm run dev` in `frontend/`
   (or `npm run build` and use the backend alone on :8000).
4. Sign in as **`demo`**, password **`waykin-demo`**. The demo family's pins appear on the Plan map.
