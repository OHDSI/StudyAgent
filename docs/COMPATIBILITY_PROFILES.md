# Compatibility Profiles

COMPATIBILITY\_PROFILES.yaml records tested, immutable component
combinations from the first supported baseline onward. It is currently
provenance only. Nothing at service startup reads or enforces it
yet. Java is likewise not enforced by the new registry today. The MCP
configuration can select JAVA_HOME for CirceR/rJava, but it does not
compare vendor or patch version to the profile registry.

Each profile is either:

- source_baseline: a tested source-and-runtime combination. It is useful for
  development and release provenance but is not itself a deployable artifact.
- deployment_artifact: a published deployment bundle. It must also identify
  the immutable runtime artifact and its manifest digest.

The current profiles track the lockfiles in this repository. Older profiles
remain as historical release records and must not be rewritten to match later
dependency updates.

The Python-only profile supports the implemented Python service capabilities.
The full-R profile additionally requires the named R runtime, renv library,
companion R packages, JDK, and host-system dependencies. A Windows service
bundle will add a Windows deployment_artifact profile after its CI pipeline
publishes an attested runtime ZIP.

When changing a dependency, R library, companion package, or supported runtime,
create a new profile (or explicitly advance the current baseline), run its
declared test gate, and retain the previous profile for the documented support
window. Never use a mutable branch or latest label as a profile identifier.

Compatibility profiles record exact, tested environments. Runtime enforcement
should initially be conservative:

- exact lockfile digests and companion-package commits;
- exact selected profile identity;
- R/JDK versions reported prominently;
- failure only for missing runtimes, incompatible required packages, or an
  explicitly unsupported major/minor version.

## Support policy

Every deployment_artifact profile must include quoted ISO-8601 released_on and
supported_until dates. The initial policy is two years of compatibility support
from the release date. A future policy change applies to new profiles; it must
not silently rewrite the support commitment recorded for an existing deployment.

source_baseline profiles are not deployed releases and must set both fields to
null.

For each thoroughly validated deployment, add a profile entry to
COMPATIBILITY_PROFILES.yaml, for example:

```yaml
profiles:
  study-agent-full-r-4.6.1-msjdk-21-windows-2026.11:
    current: true
    kind: deployment_artifact
    released_on: "2026-11-21"
    supported_until: "2028-11-21"
    deployment_artifact:
      runtime_zip_sha256: <sha256>
      runtime_manifest_sha256: <sha256>
    study_agent:
      version: 0.0.3
      commit: <immutable-study-agent-sha>
    python:
      requires_python: ">=3.12"
      tested_version: <Windows Python version>
      uv_lock_sha256: <sha256>
    r:
      required: true
      version: 4.6.1
      platform: windows-x86_64
      renv_lock_sha256: <sha256>
      companion_packages:
        slashOhdsiAcpClient:
          version: 0.0.3
          commit: <immutable-sha>
        slashOhdsiStrategusAssistant:
          version: 0.1.0
          commit: <immutable-sha>
      jdk:
        vendor: Microsoft OpenJDK
        version: 21.0.12.1

```


