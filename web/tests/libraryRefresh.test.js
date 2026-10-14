import test from "node:test";
import assert from "node:assert/strict";
import { fetchLibraryUpdates } from "../src/libraryRefresh.js";

test("newly saved chats are returned without browser caching", async () => {
  const requests = [];
  const { updates, error } = await fetchLibraryUpdates("", async (url, options) => {
    requests.push(options);
    return { ok: true, json: async () => url.endsWith("history") ? { conversations: [{ id: "new-chat" }] } : { courses: [] } };
  });
  assert.equal(updates.conversations[0].id, "new-chat");
  assert.equal(error, "");
  assert.ok(requests.every(options => options.cache === "no-store" && options.signal));
});

test("a course endpoint failure does not freeze recent chats", async () => {
  const { updates, error } = await fetchLibraryUpdates("", async url => url.endsWith("history")
    ? { ok: true, json: async () => ({ conversations: [{ id: "latest" }] }) }
    : { ok: false });
  assert.equal(updates.conversations[0].id, "latest");
  assert.ok(!("courses" in updates));
  assert.match(error, /courses/);
});

test("failed history does not erase previously displayed conversations", async () => {
  const previous = { conversations: [{ id: "saved" }], courses: [] };
  const { updates, error } = await fetchLibraryUpdates("", async url => url.endsWith("history")
    ? { ok: false }
    : { ok: true, json: async () => ({ courses: [{ id: "course" }] }) });
  assert.deepEqual({ ...previous, ...updates }.conversations, previous.conversations);
  assert.match(error, /chat history/);
});
