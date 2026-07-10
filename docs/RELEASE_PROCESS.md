# PodFlow Release Process

## Versioning

PodFlow follows `MAJOR.MINOR.PATCH` (Semantic Versioning).

| Bump | When |
|---|---|
| **Patch** (0.5.0 → 0.5.1) | Bug fixes, no API changes |
| **Minor** (0.5.0 → 0.6.0) | New features, backward-compatible |
| **Major** (1.0.0) | Breaking changes, production-ready |

Current: **0.5.0** (pre-release beta).

## Release Checklist

### Before Release

- [ ] All tests pass: `pytest tests/ -v`
- [ ] Quality gates pass: `pre-commit run --all-files`
- [ ] CI is green on `main`
- [ ] Documentation is up to date (`docs/`)
- [ ] Migrations are current: `alembic current`
- [ ] `pyproject.toml` version is bumped

### Release Steps

```bash
# 1. Bump version in pyproject.toml
#    [project]
#    version = "0.6.0"

# 2. Verify everything
pip install -e ".[dev]"
pytest tests/ -v
pre-commit run --all-files

# 3. Commit and tag
git add -A
git commit -m "release: v0.6.0"
git tag -a v0.6.0 -m "PodFlow v0.6.0 — <summary>"

# 4. Push
git push origin main
git push origin v0.6.0

# 5. Create GitHub Release
#    - Title: v0.6.0
#    - Describe changes since last release
#    - Attach any artifacts if needed
```

### Release Notes Template

```markdown
## What's New

- Feature A
- Feature B

## Changes

- Updated X to support Y
- Removed deprecated Z

## Fixes

- Fixed bug in downloader retry logic

## Migration

- Run `alembic upgrade head` if schema changed
- No breaking changes (or: see below)
```

## Hotfix Process

For critical production fixes between releases:

```bash
git checkout main
git checkout -b hotfix/description
# ... fix ...
git commit -m "hotfix: description"
git push origin hotfix/description
# Create PR → merge to main
# Tag with patch bump: v0.5.1
```

## Rollback

If a release causes issues:

```bash
# Revert to previous tag
git checkout v0.5.0

# Or downgrade migrations
alembic downgrade -1
```
