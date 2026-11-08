# WayKin Web SOS Audio Demo

Drop-in React feature for demonstrating the basic SOS audio idea without changing the team repo. It asks for microphone permission only after the user presses **Start SOS recording**, records until Stop is pressed, and shows playback in a simulated parent inbox.

## Run it as a standalone demo

1. Create a Vite React TypeScript app: `npm create vite@latest waykin-sos-demo -- --template react-ts`
2. In that app's `src`, copy `SOSDemo.tsx` and `sos-demo.css` from this folder.
3. Replace `src/App.tsx` with:

```tsx
import { SOSDemo } from "./SOSDemo";
import "./sos-demo.css";
export default function App() { return <SOSDemo />; }
```

4. Run `npm install` then `npm run dev` and open Vite's URL. Microphone access works on `localhost` or HTTPS; approve the browser prompt.

## Add this feature to the WayKin app

These steps are for a teammate integrating the component into the full WayKin repository. The demo folder itself is intentionally standalone; do not replace WayKin's `App.tsx` or global stylesheet.

1. Copy `SOSDemo.tsx` and `sos-demo.css` into `frontend/src/components/sos/` in the WayKin repository.
2. Add a small page at `frontend/src/pages/SOSDemoPage.tsx`:

   ```tsx
   import { SOSDemo } from "../components/sos/SOSDemo";
   import "../components/sos/sos-demo.css";

   export function SOSDemoPage() {
     return <SOSDemo />;
   }
   ```

3. In `frontend/src/App.tsx`, import `SOSDemoPage` and add a temporary route inside the existing `<Routes>`:

   ```tsx
   <Route path="/sos-demo" element={<SOSDemoPage />} />
   ```

   Keep all existing imports/routes. Visit `/sos-demo` while the WayKin frontend is running.
4. Run `npm run build` in `frontend` to catch TypeScript or bundling issues. On Windows PowerShell where `npm.ps1` is blocked, use `& "C:\Program Files\nodejs\npm.cmd" run build`.
5. For a real-phone browser demo, serve the frontend over HTTPS (localhost is considered secure only on the same device). Tap **Start SOS recording** and allow microphone access. Browser permission is requested only after that user action.

### What this integration demonstrates

It captures real microphone audio in the browser, stops when the user taps Stop, and renders an audio player under a **simulated parent inbox**. No backend endpoint is called. The clip exists only in browser memory and is lost on refresh; it is not sent to the user's actual parent. To make sharing real, the team must add authenticated upload/storage, link a recording to the user's trusted-contact relationship, authorize parent playback, and add notification/retention/deletion behavior. Do not describe the browser demo as lock-screen recording, Siri activation, or an emergency service.

## Demo limits

This is real browser microphone capture, but the “parent inbox” is simulated in the same browser session. Audio is held in memory as a blob URL and disappears on refresh. No upload, account auth, notifications, lock-screen recording, Siri, or emergency dispatch is implemented. Present those as future native/backend work, not as working demo capabilities. Browser recording requires an explicit tap and browser permission.
