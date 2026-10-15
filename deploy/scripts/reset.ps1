<#
==============================================================================
 reset.ps1 —— 【危险】清空全部数据并重建环境
------------------------------------------------------------------------------
 本脚本会执行 docker compose down -v，删除以下具名卷中的全部数据：
   gz_postgres_data（gz_odoo / gz_platform / superset 三个库）
   gz_redis_data、gz_minio_data、gz_es_data、gz_odoo_data、gz_superset_data
 删除后不可恢复！执行前请先备份：.\scripts\backup.ps1
------------------------------------------------------------------------------
 用法：
   .\scripts\reset.ps1          # 交互式二次确认（依次输入 YES 和 DELETE）
   .\scripts\reset.ps1 -Yes     # 跳过确认（仅供 CI / 自动化，慎用）
==============================================================================
#>
[CmdletBinding()]
param([switch]$Yes)

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

$volumes = @('gz_postgres_data', 'gz_redis_data', 'gz_minio_data', 'gz_es_data', 'gz_odoo_data', 'gz_superset_data')

Write-Host '############################################################' -ForegroundColor Red
Write-Host '#  【危险操作】即将删除全部数据卷，数据不可恢复！          #' -ForegroundColor Red
Write-Host '############################################################' -ForegroundColor Red
Write-Host '将删除的卷：'
foreach ($v in $volumes) {
    & docker volume inspect $v *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  - $v （存在，将被删除）" -ForegroundColor Yellow
    } else {
        Write-Host "  - $v （不存在，跳过）"
    }
}
Write-Host ''

if (-not $Yes) {
    $reply = Read-Host '确认要删除以上全部数据吗？请输入大写 YES 继续，其他任意输入取消'
    if ($reply -ne 'YES') { Write-Host '已取消，未做任何修改。'; exit 0 }
    $reply2 = Read-Host '再次确认（最后一次机会）：请输入 DELETE 执行删除'
    if ($reply2 -ne 'DELETE') { Write-Host '已取消，未做任何修改。'; exit 0 }
}

Write-Host '==> 1/3 停止并移除容器、网络、数据卷（docker compose down -v）' -ForegroundColor Cyan
Invoke-ComposeRaw down -v --remove-orphans

Write-Host '==> 2/3 清理残留的具名卷' -ForegroundColor Cyan
foreach ($v in $volumes) {
    & docker volume inspect $v *> $null
    if ($LASTEXITCODE -eq 0) {
        & docker volume rm -f $v *> $null
        if ($LASTEXITCODE -eq 0) { Write-Host "    已删除 $v" } else { Write-Warning "卷 $v 删除失败（可能仍被其他容器占用）" }
    }
}

Write-Host '==> 3/3 重新构建并启动' -ForegroundColor Cyan
Invoke-ComposeRaw up -d --build

Write-Host ''
Write-Host '重置完成。当前状态：'
Invoke-ComposeRaw ps
Write-Host @'

后续步骤：
  1) 等待全部服务 healthy：.\scripts\logs.ps1 postgres
  2) 初始化业务数据：.\scripts\init-data.ps1
  3) 首次登录后立即修改 Odoo 与 Superset 管理员密码
'@
