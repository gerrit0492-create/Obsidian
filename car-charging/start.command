#!/usr/bin/env bash
# One-click launcher for the Car Charging dashboard (macOS / Linux).
# Double-click this file (macOS) or run ./start.command. First run installs the
# dependencies; after that it opens the dashboard in your browser.
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 was not found. Install it from https://www.python.org/downloads/ and try again."
    read -r -p "Press Enter to close..."
    exit 1
fi

echo "Installing dependencies (first run only)..."
python3 -m pip install --quiet --upgrade pip
python3 -m pip install --quiet -r requirements.txt || {
    echo "Could not install the dependencies. Check your internet connection and try again."
    read -r -p "Press Enter to close..."
    exit 1
}

echo "Starting the dashboard - a browser tab will open at http://localhost:8501"
echo "Keep this window open while you use it. Close it to stop the app."
python3 -m streamlit run app.py
