# Current Sprint Plan 

Refactor the test harness for deployment and establish a supported compatibility baseline, not merely make today’s tests cleaner.

The key idea is to version components independently, but support and release them as tested compatibility profiles. Do not require every repository to share the same version number; require every supported deployment to select one known-good combination.

A release profile should pin:


yaml ⧉

profile: study-agent-full-r-4.6.2-2026.11
study_agent:
  version: <release tag>
  commit: <immutable SHA>
python:
  lockfile_sha256: <digest>
r:
  version: 4.6.2
  renv_lock_sha256: <digest>
  platform: linux-ubuntu-noble-x86_64
  companion_packages:
    slashOhdsiAcpClient:
      version: <release version>
      commit: <immutable SHA>
    slashOhdsiStrategusAssistant:
      version: <release version>
      commit: <immutable SHA>
system_requirements:
  - unixodbc-dev
  - supported JDK version


The renv.lock pins R packages, but it does not fully pin the R executable, Ubuntu system libraries, or the OS-specific compiled result. The release-profile manifest fills that gap.

This changes the implementation plan as follows:

1. Define the first supported baseline before moving tests.

   Treat the current R-4.6.2 rebuilt library, updated odbc, and selected companion-package branches as the candidate first compatibility profile. Save the exact lockfile and package commit IDs now.

2. Move R behavior tests into the companion packages.

   Those testthat cases become part of each package’s release criteria. A behavior change cannot quietly reach Study Agent through a changed sandbox checkout; it must arrive through a released, versioned R package.

3. Replace source-string coupling with versioned runtime compatibility.

   Study Agent’s r_client_compatibility check should verify:

   ◦ expected package versions and, where available, immutable source revisions;
   ◦ required exported functions / public contract;
   ◦ the required Strategus runtime capability;
   ◦ the active R version and selected profile identity.

   Its deep-health result should state the expected and observed profile—not just “passed” or “failed.”

4. Make deployment profiles explicit.
   ◦ Python-only profile: no R requirement; supports the implemented Python-side capabilities.
   ◦ Full Study Agent profile: requires the matching R binary, renv library, system dependencies, and released companion packages.

   The developer symlink to a shared renv/ is fine locally, but a supported deployment should use an explicit, immutable profile location rather than depend on an ambient shared library.

5. Split tests by support level.
   ◦ Python-only test gate: must work from a clean Study Agent checkout.
   ◦ R package gates: run in their own repositories using their release-profile R library.
   ◦ Full deployment gate: install the exact companion releases into the selected profile, then run Study Agent’s runtime compatibility test and full integration suite.
6. Establish upgrade and support policy.

   From the first supported baseline onward:

   ◦ publish compatibility profiles and retain old ones for a defined support window;
   ◦ make incompatible protocol or artifact changes a deliberate release event with migration notes;
   ◦ test upgrades as profile-to-profile transitions, not ad hoc package updates;
   ◦ never describe latest, a branch name, or an unpinned shared renv library as a reproducible deployment.

I would add the compatibility manifest and its validation test at the same time as the test-suite refactor. That makes this transition the line between exploratory development and controlled releases, while avoiding a claim of backward compatibility for pre-baseline development snapshots.

