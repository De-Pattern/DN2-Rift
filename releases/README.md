# Release announcements

One file a release, `releases/vX.Y.md`, added to `main` only after that build's gate printed
`CLEARED TO FLASH`. Its first line is `# vX.Y · NAME`; the rest is the post, ending with a
**Coming next (not available yet)** section. Pushing a new file here makes the GitHub
release and posts it to RIFT ANNOUNCEMENTS (`.github/workflows/release.yml`). No firmware is
ever attached to a release.
