#!/bin/bash

cd src
../.venv/bin/python -m uvicorn api:app --port 9999 --reload
