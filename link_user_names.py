#!/usr/bin/env python3
"""
Link User Names to Historical Purchase Requests

This script extracts all unique user IDs from the historical data,
creates a mapping file for real names, and updates the CSV files.
"""

import os
import json
import csv
import glob
from collections import defaultdict

# Paths
BASE_DIR = "/Users/paul/Desktop/slackbot"
HISTORICAL_FOLDER = os.path.join(BASE_DIR, "purchase_requests", "historical")
MAPPING_FILE = os.path.join(BASE_DIR, "user_id_mapping.json")

def extract_unique_user_ids():
    """Extract all unique user IDs from historical JSON files."""
    user_ids = set()
    user_stats = defaultdict(int)
    
    # Find all historical JSON files
    json_files = glob.glob(os.path.join(HISTORICAL_FOLDER, "*.json"))
    
    for json_file in json_files:
        with open(json_file, 'r') as f:
            data = json.load(f)
            
        for request in data:
            user_id = request.get('original_user_id') or request.get('requester_name')
            if user_id and user_id.startswith('U'):
                user_ids.add(user_id)
                user_stats[user_id] += 1
    
    return user_ids, user_stats

def create_mapping_file(user_ids, user_stats):
    """Create a mapping file template for user names."""
    mapping = {}
    
    # Load existing mapping if it exists
    if os.path.exists(MAPPING_FILE):
        with open(MAPPING_FILE, 'r') as f:
            mapping = json.load(f)
    
    # Add new user IDs with placeholder names
    for user_id in user_ids:
        if user_id not in mapping:
            mapping[user_id] = f"User_{user_id[-4:]}"  # Use last 4 chars as placeholder
    
    # Save the mapping file
    with open(MAPPING_FILE, 'w') as f:
        json.dump(mapping, f, indent=2)
    
    print(f"📝 User mapping file created: {MAPPING_FILE}")
    print("\n👥 User IDs found (with request counts):")
    for user_id in sorted(user_ids, key=lambda x: user_stats[x], reverse=True):
        current_name = mapping[user_id]
        print(f"   {user_id}: {user_stats[user_id]} requests → {current_name}")
    
    return mapping

def update_csv_files(mapping):
    """Update all CSV files with real names from the mapping."""
    csv_files = glob.glob(os.path.join(HISTORICAL_FOLDER, "*.csv"))
    
    for csv_file in csv_files:
        print(f"📄 Updating: {os.path.basename(csv_file)}")
        
        # Read the CSV file
        rows = []
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Update requester_name with mapped name
                user_id = row.get('original_user_id') or row.get('requester_name')
                if user_id in mapping:
                    row['requester_name'] = mapping[user_id]
                rows.append(row)
        
        # Write back the updated CSV
        if rows:
            with open(csv_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

def main():
    print("🔗 User Name Linking Tool")
    print("=" * 50)
    
    # Extract unique user IDs
    user_ids, user_stats = extract_unique_user_ids()
    
    if not user_ids:
        print("❌ No user IDs found in historical data!")
        return
    
    print(f"✅ Found {len(user_ids)} unique users")
    
    # Create/update mapping file
    mapping = create_mapping_file(user_ids, user_stats)
    
    print("\n📝 Instructions:")
    print("1. Edit the file: user_id_mapping.json")
    print("2. Replace the placeholder names (User_XXXX) with real names")
    print("3. Run this script again to update all CSV files")
    
    # Ask if user wants to update CSVs now
    choice = input("\n❓ Do you want to update CSV files with current mapping? (y/n): ").lower().strip()
    
    if choice == 'y':
        update_csv_files(mapping)
        print("\n✅ All CSV files updated with mapped names!")
    else:
        print("\n💡 Run this script again after updating the mapping file to apply changes.")

if __name__ == "__main__":
    main() 