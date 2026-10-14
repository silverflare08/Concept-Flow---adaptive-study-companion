import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

let server;
let RichStudyText;
let avatarModule;
let WelcomePage;
let DashboardPage;
test.before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: "custom", ssr: { external: ["react", "react-dom", "katex"] } });
  RichStudyText = (await server.ssrLoadModule("/src/RichStudyText.jsx")).default;
  avatarModule = await server.ssrLoadModule("/src/Avatar.jsx");
  WelcomePage = (await server.ssrLoadModule("/src/WelcomePage.jsx")).default;
  DashboardPage = (await server.ssrLoadModule("/src/DashboardPage.jsx")).default;
});
test.after(async () => { await server?.close(); });

test("five neutrally named avatars include two short-haired portraits and one animal", () => {
  assert.equal(avatarModule.AVATARS.length, 5);
  const male = avatarModule.AVATARS.filter(avatar => avatar.id.endsWith("-male"));
  assert.equal(male.length, 2);
  assert.equal(avatarModule.AVATARS.filter(avatar => avatar.id === "owl").length, 1);
  assert.ok(avatarModule.AVATARS.every(avatar => !/male|female/i.test(avatar.name)));
  const render = id => renderToStaticMarkup(React.createElement(avatarModule.default, { id }));
  assert.notEqual(render("scholar-male"), render("scholar"));
  assert.equal(render("unknown"), render("scholar"));
  assert.equal(render("thinker-male"), render("scholar-male"));
  assert.match(render("owl"), /<svg/);
});

test("welcome page reuses enlarged brain logo and retains auth slot and FAQs", () => {
  const html = renderToStaticMarkup(React.createElement(WelcomePage, null, React.createElement("form", { id: "signin" }, "Sign in")));
  assert.match(html, /lucide-brain-circuit/);
  assert.match(html, /sm:h-20 sm:w-20/);
  assert.match(html, /id="signin"/);
  assert.match(html, /id="faq"/);
  assert.match(html, /Illustrative preview/);
  assert.match(html, /Less confusion/);
  assert.match(html, /More clarity/);
  assert.match(html, /welcome-page/);
  assert.match(html, /font-brand/);
  assert.match(html, /welcome-wave/);
  assert.doesNotMatch(html, /Welcome navigation/);
});

test("dashboard preserves all eight tool buttons with background accent colors", () => {
  const html = renderToStaticMarkup(React.createElement(DashboardPage, { workspace: { name: "Study", source_count: 1 }, setPage: () => {} }));
  assert.equal((html.match(/feature-card/g) || []).length, 8);
  assert.equal((html.match(/--tool-accent:/g) || []).length, 8);
  assert.match(html, /lg:grid-cols-4/);
});

test("maths renders fractions and letter superscripts rather than raw commands", () => {
  const html = renderToStaticMarkup(React.createElement(RichStudyText, { text: "Complement y^c; PMF p_x(a).\n$$\\frac{1}{2} + x^2$$" }));
  assert.match(html, /<mfrac>/);
  assert.match(html, /<msup>/);
  assert.match(html, /<msub>/);
});

test("probability rows become a table and untrusted text remains escaped", () => {
  const html = renderToStaticMarkup(React.createElement(RichStudyText, { text: "| x | p(x) |\n|---|---|\n| 0 | 0.855 |\n| 1 | 0.140 |\n<img src=x onerror=alert(1)>" }));
  assert.match(html, /<table/);
  assert.match(html, /0\.855/);
  assert.ok(!html.includes("<img src=x"));
});

test("recording filenames are not misinterpreted as mathematical subscripts", () => {
  const filename = "MIT8_03SCF16_lec01_300k.mp4";
  const html = renderToStaticMarkup(React.createElement(RichStudyText, { text: `### ${filename}, 00:01` }));
  assert.ok(html.includes(filename));
  assert.ok(!html.includes("<msub>"));
});
