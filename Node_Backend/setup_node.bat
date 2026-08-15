@echo off
echo ==============================================
echo   CAI DAT NODE.JS BACKEND (THAP PHAT NGUOI)
echo ==============================================

echo [1] Kiem tra Node.js...
node -v
if %errorlevel% neq 0 (
    echo [Loi] Khong tim thay Node.js!
    echo Vui long tai va cai dat Node.js tai: https://nodejs.org/
    echo (Sau khi cai dat xong, hay khoi dong lai may tinh hoac terminal roi chay lai file nay)
    pause
    exit /b
)

echo.
echo [2] Dang tai va cai dat cac thu vien Node.js...
call npm install

echo.
echo [3] Tao du lieu mau vao MongoDB...
node seed.js

echo.
echo ==============================================
echo HOAN TAT CAI DAT!
echo.
echo De chay he thong Dashboard Phat Nguoi, hay go:
echo   node server.js
echo ==============================================
pause
