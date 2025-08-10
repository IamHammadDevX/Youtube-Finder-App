@echo off
set PYTHONPATH=%cd%
python app/scheduler/headless.py --settings settings.json