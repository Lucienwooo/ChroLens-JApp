# -*- coding: utf-8 -*-
"""
版本管理器 - JApp
負責檢查更新和執行更新流程
基於 GitHub Releases + 獨立更新腳本 (BAT + robocopy)
"""

import os
import sys
import json
import urllib.request
import urllib.error
import zipfile
import tempfile
import shutil
import subprocess
import threading
import time
from typing import Optional, Dict, Callable


class VersionManager:
    """版本管理器"""
    
    GITHUB_REPO = "Lucienwooo/ChroLens-JApp"
    API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    
    def __init__(self, current_version: str, logger: Optional[Callable] = None):
        """
        初始化版本管理器
        
        Args:
            current_version: 當前版本號（如 "1.0"）
            logger: 日誌函數
        """
        self.current_version = current_version
        self._logger = logger or (lambda msg: print(f"[VersionManager] {msg}"))
        
        # 取得應用程式目錄
        if getattr(sys, 'frozen', False):
            self.app_dir = os.path.dirname(sys.executable)
        else:
            self.app_dir = os.path.dirname(os.path.abspath(__file__))
            
    def log(self, msg: str):
        """記錄日誌"""
        self._logger(msg)
        
    def check_for_updates(self) -> Optional[Dict]:
        """
        檢查是否有新版本
        
        Returns:
            如果有更新，返回更新資訊字典，否則返回 None
        """
        try:
            self.log("正在檢查更新...")
            
            # 發送請求到 GitHub API
            req = urllib.request.Request(
                self.API_URL,
                headers={'User-Agent': 'JApp-Update-Client'}
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            # 解析版本資訊 (移除 'JApp' 和 'v'，例如 'JApp1.2' -> '1.2')
            latest_version = data['tag_name'].replace('JApp', '').lstrip('v').strip()
            curr_version_normalized = self.current_version.replace('JApp', '').lstrip('v').strip()
            
            # 比較版本
            if self._is_newer_version(latest_version, curr_version_normalized):
                # 尋找下載連結（找 .zip 檔案）
                download_url = None
                for asset in data.get('assets', []):
                    if asset['name'].endswith('.zip'):
                        download_url = asset['browser_download_url']
                        break
                
                if not download_url:
                    self.log("找不到 ZIP 下載連結，嘗試獲取第一個釋出資源")
                    if data.get('assets'):
                        download_url = data['assets'][0]['browser_download_url']
                
                if not download_url:
                    # 備用：使用 source code zip
                    download_url = data.get('zipball_url')
                
                if not download_url:
                    self.log("找不到任何下載連結")
                    return None
                
                update_info = {
                    'version': latest_version,
                    'download_url': download_url,
                    'release_notes': data.get('body', '無更新說明'),
                    'published_at': data.get('published_at', ''),
                    'html_url': data.get('html_url', '')
                }
                
                self.log(f"發現新版本: {latest_version}")
                return update_info
            else:
                self.log("目前已是最新版本")
                return None
                
        except urllib.error.HTTPError as e:
            self.log(f"HTTP 錯誤: {e.code} - {e.reason}")
            return None
        except urllib.error.URLError as e:
            self.log(f"網路錯誤: {e.reason}")
            return None
        except Exception as e:
            self.log(f"檢查更新失敗: {e}")
            return None
            
    def _is_newer_version(self, latest: str, current: str) -> bool:
        """比較版本號"""
        try:
            from packaging import version as pkg_version
            return pkg_version.parse(latest) > pkg_version.parse(current)
        except Exception:
            # 簡單的字串比較或切割比較作為備援
            try:
                l_parts = [int(x) for x in latest.split('.') if x.isdigit()]
                c_parts = [int(x) for x in current.split('.') if x.isdigit()]
                return l_parts > c_parts
            except:
                return latest > current
                
    def download_update(self, download_url: str, progress_callback: Optional[Callable] = None) -> Optional[str]:
        """下載更新檔案"""
        try:
            self.log(f"開始下載: {download_url}")
            
            # 創建臨時目錄
            temp_dir = tempfile.mkdtemp(prefix='japp_update_')
            zip_path = os.path.join(temp_dir, 'update.zip')
            
            # 下載檔案
            def reporthook(block_num, block_size, total_size):
                if progress_callback:
                    downloaded = block_num * block_size
                    progress_callback(downloaded, total_size)
            
            # 加上 User-Agent header 下載
            req = urllib.request.Request(
                download_url,
                headers={'User-Agent': 'JApp-Update-Client'}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.info().get('Content-Length', 0))
                downloaded = 0
                block_size = 8192
                with open(zip_path, 'wb') as out_file:
                    while True:
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        downloaded += len(buffer)
                        out_file.write(buffer)
                        if progress_callback:
                            progress_callback(downloaded, total_size)
            
            self.log(f"下載完成: {zip_path}")
            return zip_path
            
        except Exception as e:
            self.log(f"下載失敗: {e}")
            return None
            
    def extract_update(self, zip_path: str) -> Optional[str]:
        """解壓縮更新檔案"""
        try:
            self.log(f"正在解壓縮: {zip_path}")
            
            extract_dir = os.path.join(os.path.dirname(zip_path), 'extracted')
            os.makedirs(extract_dir, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            self.log(f"解壓縮完成: {extract_dir}")
            return extract_dir
            
        except Exception as e:
            self.log(f"解壓縮失敗: {e}")
            return None
            
    def apply_update(self, extract_dir: str, restart_after: bool = True) -> bool:
        """
        應用更新(使用簡單可靠的 BAT 批次腳本)
        
        Args:
            extract_dir: 解壓縮目錄
            restart_after: 是否在更新後重新啟動
            
        Returns:
            是否成功創建並啟動更新腳本
        """
        try:
            self.log("準備應用更新...")
            
            # 尋找解壓縮後的實際程式目錄
            actual_source_dir = self._find_update_source(extract_dir)
            if not actual_source_dir:
                self.log("錯誤: 找不到有效的更新來源目錄")
                return False
            
            self.log(f"找到更新來源: {actual_source_dir}")
            
            # 獲取當前運行的執行檔路徑及檔名
            current_exe = sys.executable
            exe_name = os.path.basename(current_exe)
            is_frozen = getattr(sys, 'frozen', False)
            
            # 創建批次更新腳本
            bat_script = os.path.join(self.app_dir, 'update_now.bat')
            log_path = os.path.join(self.app_dir, 'update_log.txt')
            
            # 先創建初始日誌
            try:
                with open(log_path, 'w', encoding='utf-8') as f:
                    f.write("="*60 + "\n")
                    f.write("JApp 更新程式\n")
                    f.write(f"時間: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("="*60 + "\n")
                    f.write(f"來源: {actual_source_dir}\n")
                    f.write(f"目標: {self.app_dir}\n")
                    f.write(f"腳本: {bat_script}\n")
                    f.write(f"執行檔: {exe_name} (打包模式: {is_frozen})\n")
                    f.write("\n")
            except Exception as e:
                self.log(f"警告: 無法創建日誌檔案: {e}")
            
            # BAT 批次腳本內容
            script_content = f'''@echo off
chcp 65001 >nul
title JApp 更新程式

set "LOG_FILE={log_path}"
set "SOURCE_DIR={actual_source_dir}"
set "TARGET_DIR={self.app_dir}"
set "EXE_PATH={current_exe}"
set "EXE_NAME={exe_name}"

echo ======================================== >> "%LOG_FILE%"
echo 批次腳本開始執行 >> "%LOG_FILE%"
echo 時間: %DATE% %TIME% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

echo.
echo ========================================
echo JApp 更新程式
echo ========================================
echo.

REM 等待主程式完全關閉
echo 等待主程式關閉...
echo 等待主程式關閉... >> "%LOG_FILE%"

timeout /t 3 /nobreak >nul

REM 強制終止所有相關程式
taskkill /F /IM "%EXE_NAME%" >nul 2>&1
taskkill /F /IM JApp.exe >nul 2>&1
taskkill /F /IM JavGallery.exe >nul 2>&1

REM 再等待一下確保資源釋放
timeout /t 2 /nobreak >nul

echo 主程式已關閉 >> "%LOG_FILE%"
echo.

REM 創建備份標記
echo 創建備份標記...
echo 創建備份標記... >> "%LOG_FILE%"
if not exist "%TARGET_DIR%\\backup" mkdir "%TARGET_DIR%\\backup"
echo {self.current_version} > "%TARGET_DIR%\\backup\\pre_update_version.txt"

echo.
echo 開始複製檔案...
echo 開始複製檔案... >> "%LOG_FILE%"
echo 使用 robocopy 複製... >> "%LOG_FILE%"

REM 使用 robocopy 複製檔案
robocopy "%SOURCE_DIR%" "%TARGET_DIR%" /E /IS /IT /R:3 /W:1 /NP /NFL /NDL >> "%LOG_FILE%" 2>&1

REM robocopy 的返回碼: 0-7 是成功, >7 是錯誤
if %ERRORLEVEL% LEQ 7 (
    echo 檔案複製成功 >> "%LOG_FILE%"
    echo.
    echo 更新完成!
    echo 更新完成! >> "%LOG_FILE%"
) else (
    echo 檔案複製失敗，錯誤碼: %ERRORLEVEL% >> "%LOG_FILE%"
    echo.
    echo 更新失敗! 錯誤碼: %ERRORLEVEL%
    echo 請查看日誌: %LOG_FILE%
    pause
    exit /b 1
)

'''

            if restart_after and is_frozen:
                script_content += f'''
REM 重新啟動程式
echo.
echo 正在啟動程式...
echo 正在啟動程式... >> "%LOG_FILE%"

timeout /t 2 /nobreak >nul

cd /d "%TARGET_DIR%"
start "" "%EXE_NAME%"

if %ERRORLEVEL% EQU 0 (
    echo 程式已啟動 >> "%LOG_FILE%"
    echo 程式已啟動!
) else (
    echo 啟動失敗，錯誤碼: %ERRORLEVEL% >> "%LOG_FILE%"
    echo 啟動失敗!
    echo 請手動執行: %EXE_NAME%
    pause
    exit /b 1
)
'''
            elif restart_after and not is_frozen:
                # 如果是開發環境，就啟動 python app.py
                script_content += f'''
REM 重新啟動開發環境
echo.
echo 正在重啟開發環境...
echo 正在重啟開發環境... >> "%LOG_FILE%"

timeout /t 2 /nobreak >nul

cd /d "%TARGET_DIR%"
start python app.py
'''

            script_content += f'''
REM 完成
echo. >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"
echo 更新流程完成 >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"

timeout /t 2 /nobreak >nul

REM 清理臨時檔案
rd /S /Q "{os.path.dirname(extract_dir)}" >nul 2>&1

REM 刪除自己
del "%~f0"
'''
            
            # 寫入批次腳本
            with open(bat_script, 'w', encoding='utf-8') as f:
                f.write(script_content)
            
            self.log(f"更新腳本已創建: {bat_script}")
            
            # 啟動批次腳本
            try:
                subprocess.Popen(
                    ['cmd', '/c', 'start', '', '/min', bat_script],
                    shell=True,
                    cwd=self.app_dir
                )
                self.log("✓ 更新腳本已啟動，主程式即將關閉")
                return True
            except Exception as e:
                self.log(f"啟動批次腳本失敗: {e}")
                return False
            
        except Exception as e:
            self.log(f"創建更新腳本失敗: {e}")
            return False
            
    def _find_update_source(self, extract_dir: str) -> Optional[str]:
        """尋找更新檔案來源目錄"""
        # 檢查根目錄
        if self._is_valid_update_source(extract_dir):
            return extract_dir
        
        # 檢查子目錄（一層）
        for item in os.listdir(extract_dir):
            item_path = os.path.join(extract_dir, item)
            if os.path.isdir(item_path):
                if self._is_valid_update_source(item_path):
                    return item_path
        
        # 檢查子目錄的子目錄（兩層）
        for item in os.listdir(extract_dir):
            item_path = os.path.join(extract_dir, item)
            if os.path.isdir(item_path):
                for subitem in os.listdir(item_path):
                    subitem_path = os.path.join(item_path, subitem)
                    if os.path.isdir(subitem_path) and self._is_valid_update_source(subitem_path):
                        return subitem_path
        
        return None
        
    def _is_valid_update_source(self, path: str) -> bool:
        """檢查目錄是否包含有效的更新檔案"""
        try:
            # 只要包含 JApp.exe、JavGallery.exe 或 app.py 之一即可視為有效目錄
            has_exe = any(f.endswith('.exe') and ('JApp' in f or 'JavGallery' in f) for f in os.listdir(path))
            has_app = os.path.exists(os.path.join(path, 'app.py'))
            return has_exe or has_app
        except:
            return False
