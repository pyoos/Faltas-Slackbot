#!/usr/bin/env python3
"""
Extract Historical Purchase Requests from Slack Channel

This script scans through the entire Slack channel history and extracts
all previous purchase requests, organizing them by date and saving them
in the same format as the main slackbot.
"""

import os
import json
import csv
import re
import requests
from datetime import datetime
from collections import defaultdict

# Configuration
SLACK_BOT_TOKEN = "xoxb-your-bot-token-here"  # Replace with your actual bot token
CHANNEL_NAME = "#ordering-and-lab-mainatenance"  # Same as main bot
BASE_DIR = "/Users/paul/Desktop/slackbot"
REQUESTS_FOLDER = os.path.join(BASE_DIR, "purchase_requests")
HISTORICAL_FOLDER = os.path.join(REQUESTS_FOLDER, "historical")

# Ensure directories exist
os.makedirs(REQUESTS_FOLDER, exist_ok=True)
os.makedirs(HISTORICAL_FOLDER, exist_ok=True)

def get_channel_id(channel_name):
    """Get the channel ID from channel name."""
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Remove # if present
    channel_name = channel_name.lstrip('#')
    
    response = requests.get("https://slack.com/api/conversations.list", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("ok"):
            for channel in data.get("channels", []):
                if channel.get("name") == channel_name:
                    return channel.get("id")
    
    print(f"❌ Could not find channel: {channel_name}")
    return None

def get_user_info(user_id):
    """Get user's display name from Slack API."""
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(f"https://slack.com/api/users.info?user={user_id}", headers=headers)
        
        if response.status_code == 200:
            resp_json = response.json()
            if resp_json.get("ok"):
                user_info = resp_json.get("user", {})
                profile = user_info.get("profile", {})
                # Try display_name first, then real_name, then fall back to username
                display_name = profile.get("display_name") or profile.get("real_name") or user_info.get("name")
                return display_name
            else:
                print(f"❌ Slack API error for user {user_id}: {resp_json.get('error', 'Unknown error')}")
        else:
            print(f"❌ HTTP error {response.status_code} when getting user info for {user_id}")
    except Exception as e:
        print(f"❌ Exception when getting user info for {user_id}: {e}")
    
    # Fallback: return the user_id if we can't get the display name
    return user_id

def find_original_requester(messages_sorted, current_index, request_data):
    """Find the original user who sent the slash command that triggered this bot response."""
    current_msg = messages_sorted[current_index]
    current_timestamp = float(current_msg.get("ts", "0"))
    
    # Look for messages around the same time (within 60 seconds before the bot message)
    search_window = 60  # seconds
    
    # Search backwards from current message
    for i in range(current_index - 1, max(0, current_index - 50), -1):
        msg = messages_sorted[i]
        msg_timestamp = float(msg.get("ts", "0"))
        msg_text = msg.get("text", "")
        msg_user = msg.get("user", "")
        
        # If message is too old, stop searching
        if current_timestamp - msg_timestamp > search_window:
            break
        
        # Look for slash command that matches this request
        if "/purchase_request" in msg_text.lower():
            # Try to match the item name from the slash command to the bot response
            slash_data = parse_slash_command_format(msg_text)
            if slash_data and request_data:
                # Compare item names (fuzzy match)
                slash_item = slash_data.get('item_name', '').lower().strip()
                bot_item = request_data.get('item_name', '').lower().strip()
                
                # Remove common formatting differences
                slash_item_clean = re.sub(r'[^a-zA-Z0-9\s]', '', slash_item)
                bot_item_clean = re.sub(r'[^a-zA-Z0-9\s]', '', bot_item)
                
                # Check if items match (exact or significant overlap)
                if (slash_item_clean and bot_item_clean and 
                    (slash_item_clean == bot_item_clean or 
                     slash_item_clean in bot_item_clean or 
                     bot_item_clean in slash_item_clean or
                     len(set(slash_item_clean.split()) & set(bot_item_clean.split())) >= 2)):
                    
                    # Found matching slash command, get user info
                    user_info = get_user_info(msg_user)
                    if user_info:
                        return user_info
    
    # If no exact match found, look for any slash command around the same time
    for i in range(max(0, current_index - 10), min(len(messages_sorted), current_index + 3)):
        if i == current_index:
            continue
            
        msg = messages_sorted[i]
        msg_timestamp = float(msg.get("ts", "0"))
        msg_text = msg.get("text", "")
        msg_user = msg.get("user", "")
        
        # Within a smaller window for fallback
        if abs(current_timestamp - msg_timestamp) <= 30:
            if "/purchase_request" in msg_text.lower():
                user_info = get_user_info(msg_user)
                if user_info:
                    return user_info
    
    return None

def get_channel_history(channel_id):
    """Get all messages from the channel."""
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    all_messages = []
    cursor = None
    
    print("📥 Fetching channel history...")
    
    while True:
        params = {
            "channel": channel_id,
            "limit": 1000  # Maximum allowed
        }
        
        if cursor:
            params["cursor"] = cursor
        
        response = requests.get("https://slack.com/api/conversations.history", 
                              headers=headers, params=params)
        
        if response.status_code != 200:
            print(f"❌ API request failed: {response.status_code}")
            break
            
        data = response.json()
        
        if not data.get("ok"):
            print(f"❌ API error: {data.get('error')}")
            break
        
        messages = data.get("messages", [])
        all_messages.extend(messages)
        
        print(f"   Fetched {len(messages)} messages (total: {len(all_messages)})")
        
        # Check if there are more messages
        if not data.get("has_more"):
            break
            
        cursor = data.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    
    print(f"✅ Total messages fetched: {len(all_messages)}")
    return all_messages

def parse_purchase_request(message_text):
    """Extract purchase request data from a message - handles multiple formats."""
    
    # Format 1: Slash command format - "/purchase_request Item, Quantity, Catalog, Link, Date"
    slash_format = parse_slash_command_format(message_text)
    if slash_format:
        slash_format['format_type'] = 'slash_command'
        return slash_format
    
    # Format 2: Current bot format - "*New Purchase Request by {name}:*"
    current_format = parse_current_format(message_text)
    if current_format:
        current_format['format_type'] = 'current_bot'
        return current_format
    
    # Format 3: Look for other potential purchase request patterns
    alternative_format = parse_alternative_formats(message_text)
    if alternative_format:
        alternative_format['format_type'] = 'alternative'
        return alternative_format
    
    return None

def parse_slash_command_format(message_text):
    """Parse the /purchase_request slash command format."""
    # Look for /purchase_request followed by comma-separated values
    slash_pattern = r'/purchase_request\s+(.+)'
    
    match = re.search(slash_pattern, message_text, re.IGNORECASE)
    if not match:
        return None
    
    # Extract the part after /purchase_request
    params_text = match.group(1).strip()
    
    # Split by commas and clean up
    parts = [part.strip() for part in params_text.split(',')]
    
    if len(parts) < 3:  # Need at least item, quantity, catalog
        return None
    
    extracted_data = {
        'confidence': 'high',
        'format_type': 'slash_command'
    }
    
    # Parse the parts
    if len(parts) >= 1:
        item_name = parts[0]
        # Remove asterisks and quotes from item name
        item_name = re.sub(r'[\*"\']', '', item_name).strip()
        extracted_data['item_name'] = item_name
    
    if len(parts) >= 2:
        quantity = parts[1].strip()
        # Remove asterisks and quotes
        quantity = re.sub(r'[\*"\']', '', quantity).strip()
        extracted_data['quantity'] = quantity
    
    if len(parts) >= 3:
        catalog = parts[2].strip()
        # Remove asterisks and quotes
        catalog = re.sub(r'[\*"\']', '', catalog).strip()
        extracted_data['catalog_number'] = catalog
    
    if len(parts) >= 4:
        link = parts[3].strip()
        # Extract URL from <URL> format
        url_match = re.search(r'<(https?://[^>]+)>', link)
        if url_match:
            extracted_data['link'] = url_match.group(1)
        elif link.startswith('http'):
            extracted_data['link'] = link
    
    if len(parts) >= 5:
        date = parts[4].strip()
        extracted_data['date_of_request'] = date
    
    return extracted_data

def parse_current_format(message_text):
    """Parse the current bot format."""
    request_pattern = r'\*New Purchase Request by (.+?):\*'
    
    if not re.search(request_pattern, message_text):
        return None
    
    # Extract the requester name
    name_match = re.search(request_pattern, message_text)
    requester_name = name_match.group(1) if name_match else "Unknown"
    
    # Extract individual fields using bullet points
    patterns = {
        'item_name': r'• \*Item:\* (.+?)(?:\n|$)',
        'quantity': r'• \*Quantity:\* (.+?)(?:\n|$)',
        'catalog_number': r'• \*Catalog #:\* (.+?)(?:\n|$)',
        'link': r'• \*Link:\* (.+?)(?:\n|$)',
        'date_of_request': r'• \*Date:\* (.+?)(?:\n|$)'
    }
    
    extracted_data = {
        'requester_name': requester_name
    }
    
    for field, pattern in patterns.items():
        match = re.search(pattern, message_text)
        if match:
            extracted_data[field] = match.group(1).strip()
        else:
            # If we can't find all required fields, this isn't a valid purchase request
            return None
    
    return extracted_data

def parse_alternative_formats(message_text):
    """Parse alternative formats that might be purchase requests from bots."""
    
    # Bot message patterns - much more specific for actual purchase request messages
    bot_patterns = [
        # Pattern 1: "Purchase request added: *item* (Quantity: X, Catalog #: Y)"
        r'Purchase request added:\s*\*?["\']?([^*"\']+?)\*?["\']?\s*\((?:.*?Quantity:\s*["\']?([^,"\']+)["\']?)?(?:.*?Catalog #?:\s*["\']?([^,"\']+)["\']?)?\)',
        
        # Pattern 2: Simple "Item Name (Quantity: X, Catalog: Y)"
        r'\*?["\']?([^*"\'()]+?)\*?["\']?\s*\(\s*(?:Quantity:\s*["\']?([^,"\']+)["\']?)?(?:.*?Catalog[^:]*:\s*["\']?([^,"\']+)["\']?)?\)',
        
        # Pattern 3: "Product name: X (Quantity: Y)"
        r'Product name:\s*\*?["\']?([^*"\']+?)\*?["\']?\s*\(\s*(?:Quantity:\s*["\']?([^,"\']+)["\']?)?',
        
        # Pattern 4: Look for quoted items with catalog numbers
        r'["\']([^"\']+)["\'].*?(?:Catalog[^:]*:\s*["\']?([^,"\']+)["\']?)?.*?(?:Quantity:\s*["\']?([^,"\']+)["\']?)?',
        
        # Pattern 5: Items with asterisks and parentheses
        r'\*([^*]+)\*\s*\([^)]*\)',
    ]
    
    # Only proceed if message contains purchase-related indicators
    purchase_indicators = ['purchase request', 'catalog', 'quantity', 'requested', 'added:', 'item']
    text_lower = message_text.lower()
    
    if not any(indicator in text_lower for indicator in purchase_indicators):
        return None
    
    extracted_data = {
        'message_text': message_text,
        'confidence': 'medium',
        'format_type': 'bot_format'
    }
    
    # Try each pattern
    for pattern in bot_patterns:
        match = re.search(pattern, message_text, re.IGNORECASE | re.DOTALL)
        if match:
            groups = match.groups()
            
            if groups[0]:  # Item name found
                extracted_data['item_name'] = groups[0].strip()
                
                # Try to get quantity and catalog from the match
                if len(groups) > 1 and groups[1]:
                    extracted_data['quantity'] = groups[1].strip()
                if len(groups) > 2 and groups[2]:
                    extracted_data['catalog_number'] = groups[2].strip()
                
                break
    
    # If no item found with patterns, try simpler extraction
    if 'item_name' not in extracted_data:
        # Look for items in quotes or asterisks
        simple_patterns = [
            r'\*([^*]+)\*',  # *item*
            r'"([^"]+)"',    # "item"
            r"'([^']+)'",    # 'item'
        ]
        
        for pattern in simple_patterns:
            matches = re.findall(pattern, message_text)
            for match in matches:
                # Skip if it's obviously not an item (too short, common words, etc.)
                if len(match.strip()) > 3 and not match.lower() in ['quantity', 'catalog', 'link', 'date']:
                    extracted_data['item_name'] = match.strip()
                    break
            if 'item_name' in extracted_data:
                break
    
    # Extract additional fields with more patterns
    if 'item_name' in extracted_data:
        # Look for quantity more broadly
        quantity_patterns = [
            r'quantity[:\s]+["\']?(\d+(?:\.\d+)?)["\']?',
            r'qty[:\s]+["\']?(\d+(?:\.\d+)?)["\']?',
            r'\(\s*quantity[:\s]*["\']?(\d+(?:\.\d+)?)["\']?',
            r'(\d+)\s*(?:units?|pcs?|pieces?)',
        ]
        
        for pattern in quantity_patterns:
            match = re.search(pattern, message_text, re.IGNORECASE)
            if match:
                extracted_data['quantity'] = match.group(1)
                break
        
        # Look for catalog numbers more broadly
        catalog_patterns = [
            r'catalog[^:]*:\s*["\']?([A-Z0-9\-_.]+)["\']?',
            r'cat[^:]*:\s*["\']?([A-Z0-9\-_.]+)["\']?',
            r'part[^:]*:\s*["\']?([A-Z0-9\-_.]+)["\']?',
            r'#\s*([A-Z0-9\-_.]+)',
        ]
        
        for pattern in catalog_patterns:
            match = re.search(pattern, message_text, re.IGNORECASE)
            if match:
                extracted_data['catalog_number'] = match.group(1)
                break
        
        # Look for URLs
        url_match = re.search(r'https?://[^\s\)>]+', message_text)
        if url_match:
            extracted_data['link'] = url_match.group(0)
        
        # Look for dates
        date_patterns = [
            r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            r'(\d{4}-\d{1,2}-\d{1,2})',
            r'on\s+["\']?([^"\']+)["\']?',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, message_text, re.IGNORECASE)
            if match:
                extracted_data['date_of_request'] = match.group(1)
                break
        
        return extracted_data
    
    return None

def save_requests_by_month(requests_by_month):
    """Save extracted requests organized by month."""
    for month, requests in requests_by_month.items():
        if not requests:
            continue
            
        # Create filenames for this month
        json_file = os.path.join(HISTORICAL_FOLDER, f"historical_requests_{month}.json")
        csv_file = os.path.join(HISTORICAL_FOLDER, f"historical_requests_{month}.csv")
        
        # Save to JSON
        with open(json_file, 'w') as f:
            json.dump(requests, f, indent=2)
        
        # Save to CSV
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            # Write header
            writer.writerow(["requester_name", "item_name", "quantity", "catalog_number", "link", "date_of_request", "slack_timestamp", "format_type", "confidence", "extracted_date", "original_user_id"])
            
            # Write requests
            for req in requests:
                writer.writerow([
                    req.get("requester_name", "Unknown"),
                    req.get("item_name", ""),
                    req.get("quantity", ""),
                    req.get("catalog_number", ""),
                    req.get("link", ""),
                    req.get("date_of_request", ""),
                    req.get("slack_timestamp", ""),
                    req.get("format_type", ""),
                    req.get("confidence", "high"),
                    req.get("extracted_date", ""),
                    req.get("original_user_id", "")
                ])
        
        print(f"✅ Saved {len(requests)} requests for {month}")
        print(f"   JSON: {json_file}")
        print(f"   CSV:  {csv_file}")

def analyze_message_authors(messages):
    """Analyze who sent messages to identify potential bots."""
    user_message_counts = {}
    user_samples = {}
    
    for message in messages:
        user_id = message.get("user", "")
        message_text = message.get("text", "")
        
        if user_id:
            if user_id not in user_message_counts:
                user_message_counts[user_id] = 0
                user_samples[user_id] = []
            
            user_message_counts[user_id] += 1
            
            # Keep a few sample messages from each user
            if len(user_samples[user_id]) < 3:
                user_samples[user_id].append(message_text[:100])
    
    print("\n👥 Top message senders (potential bots):")
    sorted_users = sorted(user_message_counts.items(), key=lambda x: x[1], reverse=True)
    
    for i, (user_id, count) in enumerate(sorted_users[:10]):
        user_info = get_user_info(user_id)
        user_name = user_info if user_info else user_id
        print(f"   {i+1}. {user_name} ({user_id}): {count} messages")
        
        # Show sample messages to help identify bots
        for j, sample in enumerate(user_samples[user_id]):
            print(f"      Sample {j+1}: {sample}...")
        print()
    
    return sorted_users

def main():
    """Main execution function."""
    print("🔍 Historical Purchase Request Extractor")
    print("=" * 50)
    
    # Get channel ID
    channel_id = get_channel_id(CHANNEL_NAME)
    if not channel_id:
        return
    
    print(f"✅ Found channel ID: {channel_id}")
    
    # Get all messages
    messages = get_channel_history(channel_id)
    
    if not messages:
        print("❌ No messages found")
        return
    
    # Analyze message authors to identify potential bots
    user_stats = analyze_message_authors(messages)
    
    # Ask user to specify bot user or auto-detect
    print("🤖 Looking for potential purchasing bot messages...")
    bot_keywords = ['purchase', 'request', 'added', 'order', 'item', 'catalog']
    
    potential_bots = []
    for user_id, count in user_stats[:5]:  # Check top 5 message senders
        user_messages = [msg for msg in messages if msg.get("user") == user_id]
        bot_message_count = 0
        
        for msg in user_messages[:20]:  # Sample first 20 messages
            text_lower = msg.get("text", "").lower()
            if any(keyword in text_lower for keyword in bot_keywords):
                bot_message_count += 1
        
        if bot_message_count >= 5:  # If 5+ messages contain bot keywords
            user_info = get_user_info(user_id) 
            user_name = user_info if user_info else user_id
            potential_bots.append((user_id, user_name, bot_message_count, count))
            print(f"   🤖 Potential bot: {user_name} ({bot_message_count}/{min(20, count)} messages have purchase keywords)")
    
    # Check for slash command users specifically
    print(f"\n🎯 Looking for /purchase_request command users...")
    slash_command_users = []
    
    for user_id, count in user_stats[:10]:  # Check top 10 users
        user_messages = [msg for msg in messages if msg.get("user") == user_id]
        slash_count = sum(1 for msg in user_messages if '/purchase_request' in msg.get("text", "").lower())
        
        if slash_count > 0:
            user_info = get_user_info(user_id)
            user_name = user_info if user_info else user_id
            slash_command_users.append((user_id, user_name, slash_count, count))
            print(f"   📝 {user_name}: {slash_count} /purchase_request commands")
    
    if slash_command_users:
        print(f"\n🎯 Extracting from ALL users with /purchase_request commands...")
        # Get messages from ALL users who use slash commands
        all_slash_users = [user_id for user_id, _, _, _ in slash_command_users]
        user_messages = [msg for msg in messages if msg.get("user") in all_slash_users]
        print(f"   Found {len(user_messages)} messages from slash command users")
        messages = user_messages
    elif potential_bots:
        print(f"\n🎯 Falling back to bot detection...")
        # Use the most likely bot (highest ratio of purchase keywords)
        selected_bot = max(potential_bots, key=lambda x: x[2])
        bot_user_id, bot_name, keyword_count, total_count = selected_bot
        print(f"   Selected bot: {bot_name} (ID: {bot_user_id})")
        
        # Filter messages to only those from the bot
        bot_messages = [msg for msg in messages if msg.get("user") == bot_user_id]
        print(f"   Bot sent {len(bot_messages)} total messages")
        
        messages = bot_messages  # Replace messages with only bot messages
    else:
        print("   ❌ No clear bot identified, analyzing all messages...")
    
    # Extract purchase requests
    print(f"\n🔍 Analyzing {len(messages)} messages for purchase requests...")
    
    # Sort messages by timestamp to maintain chronological order
    messages_sorted = sorted(messages, key=lambda x: float(x.get("ts", "0")))
    
    requests_by_month = defaultdict(list)
    total_requests = 0
    
    for i, message in enumerate(messages_sorted):
        message_text = message.get("text", "")
        timestamp = message.get("ts", "")
        user_id = message.get("user", "")
        
        # Parse the message
        request_data = parse_purchase_request(message_text)
        
# Debug removed - user ID capture is working
        
        if request_data:
            # Add Slack timestamp for reference
            request_data["slack_timestamp"] = timestamp
            
            # Determine the requester based on the format type
            format_type = request_data.get('format_type', '')
            
            if format_type == 'slash_command' and user_id:
                # This IS the original slash command, so use this user directly
                display_name = get_user_info(user_id)
                request_data["requester_name"] = display_name
                request_data["original_user_id"] = user_id
            else:
                # For bot messages or other formats, try to find the original requester
                original_requester = find_original_requester(messages_sorted, i, request_data)
                if original_requester:
                    # original_requester might be a user_id, so get the display name
                    display_name = get_user_info(original_requester)
                    request_data["requester_name"] = display_name
                    request_data["original_user_id"] = original_requester
                elif user_id:
                    # Fallback: use the current message user ID
                    display_name = get_user_info(user_id)
                    request_data["requester_name"] = display_name
                    request_data["original_user_id"] = user_id
            
            # Convert timestamp to readable date
            if timestamp:
                try:
                    msg_date = datetime.fromtimestamp(float(timestamp))
                    month_key = msg_date.strftime("%Y-%m")
                    request_data["extracted_date"] = msg_date.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    month_key = "unknown"
                    request_data["extracted_date"] = "unknown"
            else:
                month_key = "unknown"
                request_data["extracted_date"] = "unknown"
            
            requests_by_month[month_key].append(request_data)
            total_requests += 1
            
            format_type = request_data.get('format_type', 'unknown')
            confidence = request_data.get('confidence', 'high')
            requester = request_data.get('requester_name', 'Unknown')
            item = request_data.get('item_name', 'No item found')
            
            print(f"   ✅ Found request ({format_type}, {confidence}) by {requester}: {item}")
            
            # For low confidence matches, show a snippet of the original message
            if confidence == 'low':
                snippet = message_text[:100] + "..." if len(message_text) > 100 else message_text
                print(f"      Original: {snippet}")
    
    print(f"\n📊 Summary:")
    print(f"   Total purchase requests found: {total_requests}")
    print(f"   Organized into {len(requests_by_month)} months")
    
    if total_requests > 0:
        print(f"\n💾 Saving requests...")
        save_requests_by_month(requests_by_month)
        
        print(f"\n✅ Extraction complete!")
        print(f"   Files saved in: {HISTORICAL_FOLDER}")
    else:
        print("❌ No purchase requests found in channel history")

if __name__ == "__main__":
    main() 