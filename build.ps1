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

# --- 0. 预检：关键文件是否齐全与释放运行占用 ----------------------------------------------
if (-not (Test-Path $Spec))    { throw "缺少打包配置 $Spec。" }
if (-not (Test-Path $CharSrc)) { throw "缺少角色资源目录 $CharSrc。" }
if (-not (Test-Path $IconPath)) {
    Write-Warning "未找到图标 $IconPath，快捷方式将使用 exe 自带图标。"
}

# 停止可能正在后台运行的桌宠进程，防止 exe / dll 文件占用导致构建覆盖失败
Get-Process -Name "DesktopPet" -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "    关闭正在运行的桌宠进程 (PID: $($_.Id))..." -ForegroundColor DarkYellow
    Stop-Process -Id $_.Id -Force
}
Start-Sleep -Milliseconds 800

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

# 同步更新本地安装目录（如 D:\AmiyaDesktopPet）
$InstalledDir = 'D:\AmiyaDesktopPet'
if (Test-Path $InstalledDir) {
    Write-Host "==> 同步最新构建至安装目录 $InstalledDir..." -ForegroundColor Yellow
    Copy-Item "$AppDir\*" $InstalledDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "    已更新安装目录: $InstalledDir" -ForegroundColor DarkGray
}

# --- 4. 刷新桌面快捷方式 ----------------------------------------------------
Write-Host '==> [3/4] 刷新桌面快捷方式...' -ForegroundColor Yellow
$wsh = New-Object -ComObject WScript.Shell

$shortcuts = @(
    (Join-Path $Desktop '桌面宠物.lnk'),
    (Join-Path $Desktop 'Amiya Desktop Pet.lnk')
)

foreach ($scPath in $shortcuts) {
    $lnk = $wsh.CreateShortcut($scPath)
    # 如果存在安装目录且快捷方式原本指向安装目录，则保留指向安装目录
    if ((Test-Path $InstalledDir) -and ($scPath -like "*Amiya Desktop Pet*")) {
        $lnk.TargetPath       = Join-Path $InstalledDir 'DesktopPet.exe'
        $lnk.WorkingDirectory = $InstalledDir
        $lnk.IconLocation     = if (Test-Path $IconPath) { "$IconPath,0" } else { "$(Join-Path $InstalledDir 'DesktopPet.exe'),0" }
    } else {
        $lnk.TargetPath       = $ExePath
        $lnk.WorkingDirectory = $AppDir
        $lnk.IconLocation     = if (Test-Path $IconPath) { "$IconPath,0" } else { "$ExePath,0" }
    }
    $lnk.Arguments        = ''
    $lnk.Description       = '阿米娅桌宠 · 支持将课件/讲义直接拖拽至此图标一键导入知识库'
    $lnk.Save()
    Write-Host "    已更新快捷方式: $scPath" -ForegroundColor DarkGray
}

# 清理历史遗留的旧快捷方式
$LegacyShortcut = Join-Path $Desktop 'AmiyaDesktopPet.lnk'
if (Test-Path $LegacyShortcut) {
    Remove-Item -Force $LegacyShortcut -ErrorAction SilentlyContinue
    Write-Host "    已清理历史遗留快捷方式: $LegacyShortcut" -ForegroundColor DarkGray
}

Write-Host '==> [4/4] 完成 ✅  桌面宠物已构建并更新，双击桌面快捷方式即可运行。' -ForegroundColor Green
