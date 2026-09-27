# -*- coding: utf-8 -*-
# 桌面宠物 —— 一键构建脚本
#
# 作用：重新用 PyInstaller 打包 DesktopPet.exe，同步角色资源（阿米娅 / 圣聆初雪
#       等），并刷新桌面「桌面宠物」快捷方式。每次改完功能直接跑这个脚本即可。
#
# 用法：直接双击 build.bat，或在此目录执行  powershell -ExecutionPolicy Bypass -File build.ps1

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# --- 路径配置（脚本所在目录即项目根目录）------------------------------------
$Root      = $PSScriptRoot
$Spec      = Join-Path $Root 'DesktopPet.spec'
$DistDir   = Join-Path $Root 'dist'
$AppDir    = Join-Path $DistDir 'DesktopPet'   # onedir 输出目录（exe + _internal）
$ExePath   = Join-Path $AppDir 'DesktopPet.exe'
$IconPath  = Join-Path $Root 'app.ico'
$CharSrc   = Join-Path $Root 'characters'
$CharDst   = Join-Path $AppDir 'characters'
$Desktop   = [Environment]::GetFolderPath('Desktop')
$Shortcut  = Join-Path $Desktop '桌面宠物.lnk'

Set-Location $Root
Write-Host '==> 桌面宠物构建开始' -ForegroundColor Cyan

# --- 0. 预检：关键文件是否齐全 ----------------------------------------------
if (-not (Test-Path $Spec))    { throw "缺少打包配置 $Spec。" }
if (-not (Test-Path $CharSrc)) { throw "缺少角色资源目录 $CharSrc。" }
if (-not (Test-Path $IconPath)) {
    Write-Warning "未找到图标 $IconPath，快捷方式将使用 exe 自带图标。"
}

# --- 1. 选择 Python 解释器 --------------------------------------------------
$Py = $null
foreach ($cand in @('python', 'py')) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) { $Py = $cand; break }
}
if (-not $Py) { throw '找不到 Python，请先安装并加入 PATH。' }
Write-Host "    使用解释器: $Py" -ForegroundColor DarkGray

# --- 2. 打包（PyInstaller 读取 DesktopPet.spec）-----------------------------
Write-Host '==> [1/4] 运行 PyInstaller 打包...' -ForegroundColor Yellow
& $Py -m PyInstaller --noconfirm --clean $Spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败（退出码 $LASTEXITCODE）。" }
if (-not (Test-Path $ExePath)) { throw "打包结束但未找到 $ExePath。" }

# --- 3. 同步角色资源到 dist\characters -------------------------------------
# main.py 在打包运行时优先读取 exe 旁边的 characters\，
# 所以每次构建都用源目录覆盖它，保证角色/配置是最新的。
# **排除敏感文件**：ai_config.json 可能含有 API key；.claude 是本地工具状态。
Write-Host '==> [2/4] 同步角色资源...' -ForegroundColor Yellow
if (Test-Path $CharDst) { Remove-Item $CharDst -Recurse -Force }
Copy-Item $CharSrc $CharDst -Recurse -Force
Get-ChildItem $CharDst -Recurse -Filter 'ai_config.json' -File |
    Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem $CharDst -Recurse -Directory -Filter '.claude' |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
$chars = Get-ChildItem $CharDst -Directory |
    Where-Object { Test-Path (Join-Path $_.FullName 'config.json') } |
    Select-Object -ExpandProperty Name
Write-Host "    已同步: $CharDst" -ForegroundColor DarkGray
Write-Host ("    角色（{0}个）: {1}" -f $chars.Count, ($chars -join ', ')) -ForegroundColor DarkGray

# --- 4. 刷新桌面与发送到快捷方式 -------------------------------------------
Write-Host '==> [3/4] 刷新桌面与系统快捷方式...' -ForegroundColor Yellow
$wsh = New-Object -ComObject WScript.Shell

# 优先同步到用户已安装的 D:\AmiyaDesktopPet 目录（若存在）
$InstalledDir = "D:\AmiyaDesktopPet"
$FinalExePath = $ExePath
$FinalAppDir  = $AppDir

if (Test-Path $InstalledDir) {
    Write-Host "    检测到现有安装目录: $InstalledDir，正在同步最新程序文件..." -ForegroundColor DarkGray
    Copy-Item (Join-Path $AppDir "DesktopPet.exe") (Join-Path $InstalledDir "DesktopPet.exe") -Force
    if (Test-Path (Join-Path $AppDir "_internal")) {
        Copy-Item (Join-Path $AppDir "_internal\*") (Join-Path $InstalledDir "_internal") -Recurse -Force
    }
    $FinalExePath = Join-Path $InstalledDir "DesktopPet.exe"
    $FinalAppDir  = $InstalledDir
    Write-Host "    已同步最新版本至: $InstalledDir" -ForegroundColor DarkGray
}

$DesktopShortcuts = @(
    Join-Path $Desktop 'Amiya Desktop Pet.lnk',
    Join-Path $Desktop '桌面宠物.lnk'
)

foreach ($sc in $DesktopShortcuts) {
    $lnk = $wsh.CreateShortcut($sc)
    $lnk.TargetPath       = $FinalExePath
    $lnk.Arguments        = ''
    $lnk.WorkingDirectory = $FinalAppDir
    $lnk.IconLocation     = if (Test-Path $IconPath) { "$IconPath,0" } else { "$FinalExePath,0" }
    $lnk.Description       = '阿米娅桌宠 · 支持将课件/讲义直接拖拽至此图标一键导入知识库'
    $lnk.Save()
    Write-Host "    已更新快捷方式: $sc" -ForegroundColor DarkGray
}

# 刷新资源管理器「发送到」快捷方式
$SendToDir = [Environment]::GetFolderPath('SendTo')
if (Test-Path $SendToDir) {
    $SendToLnk = Join-Path $SendToDir '导入到阿米娅课程知识库.lnk'
    $slnk = $wsh.CreateShortcut($SendToLnk)
    $slnk.TargetPath       = $FinalExePath
    $slnk.WorkingDirectory = $FinalAppDir
    $slnk.IconLocation     = if (Test-Path $IconPath) { "$IconPath,0" } else { "$FinalExePath,0" }
    $slnk.Description      = '将选中的课件/讲义导入阿米娅课程知识库'
    $slnk.Save()
    Write-Host "    已更新发送到快捷方式: $SendToLnk" -ForegroundColor DarkGray
}

# 清理历史遗留的旧快捷方式
$LegacyShortcut = Join-Path $Desktop 'AmiyaDesktopPet.lnk'
if (Test-Path $LegacyShortcut) {
    Remove-Item -Force $LegacyShortcut -ErrorAction SilentlyContinue
    Write-Host "    已清理历史遗留快捷方式: $LegacyShortcut" -ForegroundColor DarkGray
}

Write-Host '==> [4/4] 完成 ✅  桌面宠物已更新，双击桌面快捷方式即可运行。' -ForegroundColor Green
