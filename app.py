from flask import Flask, render_template, jsonify
import json
import os
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv("C:/Users/jwils/Desktop/LMS/.env.txt")

app = Flask(__name__)

# Define the path to the configuration file and data file from environment variables
CONFIG_PATH = os.getenv('CONFIG_PATH')
FILE_PATH = os.getenv('FILE_PATH')
SHEET_ID = os.getenv('SHEET_ID')

def load_config():
    """Load configuration from a file."""
    try:
        with open(CONFIG_PATH, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError("Configuration file not found.")
    except json.JSONDecodeError:
        raise ValueError("Error decoding the configuration file.")

def load_data():
    try:
        with open(FILE_PATH, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

def get_upcoming_weekend():
    today = datetime.now()
    today_weekday = today.weekday()

    days_until_saturday = (5 - today_weekday + 7) % 7
    days_until_sunday = (6 - today_weekday + 7) % 7

    if today_weekday == 6:
        days_until_saturday += 7
        days_until_sunday += 7

    saturday = today + timedelta(days=days_until_saturday)
    sunday = today + timedelta(days=days_until_sunday)

    return saturday.strftime('%Y-%m-%d'), sunday.strftime('%Y-%m-%d')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/teams')
def get_teams():
    all_data = load_data()
    saturday_str, sunday_str = get_upcoming_weekend()
    
    teams = set()

    for page, data in all_data.items():
        if 'data' in data:
            events = data['data']
            for event in events:
                event_datetime = event.get('start_at', '')
                try:
                    event_date_str = event_datetime.split(' ')[0]
                    event_date = datetime.strptime(event_date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
                    
                    if event_date == saturday_str or event_date == sunday_str:
                        home_team = event.get('home_team', {}).get('name', 'Unknown Home Team')
                        away_team = event.get('away_team', {}).get('name', 'Unknown Away Team')
                        teams.add(home_team)
                        teams.add(away_team)
                except ValueError:
                    print(f"Date format issue with event: {event}")

    return jsonify(list(teams))

@app.route('/api/names')
def get_names():
    try:
        config = load_config()
        # Define the scope of the API
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"]

        # Load credentials from the config file
        creds = Credentials.from_service_account_info(config, scopes=scopes)

        # Authenticate and connect to Google Sheets
        client = gspread.authorize(creds)

        # Open the Google Sheet by ID
        sheet = client.open_by_key(SHEET_ID)

        # Select the specific worksheet
        worksheet = sheet.worksheet("Players")

        # Fetch all values from column A (assumed to be names)
        names = worksheet.col_values(1)

        return jsonify(names)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
