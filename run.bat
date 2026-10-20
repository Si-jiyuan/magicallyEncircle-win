@echo off
rem Run the app with the project's Python 3.11 environment.
setlocal
set PYTHON=%PYTHON%
if "%PYTHON%"=="" set PYTHON=D:\work\env\miniconda\envs\p3.11\python.exe
"%PYTHON%" "%~dp0run_app.py" %*
