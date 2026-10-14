import test from "node:test";
import assert from "node:assert/strict";
import { filterLibraryItems } from "../src/libraryFilters.js";

const chats = [{ id: "a", title: "Waves revision", course_name: "Physics", course_id: "physics", pinned: true },
  { id: "b", title: "BFS quiz", course_name: "Algorithms", course_id: "dsa", pinned: false }];

test("search matches chat titles or workspace names without changing order", () => {
  assert.deepEqual(filterLibraryItems(chats, { query: "  PHYSICS " }).map(item => item.id), ["a"]);
  assert.deepEqual(filterLibraryItems(chats, { query: "quiz" }).map(item => item.id), ["b"]);
  assert.deepEqual(filterLibraryItems(chats), chats);
});
test("workspace scope and pinned filter combine with search", () => {
  assert.deepEqual(filterLibraryItems(chats, { courseId: "dsa", pinnedOnly: true }), []);
  assert.deepEqual(filterLibraryItems(chats, { courseId: "physics", query: "waves", pinnedOnly: true }).map(item => item.id), ["a"]);
});
test("workspace search includes entries beyond the first eight", () => {
  const workspaces = Array.from({ length: 12 }, (_, number) => ({ id: number, name: `Course ${number}` }));
  assert.deepEqual(filterLibraryItems(workspaces, { query: "Course 11" }).map(item => item.id), [11]);
});
