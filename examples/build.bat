@echo off
setlocal enabledelayedexpansion
REM Prepare the examples: generate the C, C++ and Python bindings and the Sphinx documentation of
REM examples\proto\weather.proto into build\examples\generated, build the C and C++ examples into
REM build\examples\bin and the documentation into build\examples\docs.
REM
REM Usage: examples\build.bat
REM
REM Requires protoc and the Python packages in protoc\requirements.txt (see scripts\generate.bat). The examples are only
REM built when a compiler is found (CC / CXX, default gcc / g++); the Python example needs no build. The documentation
REM is only built when sphinx-build and the Python package myst_parser are installed.

for %%I in ("%~dp0.") do set EXAMPLES_DIR=%%~fI
for %%I in ("%EXAMPLES_DIR%\..") do set ROOT_DIR=%%~fI
set SCRIPT_DIR=%ROOT_DIR%\scripts\
set OUT_DIR=%ROOT_DIR%\build\examples
set GEN_DIR=%OUT_DIR%\generated
set BIN_DIR=%OUT_DIR%\bin
set PROTO_FILE=%EXAMPLES_DIR%\proto\weather.proto

if not defined CC set CC=gcc
if not defined CXX set CXX=g++

if exist "%OUT_DIR%" rmdir /s /q "%OUT_DIR%"

REM One prefix per backend keeps the runtime files of the C and C++ output apart, so both directories can be on
REM one include path (see .vscode\settings.json).
call "%SCRIPT_DIR%generate.bat" "%PROTO_FILE%" "%GEN_DIR%\c" weather_c c
if errorlevel 1 exit /b 1
call "%SCRIPT_DIR%generate.bat" "%PROTO_FILE%" "%GEN_DIR%\cpp" weather_cpp cpp
if errorlevel 1 exit /b 1
call "%SCRIPT_DIR%generate.bat" "%PROTO_FILE%" "%GEN_DIR%\py" weather_py py
if errorlevel 1 exit /b 1
call "%SCRIPT_DIR%generate.bat" "%PROTO_FILE%" "%GEN_DIR%\sphinx" weather_docs sphinxdocs "title=Weather+station+protocol"
if errorlevel 1 exit /b 1

mkdir "%BIN_DIR%"

REM -Wno-unused-parameter: the generated inline setters only use their handle parameter in debug assertions.
REM !var! instead of %var% inside the blocks: a closing parenthesis in a path would end the block.
where %CC% >nul 2>&1
if errorlevel 1 (
    echo No C compiler found ^(!CC!^), the C example is not built.
) else (
    echo Building the C example -^> !BIN_DIR!\weather_c.exe
    set SOURCES=
    for %%F in ("!GEN_DIR!\c\*.c") do set SOURCES=!SOURCES! "%%F"
    "!CC!" -std=c11 -Wall -Wextra -Wno-unused-parameter -g -I"!EXAMPLES_DIR!\c" -I"!GEN_DIR!\c" "!EXAMPLES_DIR!\c\main.c" !SOURCES! -o "!BIN_DIR!\weather_c.exe"
    if errorlevel 1 exit /b 1
)

where %CXX% >nul 2>&1
if errorlevel 1 (
    echo No C++ compiler found ^(!CXX!^), the C++ example is not built.
) else (
    echo Building the C++ example -^> !BIN_DIR!\weather_cpp.exe
    set SOURCES=
    for %%F in ("!GEN_DIR!\cpp\*.cc") do set SOURCES=!SOURCES! "%%F"
    "!CXX!" -std=c++17 -Wall -Wextra -Wno-unused-parameter -g -I"!EXAMPLES_DIR!\cpp" -I"!GEN_DIR!\cpp" "!EXAMPLES_DIR!\cpp\main.cc" !SOURCES! -o "!BIN_DIR!\weather_cpp.exe"
    if errorlevel 1 exit /b 1
)

where sphinx-build >nul 2>&1
if errorlevel 1 (
    echo sphinx-build not found, the documentation is not built.
) else (
    python -c "import myst_parser" >nul 2>&1
    if errorlevel 1 (
        echo myst_parser not found, the documentation is not built.
    ) else (
        echo Building the documentation -^> !OUT_DIR!\docs
        sphinx-build -q -b html "!GEN_DIR!\sphinx" "!OUT_DIR!\docs"
        if errorlevel 1 exit /b 1
    )
)

echo Examples are ready:
echo   %BIN_DIR%\weather_c.exe
echo   %BIN_DIR%\weather_cpp.exe
echo   python %EXAMPLES_DIR%\py\main.py
echo   %GEN_DIR%\sphinx (Sphinx sources of the documentation)
exit /b 0
