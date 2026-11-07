import { expect, it } from "vitest";
import { buildShareLink } from "./relay";

it("puts the token and key only after #", () => {
  const link = buildShareLink("abc", "viewer-token", "KEY");
  const [before, after] = link.split("#");
  expect(before).toBe(`${location.origin}/f/abc`);
  expect(before).not.toContain("viewer-token");
  expect(new URLSearchParams(after).get("t")).toBe("viewer-token");
  expect(new URLSearchParams(after).get("k")).toBe("KEY");
});
