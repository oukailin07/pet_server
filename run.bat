@echo off
chcp 65001 >nul
echo ========================================
echo 宠物喂食器服务器启动器
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.7+
    pause
    exit /b 1
)

echo Python环境检查通过
echo.

REM 检查依赖
echo 检查依赖...
python -c "import flask, flask_sqlalchemy" >nul 2>&1
if errorlevel 1 (
    echo 正在安装依赖...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo 依赖安装失败，请手动安装: pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo 依赖安装完成
) else (
    echo 依赖检查通过
)

echo.
echo 启动服务器...
echo 服务器地址: http://127.0.0.1:80
echo 按 Ctrl+C 停止服务器
echo ========================================
echo.

REM 启动服务器
python pet_feeder_server.py

pause 