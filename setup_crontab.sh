#!/bin/bash

# Crontab Setup Script for Trading Bot
# This script helps set up the crontab to run the trading bot every 5 minutes during regular trading hours

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_SCRIPT="$SCRIPT_DIR/run_auto.sh"

echo "Setting up crontab for trading bot..."

# Check if the runner script exists
if [ ! -f "$RUNNER_SCRIPT" ]; then
    echo "ERROR: Runner script not found at $RUNNER_SCRIPT"
    exit 1
fi

# Check if the runner script is executable
if [ ! -x "$RUNNER_SCRIPT" ]; then
    echo "ERROR: Runner script is not executable. Run: chmod +x $RUNNER_SCRIPT"
    exit 1
fi

# Create a temporary crontab file
TEMP_CRON=$(mktemp)

# Get current crontab (if any) and filter out any existing entries for this script
crontab -l 2>/dev/null | grep -v "$RUNNER_SCRIPT" > "$TEMP_CRON" || true

# Add the new crontab entry
# Run every 5 minutes during trading window (9:00 AM - 5:00 PM ET, Monday-Friday)
# The script itself will check if it's within the precise 9:30 AM - 4:30 PM window
cat >> "$TEMP_CRON" << EOF

# Set timezone to Eastern Time for trading hours
TZ=America/New_York

# Trading Bot - Run every 25 minutes during trading window (script handles 9:30 AM - 4:30 PM ET check)
*/25 9-17 * * 1-5 $RUNNER_SCRIPT

EOF

# Install the new crontab
if crontab "$TEMP_CRON"; then
    echo "Crontab installed successfully!"
    echo ""
    echo "The trading bot will now run every 25 minutes during trading hours (9:30 AM - 4:30 PM ET, Mon-Fri)"
    echo "Timezone is enforced as America/New_York (Eastern Time) regardless of system timezone"
    echo ""
    echo "To view the current crontab:"
    echo "  crontab -l"
    echo ""
    echo "To remove the crontab entry:"
    echo "  crontab -e"
    echo "  (then delete the line containing '$RUNNER_SCRIPT')"
    echo ""
    echo "Logs will be stored in: $SCRIPT_DIR/logs/"
else
    echo "ERROR: Failed to install crontab"
    exit 1
fi

# Clean up
rm -f "$TEMP_CRON"

echo "Setup complete!"
