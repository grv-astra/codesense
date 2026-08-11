# Azure DevOps CI/CD integration

Code Sense scans can be triggered from an Azure DevOps pipeline using a project-scoped
API key instead of a human login. This reuses the same scan endpoints the web app uses —
there is no separate CI-only report format, and results always land in the app's normal
scan history for the target project.

## 1. Generate an API key

In the app, open the project → **Settings** tab → **CI API Keys** → **Generate new key**.
Copy the plaintext value shown — it is never shown again. (Alternatively, from the server:
`python manage.py create_api_key --project <project-id> --name "azure-devops-prod"`.)

Store these as secret pipeline variables in Azure DevOps:

- `CODESENSE_API_URL` — base URL of the reachable Code Sense instance (leave unset/empty
  if the app is not reachable from this pipeline's agents — see "If the app isn't
  reachable" below)
- `CODESENSE_API_KEY` — the generated `csk_...` key
- `CODESENSE_PROJECT_ID` — the project ID the key is bound to

## 2. Zip mode (recommended — scans the pipeline's exact checkout)

```yaml
steps:
  - task: PowerShell@2
    displayName: 'Package workspace for Code Sense scan'
    inputs:
      targetType: inline
      script: |
        Compress-Archive -Path "$(Build.SourcesDirectory)\*" -DestinationPath "$(Build.ArtifactStagingDirectory)\codesense-scan.zip" -Force

  - task: PublishPipelineArtifact@1
    displayName: 'Publish scan payload as a pipeline artifact'
    inputs:
      targetPath: '$(Build.ArtifactStagingDirectory)\codesense-scan.zip'
      artifact: 'codesense-scan-payload'

  - task: PowerShell@2
    displayName: 'Submit scan to Code Sense (if reachable)'
    condition: ne(variables['CODESENSE_API_URL'], '')
    inputs:
      targetType: inline
      script: |
        $ErrorActionPreference = 'Stop'
        $zipPath = "$(Build.ArtifactStagingDirectory)\codesense-scan.zip"
        $uri = "$(CODESENSE_API_URL)/api/scans/create/"

        $form = @{
          scan_name  = "$(Build.Repository.Name)-$(Build.SourceBranchName)"
          project_id = "$(CODESENSE_PROJECT_ID)"
          zip_file   = Get-Item -Path $zipPath
        }

        try {
          $response = Invoke-RestMethod -Uri $uri -Method Post -Form $form `
            -Headers @{ Authorization = "Bearer $(CODESENSE_API_KEY)" }
          Write-Host "Code Sense scan submitted: $($response | ConvertTo-Json -Compress)"
        } catch {
          Write-Error "Code Sense scan submission failed: $($_.Exception.Message)"
          exit 1
        }
```

The artifact-publish step always runs, with zero dependency on the app being reachable —
it never fails for network reasons. The submission step only runs when
`CODESENSE_API_URL` is set, and **fails the pipeline step (non-zero exit) on any
non-2xx response** — a revoked key, wrong project, or unreachable app all surface as a
loud, visible pipeline failure rather than silently doing nothing. This is a submission
check only, not a build gate: a scan that submits successfully and later reports findings
still does not fail the build.

## 3. Repo-clone mode (alternative — app clones the repo itself)

```yaml
  - task: PowerShell@2
    displayName: 'Trigger Code Sense scan via repo clone'
    inputs:
      targetType: inline
      script: |
        $ErrorActionPreference = 'Stop'
        $uri = "$(CODESENSE_API_URL)/api/scans/github/"
        $body = @{
          token      = "$(CODESENSE_GIT_TOKEN)"
          username   = "$(CODESENSE_GIT_OWNER)"
          repo       = "$(Build.Repository.Name)"
          branch     = "$(Build.SourceBranchName)"
          project_id = "$(CODESENSE_PROJECT_ID)"
        } | ConvertTo-Json

        try {
          $response = Invoke-RestMethod -Uri $uri -Method Post -Body $body -ContentType 'application/json' `
            -Headers @{ Authorization = "Bearer $(CODESENSE_API_KEY)" }
          Write-Host "Code Sense scan submitted: $($response | ConvertTo-Json -Compress)"
        } catch {
          Write-Error "Code Sense scan submission failed: $($_.Exception.Message)"
          exit 1
        }
```

Requires the app to have network access to the git host — use zip mode instead if that's
not the case, or if you want to scan the pipeline's exact checkout rather than a fresh
clone of the pushed branch.

## 4. If the app isn't reachable from CI

Leave `CODESENSE_API_URL` unset — the submission step is skipped (via its `condition`)
and only the artifact-publish step runs, which has no network dependency. The
`codesense-scan-payload` artifact stays available in the pipeline run. Later, from
anywhere that *can* reach the app (a person's machine, a scheduled job with both artifact
and network access), download that artifact and run the same `Invoke-RestMethod` POST
from step 2 by hand or via script, using the same `CODESENSE_API_KEY`. No separate
"import" endpoint exists — it's the same `/api/scans/create/` call, just made later from
a different place.

## 5. Storing and rotating the key

The key is a long-lived credential with no automatic expiry — store it only in Azure
DevOps's secret pipeline variables (never in the YAML file itself, never logged). If a
pipeline step's output could echo the key (e.g. verbose logging), mark the variable as
secret so Azure DevOps redacts it automatically. Revoke and regenerate a key from the
same **Settings → CI API Keys** panel (or `manage.py create_api_key` again for a fresh
one) if it's ever suspected of being exposed — revocation is immediate.
