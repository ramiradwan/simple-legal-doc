@echo off  
setlocal EnableDelayedExpansion  
  
echo ==========================================  
echo simple-legal-doc MCP Connector Setup  
echo Windows Enterprise Deployment  
echo ==========================================  
echo.  
  
REM ============================================================================  
REM Normalize paths (avoid parentheses bugs)  
REM ============================================================================  
  
set "PF=%ProgramFiles%"  
set "PF86=%ProgramFiles(x86)%"  
set "LOCAL=%LocalAppData%"  
  
REM ============================================================================  
REM Locate Claude Desktop  
REM ============================================================================  
  
set "CLAUDE_DIR="  
set "CLAUDE_MODE="  
  
REM --- MSIX ---  
for /d %%D in ("%LOCAL%\Packages\AnthropicPBC.ClaudeDesktop_*") do (  
    set "CLAUDE_DIR=%%D"  
    set "CLAUDE_MODE=MSIX"  
)  
  
if not defined CLAUDE_DIR (  
    for /d %%D in ("%LOCAL%\Packages\Claude_*") do (  
        set "CLAUDE_DIR=%%D"  
        set "CLAUDE_MODE=MSIX"  
    )  
)  
  
REM --- EXE installs ---  
if not defined CLAUDE_DIR if exist "%LOCAL%\Claude\Claude.exe" (  
    set "CLAUDE_DIR=%LOCAL%\Claude"  
    set "CLAUDE_MODE=EXE"  
)  
  
if not defined CLAUDE_DIR if exist "%LOCAL%\AnthropicClaude\claude.exe" (  
    set "CLAUDE_DIR=%LOCAL%\AnthropicClaude"  
    set "CLAUDE_MODE=EXE"  
)  
  
if not defined CLAUDE_DIR if exist "%PF%\Claude\Claude.exe" (  
    set "CLAUDE_DIR=%PF%\Claude"  
    set "CLAUDE_MODE=EXE"  
)  
  
if not defined CLAUDE_DIR if exist "%PF86%\Claude\Claude.exe" (  
    set "CLAUDE_DIR=%PF86%\Claude"  
    set "CLAUDE_MODE=EXE"  
)  
  
REM --- Manual fallback ---  
if not defined CLAUDE_DIR (  
    echo WARNING: Claude Desktop installation not auto-detected.  
    echo.  
    choice /M "Continue with manual MCP configuration?"  
    if errorlevel 2 exit /b 1  
    set "CLAUDE_MODE=MANUAL"  
) else (  
    echo Found Claude Desktop:  
    echo   !CLAUDE_DIR!  
    echo   Mode: !CLAUDE_MODE!  
    echo.  
)  
  
REM ============================================================================  
REM Canonical config directory  
REM ============================================================================  
  
set "SOURCE_CONFIG=%AppData%\Claude"  
set "CLAUDE_DESKTOP_CONFIG=%SOURCE_CONFIG%\claude_desktop_config.json"  
  
if not exist "%SOURCE_CONFIG%" (  
    mkdir "%SOURCE_CONFIG%"  
    echo Created canonical config directory:  
    echo   %SOURCE_CONFIG%  
) else (  
    echo Canonical config directory already exists:  
    echo   %SOURCE_CONFIG%  
)  
  
REM ============================================================================  
REM MSIX junction (MSIX only)  
REM ============================================================================  
  
if "!CLAUDE_MODE!"=="MSIX" (  
    set "MSIX_ROAMING=!CLAUDE_DIR!\LocalCache\Roaming\Claude"  
  
    if not exist "!MSIX_ROAMING!" (  
        echo.  
        echo Creating directory junction:  
        echo   !MSIX_ROAMING! --^> %SOURCE_CONFIG%  
        mklink /D "!MSIX_ROAMING!" "%SOURCE_CONFIG%"  
        if errorlevel 1 (  
            echo WARNING: Junction creation failed - admin rights may be required.  
        ) else (  
            echo Junction created successfully.  
        )  
    ) else (  
        echo MSIX roaming path already exists.  
    )  
) else (  
    echo.  
    echo Non-MSIX Claude Desktop detected.  
    echo Skipping MSIX junction setup.  
)  
  
REM ============================================================================  
REM Write MCP config (single-line Python, CMD-safe)  
REM ============================================================================  
  
set "WORKSPACE=%UserProfile%\Downloads"  
  
echo.  
set /p CONNECTOR_PATH="Enter absolute path to mcp_server.py: "  
set /p PYTHON_PATH="Enter absolute path to python.exe: "  
  
python.exe -c "import json,os; p=r'%CLAUDE_DESKTOP_CONFIG%'; d=json.load(open(p,'r',encoding='utf-8')) if os.path.exists(p) else {}; d.setdefault('mcpServers',{}); d['mcpServers']['simple-legal-doc']={'command':r'%PYTHON_PATH%','args':[r'%CONNECTOR_PATH%'],'env':{'BACKEND_URL':'http://localhost:8000','AUDITOR_URL':'http://localhost:8001','WORKSPACE_DIR':r'%WORKSPACE%','X402_ENABLED':'false'}}; json.dump(d,open(p,'w',encoding='utf-8'),indent=2); print('Configuration written to:',p)"  
  
echo.  
echo ==========================================  
echo Setup complete.  
echo IMPORTANT:  
echo   Do NOT use Claude Desktop's "Edit Config" button.  
echo   Edit directly at:  
echo   %CLAUDE_DESKTOP_CONFIG%  
echo ==========================================  
pause  