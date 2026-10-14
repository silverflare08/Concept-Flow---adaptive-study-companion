import test from "node:test";
import assert from "node:assert/strict";
import { THEMES, themeId, isDarkTheme } from "../src/appearance.js";
test("seven distinct themes include neutral default and two dark palettes", () => {
  assert.equal(THEMES.length, 7);
  assert.equal(new Set(THEMES.map(theme => theme.id)).size, 7);
  assert.equal(THEMES.filter(theme => isDarkTheme(theme.id)).length, 2);
  assert.equal(themeId("charcoal"), "charcoal");
  assert.equal(themeId("midnight"), "midnight");
  assert.equal(themeId("unknown"), "neutral");
  assert.equal(themeId(undefined), "neutral");
});
