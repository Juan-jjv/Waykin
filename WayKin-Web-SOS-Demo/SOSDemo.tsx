import { useEffect, useRef, useState } from "react";

type Clip = { id: string; name: string; createdAt: string; blobUrl: string; duration: number };

/** Browser-only demo: records from an explicit click and stores clips in this tab's memory. */
export function SOSDemo() {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [clips, setClips] = useState<Clip[]>([]);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const startedRef = useRef(0);

  useEffect(() => () => {
    recorderRef.current?.stop();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    clips.forEach((clip) => URL.revokeObjectURL(clip.blobUrl));
  }, []);

  useEffect(() => {
    if (!recording) return;
    const timer = window.setInterval(() => setSeconds(Math.floor((Date.now() - startedRef.current) / 1000)), 250);
    return () => window.clearInterval(timer);
  }, [recording]);

  async function start() {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      alert("This browser does not support audio recording. Try a recent Chrome, Edge, or Safari over HTTPS or localhost.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recorderRef.current = recorder;
      startedRef.current = Date.now();
      setSeconds(0);
      recorder.ondataavailable = (event) => { if (event.data.size) chunksRef.current.push(event.data); };
      recorder.onstop = () => {
        const duration = Math.max(1, Math.round((Date.now() - startedRef.current) / 1000));
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        const clip: Clip = { id: crypto.randomUUID(), name: `SOS recording ${new Date().toLocaleTimeString()}`,
          createdAt: new Date().toISOString(), blobUrl: URL.createObjectURL(blob), duration };
        setClips((current) => [clip, ...current]);
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        setRecording(false);
      };
      recorder.start(250);
      setRecording(true);
    } catch (error) {
      alert(error instanceof Error ? `Microphone could not start: ${error.message}` : "Microphone permission was not granted.");
    }
  }

  function stop() {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }

  function remove(clip: Clip) {
    URL.revokeObjectURL(clip.blobUrl);
    setClips((current) => current.filter((item) => item.id !== clip.id));
  }

  return <main className="sos-demo">
    <header><span className="sos-mark">W</span><div><strong>WayKin SOS</strong><small>Audio demo</small></div><span className="demo-pill">DEMO</span></header>
    <section className="sos-intro"><p className="eyebrow">TRUSTED CONTACTS</p><h1>A voice can help tell the story.</h1>
      <p>Record a short SOS audio clip. In this demo, it appears immediately in the simulated parent inbox below.</p></section>
    <section className={`record-card ${recording ? "is-recording" : ""}`} aria-live="polite">
      <div className="mic-orb">{recording ? <span className="pulse-dot" /> : "🎙"}</div>
      <h2>{recording ? "Recording in progress" : "Ready when you are"}</h2>
      <p>{recording ? `Keep speaking. ${formatTime(seconds)}` : "Tap start and allow microphone access when asked."}</p>
      {recording ? <button className="stop-button" onClick={stop}><span /> Stop and save</button>
        : <button className="start-button" onClick={() => void start()}>Start SOS recording</button>}
      <small className="privacy-note">Recording starts only after you tap. Audio stays in this browser tab; nothing is uploaded.</small>
    </section>
    <section className="inbox"><div className="inbox-title"><div><p className="eyebrow">PARENT VIEW · SIMULATED</p><h2>Recent SOS recordings</h2></div><span className="count">{clips.length}</span></div>
      {!clips.length ? <div className="empty"><span>♪</span><p>No recordings yet</p><small>Finish a recording to see how it could appear to a trusted contact.</small></div> :
        <ul>{clips.map((clip) => <li key={clip.id}><div className="clip-icon">♪</div><div className="clip-details"><strong>{clip.name}</strong><small>{new Date(clip.createdAt).toLocaleString()} · {formatTime(clip.duration)}</small><audio controls preload="metadata" src={clip.blobUrl}>Audio playback unavailable.</audio></div><button className="delete" onClick={() => remove(clip)} aria-label="Delete recording">×</button></li>)}</ul>}
    </section>
    <footer>Concept demo only · Not connected to a real parent account or emergency service</footer>
  </main>;
}

function formatTime(total: number) { return `${Math.floor(total / 60).toString().padStart(2, "0")}:${(total % 60).toString().padStart(2, "0")}`; }
