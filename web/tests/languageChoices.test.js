import test from "node:test";
import assert from "node:assert/strict";
import { LANGUAGE_CHOICES, EXPERIMENTAL_LANGUAGE_NOTICE } from "../src/languageChoices.js";
test("English is default and both additional languages are labelled experimental", () => {
  assert.deepEqual(LANGUAGE_CHOICES[0], ["english", "English (default)"]);
  assert.equal(LANGUAGE_CHOICES.length, 3);
  assert.ok(LANGUAGE_CHOICES.slice(1).every(([, label]) => label.includes("Experimental")));
  assert.match(EXPERIMENTAL_LANGUAGE_NOTICE, /try English/);
  assert.match(EXPERIMENTAL_LANGUAGE_NOTICE, /original language/);
});
