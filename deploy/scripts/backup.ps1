<#
==============================================================================
 backup.ps1 —— 备份 PostgreSQL 业务库（gz_odoo / gz_platform）
------------------------------------------------------------------------------
 输出目录：deploy\backups\
 文件名：  gz_odoo_20240612_183000.dump / gz_platform_20240612_183000.dump
 格式：    pg_dump -Fc（自定义格式，压缩、支持选择性还原）
 保留策略：默认每个库保留最近 7 份，更早的自动删除
------------------------------------------------------------------------------
 用法：
   .\scripts\backup.ps1                     # 备份两个库，保留最近 7 份
   .\scripts\backup.ps1 -Keep 14            # 保留最近 14 份
   .\scripts\backup.ps1 -WithOdooData       # 额外打包 Odoo filestore 具名卷
------------------------------------------------------------------------------
 编码注意：本脚本用 PowerShell 重定向 (>) 写入 .dump 文件。若你的 PowerShell
   版本对原生命令重定向使用 UTF-16 编码（PowerShell 5.1 的 > 会写 UTF-16LE），
   会导致 pg_restore 无法读取。此时请改用备份脚本的 bash 版本（WSL/Git Bash）：
       bash scripts/backup.sh
   或手工执行（cmd.exe 重定向为二进制安全）：
       docker compose exec -T postgres pg_dump -U gz -Fc gz_odoo > backups\gz_odoo.dump
   判断方法：文件头应为 "PGDMP"；若看到 0x50 0x00 0x47 0x00 即为 UTF-16。
==============================================================================
#>
[CmdletBinding()]
param(
    [int]$Keep = 7,
    [switch]$WithOdooData
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DeployDir = (Resolve-Path (Join-Path $ScriptDir '..')).Path
Set-Location $DeployDir

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

function Get-EnvValue {
    param([string]$Key, [string]$Default = '')
    $line = Get-Content (Join-Path $DeployDir '.env') -Encoding UTF8 |
            Where-Object { $_ -match "^\s*$([regex]::Escape($Key))=" } |
            Select-Object -Last 1
    if (-not $line) { return $Default }
    return (($line -split '=', 2)[1]).Trim().Trim('"').Trim("'")
}

if (-not (Test-Path (Join-Path $DeployDir '.env'))) { throw '未找到 .env。' }
$PgUser     = Get-EnvValue 'POSTGRES_USER' 'gz'
$OdooDb     = Get-EnvValue 'ODOO_DB' 'gz_odoo'
$PlatformDb = Get-EnvValue 'PLATFORM_DB' 'gz_platform'

$BackupDir = Join-Path $DeployDir 'backups'
if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir | Out-Null }
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'

# 检查 postgres 是否运行
$raw = (Invoke-ComposeRaw ps --format json 2>$null) -join "`n"
$items = @()
if ($raw.Trim()) {
    if ($raw.TrimStart().StartsWith('[')) { $items = $raw | ConvertFrom-Json }
    else { $items = $raw -split "`n" | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json } }
}
$pgState = ($items | Where-Object { $_.Service -eq 'postgres' } | Select-Object -First 1).State
if ($pgState -ne 'running') {
    throw "postgres 服务未运行（当前：$(if ($pgState) { $pgState } else { '未创建' })），无法备份。"
}

Write-Host "==> 备份目录：$BackupDir" -ForegroundColor Cyan
Write-Host "==> 时间戳：$Stamp"

function Backup-Database {
    param([string]$Db)
    $file = Join-Path $BackupDir "${Db}_${Stamp}.dump"
    Write-Host "    - 导出 $Db -> $(Split-Path -Leaf $file)"
    # -T 关闭 TTY（脚本环境必需）
    Invoke-ComposeRaw exec -T postgres pg_dump -U $PgUser -Fc --no-owner --no-privileges $Db > $file
    if ($LASTEXITCODE -ne 0) { throw "$Db 备份失败。" }

    # 校验：读取文件头 5 字节应为 "PGDMP"（可及早发现编码/重定向问题）
    $fs = [System.IO.File]::OpenRead($file)
    try {
        $buf = New-Object byte[] 5
        [void]$fs.Read($buf, 0, 5)
        $magic = [System.Text.Encoding]::ASCII.GetString($buf)
    } finally { $fs.Close() }
    if ($magic -ne 'PGDMP') {
        Write-Warning "备份文件头不是 PGDMP（实际：$magic），很可能被 PowerShell 写成了 UTF-16。请改用 bash 版备份脚本 scripts/backup.sh。"
    } else {
        $sizeMb = [math]::Round((Get-Item $file).Length / 1MB, 2)
        Write-Host "      完成：$(Split-Path -Leaf $file)（${sizeMb} MB）" -ForegroundColor Green
    }
}

Write-Host '==> 1) 备份数据库' -ForegroundColor Cyan
Backup-Database $OdooDb
Backup-Database $PlatformDb

if ($WithOdooData) {
    Write-Host '==> 2) 打包 Odoo filestore（附件实体，须与数据库一起还原）' -ForegroundColor Cyan
    $tarName = "gz_odoo_data_${Stamp}.tar.gz"
    & docker run --rm -v gz_odoo_data:/data:ro -v "${BackupDir}:/backup" alpine:3.20 `
        tar -czf "/backup/$tarName" -C /data .
    if ($LASTEXITCODE -eq 0) {
        Write-Host "      完成：$tarName（$([math]::Round((Get-Item (Join-Path $BackupDir $tarName)).Length / 1MB, 2)) MB）" -ForegroundColor Green
    } else {
        Write-Warning 'filestore 打包失败（可跳过，但恢复时附件会丢失）。'
    }
}

Write-Host "==> 3) 清理历史备份（保留最近 $Keep 份/库）" -ForegroundColor Cyan
foreach ($db in @($OdooDb, $PlatformDb)) {
    $old = Get-ChildItem -Path $BackupDir -Filter "${db}_*.dump" |
           Sort-Object LastWriteTime -Descending |
           Select-Object -Skip $Keep
    foreach ($f in $old) {
        Remove-Item $f.FullName -Force
        Write-Host "    已删除旧备份：$($f.Name)"
    }
    if (-not $old) { Write-Host "    ${db}：无需清理" }
}

Write-Host ''
Write-Host '==> 备份完成，当前 backups 目录内容：' -ForegroundColor Green
Get-ChildItem $BackupDir | Sort-Object LastWriteTime -Descending | Select-Object -First 20 |
    Format-Table Name, @{ N = 'SizeMB'; E = { [math]::Round($_.Length / 1MB, 2) } }, LastWriteTime -AutoSize

@"

还原示例（务必先在测试环境演练）：
  # 1) 停止写入方，避免还原期间有新数据
  docker compose stop api worker odoo

  # 2) 还原 gz_platform（cmd.exe 重定向为二进制安全，建议在 cmd 中执行本段）
  docker compose exec -T postgres pg_restore -U $PgUser -d $PlatformDb --clean --if-exists --no-owner < backups\${PlatformDb}_${Stamp}.dump

  # 3) 还原 gz_odoo
  docker compose exec -T postgres pg_restore -U $PgUser -d $OdooDb --clean --if-exists --no-owner < backups\${OdooDb}_${Stamp}.dump

  # 4) 恢复 Odoo filestore（若用了 -WithOdooData）
  docker run --rm -v gz_odoo_data:/data -v "`${PWD}\backups:/backup" alpine:3.20 tar -xzf /backup/gz_odoo_data_${Stamp}.tar.gz -C /data

  # 5) 重启并自检
  docker compose up -d
"@ | Write-Host
