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

# Add the new crontab entries
# Run every 5 minutes during regular trading hours (9:30 AM - 4:00 PM ET, Monday-Friday)
# Note: These times are in the system's local timezone. Adjust if your system is not in ET.
cat >> "$TEMP_CRON" << EOF

# Trading Bot - Run every 5 minutes during regular trading hours (9:30 AM - 4:00 PM ET, Mon-Fri)
# Minutes: */5 (every 5 minutes)
# Hours: 9-16 (9 AM to 4 PM, but we'll handle the 9:30 start in the script logic)
# Day of month: * (every day)
# Month: * (every month)
# Day of week: 1-5 (Monday to Friday)
*/5 9-16 * * 1-5 $RUNNER_SCRIPT

EOF

# Install the new crontab
if crontab "$TEMP_CRON"; then
    echo "Crontab installed successfully!"
    echo ""
    echo "The trading bot will now run every 5 minutes during trading hours (9:30 AM - 4:00 PM ET, Mon-Fri)"
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
