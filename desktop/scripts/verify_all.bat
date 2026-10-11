@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0\.."

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if exist "%VSWHERE%" (
  for /f "usebackq tokens=*" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSROOT=%%I"
)
if defined VSROOT if exist "%VSROOT%\VC\Auxiliary\Build\vcvars64.bat" (
  call "%VSROOT%\VC\Auxiliary\Build\vcvars64.bat" >nul
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\verify_all.py %*
) else (
  python scripts\verify_all.py %*
)
exit /b %errorlevel%
