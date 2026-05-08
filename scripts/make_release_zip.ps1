$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$version = (Get-Content (Join-Path $projectRoot "VERSION") -Raw).Trim()
$distDir = Join-Path $projectRoot "dist"
$zipPath = Join-Path $distDir "pdf_binding_sample_tool_v$version.zip"
$stagingDir = Join-Path $env:TEMP "pdf_binding_sample_tool_release_$version"

if (Test-Path $stagingDir) {
    Remove-Item -LiteralPath $stagingDir -Recurse -Force
}

if (!(Test-Path $distDir)) {
    New-Item -ItemType Directory -Path $distDir | Out-Null
}

New-Item -ItemType Directory -Path $stagingDir | Out-Null

$excludedDirectories = @(".venv", "__pycache__", "dist", ".git")
$excludedFiles = @("streamlit_stdout.log", "streamlit_stderr.log")

Get-ChildItem -LiteralPath $projectRoot -Force | ForEach-Object {
    if ($_.PSIsContainer -and ($excludedDirectories -contains $_.Name)) {
        return
    }

    if (!$_.PSIsContainer -and ($excludedFiles -contains $_.Name)) {
        return
    }

    Copy-Item -LiteralPath $_.FullName -Destination $stagingDir -Recurse -Force
}

if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

Compress-Archive -Path (Join-Path $stagingDir "*") -DestinationPath $zipPath
Remove-Item -LiteralPath $stagingDir -Recurse -Force

Write-Host "Release ZIP created:"
Write-Host $zipPath
