import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { STATIONS } from "../map/stations";
import { StationList } from "./StationList";

describe("StationList", () => {
  it("lists the nearest stations to the start first and routes to the one tapped", () => {
    const onRoute = vi.fn();
    const nearSouthwest = { lat: 53.436, lon: -113.61 };
    render(<StationList from={nearSouthwest} note={null} onRoute={onRoute} />);

    const names = screen.getAllByRole("button").map((button) => button.textContent ?? "");
    expect(names[1]).toMatch(/^Southwest Division/);
    expect(names).toHaveLength(4);

    fireEvent.click(screen.getByText("Show all 7"));
    expect(screen.getAllByRole("button")).toHaveLength(STATIONS.length + 1);

    fireEvent.click(screen.getByText("Southwest Division"));
    expect(onRoute).toHaveBeenCalledWith(expect.objectContaining({ id: "southwest" }));
  });
});
