import os
import sys
import runpy

# 切換至 main 目錄，讓相對路徑讀取與 version_manager 正常運作
main_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main')
os.chdir(main_dir)
sys.path.insert(0, main_dir)

print("[Wrapper] Redirecting execution to main/japp.py...")
runpy.run_path('japp.py', run_name='__main__')
