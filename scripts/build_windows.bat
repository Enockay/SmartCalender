@echo off
REM =============================================================================
REM  SmartCalender – Windows Build Script
REM  Designed by Enock Mwems
REM
REM  Produces:
REM    dist\windows\SmartCalender\          – standalone directory
REM    dist\windows\SmartCalender-Setup.exe – NSIS installer
REM
REM  Prerequisites:
REM    pip install pyinstaller
REM    NSIS (https://nsis.sourceforge.io/Download)  – for the installer
REM    signtool.exe in PATH                         – Windows SDK for signing
REM
REM  Code-signing prerequisites (optional):
REM    A valid code-signing certificate (.pfx file).
REM    Set SIGN_CERT_PATH and SIGN_CERT_PASS before running.
REM
REM  Usage (from project root in a Command Prompt / PowerShell):
REM    scripts\build_windows.bat
REM =============================================================================

setlocal EnableDelayedExpansion

REM ---------------------------------------------------------------------------
REM  Configuration – edit these values
REM ---------------------------------------------------------------------------
set APP_NAME=SmartCalender
set VERSION=1.0.0
set AUTHOR=Enock Mwems
set DESCRIPTION=Smart Calender – Designed by Enock Mwems

REM Path to your code-signing certificate (leave empty to skip signing)
REM  Example: set SIGN_CERT_PATH=C:\certs\my_certificate.pfx
set SIGN_CERT_PATH=%SIGN_CERT_PATH%

REM Password for the certificate (leave empty if certificate has no password)
set SIGN_CERT_PASS=%SIGN_CERT_PASS%

REM Timestamp server for code signing
set TIMESTAMP_URL=http://timestamp.digicert.com

REM Directories
set ROOT=%~dp0..
set DIST_DIR=%ROOT%\dist\windows
set BUILD_DIR=%ROOT%\build

REM ---------------------------------------------------------------------------
REM  Banner
REM ---------------------------------------------------------------------------
echo ============================================================
echo   Smart Calender – Windows Build
echo   Designed by %AUTHOR%  ^|  v%VERSION%
echo ============================================================

REM ---------------------------------------------------------------------------
REM  1. Move to project root
REM ---------------------------------------------------------------------------
cd /d "%ROOT%"

REM ---------------------------------------------------------------------------
REM  2. Clean previous build
REM ---------------------------------------------------------------------------
echo [1/6] Cleaning previous build...
if exist "%BUILD_DIR%" rd /s /q "%BUILD_DIR%"
if exist "%DIST_DIR%"  rd /s /q "%DIST_DIR%"
mkdir "%DIST_DIR%"

REM ---------------------------------------------------------------------------
REM  3. Install / upgrade PyInstaller
REM ---------------------------------------------------------------------------
echo [2/6] Installing build dependencies...
pip install --quiet --upgrade pyinstaller
if errorlevel 1 (
    echo ERROR: pip install failed. Make sure Python is on PATH.
    exit /b 1
)

REM ---------------------------------------------------------------------------
REM  4. Create Windows version-info file
REM ---------------------------------------------------------------------------
echo [3/6] Generating Windows version info...

REM  Convert dotted version to comma-separated tuple
for /f "tokens=1,2,3,4 delims=." %%a in ("%VERSION%.0") do (
    set V1=%%a & set V2=%%b & set V3=%%c & set V4=%%d
)

(
echo VSVersionInfo^(
echo   ffi=FixedFileInfo^(
echo     filevers=^(%V1%,%V2%,%V3%,%V4%^),
echo     prodvers=^(%V1%,%V2%,%V3%,%V4%^),
echo     mask=0x3f,
echo     flags=0x0,
echo     OS=0x4,
echo     fileType=0x1,
echo     subtype=0x0,
echo     date=^(0,0^)
echo   ^),
echo   kids=[
echo     StringFileInfo^(
echo       [
echo         StringTable^(
echo           u'040904B0',
echo           [StringStruct^(u'CompanyName',      u'%AUTHOR%'^),
echo            StringStruct^(u'FileDescription',  u'%DESCRIPTION%'^),
echo            StringStruct^(u'FileVersion',      u'%VERSION%'^),
echo            StringStruct^(u'InternalName',     u'%APP_NAME%'^),
echo            StringStruct^(u'LegalCopyright',   u'Copyright ^(c^) 2024 %AUTHOR%. All rights reserved.'^),
echo            StringStruct^(u'OriginalFilename', u'%APP_NAME%.exe'^),
echo            StringStruct^(u'ProductName',      u'Smart Calender'^),
echo            StringStruct^(u'ProductVersion',   u'%VERSION%'^)]
echo         ^)
echo       ]
echo     ^),
echo     VarFileInfo^([VarStruct^(u'Translation', [1033, 1200]^)]^)
echo   ]
echo ^)
) > "%BUILD_DIR%\version_info.txt" 2>nul || mkdir "%BUILD_DIR%" && (
echo VSVersionInfo^( > "%BUILD_DIR%\version_info.txt"
)

REM ---------------------------------------------------------------------------
REM  5. Run PyInstaller
REM ---------------------------------------------------------------------------
echo [4/6] Running PyInstaller...
pyinstaller SmartCalender.spec ^
    --distpath "%DIST_DIR%" ^
    --workpath "%BUILD_DIR%\work" ^
    --noconfirm ^
    --clean
if errorlevel 1 (
    echo ERROR: PyInstaller failed.
    exit /b 1
)

set APP_DIR=%DIST_DIR%\%APP_NAME%
if not exist "%APP_DIR%" (
    echo ERROR: output directory not found at %APP_DIR%
    exit /b 1
)
echo   Built: %APP_DIR%

REM ---------------------------------------------------------------------------
REM  6. Code-sign the EXE (if certificate is set)
REM ---------------------------------------------------------------------------
if defined SIGN_CERT_PATH (
    if exist "%SIGN_CERT_PATH%" (
        echo [5/6] Code-signing %APP_NAME%.exe...
        set EXE_PATH=%APP_DIR%\%APP_NAME%.exe
        where signtool >nul 2>&1
        if errorlevel 1 (
            echo   WARNING: signtool not found on PATH. Install Windows SDK.
            echo   Skipping code-signing.
        ) else (
            if defined SIGN_CERT_PASS (
                signtool sign /fd SHA256 ^
                    /tr "%TIMESTAMP_URL%" /td SHA256 ^
                    /f "%SIGN_CERT_PATH%" /p "%SIGN_CERT_PASS%" ^
                    /d "Smart Calender" ^
                    /du "https://enockmwems.com" ^
                    "!EXE_PATH!"
            ) else (
                signtool sign /fd SHA256 ^
                    /tr "%TIMESTAMP_URL%" /td SHA256 ^
                    /f "%SIGN_CERT_PATH%" ^
                    /d "Smart Calender" ^
                    /du "https://enockmwems.com" ^
                    "!EXE_PATH!"
            )
            if errorlevel 1 (
                echo   WARNING: signtool returned an error.
            ) else (
                echo   Code-signing: OK
            )
        )
    ) else (
        echo [5/6] Certificate not found at %SIGN_CERT_PATH% – skipping signing
    )
) else (
    echo [5/6] Skipping code-signing ^(SIGN_CERT_PATH not set^)
    echo   To sign, set SIGN_CERT_PATH=path\to\your\certificate.pfx
)

REM ---------------------------------------------------------------------------
REM  7. Create NSIS installer
REM ---------------------------------------------------------------------------
echo [6/6] Creating NSIS installer...

set NSI_SCRIPT=%BUILD_DIR%\installer.nsi
set INSTALLER_OUT=%DIST_DIR%\%APP_NAME%-Setup-%VERSION%.exe

(
echo !define APP_NAME        "%APP_NAME%"
echo !define APP_VERSION     "%VERSION%"
echo !define APP_AUTHOR      "%AUTHOR%"
echo !define APP_DESCRIPTION "%DESCRIPTION%"
echo !define INSTALLER_NAME  "%INSTALLER_OUT%"
echo !define APP_DIR         "%APP_DIR%"
echo !define APP_EXE         "%APP_NAME%.exe"
echo.
echo Name "${APP_NAME}"
echo OutFile "${INSTALLER_NAME}"
echo InstallDir "$PROGRAMFILES64\${APP_NAME}"
echo InstallDirRegKey HKLM "Software\${APP_NAME}" "InstallDir"
echo RequestExecutionLevel admin
echo.
echo ; Modern UI
echo !include "MUI2.nsh"
echo !define MUI_ABORTWARNING
echo !define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
echo !insertmacro MUI_PAGE_WELCOME
echo !insertmacro MUI_PAGE_LICENSE "%ROOT%\LICENSE.txt"
echo !insertmacro MUI_PAGE_DIRECTORY
echo !insertmacro MUI_PAGE_INSTFILES
echo !insertmacro MUI_PAGE_FINISH
echo !insertmacro MUI_UNPAGE_CONFIRM
echo !insertmacro MUI_UNPAGE_INSTFILES
echo !insertmacro MUI_LANGUAGE "English"
echo.
echo Section "Install"
echo   SetOutPath "$INSTDIR"
echo   File /r "${APP_DIR}\*.*"
echo.
echo   ; Write registry keys
echo   WriteRegStr HKLM "Software\${APP_NAME}" "InstallDir" "$INSTDIR"
echo   WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayName"          "${APP_NAME}"
echo   WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayVersion"       "${APP_VERSION}"
echo   WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "Publisher"            "${APP_AUTHOR}"
echo   WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString"      "$INSTDIR\Uninstall.exe"
echo   WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayIcon"          "$INSTDIR\${APP_EXE}"
echo.
echo   ; Shortcuts
echo   CreateDirectory "$SMPROGRAMS\${APP_NAME}"
echo   CreateShortcut  "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
echo   CreateShortcut  "$DESKTOP\${APP_NAME}.lnk"                "$INSTDIR\${APP_EXE}"
echo.
echo   WriteUninstaller "$INSTDIR\Uninstall.exe"
echo SectionEnd
echo.
echo Section "Uninstall"
echo   RMDir /r "$INSTDIR"
echo   Delete   "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
echo   RMDir    "$SMPROGRAMS\${APP_NAME}"
echo   Delete   "$DESKTOP\${APP_NAME}.lnk"
echo   DeleteRegKey HKLM "Software\${APP_NAME}"
echo   DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
echo SectionEnd
) > "%NSI_SCRIPT%"

REM Create a dummy LICENSE.txt if none exists
if not exist "%ROOT%\LICENSE.txt" (
    echo Smart Calender - Designed by Enock Mwems > "%ROOT%\LICENSE.txt"
    echo Copyright ^(c^) 2024 Enock Mwems. All rights reserved. >> "%ROOT%\LICENSE.txt"
)

where makensis >nul 2>&1
if errorlevel 1 (
    echo   WARNING: makensis ^(NSIS^) not found on PATH.
    echo   Install NSIS from https://nsis.sourceforge.io/Download
    echo   Then run:  makensis "%NSI_SCRIPT%"
) else (
    makensis "%NSI_SCRIPT%"
    if errorlevel 1 (
        echo   WARNING: NSIS returned an error.
    ) else (
        echo   Installer: %INSTALLER_OUT%

        REM Sign the installer too
        if defined SIGN_CERT_PATH (
            if exist "%SIGN_CERT_PATH%" (
                where signtool >nul 2>&1
                if not errorlevel 1 (
                    if defined SIGN_CERT_PASS (
                        signtool sign /fd SHA256 ^
                            /tr "%TIMESTAMP_URL%" /td SHA256 ^
                            /f "%SIGN_CERT_PATH%" /p "%SIGN_CERT_PASS%" ^
                            /d "Smart Calender Installer" ^
                            "%INSTALLER_OUT%"
                    ) else (
                        signtool sign /fd SHA256 ^
                            /tr "%TIMESTAMP_URL%" /td SHA256 ^
                            /f "%SIGN_CERT_PATH%" ^
                            /d "Smart Calender Installer" ^
                            "%INSTALLER_OUT%"
                    )
                    echo   Installer signed: OK
                )
            )
        )
    )
)

REM ---------------------------------------------------------------------------
REM  Summary
REM ---------------------------------------------------------------------------
echo.
echo ============================================================
echo   BUILD COMPLETE
echo   App dir  : %APP_DIR%
echo   Installer: %INSTALLER_OUT%
echo   Author   : %AUTHOR%
echo   Version  : %VERSION%
echo ============================================================

endlocal
