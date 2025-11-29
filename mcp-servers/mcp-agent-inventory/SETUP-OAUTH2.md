# Setting Up OAuth2 Authentication for Reasoning Engine API

The Reasoning Engine API requires OAuth2 authentication (not API keys). Here are two ways to set it up:

## Option 1: Service Account (Recommended)

You already have a service account JSON file. Use it by setting `GOOGLE_APPLICATION_CREDENTIALS`:

### In your `.env` file:
```env
GOOGLE_APPLICATION_CREDENTIALS=C:\AI Agents\Day5\sample_agent\your-service-account.json
```

### Or in PowerShell (for current session):
```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\AI Agents\Day5\sample_agent\your-service-account.json"
```

### Or set it permanently (User environment variable):
```powershell
[Environment]::SetEnvironmentVariable("GOOGLE_APPLICATION_CREDENTIALS", "C:\AI Agents\Day5\sample_agent\your-service-account.json", "User")
```

## Option 2: Application Default Credentials (User Account)

If you prefer to use your user account instead of a service account:

### Step 1: Authenticate with gcloud
```powershell
gcloud auth application-default login
```

This will:
- Open a browser for you to sign in
- Store credentials in a default location
- Allow the server to use your user account credentials

### Step 2: Set quota project (if needed)
```powershell
gcloud auth application-default set-quota-project aiagent-capstoneproject
```

## Verify Your Setup

After setting up, verify it works:

```powershell
# Check if the environment variable is set
echo $env:GOOGLE_APPLICATION_CREDENTIALS

# Or test with Python
python -c "from google.auth import default; creds, project = default(); print(f'Authenticated as: {creds.service_account_email if hasattr(creds, \"service_account_email\") else \"User account\"}')"
```

## Troubleshooting

### Error: "Authentication failed"
- Make sure `GOOGLE_APPLICATION_CREDENTIALS` points to a valid JSON file
- Or run `gcloud auth application-default login` if using user account

### Error: "Permission denied"
- The service account or user account needs these roles:
  - `roles/aiplatform.user` (to list reasoning engines)
  - `roles/monitoring.viewer` (to view usage metrics)

### Error: "Quota project not set"
- Run: `gcloud auth application-default set-quota-project aiagent-capstoneproject`


