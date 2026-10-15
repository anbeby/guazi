<#
==============================================================================
 start.ps1 —— 一键启动全栈（Windows PowerShell 版）
 用法：
   .\scripts\start.ps1                      # 构建并启动
   .\scripts\start.ps1 -NoBuild             # 不重新构建镜像
   .\scripts\start.ps1 -WaitSeconds 900     # 加长健康等待时间
   .\scripts\start.ps1 -AllowDefaultSecrets # 本机演示：允许直接使用模板默认密码
------------------------------------------------------------------------------
 与 start.sh 等价；不会删除任何数据卷。清空数据请用 .\scripts\reset.ps1
==============================================================================
#>
[CmdletBinding()]
param(
    [switch]$NoBuild,
    [switch]$AllowDefaultSecrets,
    [int]$WaitSeconds = 600
)

$ErrorActionPreference = 'Stop'

# 切换到 deploy 目录（脚本上级目录），保证 compose 能找到 .env 与 conf/
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DeployDir = (Resolve-Path (Join-Path $ScriptDir '..')).Path
Set-Location $DeployDir

# ---------------------------------------------------------------------------
# 读取 .env 中某个键（不 dot-source，避免执行文件内容带来的风险）
# ---------------------------------------------------------------------------
function Get-EnvValue {
    param([string]$Key, [string]$Default = '')
    if (-not (Test-Path (Join-Path $DeployDir '.env'))) { return $Default }
    $line = Get-Content (Join-Path $DeployDir '.env') -Encoding UTF8 |
            Where-Object { $_ -match "^\s*$([regex]::Escape($Key))=" } |
            Select-Object -Last 1
    if (-not $line) { return $Default }
    $v = ($line -split '=', 2)[1]
    return $v.Trim().Trim('"').Trim("'")
}

Write-Host '==> [1/5] 检查 Docker 环境' -ForegroundColor Cyan
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw '未找到 docker 命令。请安装 Docker Desktop（含 Compose v2）并确保其正在运行。'
}
& docker info *> $null
if ($LASTEXITCODE -ne 0) { throw '无法连接 Docker 守护进程，请先启动 Docker Desktop / dockerd。' }

# 优先使用 Compose v2 插件（docker compose），否则回退到独立可执行文件 docker-compose
$useComposeV2 = $true
& docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    $useComposeV2 = $false
    if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
        throw '未找到 docker compose（Compose v2 插件）也未找到 docker-compose，请先安装 Docker Compose v2。'
    }
    Write-Warning '检测到旧版 docker-compose，建议升级到 Compose v2（docker compose）。'
}
function Invoke-Compose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CmdArgs)
    if ($useComposeV2) { & docker compose @CmdArgs } else { & docker-compose @CmdArgs }
    if ($LASTEXITCODE -ne 0) { throw "compose 命令失败：$($CmdArgs -join ' ')" }
}
# 不带失败抛出的版本（用于 ps / config 这类允许非零退出的调用）
function Invoke-ComposeRaw {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CmdArgs)
    if ($useComposeV2) { & docker compose @CmdArgs } else { & docker-compose @CmdArgs }
}
Write-Host "    docker: $((& docker --version) -join '')"

Write-Host '==> [2/5] 检查环境变量文件 .env' -ForegroundColor Cyan
$envPath = Join-Path $DeployDir '.env'
$envExample = Join-Path $DeployDir '.env.example'
if (-not (Test-Path $envPath)) {
    if (-not (Test-Path $envExample)) { throw "既没有 .env 也没有 .env.example，无法继续：" + $DeployDir }
    Copy-Item $envExample $envPath
    Write-Host '    已从 .env.example 生成 .env（含默认演示密码）。' -ForegroundColor Yellow
    Write-Host "    ！！请立即编辑 $envPath，修改所有标注【请务必修改】的密码与密钥。！！" -ForegroundColor Yellow
    if (-not $AllowDefaultSecrets) {
        Write-Host '    已停止启动，避免把默认密码带到共享环境。' -ForegroundColor Yellow
        Write-Host '    仅本机演示可重新执行：.\scripts\start.ps1 -AllowDefaultSecrets' -ForegroundColor Yellow
        exit 0
    }
    Write-Host '    已指定 -AllowDefaultSecrets，继续使用默认密码启动（仅限本机演示）。' -ForegroundColor Yellow
}

