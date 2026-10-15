<#
==============================================================================
 stop.ps1 —— 停止全部服务（保留数据卷，数据不丢）
 用法：.\scripts\stop.ps1
==============================================================================
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DeployDir = (Resolve-Path (Join-Path $ScriptDir '..')).Path
Set-Location $DeployDir

$useComposeV2 = $true
try { & docker compose version *> $null; if ($LASTEXITCODE -ne 0) { $useComposeV2 = $false } }
catch { $useComposeV2 = $false }

function Invoke-ComposeRaw {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CmdArgs)
    if ($useComposeV2) { & docker compose @CmdArgs } else { & docker-compose @CmdArgs }
}

if (-not $useComposeV2 -and -not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    throw '未找到 docker compose（Compose v2）。'
}

Write-Host '==> 停止全部服务（数据卷 postgres_data / minio_data / odoo_data 等均保留）' -ForegroundColor Cyan
Invoke-ComposeRaw stop

Write-Host ''
Write-Host '已停止。当前状态：'
Invoke-ComposeRaw ps

Write-Host @'

提示：
  - 重新启动：.\scripts\start.ps1 -NoBuild
  - 彻底移除容器与网络（仍保留数据卷）：docker compose down
  - 清空全部数据（危险）：.\scripts\reset.ps1
'@
