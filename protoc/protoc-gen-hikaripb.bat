@echo off
REM protoc plugin entry point for native Windows: protoc cannot start hikaripb.py itself.
REM   protoc --plugin=protoc-gen-hikaripb=protoc\protoc-gen-hikaripb.bat --hikaripb_out=type=c:out file.proto
REM Set PYTHON to use another interpreter than the "python" on PATH.
if not defined PYTHON set PYTHON=python
"%PYTHON%" "%~dp0hikaripb.py" %*
