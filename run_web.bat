@echo off
set FLASK_APP=web.app
if "%FLASK_RUN_HOST%"=="" set FLASK_RUN_HOST=0.0.0.0
if "%FLASK_RUN_PORT%"=="" set FLASK_RUN_PORT=5000
flask run