$GatewayPort      = Get-EnvValue 'GATEWAY_PORT' '8080'
$SupersetPort     = Get-EnvValue 'SUPERSET_PORT' '8088'
$OdooPort         = Get-EnvValue 'ODOO_PORT' '8069'
$MinioConsolePort = Get-EnvValue 'MINIO_CONSOLE_PORT' '9001'
$MinioApiPort     = Get-EnvValue 'MINIO_API_PORT' '9000'

Write-Host '==> [3/5] 校验配置并构建镜像（首次构建约 3~10 分钟）' -ForegroundColor Cyan
Invoke-Compose config -q
$upArgs = @('up', '-d')
if (-not $NoBuild) { $upArgs += '--build' }
Invoke-Compose @upArgs

Write-Host "==> [4/5] 等待服务健康（最多 ${WaitSeconds}s）" -ForegroundColor Cyan
Write-Host '    说明：minio-init / superset-init 是一次性任务，Exited(0) 属正常。'
$deadline = (Get-Date).AddSeconds($WaitSeconds)
while ((Get-Date) -lt $deadline) {
    $pending = @()
    try {
        $raw = (Invoke-ComposeRaw ps --format json 2>$null) -join "`n"
        $items = @()
        if ($raw.Trim()) {
            # Docker Compose v2 输出可能是流式 JSON 行（每行一个对象），也可能是 JSON 数组
            if ($raw.TrimStart().StartsWith('[')) {
                $items = $raw | ConvertFrom-Json
            } else {
                $items = $raw -split "`n" | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json }
            }
        }
        foreach ($it in $items) {
            $svc = $it.Service
            $state = $it.State
            $health = $it.Health
            if ($state -eq 'running' -and $health -and $health -ne 'healthy') {
                $pending += "$svc`:$health"
            } elseif ($state -and $state -ne 'running' -and $state -ne 'exited') {
                $pending += "$svc`:$state"
            }
        }
    } catch {
        $pending = @('（无法解析 compose ps 输出，继续等待）')
    }
    if ($pending.Count -eq 0) {
        Write-Host '    所有服务已就绪。' -ForegroundColor Green
        break
    }
    Write-Host ("    等待中... 未就绪: " + ($pending -join ', '))
    Start-Sleep -Seconds 5
}

Write-Host '==> [5/5] 当前服务状态' -ForegroundColor Cyan
Invoke-ComposeRaw ps

@"

================================================================================
  启动完成，访问入口如下（服务器部署请把 localhost 换成实际 IP / 域名）
--------------------------------------------------------------------------------
  统一网关（推荐入口）    http://localhost:$GatewayPort
  平台 API 文档           http://localhost:$GatewayPort/api/docs
  API 健康检查            http://localhost:$GatewayPort/health
  Odoo ERP                http://localhost:$GatewayPort/odoo
  Superset BI             http://localhost:$GatewayPort/superset   （直连 :$SupersetPort）
  MinIO 控制台            http://localhost:$MinioConsolePort     （S3 API :$MinioApiPort）
  Odoo 直连（调试）       http://localhost:$OdooPort

  首次使用请初始化数据：
      .\scripts\init-data.ps1        # 平台种子数据 + Odoo 模块安装
  账号密码见 deploy\.env（ODOO_ADMIN_USER / ODOO_ADMIN_PASSWD / SUPERSET_ADMIN_*）
--------------------------------------------------------------------------------
  查看日志：.\scripts\logs.ps1 [服务名]
  停止服务：.\scripts\stop.ps1        停止并清空数据：.\scripts\reset.ps1
  数据备份：.\scripts\backup.ps1
================================================================================
"@ | Write-Host
