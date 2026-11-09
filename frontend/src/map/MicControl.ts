import type { IControl } from "maplibre-gl";
import { strings } from "../copy/strings";

const MIC_SVG = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
  stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
  <rect x="9" y="3" width="6" height="11" rx="3" />
  <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M9 21h6" />
</svg>`;

/** Map button under the zoom controls that records a voice message. The recording isn't kept or sent anywhere. */
export class MicControl implements IControl {
  private container: HTMLDivElement | null = null;
  private button: HTMLButtonElement | null = null;
  private recorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;

  onAdd() {
    const container = document.createElement("div");
    container.className = "maplibregl-ctrl maplibregl-ctrl-group wk-mic";
    const button = document.createElement("button");
    button.type = "button";
    button.innerHTML = MIC_SVG;
    button.addEventListener("click", () => void this.toggle());
    container.append(button);
    this.container = container;
    this.button = button;
    this.render();
    return container;
  }

  onRemove() {
    this.stop();
    this.container?.remove();
    this.container = this.button = null;
  }

  private async toggle() {
    if (this.recorder) {
      this.stop();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") return;
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.recorder = new MediaRecorder(this.stream);
      this.recorder.start();
    } catch {
      this.stop();
    }
    this.render();
  }

  private stop() {
    if (this.recorder?.state === "recording") this.recorder.stop();
    this.stream?.getTracks().forEach((track) => track.stop());
    this.recorder = this.stream = null;
    this.render();
  }

  private render() {
    if (!this.button) return;
    const on = this.recorder !== null;
    this.button.classList.toggle("recording", on);
    this.button.setAttribute("aria-pressed", String(on));
    const label = on ? strings.stopRecording : strings.recordMessage;
    this.button.setAttribute("aria-label", label);
    this.button.title = label;
  }
}
