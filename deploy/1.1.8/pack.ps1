# ============================================================
# 电炉监控后端 v1.1.8 - 打包脚本 (在开发机运行)
# ============================================================
# 功能: 将后端代码打包为 ZIP，方便复制到工控机
# ============================================================

$ErrorActionPreference = "Stop"

$VERSION = "1.1.8"
$PROJECT_ROOT = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$DEPLOY_DIR = Join-Path $PROJECT_ROOT "deploy\$VERSION"
$OUTPUT_ZIP = Join-Path $DEPLOY_DIR "furnace-backend-$VERSION.zip"
$TEMP_DIR = Join-Path $env:TEMP "furnace-backend-pack"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " 电炉监控后端 v$VERSION - 打包脚本" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# 清理临时目录
if (Test-Path $TEMP_DIR) {
    Remove-Item $TEMP_DIR -Recurse -Force
}
New-Item -ItemType Directory -Path $TEMP_DIR -Force | Out-Null

# 复制后端代码
Write-Host "`n[1/3] 复制后端代码..." -ForegroundColor Yellow
$itemsToCopy = @(
    "app",
    "configs", 
    "config.py",
    "main.py",
    "requirements.txt"
)

foreach ($item in $itemsToCopy) {
    $sourcePath = Join-Path $PROJECT_ROOT $item
    $destPath = Join-Path $TEMP_DIR $item
    
    if (Test-Path $sourcePath) {
        Copy-Item $sourcePath $destPath -Recurse -Force
        Write-Host "   ✅ $item" -ForegroundColor Green
    }
}

# 复制部署脚本和配置
Write-Host "`n[2/3] 复制部署脚本..." -ForegroundColor Yellow
$deployFiles = @(
    ".env",
    "install.ps1",
    "start_backend.ps1",
    "stop_backend.ps1",
    "docker-compose-influxdb.yml",
    "README.md"
)

foreach ($file in $deployFiles) {
    $sourcePath = Join-Path $DEPLOY_DIR $file
    $destPath = Join-Path $TEMP_DIR $file
    
    if (Test-Path $sourcePath) {
        Copy-Item $sourcePath $destPath -Force
        Write-Host "   ✅ $file" -ForegroundColor Green
    }
}

# 打包为 ZIP
Write-Host "`n[3/3] 创建 ZIP 压缩包..." -ForegroundColor Yellow
if (Test-Path $OUTPUT_ZIP) {
    Remove-Item $OUTPUT_ZIP -Force
}

Compress-Archive -Path "$TEMP_DIR\*" -DestinationPath $OUTPUT_ZIP -CompressionLevel Optimal

# 清理临时目录
Remove-Item $TEMP_DIR -Recurse -Force

# 显示结果
$zipSize = (Get-Item $OUTPUT_ZIP).Length / 1MB
Write-Host "`n============================================" -ForegroundColor Green
Write-Host " ✅ 打包完成!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host "`n输出文件: $OUTPUT_ZIP" -ForegroundColor Cyan
Write-Host "文件大小: $([math]::Round($zipSize, 2)) MB" -ForegroundColor Cyan
Write-Host "`n部署步骤:" -ForegroundColor Yellow
Write-Host "  1. 复制 ZIP 到工控机 D:\deploy\$VERSION\" -ForegroundColor White
Write-Host "  2. 执行以下命令:" -ForegroundColor White
Write-Host @"
     Expand-Archive -Path "D:\deploy\$VERSION\furnace-backend-$VERSION.zip" -DestinationPath "D:\furnace-backend" -Force
     cd D:\furnace-backend
     python -m venv venv
     .\venv\Scripts\pip install -r requirements.txt
     Start-Process -FilePath ".\venv\Scripts\python.exe" -ArgumentList "main.py" -WorkingDirectory "D:\furnace-backend" -WindowStyle Hidden
"@ -ForegroundColor Gray
