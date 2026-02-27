# Quick‑start command cheat sheet

## Set up remotes (run once)
```
git remote add upstream https://github.com/<org>/<repo>.git
git remote -v
```

## Import public → VA sync branch
```
git fetch upstream main
git checkout -B sync/public upstream/main
git push origin sync/public
```


## Export curated commits VA → public (direct push)
```
git checkout -B export/public va/main
```

## Cherry-pick only the commits you want public:
```
git cherry-pick <commit1> <commit2> ...
```

## Push curated branch to public main via explicit refspec:
```
git push upstream export/public:main
```

## Patch‑based export (air‑gap friendly)
```
# On VA side: generate patches for commits to export
git format-patch <base>..export/public -o patches/
# On a machine with outbound access: apply and push
git am patches/*.patch
git push upstream main
```

## Import public → VA sync branch then Export curated commits VA → public
Assumptions
- Default branch name: main
- No Git LFS
- Exports are manual (you’ll choose which commits to publish)
- GitHub Actions are enabled (optional automation not required for these commands)

### 1) Import public → VA sync branch
```
# Add public remote (run once)
git remote add upstream https://github.com/<org>/<repo>.git

# Fetch latest from GitHub.com public repo
git fetch upstream main

# Create/refresh the VA mirror branch to exactly match upstream/main
git checkout -B sync/public upstream/main

# Publish/refresh the sync branch inside VA GitHub Enterprise
git push origin sync/public
```

### 2) Export curated commits VA → public
```
# Start (or refresh) your export branch from internal work
git checkout -B export/public va/main

# Curate the export: cherry-pick only the commits that are allowed to go public
git cherry-pick <commit1> <commit2> ...

# Push the curated export branch to public main via explicit refspec
# (local export/public → remote main). This sends only what you intend.
git push upstream export/public:main
```