<!-- File: docs/phases/delight/EXTENSION_API.md -->
# Extension API (M30)

Read from the code, not run in a browser (UNVERIFIED in a browser).

## Module
`frontend/js/features/<slug>.js`: `export default function init(ctx)`; optional `export const styles = true` loads `css/features/<slug>.css`.
`ctx = { slot(id), t(key, vars), store, on(type, fn), flags, lang }`. `store` is a no-op until M31 adds `features/store.js`.
Registry also exports `fire(trigger)`, `registerCommand(cmd)`, `commands()`.

## Flags (`frontend/data/features.json`)
`features.<slug> = { enabled, module, trigger, needs, playful }`; `profiles = { public: [], exhibition: [] }`.
Loads when `enabled` and the slug is in the active profile (`?profile=`, default `public`). Slugs starting `_` skip the profile check.
Triggers: `home`, `capture`, `result`, `browse` (on `wasteai:route` / `capture` / `result`), `header`, `footer` (at start), `idle`, `command` (via `fire("command")`).

## Slots
`#slot-header-tools` (inside the toolbar), `#slot-home`, `#slot-capture` (end of the home view), `#slot-result`, `#slot-browse`, `#slot-footer`. Empty, no styles.

## Events (real payloads)
- `wasteai:route` `{ view }` (from `app.js renderRoute`, every route render).
- `wasteai:capture` `{ stage, ... }`: `open` (panel leaves idle), `ready` `{ blob, replace(blob) }` (preview shown; `replace` swaps the file without re-firing `ready`), `before-send` `{ blob }`, `sent`, `cancel`.
- `wasteai:result` `{ result, photoUrl }` (exists; from `upload.js` and `batch.js`).
- `wasteai:batch` `{ items, done: true }` (when a batch run finishes).
- `i18n:change` `{ lang, dir }`, `theme:change` `{ theme }`, `sound:change` `{ muted }`.

## Strings
`i18n/features/<slug>.<lang>.json`, keys start `f.<slug>.`. A missing key returns "" and logs `i18n_missing_key`. Reloaded on `i18n:change`.

## Example
`js/features/_probe.js` (set `_probe.enabled` true locally).
