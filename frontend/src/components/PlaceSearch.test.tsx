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
      { key: "here", label: strings.yourLocation, pick: () => here },
      { key: "maya", label: "Maya", hint: "Near Victoria Trail NW", pick: () => ({ label: "Maya", point: { lat: 53.6, lon: -113.38 } }) },
    ]);
    fireEvent.focus(input);
    expect(screen.getByText("Near Victoria Trail NW")).toBeTruthy();
    expect(screen.getByText("Maya")).toBeTruthy();
    fireEvent.click(screen.getByText(strings.yourLocation));
    await waitFor(() => expect(onSelect).toHaveBeenCalledWith(here));
  });

  it("a tap still lands when the field blurs before the finger lifts", async () => {
    const here = { label: strings.yourLocation, point: { lat: 53.54, lon: -113.5 } };
    const { onSelect, input } = setup([{ key: "here", label: strings.yourLocation, pick: () => here }]);
    fireEvent.focus(input);
    const option = screen.getByText(strings.yourLocation);
    fireEvent.pointerDown(option);
    fireEvent.blur(input);
    await new Promise((resolve) => setTimeout(resolve, 250));
    fireEvent.click(screen.getByText(strings.yourLocation));
    await waitFor(() => expect(onSelect).toHaveBeenCalledWith(here));
  });

  it("an outside update doesn't shut the open list", () => {
    const quick = [{ key: "here", label: strings.yourLocation, pick: () => ({ label: "x", point: { lat: 53.5, lon: -113.5 } }) }];
    const { rerender } = render(
      <PlaceSearch label="End" placeholder="Search for a destination" value={null} bbox={BBOX} onSelect={vi.fn()} quick={quick} />,
    );
    const input = screen.getByRole("combobox");
    input.focus();
    fireEvent.focus(input);
    expect(screen.getByRole("listbox")).toBeTruthy();
    rerender(<PlaceSearch label="End" placeholder="Search for a destination" value="Dropped pin" bbox={BBOX} onSelect={vi.fn()} quick={quick} />);
    expect(screen.getByRole("listbox")).toBeTruthy();
  });

  it("explains when the location can't be used", async () => {
    const { onSelect, input } = setup([
      { key: "here", label: strings.yourLocation, pick: () => Promise.reject(new Error(strings.locationDenied)) },
    ]);
    fireEvent.focus(input);
    fireEvent.click(screen.getByText(strings.yourLocation));
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
