# Current Sprint Plan

 plan:

1. Make dependency ownership explicit in each package’s DESCRIPTION.

   slashOhdsiStrategusAssistant should list the HADES packages it directly relies on in Imports, with minimum supported versions where appropriate. This will include Strategus and its direct runtime dependencies such as DatabaseConnector, FeatureExtraction, Capr, CohortCharacterization, and OHDSIShinyModules, plus any other packages called by shell or generated-script code.

   slashOhdsiAcpClient should remain much lighter. It should declare only its actual R dependencies, while documenting the compatible StudyAgent/ACP server release range separately.

2. Use renv.lock as the tested dependency contract.

   For every package release, the active renv.lock and installed renv library define the precise package set against which:

   ◦ the R package is developed;
   ◦ generated incidence and cohort-method scripts are tested;
   ◦ demos are exercised;
   ◦ CI validates the release.

   The lockfile is more precise than DESCRIPTION; DESCRIPTION communicates install-time requirements, while the lockfile records the exact validated environment.

3. Add runtime environment checks to both shells.

   At shell startup—and again before specification execution—the package should check installed versions against its declared expectations.

   For the Strategus assistant, the check should report:

   ◦ R version;
   ◦ installed Strategus and key HADES package versions;
   ◦ required versus installed versions;
   ◦ whether the package set matches the release-tested renv.lock where that metadata is available;
   ◦ clear remediation guidance if requirements are not met.

   A missing or incompatible critical package should stop execution before generated scripts are written or run. Noncritical capabilities, such as an optional artifact viewer dependency, can warn instead.

4. Test generated scripts against the active lockfile environment.

   Add focused CI checks that use the checked-in/current renv.lock environment to:

   ◦ parse every generated script;
   ◦ generate both incidence and cohort-method specifications;
   ◦ construct the relevant Strategus/module objects;
   ◦ run a lightweight execution test where practical;
   ◦ retain regressions such as the current targetIds/Characterization signature failure.

   This makes the lockfile-backed CI environment the authoritative proof that the emitted scripts match current signatures.

5. Version by package release and Git tag.

   When the packages separate into Odyssey repositories:

   ◦ tag each release of slashOhdsiStrategusAssistant;
   ◦ update DESCRIPTION, renv.lock, demos, and compatibility documentation together;
   ◦ test the tagged source against the associated lockfile;
   ◦ publish the exact tested HADES versions in release notes.

   We should avoid claiming broad compatibility beyond what was tested. A release can say, for example, “tested with Strategus X, DatabaseConnector Y, and CohortCharacterization Z,” while DESCRIPTION expresses the minimum installation requirements.

6. Define the ACP server compatibility separately.

   A Python/ACP server version is not an R package dependency, so it should not be forced into Imports. Instead, slashOhdsiAcpClient should have:

   ◦ a documented compatible StudyAgent/ACP server version range;
   ◦ a small runtime compatibility check against an ACP version/health endpoint;
   ◦ a protocol or API version identifier returned by the server;
   ◦ a clear error if the client and server are incompatible.

   This allows the R ACP client to be independently released while still preventing silent protocol drift.

7. Keep one small shared compatibility utility inside each package initially.

   We do not need a third compatibility package now. Start with internal helpers such as:

   ◦ checkStrategusEnvironment()
   ◦ checkAcpCompatibility()
   ◦ packageVersionReport()
   ◦ assertRequiredPackageVersion()

   If shared logic becomes substantial after the packages split, it can then be extracted deliberately.

The immediate implementation sequence should be:

1. Inventory direct R dependencies used by each package and generated script.
2. Update both DESCRIPTION files.
3. Add the startup/pre-execution checks.
4. Add lockfile-backed generated-script tests, starting with cohort method.
5. Add release documentation that connects package tags to tested renv.lock environments.
6. Add ACP server/client version negotiation to slashOhdsiAcpClient.

This keeps the maintenance model familiar to R developers, aligns naturally with standalone Odyssey package releases, and gives air-gapped users an early, actionable error when the installed HADES stack does not match what the shell was tested against.
