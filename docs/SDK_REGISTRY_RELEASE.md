# Official registry release runbook

This runbook covers the credential-bound transition from the immutable GitHub
SDK release to npm and nuget.org. It deliberately does not rebuild packages.
The workflow downloads the public release assets, verifies their frozen hashes
and package metadata twice, requires the version to be absent, and only then
enters a protected GitHub environment.

Never paste registry credentials into an issue, pull request, commit, workflow
input, or chat. Store them only in the protected GitHub environment described
below.

## Frozen release subject

| Field | Exact value |
|---|---|
| Release | `interop-sdk-v0.1.0` |
| SDK source | `de7c765243dc86226b8554757ef1f9419c194a4c` |
| Release workflow | `9cbeb2e0630e10054094369e1f5cf87707386954` |
| npm coordinate | `@contractgraph-qa/interop-report@0.1.0` |
| npm tarball SHA-256 | `b73b4b0aeb6252aa007ff64fe1037681c5a1d62625435ff7f9b81e0f7cba55d2` |
| NuGet coordinate | `ContractGraphQA.Interop@0.1.0` |
| NuGet package SHA-256 | `9f84c149c2d5f4e08ab20198106b2123b7b30fd518ef2f9a4f4fa1d68c750fe2` |

The machine-readable source of truth is
[`sdks/registry-release-v0.1.0.json`](../sdks/registry-release-v0.1.0.json).
The publish workflow accepts only the repository owner, `main`, one of the two
listed registries, and the coordinate-specific confirmation string.

## One-time GitHub environment

In repository settings, create an environment named `sdk-registry-release`:

1. Require a reviewer before deployment.
2. Restrict deployment branches to `main`.
3. Add the environment variable below exactly:

   ```text
   REGISTRY_RELEASE_ARMED=interop-sdk-v0.1.0@de7c765243dc86226b8554757ef1f9419c194a4c
   ```

4. Add only the credential needed for the selected transition. Remove the npm
   bootstrap token after npm succeeds.

If the environment is absent or the arm value differs, the publish job stops
before requesting or using a registry credential.

## npm bootstrap release

The package does not yet exist on npm. npm staged publishing and package-level
trusted publishing cannot bootstrap a brand-new package, so `0.1.0` needs one
direct owner-authorized publish. The workflow still generates npm provenance
through GitHub OIDC.

Before the run:

1. Sign in to npm as the intended long-term owner and enable 2FA.
2. Create or verify ownership of the `contractgraph-qa` npm scope. The package
   name cannot be published through the unrelated `safal207` user scope.
3. Create a short-lived granular access token with publish permission for that
   scope and **bypass 2FA enabled**; a non-interactive bootstrap job cannot
   answer an OTP prompt.
4. Add it as the `NPM_TOKEN` secret in `sdk-registry-release`.
5. Open **Actions → Publish SDK v0.1.0 to official registries → Run workflow**
   on `main` with:

   ```text
   registry: npm
   confirmation: publish @contractgraph-qa/interop-report@0.1.0
   ```

After the run succeeds, verify the publication evidence artifact
`registry-publication-npm`, revoke the bootstrap token, and remove `NPM_TOKEN`
from the environment. Configure an npm trusted publisher for later versions;
later releases should use OIDC and npm staged publishing with human 2FA
approval rather than retaining a bootstrap token.

Official references:

- [Publishing a scoped public package](https://docs.npmjs.com/creating-and-publishing-scoped-public-packages/)
- [Trusted publishing with OIDC](https://docs.npmjs.com/trusted-publishers/)
- [Staged publishing](https://docs.npmjs.com/staged-publishing/)

## NuGet trusted release

NuGet can bootstrap the package with trusted publishing, so no long-lived API
key is needed.

Before the run:

1. Sign in to nuget.org and open **Trusted Publishing**.
2. Create a GitHub policy with these exact bindings:

   | Policy field | Value |
   |---|---|
   | Owner | the nuget.org individual or organization that will own the package |
   | Repository owner | `safal207` |
   | Repository | `ContractGraph-QA` |
   | Workflow file | `publish-sdk-registries-v0.1.0.yml` |
   | Environment | `sdk-registry-release` |
   | Package pattern | `ContractGraphQA.Interop` |
   | Allowed transition | publish a new package and new versions |

3. Add the nuget.org profile name, not an email address, as the `NUGET_USER`
   secret in `sdk-registry-release`.
4. Run the workflow on `main` with:

   ```text
   registry: nuget
   confirmation: publish ContractGraphQA.Interop@0.1.0
   ```

The workflow exchanges GitHub OIDC for a one-hour NuGet key immediately before
the push. It then downloads the public package and compares the nuspec, README,
repository commit, and adapter DLL with the source package. A nuget.org
repository signature is the only allowed archive-level delta. Inspect the
`registry-publication-nuget` evidence artifact after success.

Official reference: [Trusted Publishing on nuget.org](https://learn.microsoft.com/en-us/nuget/nuget-org/trusted-publishing).

## Maven Central `0.1.0` hold

Do not upload the Java `0.1.0` files to Maven Central. The immutable GitHub
release contains the main JAR, sources JAR, and POM, but it lacks a Javadoc JAR,
GPG signatures, and developer metadata in the published POM. Reconstructing or
editing those already-released bytes under the same version would destroy the
one-source/one-version boundary, while Central components are immutable.

The next valid transition is a Central-complete Java `0.1.1` release with:

- verified `io.github.safal207` Central namespace;
- name, description, URL, license, developer, and SCM POM metadata;
- main, sources, and Javadoc JARs;
- GPG signatures and checksums for every uploaded artifact;
- a protected Central Portal token and signing key;
- a new exact source commit, tag, manifest, attestation, and public replication
  check.

Official references:

- [Maven Central publishing requirements](https://central.sonatype.org/publish/requirements/)
- [Central Portal Maven plugin](https://central.sonatype.org/publish/publish-portal-maven/)
- [Central component immutability](https://central.sonatype.org/publish/requirements/#immutability)

## Failure and replay behavior

- A non-`404` registry preflight is not treated as absence.
- An existing version stops the workflow; it is never overwritten or silently
  skipped.
- A changed release asset, manifest, checksum file, package coordinate, source
  commit, or authority boundary stops before credentials are used.
- npm and NuGet are separate jobs and separate human approvals. Success in one
  never implies success in the other.
- If the push succeeds but public replication times out, do not rerun. Inspect
  the registry and workflow evidence first because the external mutation may
  already be durable.
- A passing adapter remains `conformance_evidence_only` with
  `mayAuthorizeAction=false`; registry publication grants no execution
  authority.
