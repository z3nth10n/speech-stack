@echo off

cd src
..\.venv\Scripts\python.exe -m uvicorn api:app --port 9999 --reload