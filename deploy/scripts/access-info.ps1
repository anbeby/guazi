# 第十师瓜子油料数字化交易平台 · 访问地址自动探测（Windows PowerShell）
#
# 用途：启动容器后自动探测本机局域网 IP，打印 PC / 手机 / 后台 的完整访问地址。
# 用法：pwsh -File .\access-info.ps1
#       pwsh -File .\access-info.ps1 -GatewayPort 8080 -AdminPort 8081

param(
    [int]$GatewayPort = 8080,
    [int]$AdminPort = 8081,
    [string]$EnvFile = (Join-Path $PSScriptRoot "..\.env")
)

$ErrorActionPreference = "SilentlyContinue"

# 若存在 .env，优先使用其中的端口配置
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*GATEWAY_PORT\s*=\s*(\d+)') { $GatewayPort = [int]$Matches[1] }
        if ($_ -match '^\s*ADMIN_PORT\s*=\s*(\d+)') { $AdminPort = [int]$Matches[1] }
    }
}

function Get-LanIp {
    # 优先取默认路由对应的网卡地址（最可能是同一局域网可达的那个 IP）
    $candidates = @()
    try {
        $route = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction Stop |
            Sort-Object RouteMetric | Select-Object -First 1
        if ($route) {
            $ip = Get-NetIPAddress -InterfaceIndex $route.InterfaceIndex -AddressFamily IPv4 -ErrorAction Stop |
                Where-Object { $_.IPAddress -notlike "169.254.*" -and $_.IPAddress -ne "127.0.0.1" } |
                Select-Object -First 1
            if ($ip) { $candidates += $ip.IPAddress }
        }
    } catch { }
    if (-not $candidates) {
        # 回退方案：列出所有非回环 IPv4 私网地址
        $all = [System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) |
            Where-Object { $_.AddressFamily -eq 'InterNetwork' -and $_.IPAddressToString -notlike "127.*" }
        $candidates = $all | ForEach-Object { $_.IPAddressToString }
    }
    if ($candidates.Count -gt 0) { return $candidates[0] }
    return "127.0.0.1"
}

$ip = Get-LanIp

Write-Host ""
Write-Host "================================" -ForegroundColor Green
Write-Host " 系统启动成功" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host ""
Write-Host (" PC 访问（管理后台）：   http://{0}:{1}/" -f $ip, $GatewayPort)
Write-Host (" 手机访问（H5 移动端）： http://{0}:{1}/m/" -f $ip, $GatewayPort)
Write-Host (" 后台专用入口：         http://{0}:{1}/" -f $ip, $AdminPort)
Write-Host ""
Write-Host (" 运维控制台（免构建）：  http://{0}:{1}/console/" -f $ip, $GatewayPort)
Write-Host (" 接口文档（OpenAPI）：   http://{0}:{1}/api/docs" -f $ip, $GatewayPort)
Write-Host (" Odoo ERP：             http://{0}:{1}/odoo" -f $ip, $GatewayPort)
Write-Host (" 数据分析（Superset）：  http://{0}:{1}/superset" -f $ip, $GatewayPort)
Write-Host (" MinIO 控制台：         http://{0}:9001" -f $ip)
Write-Host ""
Write-Host " 本机访问可用 http://localhost 或 http://127.0.0.1 替换上述 IP" -ForegroundColor DarkGray
Write-Host " 手机请连接与电脑相同的 WiFi，并关闭移动数据后重试" -ForegroundColor DarkGray
Write-Host ""
Write-Host " 演示账号：admin / Admin@123（平台管理员）" -ForegroundColor DarkGray
Write-Host "           jinsui、testmerchant、gongxiao、testbuyer 密码均为 Gz@123456" -ForegroundColor DarkGray
Write-Host ""

# 自检：网关是否可达
try {
    $resp = Invoke-WebRequest -Uri ("http://127.0.0.1:{0}/nginx-health" -f $GatewayPort) -TimeoutSec 5 -UseBasicParsing
    if ($resp.StatusCode -eq 200) {
        Write-Host " [自检] 网关健康检查通过" -ForegroundColor Green
    }
} catch {
    Write-Host " [自检] 网关暂不可达，可能仍在启动中，请稍等 30 秒后重试" -ForegroundColor Yellow
}
Write-Host ""

# 若检测到 Windows 防火墙可能拦截，给出提示
try {
    $fw = Get-NetFirewallProfile -ErrorAction Stop | Where-Object { $_.Enabled -eq $true }
    if ($fw) {
        Write-Host " 提示：检测到 Windows 防火墙已开启。若局域网其他设备无法访问，请放行端口：" -ForegroundColor Yellow
        Write-Host ("       New-NetFirewallRule -DisplayName 'GZ-Platform' -Direction Inbound -Protocol TCP -LocalPort {0},{1},9001 -Action Allow" -f $GatewayPort, $AdminPort) -ForegroundColor Yellow
        Write-Host ""
    }
} catch { }
