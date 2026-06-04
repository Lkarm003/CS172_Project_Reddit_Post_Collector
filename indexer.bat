@echo off
set INPUT_DIR=%1
set INDEX_NAME=%2
if "%INPUT_DIR%"=="" set INPUT_DIR=cleaned_data
if "%INDEX_NAME%"=="" set INDEX_NAME=bluesky_posts
python indexer.py %INPUT_DIR% %INDEX_NAME%
