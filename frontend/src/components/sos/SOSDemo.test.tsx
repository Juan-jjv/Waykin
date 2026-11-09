import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SOSDemo } from "./SOSDemo";

/** A stand-in MediaRecorder: emits one chunk and fires onstop when stopped. */
class FakeRecorder {
  static isTypeSupported = () => true;
  state = "inactive";
  mimeType = "audio/webm";
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  start() { this.state = "recording"; }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["x"], { type: "audio/webm" }) });
    this.onstop?.();
  }
}

// localhost counts as a secure page in browsers; the test environment doesn't, so stand in for it.
beforeEach(() => vi.stubGlobal("isSecureContext", true));
afterEach(() => vi.unstubAllGlobals());

describe("SOS audio demo", () => {
  it("asks for the microphone only after a tap, then lists the clip in the simulated inbox", async () => {
    const stopTrack = vi.fn();
    const getUserMedia = vi.fn().mockResolvedValue({ getTracks: () => [{ stop: stopTrack }] });
    vi.stubGlobal("MediaRecorder", FakeRecorder);
    Object.defineProperty(navigator, "mediaDevices", { value: { getUserMedia }, configurable: true });
    URL.createObjectURL = vi.fn(() => "blob:clip");
    URL.revokeObjectURL = vi.fn();

    render(<SOSDemo />);
    expect(getUserMedia).not.toHaveBeenCalled();
    expect(screen.getByText("No recordings yet")).toBeTruthy();

    await act(async () => { fireEvent.click(screen.getByText("Start SOS recording")); });
    expect(getUserMedia).toHaveBeenCalledWith({ audio: true });
    expect(screen.getByText("Recording in progress")).toBeTruthy();

    fireEvent.click(screen.getByText(/Stop and save/));
    await waitFor(() => expect(screen.getByText(/^SOS recording /)).toBeTruthy());
    expect(stopTrack).toHaveBeenCalled();                     // the microphone is released after saving

    fireEvent.click(screen.getByLabelText("Delete recording"));
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:clip");
    expect(screen.getByText("No recordings yet")).toBeTruthy();
  });

  it("explains a blocked microphone on the page instead of failing silently", async () => {
    const blocked = Object.assign(new Error("Permission denied"), { name: "NotAllowedError" });
    Object.defineProperty(navigator, "mediaDevices", { value: { getUserMedia: vi.fn().mockRejectedValue(blocked) }, configurable: true });
    vi.stubGlobal("MediaRecorder", FakeRecorder);
    render(<SOSDemo />);
    await act(async () => { fireEvent.click(screen.getByText("Start SOS recording")); });
    expect(screen.getByRole("alert").textContent).toMatch(/blocked, so the browser did not ask/);
    expect(screen.getByText("Start SOS recording")).toBeTruthy();
  });

  it("explains that microphones need a secure page", async () => {
    vi.stubGlobal("isSecureContext", false);
    render(<SOSDemo />);
    await act(async () => { fireEvent.click(screen.getByText("Start SOS recording")); });
    expect(screen.getByRole("alert").textContent).toMatch(/only work on secure pages/);
  });
});
