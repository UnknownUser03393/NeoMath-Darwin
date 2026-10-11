@echo off
setlocal
cd /d "%~dp0..\..\ui-mockups"
if not exist "node_modules\vite\package.json" (
  echo Installing ui-mockups dependencies...
  call npm install
  if errorlevel 1 exit /b 1
)
echo Building AOT React notebook into desktop\src\neomath\ui\notebook ...
call npm run build:spa
if errorlevel 1 exit /b 1
echo Done.
exit /b 0
