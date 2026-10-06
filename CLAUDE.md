# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A static React prototype of **NeoMath.Darwin**, a canvas-first math-reasoning app for iPad. It implements exactly one worked example — the *Lost roots* derivation (`x(x − 1) = 0` → `x − 1 = 0` → `x = 1`) — as a design fixture. There is no kernel, no persistence, and no network layer; every mathematically meaningful result is precomputed in `src/data.ts`.

The authoritative design document is `NEOMATH_DARWIN_UI_SPEC.md` (Chinese, ~1200 lines). It is a *target* spec, not a report of what is built here — the prototype deliberately lags it. Spec section numbering is referenced by rule IDs in the code comments and in `AGENTS.md`. `Aizawa_Minato_refined.txt` is an unrelated roleplay prompt, not project material.

## Repo state — read before running anything

- **`index.html` and `.figma/make/site.json` do not exist.** `vite.config.ts` imports the latter directly at line 6, so Vite will not start until it is created. There is also no `package-lock.json` and no `node_modules` yet.
- `src/` was extracted from `src (1).zip`, which is still in the repo root; the two are byte-identical as of the extraction, so treat the zip as a stale duplicate rather than a second source of truth.
- `AGENTS.md` describes the Figma Make environment where the missing files are normally supplied and a dev server is already running on `$PORT` (default 8443) — neither holds in this checkout.

## Commands

```bash
npm install
npm run dev        # vite, port 8443 (overridable with PORT)
npm run build      # vite build
npm run preview
npm run format     # oxfmt
npx tsc --noEmit   # type check — there is no script, test runner, or linter
```

## Architecture

`src/main.tsx` → `src/App.tsx`, which owns all state and switches between two screens: `Documents` (document list) and the document workspace. There is no router, no context, and no state library — everything is `useState` in `App` and passed down as props.

```
App.tsx          session state: screen, view('canvas'|'steps'), selection, inspector
                 open/pinned, tool, zoom, grid, theme mode. Derives strongStep /
                 weakStep / selectedRel from the selection and hands them down.
data.ts          domain model + mock kernel. Exact rational arithmetic (Fr,
                 gcd-normalized), parseRational, steps[] each carrying an
                 evaluate(x) -> {left, right, holds}, relations, stateMeta.
ui.tsx           shared primitives: M (math text), Glyph, StatusLine, Chip,
                 toneText / toneTint maps.
CanvasView.tsx   spatial view: rows at fixed ROW=112 pitch, relation connectors,
                 and an SVG ink-stroke layer driven by pointer events.
StepsView.tsx    linear list view of the same steps.
Inspector.tsx    right panel, tabs Overview / Evidence / Details. Hosts the
                 Witness (automatic counterexample, with substitution), Probe
                 (manual `x` entry), and Review (repair options) pieces.
```

Data flow is one-directional: `data.ts` is the only source of truth, `App` holds selection, and leaf views are pure props renderers. `CanvasView` is the sole exception — it owns its ink strokes locally, since they are not part of the document model yet.

### Coupling points to know

- **Relation IDs are encoded arithmetically.** `RelId` is the literal union `12 | 23`, and the step→relation map is derived three separate ways: `relOfStep()` in `App.tsx`, an inline `((n - 1) * 10 + n) as RelId` in `StepsView.tsx`, and a hardcoded `[12, 23]` in `CanvasView.tsx`. Any change to step count or ordering must update all three.
- **Steps are 1-based in the UI, 0-based in the arrays** (`steps[rel.from - 1]`).
- `M` renders math text in `--font-math` and italicizes the variable by splitting the string on the literal `x`. Math strings written outside `M` will not get this treatment.
- `steps[].src` holds display strings with typographic characters (U+2212 minus), while `parseRational` normalizes `−`/`–` back to ASCII before parsing.

## The one hard product rule

Spec rule UX-04 ("状态诚实" — honest state) is enforced throughout, and it is the constraint most likely to be violated by a well-meaning change: **nothing may present demo data as a verified result.** Every kernel-dependent control is `disabled` with a `title` explaining why, the header carries a "Demo data" chip, `stateMeta` distinguishes `initial` / `lostSolution` / `tainted` rather than showing a success state, and `Probe` labels itself "Manual probe · does not replace the automatic witness". Do not wire these up to mock successes, and do not add green/equivalent styling that the fixture data doesn't support.

## Styling

Tailwind CSS v4 via `@tailwindcss/vite` — **no `tailwind.config.js` and no PostCSS config**, by design. All design tokens live in `src/index.css`:

- Raw values are CSS custom properties on `:root`, overridden under `[data-theme='dark']`.
- `@theme inline` maps them to utility names (`--color-canvas` → `bg-canvas`, `--color-ink2` → `text-ink2`, `--color-ok|warn|bad|none`, `--font-math`). To add a color, add it in *both* places.
- Theming is applied by setting `document.documentElement.dataset.theme`; `App` cycles system → light → dark and follows `prefers-color-scheme`. `Documents.tsx` receives the mode as props instead of reading it.
- Status tints use `color-mix` against `--status-blend` (`.tint-*` classes); `CanvasView` uses `var(--accent-foreground)` inline where a Tailwind class isn't enough.
- Motion durations are tokens (`--m-press`, `--m-content`, `--m-panel`) that collapse under `prefers-reduced-motion`. Spec §12.3 catalogues the intended animations as M01–M20; the prototype implements only the press/panel/content subset.

## Responsive tiers

`App` measures `window.innerWidth` and picks `wide ≥ 1180`, `regular ≥ 900`, `narrow ≥ 600`, `compact < 600`. This drives inspector placement, not just sizing: docked side panel on wide/regular, a bottom drawer (72px collapsed → 45dvh expanded) on narrow, and a full-width replacement panel on compact. The spec is explicit that layout follows available window space, not device model. `⇧⌘I` toggles the inspector.

## Code quality

From `AGENTS.md`: use double quotes for strings containing apostrophes (an unescaped apostrophe in a single-quoted string breaks the build), keep JSX tags closed and braces balanced, and export components as default exports.
