<#
==============================================================================
 init-data.ps1 —— 初始化业务数据（可重复执行，幂等）
------------------------------------------------------------------------------
 1) 自研平台种子数据：docker compose exec api python -m app.initial_data
 2) Odoo 模块安装：
      docker compose exec odoo odoo -d gz_odoo -i gz_platform_base,gz_merchant,
        gz_product,gz_inventory,gz_trade --stop-after-init
------------------------------------------------------------------------------
 用法：
   .\scripts\init-data.ps1               # 两件事都做
   .\scripts\init-data.ps1 -ApiOnly      # 只初始化平台种子数据
   .\scripts\init-data.ps1 -OdooOnly     # 只安装 Odoo 模块
   .\scripts\init-data.ps1 -Upgrade      # Odoo 用 -u（升级）而不是 -i（安装）

 安全说明：数据库密码不通过命令行传递（避免出现在进程列表与命令历史里），
           而是复用 compose 已注入容器的 POSTGRES_* 环境变量，由 Odoo 自行读取。
==============================================================================
#>
[CmdletBinding()]
param(
    [switch]$ApiOnly,
    [switch]$OdooOnly,
    [switch]$Upgrade
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DeployDir = (Resolve-Path (Join-Path $ScriptDir '..')).Path
Set-Location $DeployDir

$doApi = -not $OdooOnly
$doOdoo = -not $ApiOnly
$odooAction = if ($Upgrade) { '-u' } else { '-i' }

$useComposeV2 = $true
& docker compose version *> $null
if ($LASTEXITCODE -ne 0) { $useComposeV2 = $false }
function Invoke-ComposeRaw {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CmdArgs)
    if ($useComposeV2) { & docker compose @CmdArgs } else { & docker-compose @CmdArgs }
}
if (-not $useComposeV2 -and -not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    throw '未找到 docker compose（Compose v2）。'
}
if (-not (Test-Path (Join-Path $DeployDir '.env'))) {
    throw '未找到 .env，请先执行 .\scripts\start.ps1 生成。'
}

function Get-EnvValue {
    param([string]$Key, [string]$Default = '')
    $line = Get-Content (Join-Path $DeployDir '.env') -Encoding UTF8 |
            Where-Object { $_ -match "^\s*$([regex]::Escape($Key))=" } |
            Select-Object -Last 1
    if (-not $line) { return $Default }
    return (($line -split '=', 2)[1]).Trim().Trim('"').Trim("'")
}

$OdooDb      = Get-EnvValue 'ODOO_DB' 'gz_odoo'
$PlatformDb  = Get-EnvValue 'PLATFORM_DB' 'gz_platform'
$PgUser      = Get-EnvValue 'POSTGRES_USER' 'gz'
$GatewayPort = Get-EnvValue 'GATEWAY_PORT' '8080'

function Assert-ServiceRunning {
    param([string]$Service)
    $raw = (Invoke-ComposeRaw ps --format json 2>$null) -join "`n"
    $state = ''
    if ($raw.Trim()) {
        if ($raw.TrimStart().StartsWith('[')) {
            $items = $raw | ConvertFrom-Json
        } else {
            $items = $raw -split "`n" | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json }
        }
        $state = ($items | Where-Object { $_.Service -eq $Service } | Select-Object -First 1).State
    }
    if ($state -ne 'running') {
        throw "服务 $Service 未在运行（当前状态：$(if ($state) { $state } else { '未创建' })）。请先执行 .\scripts\start.ps1，并用 .\scripts\logs.ps1 $Service 排查。"
    }
}

# ---------------------------------------------------------------------------
# 1) 平台种子数据
# ---------------------------------------------------------------------------
if ($doApi) {
    Write-Host "==> [1/2] 初始化自研平台种子数据（库 $PlatformDb，schema gz）" -ForegroundColor Cyan
    Assert-ServiceRunning 'api'

    # 若迁移由 Alembic 管理，先升级到最新版本
    & docker compose exec -T api sh -lc 'command -v alembic >/dev/null 2>&1' *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host '    - 执行数据库迁移：alembic upgrade head'
        Invoke-ComposeRaw exec -T api alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw 'alembic upgrade head 失败，请检查 services/api 的迁移脚本与 DATABASE_URL。' }
    } else {
        Write-Host '    - 未检测到 alembic 命令，跳过迁移'
    }

    Write-Host '    - 执行种子数据：python -m app.initial_data'
    Invoke-ComposeRaw exec -T api python -m app.initial_data
    if ($LASTEXITCODE -ne 0) { throw 'app.initial_data 执行失败，请查看 .\scripts\logs.ps1 api 输出。' }
    Write-Host '    平台种子数据完成。首次登录后请立即修改管理员密码。' -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# 2) Odoo 模块安装
# ---------------------------------------------------------------------------
if ($doOdoo) {
    Write-Host "==> [2/2] 安装 / 升级 Odoo 自研模块（库 $OdooDb）" -ForegroundColor Cyan
    Assert-ServiceRunning 'odoo'

    $modules = 'gz_platform_base,gz_merchant,gz_product,gz_inventory,gz_trade'
    Write-Host "    动作：$odooAction $modules"
    Write-Host '    参数：--stop-after-init --without-demo=all --db_host=postgres --db_port=5432'

    # 连接参数由容器内已有的环境变量（compose 注入的 DB_NAME/USER/PASSWORD/HOST）提供，
    # 因此这里不传 --db_password，避免密码出现在命令行。
    Invoke-ComposeRaw exec -T odoo `
        odoo -d $OdooDb $odooAction $modules `
        --stop-after-init --without-demo=all `
        --db_host=postgres --db_port=5432 --db_user=$PgUser
    if ($LASTEXITCODE -ne 0) { throw 'Odoo 模块安装失败，请查看 .\scripts\logs.ps1 odoo 输出。' }

    Write-Host '    Odoo 模块处理完成。' -ForegroundColor Green
    Write-Host '    注意：--stop-after-init 会让 odoo 容器进程退出；'
    Write-Host '          restart: unless-stopped 会自动拉起，若未恢复请执行 docker compose restart odoo'
    Invoke-ComposeRaw up -d odoo *> $null
}

Write-Host ''
Write-Host '初始化流程结束。自检命令：' -ForegroundColor Cyan
@"

  # 平台侧表结构
  docker compose exec postgres psql -U $PgUser -d $PlatformDb -c "\dt gz.*"

  # Odoo 模块状态
  docker compose exec postgres psql -U $PgUser -d $OdooDb -c "SELECT name, state FROM ir_module_module WHERE name LIKE 'gz_%' ORDER BY name;"

  # 登录接口验证
  curl.exe -s -X POST http://localhost:$GatewayPort/api/v1/auth/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"<见文档>\"}"
"@ | Write-Host
