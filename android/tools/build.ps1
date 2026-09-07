# Build script for AmiyaPet Android
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$RepeatTools = 'D:\Dev\project\RepeatAPP\.tools'
$env:GRADLE_USER_HOME = Join-Path $RepeatTools 'gradle-home'
$env:ANDROID_USER_HOME = Join-Path $RepeatTools 'android-user'
$env:ANDROID_HOME = Join-Path $RepeatTools 'android-sdk'
if (-not $env:JAVA_HOME) { $env:JAVA_HOME = 'C:\Program Files\Java\jdk-21.0.11' }

$gradle = Join-Path $RepeatTools 'gradle-8.10.2\bin\gradle.bat'
Write-Host "Building AmiyaPet Android with local Gradle and SDK..."
& $gradle assembleDebug --no-daemon --console=plain --offline
exit $LASTEXITCODE
