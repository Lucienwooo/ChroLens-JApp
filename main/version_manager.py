# -*- coding: utf-8 -*-
"""
版本管理器 - ChroLens_AutoFlow
負責檢查更新和版本資訊顯示

更新機制：基於 GitHub Releases + 獨立更新程式 (robocopy)
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
from packaging import version as pkg_version


class VersionManager:
    """版本管理器"""
    
    def __init__(self, github_repo: str, current_version: str, logger: Optional[Callable] = None):
        """
        初始化版本管理器
        
        Args:
            github_repo: GitHub 儲存庫路徑 (如 "Lucienwooo/ChroLens_AutoFlow")
            current_version: 當前版本號（如 "1.2.0"）
            logger: 日誌函數
        """
        self.github_repo = github_repo
        self.current_version = current_version
        self._logger = logger or (lambda msg: print(f"[VersionManager] {msg}"))
        self.api_url = f"https://api.github.com/repos/{github_repo}/releases/latest"
        
        # 取得應用程式目錄
        if getattr(sys, 'frozen', False):
            self.app_dir = os.path.dirname(sys.executable)
        else:
            self.app_dir = os.path.dirname(os.path.abspath(__file__))
            # 如果在 main/ 或 src/ 目錄下，退回上一層作為根目錄
            if os.path.basename(self.app_dir) in ['main', 'src']:
                self.app_dir = os.path.dirname(self.app_dir)
    
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
            self.log(f"正在檢查 {self.github_repo} 的更新...")
            
            # 發送請求到 GitHub API
            req = urllib.request.Request(
                self.api_url,
                headers={'User-Agent': 'ChroLens-App'}
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            # 解析版本資訊
            latest_version = data['tag_name'].lstrip('v')  # 移除 'v' 前綴
            
            # 比較版本
            if self._is_newer_version(latest_version, self.current_version):
                # 尋找下載連結（優先找 .zip 檔案）
                download_url = None
                assets = data.get('assets', [])
                
                # 優先級 1: 包含版本號的 zip
                for asset in assets:
                    if asset['name'].endswith('.zip') and latest_version in asset['name']:
                        download_url = asset['browser_download_url']
                        break
                
                # 優先級 2: 任何 zip
                if not download_url:
                    for asset in assets:
                        if asset['name'].endswith('.zip'):
                            download_url = asset['browser_download_url']
                            break
                            
                # 優先級 3: 如果都沒有 zip，但有資產，可能需要報錯
                if not download_url:
                    if assets:
                        self.log("警告: 發現新版本但找不到 .zip 更新包，請手動更新。")
                        # 仍返回資訊，讓 UI 顯示有新版
                    else:
                        self.log("找不到有效的更新資產")
                
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
            self.log(f"HTTP 錯誤: {e.code}")
            return None
        except Exception as e:
            self.log(f"檢查更新失敗: {e}")
            return None
    
    def _is_newer_version(self, latest: str, current: str) -> bool:
        """比較版本號 (使用 packaging 庫)"""
        try:
            return pkg_version.parse(latest) > pkg_version.parse(current)
        except Exception:
            # 簡單的字串比較作為備援
            return latest > current
    
    def download_update(self, download_url: str, progress_callback: Optional[Callable] = None) -> Optional[str]:
        """下載更新檔案"""
        if not download_url:
            self.log("無效的下載連結")
            return None
            
        try:
            self.log(f"開始下載更新: {download_url}")
            
            # 創建臨時目錄
            temp_dir = tempfile.mkdtemp(prefix='autoflow_update_')
            zip_path = os.path.join(temp_dir, 'update.zip')
            
            # 下載檔案
            def reporthook(block_num, block_size, total_size):
                if progress_callback:
                    downloaded = block_num * block_size
                    progress_callback(downloaded, total_size)
            
            urllib.request.urlretrieve(download_url, zip_path, reporthook)
            
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
        應用更新 (仿照 Mimic 的 robocopy 腳本機制)
        """
        try:
            self.log("準備應用更新...")
            
            # 尋找解壓縮後的實際程式目錄
            actual_source_dir = self._find_update_source(extract_dir)
            if not actual_source_dir:
                self.log("錯誤: 找不到有效的更新來源目錄")
                return False
            
            self.log(f"源目錄: {actual_source_dir}")
            self.log(f"目標目錄: {self.app_dir}")
            
            # 創建批次更新腳本
            bat_script = os.path.join(self.app_dir, 'update_temp.bat')
            log_path = os.path.join(self.app_dir, 'update_log.txt')
            
            # 取得執行檔名稱
            if getattr(sys, 'frozen', False):
                exe_name = os.path.basename(sys.executable)
                exe_path = sys.executable
            else:
                exe_name = "ChroLens_AutoFlow.exe" # 預設名稱
                exe_path = os.path.join(self.app_dir, exe_name)
            
            # 構建 BAT 腳本內容
            script_content = f'''@echo off
chcp 65001 >nul
title AutoFlow 更新進行中...

set "LOG_FILE={log_path}"
set "SOURCE_DIR={actual_source_dir}"
set "TARGET_DIR={self.app_dir}"
set "EXE_NAME={exe_name}"
set "EXE_PATH={exe_path}"

echo ======================================== >> "%LOG_FILE%"
echo 開始更新流程 (AutoFlow) >> "%LOG_FILE%"
echo 時間: %DATE% %TIME% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"

echo 等待主程式關閉...
timeout /t 3 /nobreak >nul

REM 強制關閉主程式
taskkill /F /IM "%EXE_NAME%" >nul 2>&1
timeout /t 2 /nobreak >nul

echo 正在複製檔案 (robocopy)...
echo 執行 robocopy... >> "%LOG_FILE%"

REM /E: 複製子目錄
REM /IS: 包含相同檔案
REM /IT: 包含已調整的檔案
REM /R:3: 重試 3 次
REM /W:1: 等待 1 秒
robocopy "%SOURCE_DIR%" "%TARGET_DIR%" /E /IS /IT /R:3 /W:1 /NP /NFL /NDL >> "%LOG_FILE%" 2>&1

if %ERRORLEVEL% LEQ 7 (
    echo 檔案更新成功! >> "%LOG_FILE%"
    echo 檔案更新完成。
) else (
    echo 更新失敗，錯誤碼: %ERRORLEVEL% >> "%LOG_FILE%"
    echo 更新發生錯誤，請檢查日誌。
    pause
    exit /b 1
)

REM 清理臨時解壓目錄
rd /S /Q "{os.path.dirname(extract_dir)}" >nul 2>&1

'''
            if restart_after:
                if getattr(sys, 'frozen', False):
                    script_content += f'''
echo 正在重啟程式...
timeout /t 2 /nobreak >nul
start "" "%EXE_PATH%"
'''
                else:
                    # 開發模式下不支援自動重啟到 Python (路徑太複雜)
                    script_content += f'''
echo 更新完成，請手動重啟程式。
pause
'''
            
            script_content += f'''
echo 更新已完成。 >> "%LOG_FILE%"
del "%~f0"
exit
'''
            
            # 寫入腳本
            with open(bat_script, 'w', encoding='utf-8') as f:
                f.write(script_content)
            
            # 非同步啟動腳本
            subprocess.Popen(['cmd', '/c', 'start', '', '/min', bat_script], shell=True, cwd=self.app_dir)
            
            return True
            
        except Exception as e:
            self.log(f"更新腳本執行失敗: {e}")
            return False

    def _find_update_source(self, extract_dir: str) -> Optional[str]:
        """尋找包含主程式的源目錄"""
        # 可能在根目錄，也可能在 zip 產生的單個資料夾內
        if self._is_valid_dir(extract_dir):
            return extract_dir
        
        # 遍歷子目錄
        try:
            for item in os.listdir(extract_dir):
                path = os.path.join(extract_dir, item)
                if os.path.isdir(path):
                    if self._is_valid_dir(path):
                        return path
        except:
            pass
            
        return None

    def _is_valid_dir(self, path: str) -> bool:
        """判斷是否為有效的更新源 (包含 .py 或 .exe)"""
        files = os.listdir(path)
        # 判斷是否包含關鍵檔案
        if any(f == "ChroLens_AutoFlow.py" for f in files):
            return True
        if any(f.startswith("ChroLens_AutoFlow") and f.endswith(".exe") for f in files):
            return True
        return False
