$ErrorActionPreference = "Stop"

$gcloudCmd = Get-Command gcloud -ErrorAction SilentlyContinue
if ($gcloudCmd) {
    $gcloud = $gcloudCmd.Source
} else {
    $gcloud = "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
}

if (-not (Test-Path $gcloud)) {
    Write-Output "Could not find gcloud.cmd. Edit `$gcloud` at the top of this script to point at your install."
    exit 1
}

Write-Output "Using gcloud at: $gcloud"
Write-Output ""
Write-Output "Step 1/2: opening a browser window to log in and create Application Default Credentials..."
& $gcloud auth application-default login

$adcPath = "$env:APPDATA\gcloud\application_default_credentials.json"
if (-not (Test-Path $adcPath)) {
    Write-Output ""
    Write-Output "Login did not produce a credentials file at $adcPath - something went wrong, stopping."
    exit 1
}
Write-Output ""
Write-Output "Application Default Credentials saved to: $adcPath"

Write-Output ""
Write-Output "Step 2/2: setting the quota project to gen-lang-client-0133745072 (matches the script's project param)..."
& $gcloud auth application-default set-quota-project gen-lang-client-0133745072

Write-Output ""
Write-Output "Done. You can now run: uv run python scripts/test_vertex_genai.py"
