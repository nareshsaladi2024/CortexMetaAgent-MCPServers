# Security Notice

## ⚠️ IMPORTANT: Credentials Exposed

If you see this message, it means that service account credentials or API keys were accidentally committed to this repository.

## Immediate Actions Required

1. **Rotate/Regenerate All Exposed Credentials**
   - Regenerate the service account key in Google Cloud Console
   - Revoke and regenerate any exposed API keys
   - Update all systems using the old credentials

2. **Remove Secrets from Git History**
   ```powershell
   # Option 1: Using git filter-branch (built-in)
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch mcp-servers/mcp-agent-inventory/your-service-account.json" \
     --prune-empty --tag-name-filter cat -- --all
   
   # Option 2: Using BFG Repo-Cleaner (faster, recommended)
   # Download from: https://rtyley.github.io/bfg-repo-cleaner/
   bfg --delete-files your-service-account.json
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive
   
   # Force push (WARNING: This rewrites history)
   git push --force origin main
   ```

3. **Verify Secrets Are Removed**
   - Check GitHub's security alerts
   - Verify no secrets appear in git log: `git log --all --full-history -- mcp-servers/**/*.json`

## Prevention

- ✅ Never commit `.env` files
- ✅ Never commit service account JSON files
- ✅ Use `.env.example` files with placeholder values
- ✅ Use `service-account.example.json` as templates
- ✅ Enable GitHub secret scanning
- ✅ Use environment variables or secret management services

## Current Protection

The `.gitignore` file is configured to ignore:
- `*.json` files (except package.json)
- `.env` files
- Service account files matching patterns: `*capstoneproject*.json`, `*service-account*.json`

## Reporting Security Issues

If you discover any security vulnerabilities, please report them privately rather than creating a public issue.

