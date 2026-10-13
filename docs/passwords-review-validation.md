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
- Two actual CLI runs retaining the previous default export, and screenshots of
  the real review list. Default filenames are now unique; existing explicit paths
  still fail safely with an actionable message.
- Full native UI/provider integration remains outstanding. Full app installation,
  CLI startup, and the existing Ente API tests now work in the isolated Monterey
  Python 3.13 environment. Actual password-sync CLI runs and real server tests
  are still pending; startup and fixture tests do not establish those behaviors.

No personal vaults, exports, passwords, or actual account credentials were accessed.
Keep PR #35 as draft until the maintainer's real-provider validation is complete.
