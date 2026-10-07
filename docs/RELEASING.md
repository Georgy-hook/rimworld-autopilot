# Publishing a Windows release

The public installer link is:

`https://github.com/Georgy-hook/rimworld-autopilot/releases/latest/download/RimWorld-Autopilot-Installer.exe`

GitHub looks for that exact asset name on the latest published, non-prerelease release. Keep the filename unchanged for every stable version.

The tagged base is **v0.0.7, 6 October 2026**. The working branch contains later
unpublished corrections and retains product `VERSION=0.0.7` until another release
is explicitly prepared. Start with the
[documentation index](README.md) and current module/audit reports.
[0.0.6 release readiness](RELEASE_READINESS_0.0.6.md) is historical evidence.
Before tagging, close applicable regression gates with offline tests and
separately authorized live RimWorld checks. API acceptance is not completed work;
offline ending-chain tests do not establish an autonomous victory.

1. Update `VERSION` and release notes. GUI entry points, source install and packaging read this single product version; the RIMAPI assembly has its own version. Commit audited sources first, build `vendor/RIMAPI/Source/RIMAPI/RIMAPI.csproj` with `Release-1.6`, and commit the distributed DLL. Check its embedded source revision and SHA-256; tag the final distributable commit only after release approval. Never tag a source-only checkpoint with an older DLL.
2. Run `Build-GUI.ps1`. It writes a versioned Setup EXE, a fixed-name `RimWorld-Autopilot-Installer.exe`, and the ZIP. Verify `dist/RimWorld-Autopilot-<version>-install` contains only runtime files: no release notes, docs, or mod source. The ZIP keeps the complete source package. The fixed-name file is a checked, byte-for-byte copy of the **full Inno Setup installer**, not the smaller post-install assistant.
3. Create a **draft** GitHub release for the tag. Upload both installers, the ZIP, and any other release assets to the draft. Compare the assets' SHA-256 digests with the local files.
4. Publish the release as **Latest** only after the fixed-name installer is present. Test the permanent URL with a HEAD request; it should return `200`, `application/octet-stream`, and the installer's byte length.

Publishing from a draft avoids a period when `/releases/latest` points at a new version whose fixed-name installer has not yet been uploaded. Prereleases use their own links and do not replace this stable installer URL.

`Build-GUI.ps1` passes `/DAppVersion=<VERSION>` to Inno Setup and embeds the
same VERSION resource in both frozen GUI programs. Direct ISCC invocations must
supply that definition as described in the
[official preprocessor command-line reference](https://jrsoftware.org/ishelp/topic_isppcc.htm).
