# OLLM-CRYPT-SEC Upstream Sync

This directory contains scripts to safely sync your OLLM-CRYPT-SEC repository with the upstream `jonigl/mcp-client-for-ollama` repository while preserving all your security audit customizations and enhancements.

## 🚀 Quick Start

```bash
# Make sure you're in the OLLM-CRYPT-SEC repository root
cd /home/dok/tools/ollm-crypt-sec

# Run the sync script
./sync_upstream.sh
```

## 📁 Files

- **`sync_upstream.sh`** - Main sync script (comprehensive, production-ready)
- **`update_from_upstream.sh`** - Simple update script (basic version)
- **`ollm_aliases.sh`** - Convenient shell aliases
- **`quick_sync.sh`** - One-liner wrapper
- **`UPSTREAM_SYNC_README.md`** - This documentation

## 🔒 Safety Guarantees

- ✅ **Never pushes your changes to upstream** - Upstream remote is set to fetch-only
- ✅ **Preserves your audit customizations** - All your security tools and configs are safe
- ✅ **Automatic backups** - Creates backup branches before every merge
- ✅ **Stash protection** - Safely handles uncommitted changes
- ✅ **Conflict handling** - Graceful handling of merge conflicts
- ✅ **Complete logging** - Full activity log in `sync_upstream.log`
- ✅ **Easy rollback** - Simple commands to undo if needed

## 🎯 What the Script Does

1. **Safety Checks**
   - Verifies you're in the correct repository
   - Checks for uncommitted changes
   - Offers to stash changes temporarily

2. **Remote Configuration**
   - Ensures upstream remote points to `jonigl/mcp-client-for-ollama`
   - Sets upstream to fetch-only (prevents accidental pushes)

3. **Update Process**
   - Fetches latest changes from upstream
   - Shows you exactly what will be merged
   - Creates automatic backup branch
   - Performs the merge safely

4. **Post-Merge**
   - Restores any stashed changes
   - Provides clear next steps
   - Saves complete log of activities

## 🛡️ Your Security Customizations Protected

This script specifically preserves all your security audit enhancements:
- Custom audit agents and workflows
- Security configuration files
- Vulnerability detection tools
- Report templates and builders
- Chain analysis tools
- ML filtering capabilities

## 📊 Example Output

```
🚀 OLLM-CRYPT-SEC Upstream Sync Script
=======================================
📅 Mon Nov  4 21:35:00 PST 2025

✅ Confirmed: Running in OLLM-CRYPT-SEC repository
📍 Current branch: main
🔍 Checking upstream remote configuration...
✅ Upstream remote correctly configured
🔒 Ensuring upstream is fetch-only (safety measure)...
✅ Upstream remote set to fetch-only (cannot accidentally push)
📡 Fetching latest changes from upstream...
✅ Successfully fetched from upstream
📊 Checking for available updates...
📦 Found 3 new commits from upstream
```

## 🛠️ Advanced Usage

### Check for Updates (No Merge)
```bash
# Just check what's available
git fetch upstream
git log --oneline HEAD..upstream/main
```

### Manual Rollback
```bash
# If something goes wrong, rollback to backup
git reset --hard backup-before-sync-YYYYMMDD-HHMMSS
```

### Push Your Updates
```bash
# After successful sync, push to your fork
git push origin main
```

## ⚡ Quick Aliases

Source the aliases file for convenient shortcuts:

```bash
source ./ollm_aliases.sh

# Then use:
ollm-update        # Run the sync script
ollm-check         # Check for available updates
ollm-status        # Show repository status
ollm-push          # Push to your fork
ollm-audit         # Run full audit
ollm-audit-simple  # Run simple audit
```

## 🔍 Troubleshooting

### Merge Conflicts
If you encounter conflicts:
1. Edit the conflicted files (look for `<<<<<<<`, `=======`, `>>>>>>>`)
2. Remove conflict markers
3. `git add .`
4. `git commit`

### Undo Everything
```bash
git merge --abort                    # Cancel ongoing merge
git checkout backup-before-sync-*   # Go to backup branch
```

### View Sync History
```bash
tail -50 sync_upstream.log  # See recent sync activity
```

## 🎯 Repository Structure

Your OLLM-CRYPT-SEC repository includes:
- **Base MCP Client**: Core functionality from upstream
- **Security Audit Tools**: Your custom audit agents
- **Vulnerability Detection**: Advanced ML-based filtering
- **Report Generation**: Custom templates and builders
- **Chain Analysis**: Blockchain security auditing
- **Configuration Management**: Audit-specific configs

## 📝 Notes

- The script creates timestamped backup branches before each sync
- All activity is logged to `sync_upstream.log`
- Your security customizations never leave your local repository
- The upstream remote is permanently set to fetch-only for safety
- Your audit tools and configurations are always preserved

## 🚀 Upstream Repository

**Source**: `https://github.com/jonigl/mcp-client-for-ollama.git`
**Your Fork**: `https://github.com/avaloki108/ollm-crypt-sec.git`

---

**Happy syncing! 🎉** Your security audit tools will always have the latest upstream improvements while keeping all your custom security enhancements!