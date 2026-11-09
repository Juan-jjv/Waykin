### ⚠️ DISCLAIMER: COMMIT HISTORY DOES NOT REFLECT WHO DID THE WORK

**OUR WHOLE TEAM CODED TOGETHER IN ONE VS CODE LIVE SHARE SESSION. BECAUSE OF THAT, ONLY ONE PERSON (THE SESSION HOST) MADE GIT COMMITS. THE COMMIT HISTORY AND GITHUB CONTRIBUTOR STATS ARE NOT REFLECTIVE OF THE WORK EACH TEAMMATE DID.** EVERY TEAMMATE WROTE CODE FOR THIS PROJECT. 

# WayKin

## Run it

You need Python 3.11+ and Node 20+.

1. Clone it (over 1 GB, since the Edmonton data is included):
   ```bash
   git clone https://github.com/Juan-jjv/Waykin.git
   cd Waykin
   ```

2. Install:
   ```bash
   python -m venv backend/.venv
   backend\.venv\Scripts\activate        # Windows
   source backend/.venv/bin/activate     # Mac/Linux
   pip install -e "backend[dev,build]"
   cd frontend
   npm ci
   npm run build
   cd ..
   ```

3. Unpack the data and turn on the real incident reports:
   ```bash
   cd backend
   python -m scripts.data.snapshot restore
   python -c "open('.env', 'w').write('EXPOSURE_SOURCE=eps')"
   ```

4. Start it:
   ```bash
   uvicorn waykin.main:app --port 8000
   ```

5. Open http://localhost:8000 and sign in as `demo`, password `waykin-demo`.

Next time, just activate the venv (step 2), `cd backend`, and do step 4.
