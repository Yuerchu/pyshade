## Why PyShade

PyShade compiles **Pydantic component DTOs into shadcn/ui React** and runs the result on the
system WebView — no bundled Chromium, no TCP port, no Node on your machine.

- **Compile-time errors.** Pages are plain Python classes; invalid props, dead references and
  type mismatches fail your build, not your users.
- **Ownership is explicit.** Every prop has exactly one owner: server value, client expression,
  controlled `ClientVal`, `ServerState` field, or build-time constant.
- **One command to ship.** `pyshade init` + `pyshade package` produce a standalone installer
  (NSIS / DMG / DEB) with an embedded CPython — around 27 MB on Windows.

## How this site is built

This documentation is a PyShade app. Every component page below is compiled from the same
Pydantic models the framework ships, and every live demo is real generated code. Server-driven
demos are simulated in JavaScript on this static site — run `pyshade dev docs_site.app:app`
locally for the real Python backend.

## Where to go next

Use the buttons above: **Quickstart** for your first app, **Components** for the full
reference with live demos and props tables.
