# Original-image storage

Generated artwork remains in Git. `external-assets.json` records the exact acquired
JPEG bytes for sourced photographs: identity, SHA-256, download URL, source page,
and its logical path used by the renderer. These are not all full-resolution upstream
originals: some are deliberately recorded historical download renditions. Replacing
one with a larger original is a reviewed image/content change, not a silent sync.
License and attribution records remain in `rights-inventory.json`.

## Fetching originals

```sh
./scripts/asset_fetch.py
./build.sh
```

Fetch checks the local `assets/cache/sha256/` first, then the pinned public URL.
If that doesn't provide the exact bytes, it can fall back to the private backup
configured in `assets/setup/`. Private downloads may incur request and egress
charges. Use `--public-only` to exclude private storage. Every accepted file
must match the manifest SHA-256. The renderer also verifies decoded pixels.
Generated JPEG XL masters still come from Git.

Public fetches are paced at one request per second per provider (the Wikimedia
hosts share a limit). Transient failures get two retries after 10 and 60 seconds
with ±20% jitter, unless the server specifies a valid `Retry-After` of up to
five minutes. A longer wait or repeated throttling pauses that provider for the
rest of the run. Permanent HTTP errors and checksum mismatches are not retried.

Trusted GitHub Actions builds on `main` verify hashes in the restored cache and
read missing originals only from the configured private S3 bucket. They do not
contact public image hosts. The read-only GitHub OIDC role has no list, upload,
or delete permission. Credentials are scoped to the download step, and files
read from S3 are not saved to the Actions cache. Private reads can incur request
and egress charges. Pull requests run source and interactive tests without
fetching photos or receiving private access.

Populate the bucket with `./scripts/asset_sync.py`. To opt into verifying it
before pushing to `origin/main`, run from the repository root:

```sh
git config --local core.hooksPath .githooks
```

If you already use a custom hooks path, integrate `.githooks/pre-push` into your
existing hooks instead of replacing that setting. The check reads the manifest
from the commit being pushed, not from uncommitted files. It uses the same
metadata checks as `./scripts/asset_sync.py --verify`, including listing the
configured S3 hash prefix when allowed. It never transfers image bodies. If the
check finds missing or mismatched originals, it blocks the push. Other branches
and remotes aren't affected. You can run `./scripts/asset_sync.py --verify` for
the current working-tree manifest at any time.

## Storage tool

The small tool lives in `scripts/asset_setup.py`, `scripts/asset_fetch.py`, `scripts/asset_sync.py`, and their
provider helpers. Boto3 handles S3, R2, and B2; native Google Cloud and Azure SDKs
handle GCS and Blob Storage. `uv` manages an isolated Python environment from
`pyproject.toml` and the committed `uv.lock`. The document-build container retains
its separate dependencies; cloud SDKs are not added to published documents or the
offline builder.
Run the service-first terminal wizard directly, or use one of its read-only modes:

```sh
./scripts/asset_setup.py            # Configure or resume
./scripts/asset_setup.py --dry-run  # Preview setup against current settings
./scripts/asset_setup.py --verify   # Check the saved configuration
```

Dry run follows the wizard’s preflight checks and reports what would change or
still needs verification. It does not update setup state, create resources, or
publish or dispatch workflows. Verify checks existing settings without configuring
anything or downloading objects. The two flags are mutually exclusive.

Choose AWS S3, Google Cloud Storage, Azure Blob Storage, Cloudflare R2, or
Backblaze B2, then supply the
bucket/container and optional path. Azure also needs the storage account. You can also run `uv run --locked scripts/asset_setup.py`.
The same command resumes setup. `assets/setup/storage-config.json` holds the
single selected provider and nonsecret settings. This default path is anchored to the repository,
not the terminal working directory. In an interactive terminal, saved text is prefilled and editable. Enter accepts
the field; delete its contents to clear a prefix and use the bucket root. Numbered
menus keep their displayed defaults. If interactive editing is unavailable, the prompt explicitly shows
the saved value: Enter keeps it and `-` clears a prefix. Choose another provider or edit a destination
to replace those defaults.

Successful initial destination checks are recorded. On a recognized rerun the
script rechecks provider-specific ownership/privacy/retention settings, but allows
existing assets rather than falsely requiring or claiming an empty path. A new
or changed destination still needs its initial empty-path check. No saved state
authorizes deletion, overwriting, or cloud permission changes.

Install `uv` once; it installs the locked SDK dependencies automatically. No manual
virtual environment activation or global Python package installation is needed.

After setup, back up verified local originals and check the backup:

