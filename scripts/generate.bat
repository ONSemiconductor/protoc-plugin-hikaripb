@echo off
setlocal enabledelayedexpansion
REM Generate C, C++ and/or Python bindings from a .proto file using protoc\hikaripb.py.
REM
REM Usage:
REM   generate.bat <proto_file> <out_dir> [prefix] [type] [options]
REM
REM   proto_file  Path to the .proto file to compile.
REM   out_dir     Directory that will receive the generated files.
REM   prefix      Prefix used for the generated runtime symbols, the C++
REM               namespace, the Python runtime modules and the labels of the
REM               Sphinx documentation (default: hikaripb).
REM   type        c | cpp | py | both | sphinxdocs (default: both). "both" means
REM               c+py; pass "cpp" explicitly for the self-contained native C++
REM               codec (unrelated to the c backend - requires a hand-written
REM               <prefix>_config.h, see test\cpp\hikaripb_config.h). "sphinxdocs"
REM               writes Sphinx documentation (MyST Markdown) instead of code.
REM   options     Extra --hikaripb_out options appended to every backend, comma
REM               separated, e.g. "single_file=protocol" (see docs\content\options.md).
REM
REM Requires protoc (with --experimental_allow_proto3_optional support) and the
REM Python packages in protoc\requirements.txt (protobuf, jinja2) importable by
REM the python on PATH.

set SCRIPT_DIR=%~dp0
set ROOT_DIR=%SCRIPT_DIR%..
REM protoc cannot start a .py plugin on Windows, the .bat wrapper starts hikaripb.py
set PLUGIN=%ROOT_DIR%\protoc\protoc-gen-hikaripb.bat

if "%~1"=="" (
    echo Usage: %~nx0 ^<proto_file^> ^<out_dir^> [prefix] [type: c^|cpp^|py^|both^|sphinxdocs] [options]
    exit /b 1
)
if "%~2"=="" (
    echo Usage: %~nx0 ^<proto_file^> ^<out_dir^> [prefix] [type: c^|cpp^|py^|both^|sphinxdocs] [options]
    exit /b 1
)

set PROTO_FILE=%~1
set OUT_DIR=%~2
set PREFIX=%~3
if "%PREFIX%"=="" set PREFIX=hikaripb
set TYPE=%~4
if "%TYPE%"=="" set TYPE=both
set EXTRA=
if not "%~5"=="" set EXTRA=,%~5

if not defined PROTOC set PROTOC=protoc

for %%F in ("%PROTO_FILE%") do (
    set PROTO_DIR=%%~dpF
    set PROTO_BASENAME=%%~nxF
)
for %%D in ("%OUT_DIR%") do set OUT_DIR=%%~fD

REM a trailing backslash would escape the closing quote of the quoted arguments below
if "%PROTO_DIR:~-1%"=="\" set PROTO_DIR=%PROTO_DIR:~0,-1%
if "%OUT_DIR:~-1%"=="\" set OUT_DIR=%OUT_DIR:~0,-1%

if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

if "%TYPE%"=="c" goto :gen_c
if "%TYPE%"=="both" goto :gen_c
goto :maybe_py

:gen_c
echo Generating C bindings -^> %OUT_DIR%
"%PROTOC%" --experimental_allow_proto3_optional ^
    --plugin=protoc-gen-hikaripb="%PLUGIN%" ^
    --proto_path="%PROTO_DIR%" ^
    --hikaripb_out=type=c,prefix=%PREFIX%%EXTRA%:"%OUT_DIR%" ^
    "%PROTO_DIR%\%PROTO_BASENAME%"
if errorlevel 1 exit /b 1

:maybe_py
if "%TYPE%"=="py" goto :gen_py
if "%TYPE%"=="both" goto :gen_py
goto :maybe_cpp

:gen_py
echo Generating Python bindings -^> %OUT_DIR%
"%PROTOC%" --experimental_allow_proto3_optional ^
    --plugin=protoc-gen-hikaripb="%PLUGIN%" ^
    --proto_path="%PROTO_DIR%" ^
    --hikaripb_out=type=py,prefix=%PREFIX%%EXTRA%:"%OUT_DIR%" ^
    "%PROTO_DIR%\%PROTO_BASENAME%"
if errorlevel 1 exit /b 1

:maybe_cpp
if "%TYPE%"=="cpp" goto :gen_cpp
goto :maybe_sphinxdocs

:gen_cpp
echo Generating C++ bindings (self-contained hikaripb:: codec) -^> %OUT_DIR%
"%PROTOC%" --experimental_allow_proto3_optional ^
    --plugin=protoc-gen-hikaripb="%PLUGIN%" ^
    --proto_path="%PROTO_DIR%" ^
    --hikaripb_out=type=cpp,prefix=%PREFIX%%EXTRA%:"%OUT_DIR%" ^
    "%PROTO_DIR%\%PROTO_BASENAME%"
if errorlevel 1 exit /b 1

:maybe_sphinxdocs
if "%TYPE%"=="sphinxdocs" goto :gen_sphinxdocs
goto :done

:gen_sphinxdocs
echo Generating Sphinx documentation -^> %OUT_DIR%
"%PROTOC%" --experimental_allow_proto3_optional ^
    --plugin=protoc-gen-hikaripb="%PLUGIN%" ^
    --proto_path="%PROTO_DIR%" ^
    --hikaripb_out=type=sphinxdocs,prefix=%PREFIX%%EXTRA%:"%OUT_DIR%" ^
    "%PROTO_DIR%\%PROTO_BASENAME%"
if errorlevel 1 exit /b 1

:done
echo Done.
exit /b 0
