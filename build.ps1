param(
    [int]$Port = 0
)

$ErrorActionPreference = 'Stop'

trap {
    [Console]::Error.WriteLine("构建脚本执行失败：$($_.Exception.Message)")
    exit 1
}

Push-Location $PSScriptRoot
try {
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) {
        throw "站点构建失败，npm 退出代码：$LASTEXITCODE"
    }

    if ($Port -le 0) {
        $Port = [int]((& node.exe docs/.vitepress/scripts/free-port.mjs) | Select-Object -Last 1).Trim()
        if ($LASTEXITCODE -ne 0 -or $Port -le 0) {
            throw "未能找到可用端口"
        }
    }

    # 清理占用目标端口的旧进程（同一端口被上一个本脚本实例占用时）
    $portLine = netstat -ano | Select-String ":$Port" | Select-String 'LISTENING' | Select-Object -First 1
    if ($portLine) {
        $pidPort = ($portLine.ToString().Trim() -split '\s+')[-1]
        if ($pidPort) {
            Stop-Process -Id $pidPort -Force -ErrorAction SilentlyContinue
            Start-Sleep 1
        }
    }

    Write-Host "开发服务器端口：$Port"
    & npm.cmd run dev -- --port $Port --strictPort
    if ($LASTEXITCODE -ne 0) {
        throw "开发服务器异常退出，npm 退出代码：$LASTEXITCODE"
    }
} finally {
    Pop-Location
}
