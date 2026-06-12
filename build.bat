@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ==========================================
::  JApp 一鍵打包腳本
::  - 使用 PyInstaller onedir 模式打包
::  - 自動壓縮為 .zip 發行包
:: ==========================================

echo.
echo =========================================
echo   JApp 一鍵打包工具
echo =========================================
echo.

:: 設定根目錄路徑
set "ROOT_DIR=%~dp0"
set "MAIN_DIR=%ROOT_DIR%main"

:: 讀取版本號 (從 japp.py 第 22 行直接解析，不 import 模組)
set VERSION=unknown
for /f "tokens=3 delims= " %%v in ('findstr /C:"VERSION = " "%MAIN_DIR%\japp.py"') do (
    set RAW=%%v
    set VERSION=!RAW:"=!
    set VERSION=!VERSION:'=!
    goto :got_version
)
:got_version
echo   版本: v%VERSION%
echo.

:: 確認 PyInstaller 存在
python -m PyInstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [錯誤] 找不到 PyInstaller！
    echo 請先執行: pip install pyinstaller
    echo.
    pause
    exit /b 1
)

:: 切換到 main 目錄（PyInstaller 需要在此目錄執行）
cd /d "%MAIN_DIR%"

:: 清理舊的 build 與 dist/JApp
echo [步驟 1/4] 清理舊的建置資料...
if exist "build" (
    rmdir /s /q "build"
    echo   已清除 build\
)
if exist "dist\JApp" (
    rmdir /s /q "dist\JApp"
    echo   已清除 dist\JApp\
)

:: 執行 PyInstaller (onedir)
echo.
echo [步驟 2/4] 執行 PyInstaller (onedir 模式)...
echo.
python -m PyInstaller JApp.spec --noconfirm
if %errorlevel% neq 0 (
    echo.
    echo =========================================
    echo   [錯誤] PyInstaller 打包失敗！
    echo   請查看上方錯誤訊息。
    echo =========================================
    pause
    exit /b 1
)
echo.
echo   PyInstaller 打包成功！

:: 確認 Favorites.json 存在於 dist\JApp\
echo.
echo [步驟 3/4] 確認並複製 Favorites.json...
if not exist "dist\JApp\Favorites.json" (
    if exist "Favorites.json" (
        copy /y "Favorites.json" "dist\JApp\Favorites.json" >nul
        echo   已複製 Favorites.json 到 dist\JApp\
    ) else (
        echo   [警告] 找不到 Favorites.json，建立空白版本...
        echo [] > "dist\JApp\Favorites.json"
    )
) else (
    echo   dist\JApp\Favorites.json 已存在，保留現有資料庫不覆蓋。
)

:: 壓縮成 zip
echo.
echo [步驟 4/4] 壓縮為 JApp_v%VERSION%.zip...
set "ZIP_NAME=JApp_v%VERSION%.zip"
set "ZIP_OUTPUT=%MAIN_DIR%\dist\%ZIP_NAME%"

:: 刪除同名舊 zip
if exist "%ZIP_OUTPUT%" del "%ZIP_OUTPUT%"

:: 使用 PowerShell 壓縮
powershell -NoProfile -Command "Compress-Archive -Path '%MAIN_DIR%\dist\JApp' -DestinationPath '%ZIP_OUTPUT%' -Force"
if %errorlevel% neq 0 (
    echo.
    echo   [錯誤] 壓縮 zip 失敗！
    pause
    exit /b 1
)

echo.
echo =========================================
echo   打包完成！
echo.
echo   輸出資料夾: main\dist\JApp\
echo   壓縮檔案:   main\dist\%ZIP_NAME%
echo =========================================
echo.

:: 自動開啟 dist 資料夾
explorer "%MAIN_DIR%\dist"

pause
