# ACQ-1 WP-3 R1E Deterministic Account Metadata

The final image allowlists exactly `entrypoint.py` and `runtime_probe.py` under
`/opt/flowtracer-r1e/runtime`. Audit programs are bind-mounted read-only during
build or supplied to a root-only, network-none inspection through standard
input; they never enter the final filesystem.

`audit/identity_manifest.py` walks the complete persistent image filesystem,
excluding only Docker runtime-injected or ephemeral paths listed in its
`EXCLUDED` constant. It fails closed on special entries and emits absolute
paths in locale-independent Unicode code-point order. Each canonical UTF-8,
no-BOM, LF-terminated entry record contains type, mode, UID, GID, plus raw file
SHA-256 or symlink target. The document records format/version, entry count,
payload bytes and payload SHA-256. Both build manifests must be byte-identical.

`audit/validate_identity.py` independently verifies the manifest schema,
absolute normalized paths, ordinal ordering, uniqueness, entry-specific fields,
payload bytes/hash and canonical UTF-8/LF document encoding. `audit/package_tree.py`
provides the same locale-independent `relative-path + raw-file-sha256 + LF`
identity used for the Git-visible evidence package and protected historical
trees.

After creating the locked non-password `flowtracer` account, the Dockerfile fixes
its `sp_lstchg` field to `0` and deterministically synchronizes the shadow backup.
Both the build and root-only audit verify exactly one nine-field account record,
locked password state and field 3 equal to `0` without logging shadow content or
the password field. `/etc/shadow` remains inside Runtime Identity v2.

Run `run_r1e.py` exactly once for the formal session. It uses unique R1E object
names, captures every command's stdout/stderr, performs both no-cache builds and
all runtime/audit checks, then removes only those exact R1E objects.
