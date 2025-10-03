# Trading Bot Automation

This document explains how to set up automated execution of the trading bot during regular trading hours.

## Overview

The automation consists of two main components:

1. **`run_auto.sh`** - A shell script that activates the conda environment and runs the trading bot
2. **`setup_crontab.sh`** - A helper script to configure crontab for scheduled execution

## Files Created

- `run_auto.sh` - Main execution script
- `setup_crontab.sh` - Crontab configuration helper
- `logs/` - Directory for log files (created automatically)

## Setup Instructions

### 1. Ensure Prerequisites

Make sure you have:
- Conda installed and available in your PATH
- The `acciodip` conda environment created and configured
- All required dependencies installed in the environment

### 2. Set Up Automated Execution

Run the setup script:

```bash
./setup_crontab.sh
```

This will:
- Configure crontab to run the bot every 5 minutes during trading hours
- Set up proper logging
- Validate that all required files are in place

### 3. Verify Setup

Check that the crontab was installed correctly:

```bash
crontab -l
```

You should see an entry like:
```
TZ=America/New_York
*/5 9-17 * * 1-5 /path/to/your/project/run_auto.sh
```

## Schedule Details

The bot runs:
- **Frequency**: Every 5 minutes
- **Days**: Monday through Friday (weekdays only)
- **Hours**: 9:30 AM to 4:30 PM ET (precise market hours)
- **Timezone**: Enforced as America/New_York (Eastern Time) regardless of system timezone
- **Implementation**: 
  - Cron runs every 5 minutes from 9:00 AM - 5:00 PM ET
  - Script checks current time and only proceeds if between 9:30 AM - 4:30 PM ET
  - Automatic weekend detection and early exit

## Logging

Logs are automatically created in the `logs/` directory:
- **File naming**: `auto_run_YYYYMMDD.log`
- **Content**: Timestamps, execution status, and any errors
- **Rotation**: New file created daily

Example log location:
```
logs/auto_run_20241003.log
```

## Manual Execution

You can also run the script manually for testing:

```bash
./run_auto.sh
```

## Troubleshooting

### Common Issues

1. **Conda environment not found**
   - Ensure the `acciodip` environment exists: `conda env list`
   - Create it if missing: `conda create -n acciodip python=3.11`

2. **Permission denied**
   - Make scripts executable: `chmod +x run_auto.sh setup_crontab.sh`

3. **Crontab not running**
   - Check cron service is running: `sudo launchctl list | grep cron` (macOS)
   - Check system logs for cron errors

4. **Path issues in cron**
   - Cron runs with minimal environment variables
   - The script uses absolute paths to avoid this issue

### Viewing Logs

Check recent activity:
```bash
tail -f logs/auto_run_$(date +%Y%m%d).log
```

Check for errors:
```bash
grep ERROR logs/auto_run_*.log
```

## Stopping Automation

To stop the automated execution:

1. Edit crontab: `crontab -e`
2. Delete or comment out the line containing `run_auto.sh`
3. Save and exit

Or remove all crontab entries:
```bash
crontab -r
```

## Security Considerations

- The script runs with your user permissions
- Ensure your `.env` file and credentials are properly secured
- Monitor logs regularly for any suspicious activity
- Consider running in dry-run mode initially to test

## Environment Variables

The bot respects these environment variables:
- `DRY_RUN` - Set to "false" for live trading (default: "true")
- Other variables as defined in your `.env` file

## Support

If you encounter issues:
1. Check the log files first
2. Verify your conda environment is working
3. Test manual execution of `run_auto.sh`
4. Ensure your trading account credentials are valid
