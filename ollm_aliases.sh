# OLLM-CRYPT-SEC Repository Management Aliases
# Add these to your ~/.zshrc or run this script to set up convenient aliases

# Quick update from upstream
alias ollm-update="cd /home/dok/tools/ollm-crypt-sec && ./sync_upstream.sh"

# Check for available updates without merging
alias ollm-check="cd /home/dok/tools/ollm-crypt-sec && git fetch upstream && echo 'New commits available:' && git log --oneline HEAD..upstream/main || echo 'Already up to date!'"

# Show current status
alias ollm-status="cd /home/dok/tools/ollm-crypt-sec && echo '=== OLLM-CRYPT-SEC Repository Status ===' && git status && echo && echo '=== Recent commits ===' && git log --oneline -5"

# Push your local changes to your fork
alias ollm-push="cd /home/dok/tools/ollm-crypt-sec && git push origin main"

# Quick commit of all changes
alias ollm-commit="cd /home/dok/tools/ollm-crypt-sec && git add . && git commit"

# Run audit tools
alias ollm-audit="cd /home/dok/tools/ollm-crypt-sec && python run_audit.py"
alias ollm-audit-simple="cd /home/dok/tools/ollm-crypt-sec && python run_audit_simple.py"

echo "✅ OLLM-CRYPT-SEC aliases defined! You can now use:"
echo "   ollm-update      - Update from upstream"
echo "   ollm-check       - Check for available updates"
echo "   ollm-status      - Show repository status"
echo "   ollm-push        - Push to your fork"
echo "   ollm-commit      - Quick commit all changes"
echo "   ollm-audit       - Run full audit"
echo "   ollm-audit-simple - Run simple audit"