```sh
./scripts/asset_sync.py
./scripts/asset_sync.py --verify
```

Sync refuses to upload until the local cache has all manifest originals. It does
not fetch files. With a local S3 profile that permits listing, sync lists the
configured hash prefix, verifies existing objects without uploading them, and
conditionally uploads only missing ones, printing each source filename and size before
transfer. Local verify also uses that listing to
count missing objects, and checks service checksums for existing objects. If
listing is denied, both modes retain the exact-key behavior. Use `--verbose` for
per-asset details; the default output is a summary. No verification downloads
object bodies, and metadata requests can still incur charges.

AWS uses the standard Boto3 credential chain, including `~/.aws/credentials` and named
profiles. If setup used a named profile, use the same `AWS_PROFILE` for sync
and verification. GCS uses Application Default Credentials; Azure uses token credentials,
not implicit account-key lookup. Native SDK dependencies are locked by `uv`.
No credentials belong in the manifest, setup state, cache, Docker image, or Git.

Uploads are create-only except B2's preserved-version appends. GCS generation-match
zero protects an existing live object, not a historical-only key. No sync removes
historical originals. Explicit deletion remains a separate, confirmed operation.

### Implementation and verification boundary

AWS setup retains its create/inspect wizard and IAM/OIDC plan. GCS and Azure setup
provide provider-specific guidance and read-only verification; their actual cloud
identity provisioning is not claimed to be automatic. Review the terminal output
before running its manual commands. No live GCS/Azure storage or federated CI tests
have been performed. Local tests mock provider SDK calls and check request construction,
conditional writes, verification failures, and deletion safeguards.

The optional metadata-verification GitHub workflow is **AWS-only**. Selecting another
service does not configure GitHub federation or switch the Pages workflow. GCS needs
Workload Identity Federation restricted to this repository and branch; Azure needs
an Entra federated identity with equivalent issuer/audience/subject constraints.
Use read-only CI permissions and a separate local upload identity. GCS's standard
Object Viewer role includes listing; a get-only custom role is needed to exclude it.
Azure's Blob Data Reader also permits listing; exact-key operation does not imply
that the assigned cloud role forbids listing. Narrow the container scope and review
ABAC if listing must be excluded. Never store service-account keys, storage-account
keys, or signed private URLs in repository configuration.

R2 and B2 use dedicated provider settings, not an arbitrary endpoint flag.
Conditional-write and identity guarantees are checked per service rather than
assumed from S3 API compatibility.

