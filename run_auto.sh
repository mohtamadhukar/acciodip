#!/bin/bash

# Trading Bot Auto Runner Script
# This script activates the conda environment and runs the trading bot in auto mode
# Designed to be run via crontab every 5 minutes during trading hours

# Set strict error handling
set -euo pipefail

# Define paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/auto_run_$(date +%Y%m%d).log"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log messages with timestamp
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to cleanup on exit
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_message "ERROR: Script exited with code $exit_code"
    fi
    exit $exit_code
}

# Set trap for cleanup
trap cleanup EXIT

# Start logging
log_message "Starting trading bot auto run..."

# Check if we're within trading hours (9:30 AM - 4:30 PM ET)
# Set timezone to Eastern Time for the check
export TZ=America/New_York
current_time=$(date +%H%M)
current_day=$(date +%u)  # 1=Monday, 7=Sunday

# Check if it's a weekday (1-5 = Monday-Friday)
if [ "$current_day" -gt 5 ]; then
    log_message "Outside trading hours: Weekend (day $current_day). Exiting."
    exit 0
fi

# Check if we're within 9:30 AM (0930) to 4:30 PM (1630) ET
if [ "$current_time" -lt 930 ] || [ "$current_time" -gt 1630 ]; then
    log_message "Outside trading hours: Current time $current_time ET is not between 0930-1630. Exiting."
    exit 0
fi

log_message "Within trading hours ($current_time ET). Proceeding with bot execution."

# Check if conda is available
if ! command -v conda &> /dev/null; then
    log_message "ERROR: conda command not found. Please ensure conda is installed and in PATH."
    exit 1
fi

# Initialize conda for bash (required for conda activate to work in scripts)
eval "$(conda shell.bash hook)"

# Activate the conda environment
log_message "Activating conda environment 'acciodip'..."
if ! conda activate acciodip 2>> "$LOG_FILE"; then
    log_message "ERROR: Failed to activate conda environment 'acciodip'. Please ensure the environment exists."
    exit 1
fi

# Change to the project directory
cd "$SCRIPT_DIR"
log_message "Changed to project directory: $SCRIPT_DIR"

# Check if main.py exists
if [ ! -f "main.py" ]; then
    log_message "ERROR: main.py not found in $SCRIPT_DIR"
    exit 1
fi

# Run the trading bot in auto mode
log_message "Running trading bot in auto mode..."
if python main.py --mode auto >> "$LOG_FILE" 2>&1; then
    log_message "Trading bot completed successfully"
else
    log_message "ERROR: Trading bot failed with exit code $?"
    exit 1
fi

log_message "Auto run completed successfully"
