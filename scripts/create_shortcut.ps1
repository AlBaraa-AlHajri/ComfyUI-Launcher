param([string]$ExePath = '')
$ErrorActionPreference = 'Stop'
if (-not $ExePath) {
    $besideScript = Join-Path $PSScriptRoot 'ComfyUI-Launcher.exe'
    $ExePath = if (Test-Path -LiteralPath $besideScript) { $besideScript } else {
        Join-Path $PSScriptRoot '..\dist\ComfyUI-Launcher\ComfyUI-Launcher.exe'
    }
}
$resolvedExe = (Resolve-Path -LiteralPath $ExePath).Path
$shell = New-Object -ComObject WScript.Shell
$desktopFolder = [Environment]::GetFolderPath('Desktop')
$startMenuFolder = Join-Path ([Environment]::GetFolderPath('Programs')) 'ComfyUI Launcher'
New-Item -ItemType Directory -Path $startMenuFolder -Force | Out-Null
# Use the embedded icon so shortcuts survive folder relocation as a bundle.
# استخدام الأيقونة المضمنة مع الملف التنفيذي.
foreach ($folder in @($desktopFolder, $startMenuFolder)) {
    $shortcut = $shell.CreateShortcut((Join-Path $folder 'ComfyUI Launcher.lnk'))
    $shortcut.TargetPath = $resolvedExe
    $shortcut.WorkingDirectory = Split-Path -LiteralPath $resolvedExe
    $shortcut.IconLocation = "$resolvedExe,0"
    $shortcut.Description = 'Open ComfyUI in a desktop app window'
    $shortcut.Save()
}
Write-Output 'Created Desktop and Start Menu shortcuts.'
