# Deploy NODAL Screen to Cloud Run. Holds no secrets.
#   .\deploy.ps1 [-Project <id>] [-DailyLiveRuns 10] [-MinInstances 0]
# -Project defaults to GOOGLE_CLOUD_PROJECT. Do not run this from a build task.
param(
    [string]$Project = $env:GOOGLE_CLOUD_PROJECT,
    [int]$DailyLiveRuns = 10,
    [int]$MinInstances = 0
)
# Not "Stop": Windows PowerShell 5.1 reports gcloud progress on stderr as errors.
$ErrorActionPreference = "Continue"
if ($Project) { $Project = $Project.Trim() }
if (-not $Project) { throw "Pass -Project or set GOOGLE_CLOUD_PROJECT." }

$envVars = "NODAL_LIVE_AI=0,NODAL_DAILY_LIVE_RUNS=$DailyLiveRuns"
$deployArgs = @(
    "run", "deploy", "nodal-screen",
    "--source", ".",
    "--project", $Project,
    "--region", "asia-southeast1",
    "--allow-unauthenticated",
    "--max-instances", "1",
    "--min-instances", "$MinInstances",
    "--set-env-vars", $envVars
)
gcloud @deployArgs
