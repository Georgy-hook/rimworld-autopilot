# Publishing a Windows release

The public installer link is:

`https://github.com/Georgy-hook/rimworld-autopilot/releases/latest/download/RimWorld-Autopilot-Installer.exe`

GitHub looks for that exact asset name on the latest published, non-prerelease release. Keep the filename unchanged for every stable version.

Before tagging a release, close the known regression gates with automated tests and live RimWorld checks. For the next candidate, see [0.0.6 release readiness](RELEASE_READINESS_0.0.6.md); do not treat an API success response as proof that colonists finished the job.

1. Update `VERSION`, release notes, and the installer version. Tag the commit being released.
2. Run `Build-GUI.ps1`. It writes a versioned Setup EXE, a fixed-name `RimWorld-Autopilot-Installer.exe`, and the ZIP. Verify `dist/RimWorld-Autopilot-<version>-install` contains only runtime files: no release notes, docs, or mod source. The ZIP keeps the complete source package. The fixed-name file is a checked, byte-for-byte copy of the **full Inno Setup installer**, not the smaller post-install assistant.
3. Create a **draft** GitHub release for the tag. Upload both installers, the ZIP, and any other release assets to the draft. Compare the assets' SHA-256 digests with the local files.
4. Publish the release as **Latest** only after the fixed-name installer is present. Test the permanent URL with a HEAD request; it should return `200`, `application/octet-stream`, and the installer's byte length.

Publishing from a draft avoids a period when `/releases/latest` points at a new version whose fixed-name installer has not yet been uploaded. Prereleases use their own links and do not replace this stable installer URL.
