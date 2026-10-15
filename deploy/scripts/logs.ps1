<#
==============================================================================
 logs.ps1 —— 跟随查看容器日志
------------------------------------------------------------------------------
 用法：
   .\scripts\logs.ps1                    # 跟随全部服务日志
   .\scripts\logs.ps1 api                # 只看 api
   .\scripts\logs.ps1 api,worker         # 看多个服务
   .\scripts\logs.ps1 odoo -Tail 200     # 指定初始行数（默认 100）
   .\scripts\logs.ps1 es -Since 30m

 服务名可选值（与 docker-compose.yml 一致）：
   postgres redis minio minio-init elasticsearch odoo api worker admin-web
   superset superset-init nginx
==============================================================================
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$Service,
    [int]$Tail = 100,
    [string]$Since = ''
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DeployDir = (Resolve-Path (Join-Path $ScriptDir '..')).Path
Set-Location $DeployDir

$useComposeV2 = $true
& docker compose version *> $null
if ($LASTEXITCODE -ne 0) { $useComposeV2 = $false }
function Invoke-Compose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CmdArgs)
    if ($useComposeV2) { & docker compose @CmdArgs } else { & docker-compose @CmdArgs }
}
if (-not $useComposeV2 -and -not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    throw '未找到 docker compose（Compose v2）。'
}
if (-not (Test-Path (Join-Path $DeployDir '.env'))) { throw '未找到 .env。' }

# 支持 "api,worker" 与 "api worker" 两种写法
$services = @()
foreach ($s in $Service) {
    if ($s) { $services += ($s -split ',' | Where-Object { $_.Trim() } | ForEach-Object { $_.Trim() }) }
}

$logArgs = @('logs', '-f', '--tail', "$Tail")
if ($Since) { $logArgs += @('--since', $Since) }

if ($services.Count -eq 0) {
    Write-Host '==> 跟随全部服务日志（Ctrl+C 退出）' -ForegroundColor Cyan
    Invoke-Compose @logArgs
    exit $LASTEXITCODE
}

$valid = (Invoke-Compose config --services 2>$null)
foreach ($s in $services) {
    if ($valid -notcontains $s) {
        throw "未知服务 '$s'。可用服务：$($valid -join ', ')"
    }
}
Write-Host "==> 跟随日志：$($services -join ', ')（Ctrl+C 退出）" -ForegroundColor Cyan
Invoke-Compose @logArgs @services
exit $LASTEXITCODE
