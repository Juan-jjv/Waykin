import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { strings } from "../copy/strings";
import { PlaceSearch, type QuickPlace } from "./PlaceSearch";

const BBOX = [-113.7, 53.3, -113.2, 53.7];

function setup(quick: QuickPlace[]) {
  const onSelect = vi.fn();
  render(<PlaceSearch label="Start" placeholder="Search for a start" value={null} bbox={BBOX} onSelect={onSelect} quick={quick} />);
  return { onSelect, input: screen.getByRole("combobox") };
}

describe("Start dropdown", () => {
  it("offers the quick choices on focus and picks one", async () => {
    const here = { label: strings.yourLocation, point: { lat: 53.54, lon: -113.5 } };
    const { onSelect, input } = setup([
      { key: "here", label: strings.yourLocation, hint: strings.yourLocationHint, pick: () => here },
      { key: "maya", label: "Maya", hint: "Near Victoria Trail NW", pick: () => ({ label: "Maya", point: { lat: 53.6, lon: -113.38 } }) },
    ]);
    fireEvent.focus(input);
    expect(screen.getByText(strings.yourLocationHint)).toBeTruthy();
    expect(screen.getByText("Maya")).toBeTruthy();
    fireEvent.mouseDown(screen.getByText(strings.yourLocation));
    await waitFor(() => expect(onSelect).toHaveBeenCalledWith(here));
  });

  it("explains when the location can't be used", async () => {
    const { onSelect, input } = setup([
      { key: "here", label: strings.yourLocation, pick: () => Promise.reject(new Error(strings.locationDenied)) },
    ]);
    fireEvent.focus(input);
    fireEvent.mouseDown(screen.getByText(strings.yourLocation));
    await waitFor(() => expect(screen.getByText(strings.locationDenied)).toBeTruthy());
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("keyboard: arrow down and Enter choose a quick option", async () => {
    const here = { label: strings.yourLocation, point: { lat: 53.54, lon: -113.5 } };
    const { onSelect, input } = setup([{ key: "here", label: strings.yourLocation, pick: () => here }]);
    fireEvent.focus(input);
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(onSelect).toHaveBeenCalledWith(here));
  });
});
