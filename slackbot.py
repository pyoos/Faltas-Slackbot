from flask import Flask, request, jsonify
import os
import json
import csv
from datetime import datetime
import requests

app = Flask(__name__)

# Slack Config
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "xoxb-your-bot-token-here")  # Set your bot token as environment variable or replace this placeholder
SLACK_API_URL = "https://slack.com/api/chat.postMessage"
CHANNEL_NAME = "#ordering-and-lab-mainatenance"  # Slack channel name

# Base folder for storing requests
BASE_DIR = "/Users/paul/Desktop/slackbot"
REQUESTS_FOLDER = os.path.join(BASE_DIR, "purchase_requests")
os.makedirs(REQUESTS_FOLDER, exist_ok=True)


def get_monthly_file():
    """Return file paths for current month's JSON and CSV files."""
    current_month = datetime.now().strftime("%Y-%m")
    json_file = os.path.join(REQUESTS_FOLDER, f"purchase_requests_{current_month}.json")
    csv_file = os.path.join(REQUESTS_FOLDER, f"purchase_requests_{current_month}.csv")
    return json_file, csv_file


def load_purchase_requests():
    """Load purchase requests from the current month's JSON file."""
    json_file, _ = get_monthly_file()
    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            return json.load(f)
    return []

def save_purchase_requests(purchase_requests):
    """Save purchase requests to both JSON and CSV files."""
    json_file, csv_file = get_monthly_file()
    
    # Save to JSON file (for loading)
    with open(json_file, 'w') as f:
        json.dump(purchase_requests, f, indent=2)
    
    # Also save to CSV file (for easy viewing)
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        # Write header
        writer.writerow(["item_name", "quantity", "catalog_number", "link", "date_of_request"])
        
        # Write all purchase requests
        for req in purchase_requests:
            if all(key in req for key in ["item_name", "quantity", "catalog_number", "link", "date_of_request"]):
                writer.writerow([req["item_name"], req["quantity"], req["catalog_number"], req["link"], req["date_of_request"]])

def get_user_display_name(user_id):
    """Get user's display name from Slack API."""
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(f"https://slack.com/api/users.info?user={user_id}", headers=headers)
    
    if response.status_code == 200:
        resp_json = response.json()
        if resp_json.get("ok"):
            user_info = resp_json.get("user", {})
            profile = user_info.get("profile", {})
            # Try display_name first, then real_name, then fall back to username
            display_name = profile.get("display_name") or profile.get("real_name") or user_info.get("name")
            return display_name
    
    return None

def post_to_slack(channel, message_text):
    """Send a message to Slack channel using chat.postMessage API."""
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "channel": channel,  # Can use channel ID or #channel-name
        "text": message_text
    }

    response = requests.post(SLACK_API_URL, headers=headers, json=payload)
    print("Slack API Request Payload:", payload)
    print("Slack API Response:", response.status_code, response.text)

    if response.status_code != 200:
        return False
    resp_json = response.json()
    if not resp_json.get("ok"):
        print("Error from Slack API:", resp_json.get("error"))
        return False
    return True


@app.route("/health", methods=["GET"])
def health_check():
    """Simple health check endpoint to verify the app is running."""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route("/slack/commands", methods=["POST"])
def handle_slash_command():
    try:
        text = request.form.get("text", "")
        user_name = request.form.get("user_name", "unknown user")
        user_id = request.form.get("user_id", "")
        
        # Get the user's display name from Slack API
        display_name = get_user_display_name(user_id)
        # Fall back to username if we can't get display name
        user_display_name = display_name if display_name else user_name
        
        print(f"Received slash command from {user_display_name} ({user_name}): {text}")

        # Expect format: Item, Quantity, CatalogNumber, Link, Date
        parts = [p.strip() for p in text.split(",")]
        if len(parts) < 5:
            return jsonify({
                "response_type": "in_channel",
                "text": "Invalid format. Use:\n`Item, Quantity, Catalog Number, Link, Date`"
            })
        elif len(parts) > 5:
            return jsonify({
                "response_type": "in_channel",
                "text": "Too many commas in input. Use exactly:\n`Item, Quantity, Catalog Number, Link, Date`"
            })

        item, quantity, catalog_number, link, date = parts

        # Load, append, save
        purchase_requests = load_purchase_requests()
        new_request = {
            "item_name": item,
            "quantity": quantity,
            "catalog_number": catalog_number,
            "link": link,
            "date_of_request": date
        }
        purchase_requests.append(new_request)
        save_purchase_requests(purchase_requests)

        # Build Slack message
        message_text = (
            f"*New Purchase Request by {user_display_name}:*\n"
            f"• *Item:* {item}\n"
            f"• *Quantity:* {quantity}\n"
            f"• *Catalog #:* {catalog_number}\n"
            f"• *Link:* {link}\n"
            f"• *Date:* {date}"
        )

        # Post to channel
        success = post_to_slack(CHANNEL_NAME, message_text)

        if success:
            return jsonify({
                "response_type": "ephemeral",
                "text": f"✅ Your purchase request has been submitted!\n\n*What you submitted:*\n• *Item:* {item}\n• *Quantity:* {quantity}\n• *Catalog #:* {catalog_number}\n• *Link:* {link}\n• *Date:* {date}\n\nThis has been posted to {CHANNEL_NAME} for the team to see."
            })
        else:
            return jsonify({
                "response_type": "ephemeral",
                "text": "❌ Failed to post to Slack channel. Check logs and try again."
            })
    
    except Exception as e:
        print(f"Error in slash command handler: {e}")
        return jsonify({
            "response_type": "in_channel",
            "text": "❌ An error occurred while processing your request. Please try again."
        })


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3000, debug=True)