Provider references: [GCS copy/preconditions](https://docs.cloud.google.com/sdk/gcloud/reference/storage/cp),
[GCS federation](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines),
[Azure blob CLI](https://learn.microsoft.com/en-us/cli/azure/storage/blob),
[Azure login authorization](https://learn.microsoft.com/en-us/azure/storage/blobs/authorize-data-operations-cli).

## AWS bucket setup

Select **Amazon S3** in the wizard and enter the bucket name and optional
prefix. Reruns prefill the saved selection.

The wizard verifies your AWS account, then checks the bucket with an expected-owner
constraint before asking for a region. An accessible existing bucket supplies its
region automatically; setup immediately verifies its private settings and that
the selected path has no current objects, historical versions, or delete markers.
Denied or ambiguous responses do not establish that somebody else owns the bucket:
setup reports that it cannot verify access and offers another name or a clean stop.
The selected prefix is retained when changing the bucket name.

A generic `HeadBucket` 404 is not proof of absence: setup follows it with an
expected-owner `GetBucketLocation` request. Only an explicit `NoSuchBucket` error
leads to the new-bucket region prompt and
`create`/`skip` choice. Creation rechecks absence and requires separate exact
confirmation. Configuration is saved as `assets/setup/storage-config.json`; skipping
does not verify or create a bucket. Use `--verify` to inspect the saved bucket later.

GitHub access offers three numbered choices. Until access is configured, **1** is the default:

1. **Set up GitHub access.** Setup prepares the diagnostic
   and checks that GitHub CLI can write to the repository. After one confirmation,
   it fast-forwards remote `main` with a diagnostic-only commit if needed, then runs
   the workflow and waits for the exact run it started. The local branch and staged
   files stay unchanged and no new workflow file is added to your checkout; a push
   may trigger Pages. Modified or repository-mismatched
   workflow files are preserved and rejected. The diagnostic uses no AWS credentials
   and emits only its subject and audience; the script verifies and uses them without
   asking you to copy a token, inspect logs, or type the subject. If GitHub does not
   return the exact run ID or verification fails, setup stops instead of guessing or retrying dispatch.
   With a checked bucket, setup then compares the AWS role, OIDC provider and
   repository variables. If anything differs, it stops. If settings are missing,
   it asks once before creating them. The new role permits only reading the
   backup's hash-key objects from the trusted repository’s main branch, not just
   from one workflow. Avoid concurrent IAM edits during setup. Static checks do
   not prove live access; no assets are downloaded.
   If reading a run was interrupted, rerun `./scripts/asset_setup.py`. The default
   resumes the exact run saved for the same repository and S3 destination, verifying
   it at its historical commit without dispatching again. Setup offers a fresh check only when the saved run is definitively unusable.
   If access, connectivity, or verification is uncertain, it keeps the saved run and stops.
2. **I already have the workflow identity (generate templates only).** After inspecting your successful
   trusted run, resume with the command below and choose this option. Supply only its exact OIDC
   subject (`sub`), never the token, to generate local IAM policy templates. The
   script validates its format but does not independently verify the supplied
   identity, apply IAM changes, or prove that access works.
3. **Skip GitHub access for now.** Save the bucket configuration without preparing
   a diagnostic or IAM policy templates. Existing access is not changed.

Rerun the same command and press Enter to keep stored settings:

```sh
./scripts/asset_setup.py
```

The saved repository and workflow subject are offered as defaults. When those
settings exist, read-only checks compare GitHub repository variables and AWS
static role/policy settings. Results distinguish verified configuration from
unavailable or mismatched information. When both GitHub variables and AWS static
configuration match, setup finishes without regenerating a first-time creation plan.
These checks never claim working GitHub access or object integrity, and do not
download objects.

Legacy and immutable-ID branch/environment subjects are accepted by explicit
planning; repository IDs alone never establish which format GitHub emits.
The diagnostic matches the current backup job: `main` without an environment.
For environment-scoped jobs, both jobs must use the same protected environment
and its deployment-branch restrictions; customized subjects require separate
review and are not synthesized by this tool.

Bucket-only setup leaves existing IAM plans unchanged. Re-running does not revoke
any previously configured access. No IAM policies are generated from a guessed
identity; live federation and service-checksum verification remain separate checks.

### Bucket creation and checks

Choose **create** in the wizard to create a missing bucket. The wizard checks
absence and asks for confirmation after showing the account, region, security
settings and cost implications. It disables ACLs, blocks public access and uses
SSE-S3 encryption. Versioning is off by default; without it, deleted originals
cannot be recovered through S3 versions. Keep an independent backup. A partial
failure stops without rolling back or deleting the bucket.

For an existing bucket, setup verifies ownership, region, public-access blocks,
ACL-disabled ownership and encryption. A new destination must be empty of both
current objects and historical versions and delete markers. A recognized rerun
can reuse a populated destination. Versioning is inspected, not altered.
Enabled lifecycle expiration rules stop setup for review. Use
`asset_sync.py --verify` separately to check object checksum metadata.

The setup identity needs read permissions including `s3:ListBucket`,
`s3:ListBucketVersions`, and the bucket-configuration reads. The CI role still
needs **only GetObject**, not LIST. Denied, incomplete or unexpected responses stop
the check. An empty-path result is point-in-time, not a namespace lock; conditional
hash-key uploads still prevent overwrites. Public-access blocking does not prove
absence of private cross-account bucket/access-point grants, which need separate
review.

## Integrity verification

Every object key is derived from the original's SHA-256. Uploads first compute local
SHA-256, MD5, SHA-1, CRC32C and size. Verification compares provider-backed checksum
metadata and size with those expected values; arbitrary user metadata is not accepted
as integrity evidence. Missing or unsupported checksums fail as **UNVERIFIED** rather
than causing an implicit download.

- **S3:** single-part uploads send SHA-256 and Content-MD5. HEAD requests ask for the
  checksum and compare full-object SHA-256 and size. A documented single-part MD5
  ETag is a fallback only for eligible unencrypted/SSE-S3 objects; composite and
  unsupported encryption cases are rejected.
- **R2:** single-part uploads send Content-MD5; verification compares the documented
  single-part MD5 ETag and size. Multipart ETags are not whole-object checksums.
- **GCS:** uploads provide MD5/CRC32C with generation-match zero. Native metadata
  checks compare CRC32C, optional MD5 and size. SDK automatic checksum-failure
  deletion is disabled; an error never authorizes cleanup or overwrite.
- **Azure:** uploads are forced to one PUT (maximum 256 MiB) with Content-MD5.
  Verification compares the stored content MD5 and size against the manifest,
  without requiring a machine-local upload receipt. This assumes a dedicated
  location written by this workflow: Azure permits the MD5 property to be changed
  separately, so this is not protection against an independent writer changing
  both data and metadata. Missing or mismatched checksums still fail; verification
  never authorizes overwriting unexpected content. The local verification report
  is informational, not required for verification on another machine.
- **B2:** HEAD supplies the current version identifier; native `get_file_info`
  confirms the exact bucket, filename and file ID, then compares the service's
  whole-file SHA-1 or MD5 and size. Values such as `none`/unverified hashes are
  rejected. The native metadata check uses a bucket-bound application key with
  `readFiles`; it does not require LIST. See provider credentials below.

These checks avoid asset-body downloads and associated transfer costs. Metadata
requests can still have charges. They are **not** a byte-for-byte restore test,
cryptographic proof beyond the provider checksum used, or proof that the full build
can be recovered using the private backup. A denied metadata request remains a
failure; without listing permission, an S3 403 cannot reliably distinguish a missing
object from inaccessible data.

Local cache validation still hashes actual bytes with SHA-256. Retrieved public
sources and private fallback objects must match that hash before
atomic installation at `assets/cache/sha256/ab/<full-sha256>`. Changed sources fail
rather than silently substituting images. Default sync never deletes anything.
A private backup is not a redistribution license.

## Optional GitHub verification

`Verify private asset metadata` (`verify-asset-backup.yml`) is manual-only,
AWS-only and restricted to trusted `main`, without a pull-request trigger or
publication. It obtains short-lived OIDC credentials for the metadata-check step,
then runs:

```sh
uv run --locked python -m soso.assets.asset_sync_ci
```

The workflow uses manifest keys directly, never lists the bucket, and does not
read the local setup. It verifies object metadata independently of the public
image hosts. It does
not download files, build guides, use the Actions cache, or publish the site.

## Optional deletion

Deletion is an explicit, interactive maintenance action:

```sh
./scripts/asset_sync.py --delete <full-hash>
```

Repeat `--delete` for exact keys;
the tool does not list the bucket. Currently referenced objects cannot be deleted.
The warning explains that historical rebuilds can break and requires typed terminal
confirmation. There is no unattended bypass. No local files or historical object
versions are purged. Use a separate narrowly scoped maintenance identity, not the
CI reader or normal uploader.

## Cloudflare R2 and Backblaze B2

The setup wizard provides an unverified plan and limited endpoint/live-prefix
checks for these providers. It does not prove privacy, effective permissions or
historical emptiness, and does not create buckets or configure GitHub credentials.
Remaining manual checks are stated explicitly. Native endpoints are constrained;
ambient AWS credentials are never sent to these services.

Supply dedicated credentials through your local secret management:

- R2: `SOSO_R2_ACCOUNT_ID`, `SOSO_R2_ACCESS_KEY_ID`,
  `SOSO_R2_SECRET_ACCESS_KEY`.
- B2: `SOSO_B2_REGION`, `SOSO_B2_ACCESS_KEY_ID`,
  `SOSO_B2_SECRET_ACCESS_KEY` (application-key ID and key).

B2 metadata verification additionally requires the application key to be bound to
the intended bucket with `readFiles`; the tool validates its allowed bucket/prefix
and the returned file identity. Uploaders also require `writeFiles` and
`readBucketLifecycleRules`. Do not grant `deleteFiles` or lifecycle-write permission
to normal backup identities. R2 tokens may include broader LIST/delete permissions
than the AWS exact-key role; review them rather than claiming equivalent scope.
Disable R2 public access and avoid lifecycle expiry for both services.

**B2 appends versions, not conditional creation.** A matching existing object is
verified through metadata without an upload. An authenticated current-key absence
permits an append; a checksum mismatch or denied access stops. Before writing, sync
rejects lifecycle expiration or uninspectable retention settings. A new upload must
return a valid version ID; metadata checks verify both that version and the current
object. No object bodies are downloaded. Concurrent correct writers may append
identical versions, costing storage. Upload retries are disabled; an ambiguous
response may leave an unacknowledged version for the next explicit run to inspect.
Failures do not trigger deletion or history cleanup. Administrators must preserve
retention settings and limit deletion permissions.

Confirmed B2 prune hides the current key with a delete marker; it does not reclaim
historical-version storage. Version-specific deletion and automatic historical
recovery are not implemented. No live R2/B2 validation has been performed; tests
use synthetic SDK/native API responses.
