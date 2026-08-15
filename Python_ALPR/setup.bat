@echo off
echo ==============================================
echo   CAI DAT MOI TRUONG PYTHON ALPR (VENV)
echo ==============================================

echo [1] Kiem tra Python...
python --version
if %errorlevel% neq 0 (
    echo [Loi] Khong tim thay Python. Vui long cai dat Python va them vao PATH!
    pause
    exit /b
)

echo.
echo [2] Tao moi truong ao venv (chi ton vai giay)...
python -m venv venv

echo.
echo [3] Kich hoat venv va cai dat thu vien (chay lan dau co the hoi lau)...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ==============================================
echo HOAN TAT CAI DAT!
echo.
echo Cach chay Server tu bay gio:
echo Buoc 1: Kich hoat moi truong ao bang lenh: venv\Scripts\activate
echo Buoc 2: Chay server bang lenh: python server.py
echo ==============================================
pause
