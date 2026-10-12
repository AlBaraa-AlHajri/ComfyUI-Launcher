# Publishing

The public project is `AlBaraa-AlHajri/ComfyUI-Launcher`. Run these commands from the
repository root for a fresh unpublished checkout, after the local build passes:

```powershell
git init -b main
git add .
git commit -m "feat: add bilingual Windows ComfyUI launcher"
gh auth status
gh repo create ComfyUI-Launcher --public --source=. --remote=origin --description "Unofficial bilingual Windows tray launcher for ComfyUI with Chrome app mode" --push
gh repo edit --add-topic comfyui --add-topic launcher --add-topic windows --add-topic stable-diffusion
git tag v1.0.0
git push origin v1.0.0
gh run list --workflow release.yml
```

After the release run appears, use `gh run watch` to select and watch it, then:

```powershell
gh release view v1.0.0 --web
```

If `gh` is unavailable, create an empty public GitHub repository named
`ComfyUI-Launcher` in your account, then use the HTTPS clone URL shown by GitHub:

```powershell
$repositoryUrl = Read-Host 'Paste the HTTPS clone URL of your empty GitHub repository'
git remote add origin $repositoryUrl
git push -u origin main
git tag v1.0.0
git push origin v1.0.0
```

For later releases, update `__version__` in `src/comfy_launcher/__init__.py`, the
version in `pyproject.toml`, the product/file version in `version_info.txt`, and
`CHANGELOG.md`. Commit, push and tag the matching new version. The workflow rejects
tags that disagree with `__version__`. Keep releases immutable; use a new version for fixes.

The workflow runs Ruff, formatting checks and pytest on Windows, generates icons,
builds a windowed onedir bundle, runs its self-test, zips it, computes SHA-256, and
attaches both artifacts to a GitHub Release using `softprops/action-gh-release`.

Repository social preview is a separate GitHub UI setting: Settings → General →
Social preview → upload `assets/social_preview.png`. No signing certificate is
included; releases are unsigned community builds.
