# Configuration Template for Purchase Request Slackbot
# Copy this file to config.py and fill in your actual values

# Slack Configuration
SLACK_BOT_TOKEN = "xoxb-your-bot-token-here"  # Get this from your Slack App settings > OAuth & Permissions

# Channel Configuration  
CHANNEL_NAME = "#your-channel-name"  # The channel where purchase requests are submitted

# File Storage Configuration
BASE_DIR = "/path/to/your/slackbot/folder"  # Update this to your actual folder path

# Instructions:
# 1. Copy this file: cp config_template.py config.py
# 2. Edit config.py with your actual values
# 3. Import in your scripts: from config import SLACK_BOT_TOKEN, CHANNEL_NAME, BASE_DIR
# 4. Never commit config.py to version control (it's in .gitignore)

# Environment Variable Alternative:
# Instead of using config.py, you can set environment variables:
# export SLACK_BOT_TOKEN="your-actual-token"
# export CHANNEL_NAME="#your-channel"
# export BASE_DIR="/your/path" 