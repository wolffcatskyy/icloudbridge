# Password reconciliation review validation

Follow-up to upstream PR #35 review, tested October 13, 2026.

## Completed

- 68 password reconciliation, CSV, migration, provider-response, retry, Ente parser,
  and OTP matcher tests pass on Linux (0.68s) and macOS Monterey 12.7.6.
- After installing Apple Command Line Tools 14.2, the full app installs and the
  CLI help command loads successfully. Adding the existing Ente API tests gives
  70 passing tests on Monterey (3.44s), with five dependency deprecation warnings.
  This environment pins argon2-cffi-bindings 21.2.0 and html-to-markdown 2.5.1;
  the latter was compiled locally. The repository dependency declarations are unchanged.
- Real SQLite coverage includes legacy unconfirmed rows, NULL URL duplicate cleanup,
  three unchanged syncs, converged renames, tracking-only deletion, and keeping a
  one-sided old identity held when a replacement pair matches.
- HTTP response fixtures cover Nextcloud custom fields as lists and JSON strings.
  These are regression fixtures, not a real Nextcloud server.
- `node frontend/test-password-upload.mjs` executes the actual API client against
  a local HTTP listener and verifies the multipart content type, boundary, file
  field, filename, and CSV body. Browser storage is substituted.
- TypeScript checking and the production frontend build pass. Frontend lint has
  zero errors and seven pre-existing any-type warnings.
- Changed core/parser/retry/diagnostics/regression modules pass Ruff. Legacy
  modules retain unrelated existing lint findings. Python compilation and diff
  whitespace checks pass.

## Measured performance

Unchanged snapshots, synthetic provider, real SQLite; three full engine syncs for
each vault size. Includes parse, compare, mapping transaction, and stats update.
No network-server throughput or first-import speed is claimed.

| Logins | Linux seconds | Monterey VM seconds | Review items |
| --- | --- | --- | --- |
| 200 | 0.0124 / 0.0154 / 0.0124 | 0.0275 / 0.0263 / 0.0259 | 0 |
| 2000 | 0.0812 / 0.0977 / 0.0964 | 0.1152 / 0.1525 / 0.1501 | 0 |
| 4000 | 0.1548 / 0.1986 / 0.2089 | 0.2159 / 0.3076 / 0.3206 | 0 |

The Vaultwarden batch regression verifies one shared client push for 200 additions,
not 200 full-vault reads. Actual server timings remain to be measured.

## Outstanding before merge

- Real Mac app UI, API, and CLI against disposable Vaultwarden and Nextcloud
  Passwords servers, using an actual Apple export of throwaway logins.
- First import into empty providers, 200-login create throughput, all edit/rename/
  delete/convergence combinations, and real Simulate-versus-apply parity.
- Screenshots of the real review list. The actual Vaultwarden CLI repeated-export
  check is completed below; the corresponding Nextcloud and genuine-Apple-export
  runs remain outstanding.
- Full native UI/provider integration remains outstanding. Full app installation,
  CLI startup, and the existing Ente API tests now work in the isolated Monterey
  Python 3.13 environment. See the native Tahoe follow-up below for actual
  Vaultwarden CLI/API/server checks. Nextcloud and genuine-Apple-export validation
  remain pending; startup and fixture tests do not establish those behaviors.

No personal vaults, exports, passwords, or actual account credentials were accessed.
Keep PR #35 as draft until the maintainer's real-provider validation is complete.

## Native Tahoe and real Vaultwarden follow-up

A separate standard `icbtest` account on an Intel MacPro6,1 running macOS Tahoe
26.7.2 was used; the personal user's password vault was not accessed. Python
3.13.16 and the full app are installed in that account's isolated test directory.
The current dependency declarations install without the older Monterey pins.

- 71 selected reconciliation, parser, migration, retry, API, and certificate-policy
  regression tests pass on Tahoe (1.64s; five dependency deprecation warnings).
- A real, disposable Vaultwarden 1.34.3 server is bound to the Linux host's loopback
  only, and reached from the Mac through an authenticated SSH loopback tunnel.
  The Mac run created 200 synthetic logins with zero failures; Simulate plus apply
  took 0.773s. Three subsequent unchanged syncs took 0.080 / 0.081 / 0.079s,
  with zero review items, zero additions, and zero proposed exports each time.
- Actual provider edits and deletes were exercised. An Apple-side edit yielded one
  review item, then matching the provider cleared it. A provider rename yielded two
  review items, then matching Apple cleared both. A provider deletion yielded one
  review item; deleting the Apple test row cleared it without vault mutation.
- The native CLI completed twice against this real server, retaining the first
  export while creating a second distinct default export (3.761s and 2.015s).
- The actual API ran in the test user's GUI session with the app's normal macOS
  keyring backend. Real multipart uploads returned HTTP 200. Simulate proposed one
  export and produced no download; apply exported exactly one login with no review
  items (0.828s and 0.759s respectively).
- Integration setup exposed a separate API bug: Nextcloud's provider builder did
  not pass through the configured certificate policy. It now preserves that policy,
  including a custom CA path, matching the CLI. The new native regression covers it.
- The production frontend was built and served by this native API. Automated UI
  screenshots remain pending because a controllable browser is not available here.

These live-server runs use synthetic CSVs written in Apple format, **not yet a genuine
Apple Passwords export**. The fixture has been placed in the isolated Mac account
for import and export through Apple's actual app. The genuine export, Nextcloud
live integration, web UI actions/screenshots, and complete acceptance matrix remain
outstanding. The PR must remain draft; no full acceptance claim is made.
