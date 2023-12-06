from flask import Flask, render_template, request
import gspread
from gspread.auth import Credentials
from oauth2client.service_account import ServiceAccountCredentials
from dateutil.parser import parse
import datetime
from bs4 import BeautifulSoup
import pandas as pd
import requests
import time
from googleapiclient.discovery import build
from google.oauth2 import service_account

app = Flask(__name__)

def get_teams_playing_from_fixtures():
    try:
        # Authenticate with Google Sheets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            r'C:\Users\jwils\Desktop\LMS\lmscred.json', scope
        )
        gc = gspread.authorize(credentials)

        # Open the spreadsheet (replace 'Last Man Standing' and 'Fixtures' with your actual spreadsheet and sheet names)
        spreadsheet = gc.open("Last Man Standing")
        fixtures_sheet = spreadsheet.worksheet("Fixtures")

        # Fetch team names from the 'Fixtures' sheet, including the header row
        team_names_column_b = fixtures_sheet.col_values(2)
        team_names_column_c = fixtures_sheet.col_values(3)

        # Combine and return unique team names from both columns, sorted alphabetically
        teams_playing = sorted(list(set(team_names_column_b + team_names_column_c)))

        # Exclude empty strings from the list
        teams_playing = [team for team in teams_playing if team]

        return teams_playing

    except Exception as e:
        print(f"Error in get_teams_playing_from_fixtures: {e}")
        return []


def find_and_update_worksheet_sheet1(worksheet, name, team):
    try:
        # Fetch dates from the 'Sheet1' sheet
        date_columns = worksheet.row_values(1)

        submitted_date = datetime.datetime.now().date()

        week_column = None
        for i, date_str in enumerate(date_columns):
            try:
                # Skip columns with invalid date strings
                if not date_str or date_str.lower() == "premier league":
                    continue

                # Try parsing the date string using datetime.datetime.strptime with two formats
                try:
                    date_in_row = datetime.datetime.strptime(date_str, "%d/%m/%Y").date()
                except ValueError:
                    try:
                        date_in_row = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                    except ValueError as ve:
                        # Handle cases where the date string cannot be parsed
                        print(f"Error parsing date in column {i + 1}: {date_str}")
                        print(f"Exception details: {ve}")
                        continue  # Skip to the next column if parsing fails

                # Check if today's date is within the week starting with the date in row 1
                if (date_in_row <= submitted_date <= date_in_row + datetime.timedelta(days=6)):
                    week_column = i + 1  # Adding 1 as columns start at 1
                    break  # Stop searching once the correct week column is found
            except ValueError as ve:
                # Handle cases where the date string cannot be parsed
                print(f"Error parsing date in column {i + 1}: {date_str}")
                print(f"Exception details: {ve}")
                continue  # Skip to the next column if parsing fails

        print(f"date_in_row: {date_in_row}")
        print(f"submitted_date: {submitted_date}")
        print(f"week_column: {week_column}")

        if week_column is not None:
            # Find the column corresponding to the Monday of the submission week
            monday_column = week_column - (date_in_row.weekday() + 1) + 1
            if monday_column > 0:
                print(f"monday_column: {monday_column}")

                # Locate the cell corresponding to the submitted name in the first column
                cell_list = worksheet.findall(name)

                for cell in cell_list:
                    if cell.col == 1:  # Ensure the name is in the first column
                        cell_row = cell.row
                        worksheet.update_cell(cell_row, monday_column, team)
                        return

                # If the name isn't found, append a new row with the name and team for the current week
                next_row = len(worksheet.col_values(1)) + 1  # Find the next empty row
                worksheet.update_cell(next_row, 1, name)
                worksheet.update_cell(next_row, monday_column, team)
    except Exception as e:
        print(f"Error in find_and_update_worksheet_sheet1: {e}")
              
# Function to find and update worksheet for Sheet2
def find_and_update_worksheet_sheet2(worksheet, name, team):
    try:
        date_columns = worksheet.row_values(1)  # Fetch dates from the first row
        submitted_date = datetime.date.today()
        week_column = None
        for i, date_str in enumerate(date_columns):
            try:
                # Parse the date string from the spreadsheet
                date_in_row = datetime.datetime.strptime(date_str, "%d/%m/%Y").date()

                # Check if today's date is within the week starting with the date in row 1
                if (date_in_row <= submitted_date <= date_in_row + datetime.timedelta(days=6)):
                    week_column = i + 1  # Adding 1 as columns start at 1
                    break  # Stop searching once the correct week column is found
            except ValueError:
                # Handle cases where the date string cannot be parsed
                print(f"Error parsing date in column {i + 1}")

        if week_column is not None:
            cell_list = worksheet.findall(name)  # Find all cells with the name

            for cell in cell_list:
                if cell.col == 1:  # Ensure the name is in the first column
                    cell_row = cell.row
                    # Assuming the team should be updated in the column following the week column
                    worksheet.update_cell(cell_row, week_column + 2, team)  # Adding 2 for column F (1 + 2 = 3)

                    # Check if both home and away scores are available
                    if worksheet.cell(cell_row, week_column + 1).value and worksheet.cell(
                            cell_row, week_column + 2).value:
                        home_goals = int(
                            worksheet.cell(cell_row, week_column + 1).value)  # Update with the actual column (D)
                        away_goals = int(
                            worksheet.cell(cell_row, week_column + 2).value)  # Update with the actual column (E)

                        winning_team = determine_winning_team(team, home_goals, away_goals)

                        # Update the winning team in the next column (G)
                        worksheet.update_cell(cell_row, week_column + 3,
                                              winning_team)  # Update with the actual column (G)

                    return

            # If the name isn't found, append a new row with the name, team, and winning team for the current week
            next_row = len(worksheet.col_values(1)) + 1  # Find the next empty row
            worksheet.update_cell(next_row, 1, name)
            worksheet.update_cell(next_row, week_column + 2, team)  # Adding 2 for column F (1 + 2 = 3)

            # Check if both home and away scores are available
            if worksheet.cell(next_row, week_column + 1).value and worksheet.cell(next_row,
                                                                                     week_column + 2).value:
                home_goals = int(
                    worksheet.cell(next_row, week_column + 1).value)  # Update with the actual column (D)
                away_goals = int(
                    worksheet.cell(next_row, week_column + 2).value)  # Update with the actual column (E)

                winning_team = determine_winning_team(team, home_goals, away_goals)

                # Update the winning team in the next column (G)
                worksheet.update_cell(next_row, week_column + 3,
                                      winning_team)  # Update with the actual column (G)

    except Exception as e:
        print(f"Error in find_and_update_worksheet_sheet2: {e}")

# Function to scrape results and update Google Sheet (Sheet2) - including winning teams
def scrape_and_update_sheet_with_winners():
    # Set the BBC base URL
    base_url = 'https://www.bbc.co.uk/sport/football/scores-fixtures/'

    # Get the current date
    current_date = datetime.datetime.now()

    # Find the most recent Saturday (current day - current weekday + 5)
    end_date = current_date - datetime.timedelta(days=current_date.weekday() + 1)

    # Find the previous Sunday (most recent Saturday - 1 day)
    start_date = end_date - datetime.timedelta(days=1)

    # Convert dates to string in 'YYYY-MM-DD' format
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    # Generate date range
    tournament_dates = pd.date_range(start_date_str, end_date_str)

    # Generate URLs for each date
    urls = [f"{base_url}{dt.date()}" for dt in tournament_dates]

    # Leagues to include
    target_leagues = ['Premier League', 'Championship', 'League One', 'League Two']

    # Authenticate with Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        r'C:\Users\jwils\Desktop\LMS\lmscred.json', scope
    )
    gc = gspread.authorize(credentials)

    # Open the spreadsheet (replace 'Last Man Standing' and 'Sheet2' with your actual spreadsheet and sheet names)
    spreadsheet = gc.open("Last Man Standing")
    worksheet = spreadsheet.worksheet("Sheet2")

    # Clear the contents of the worksheet before appending new data
    worksheet.clear()

    # Accumulate results and winning teams in a list
    results_and_winners_list = []

    # Iterate through all URLs
    for url in urls:
        retry_count = 0
        max_retries = 3  # You can adjust this number based on your needs
        while retry_count < max_retries:
            try:
                # Extract the date from the URL
                date_str = url.split('/')[-1]

                # Fetch HTML content from the current URL
                response = requests.get(url)

                # Use BeautifulSoup to parse the HTML
                soup = BeautifulSoup(response.text, 'html.parser')

                # Find league blocks
                league_blocks = soup.find_all('div', {'class': 'qa-match-block'})

                # Iterate through league blocks
                for league_block in league_blocks:
                    # Extract league information
                    league_elem = league_block.find('h3', {'class': 'gel-minion sp-c-match-list-heading'})
                    league = league_elem.text.strip() if league_elem else "Unknown League"

                    # Check if the league is in the target_leagues
                    if league in target_leagues:
                        # Extract fixtures within the league block
                        fixtures = league_block.find_all('article', {'class': 'sp-c-fixture'})

                        # Iterate through fixtures and accumulate results and winning teams
                        for fixture in fixtures:
                            home = fixture.select_one('.sp-c-fixture__team--home .sp-c-fixture__team-name-trunc').text
                            away = fixture.select_one('.sp-c-fixture__team--away .sp-c-fixture__team-name-trunc').text
                            home_goals = fixture.select_one('.sp-c-fixture__number--home').text
                            away_goals = fixture.select_one('.sp-c-fixture__number--away').text

                            # Call helper method to get the result in the desired format
                            result = show_result(league, date_str, home, home_goals, away, away_goals)

                            # Determine the winning team
                            winning_team = determine_winning_team(home, int(home_goals), away, int(away_goals))

                            # Format the date string to dd/mm/yyyy
                            formatted_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y')

                            # Append the result and winning team to the list
                            results_and_winners_list.append([result[0], formatted_date] + result[1:] + [winning_team])

                # If successful, break out of the retry loop
                break

            except requests.exceptions.RequestException as e:
                print(f"Error: {e}")
                retry_count += 1
                print(f"Retrying... Attempt {retry_count}/{max_retries}")
                time.sleep(10)  # Wait for 10 seconds before retrying

    # Sort results_and_winners_list based on the order of target_leagues
    sorted_results_and_winners = sorted(results_and_winners_list, key=lambda x: target_leagues.index(x[0]))

    # Append all sorted results and winning teams in a batch to the Google Sheet (Sheet2)
    worksheet.append_rows(sorted_results_and_winners)
    print("Results and winning teams added to Google Sheet (Sheet2). Fixtures sorted by Premier League, Championship, League One, and League Two.")

# Function to determine the winning team
def determine_winning_team(home_team, home_goals, away_team, away_goals):
    if home_goals > away_goals:
        return home_team
    elif away_goals > home_goals:
        return away_team
    else:
        return "Draw"
# Function to show the result with the winning team
def show_result(league, date, home, home_goals, away, away_goals) -> list:
    home_goals = int(home_goals)
    away_goals = int(away_goals)

    if home_goals > away_goals:
        winner = home
    elif away_goals > home_goals:
        winner = away
    else:
        winner = "Draw"

    return [league, date, home, str(home_goals), str(away_goals), away, winner]


# Function to scrape results and update Google Sheet (Fixtures) - continued
# Function to scrape results and update Google Sheet (Fixtures) - continued
def scrape_and_update_fixture():
    try:
        # Set the BBC base URL
        base_url = 'https://www.bbc.co.uk/sport/football/scores-fixtures/'

        # Get the current date
        current_date = datetime.datetime.now()

        # Find the next Saturday (current day + days until next Saturday)
        days_until_saturday = (5 - current_date.weekday()) % 7
        next_saturday = current_date + datetime.timedelta(days=days_until_saturday)

        # Find the next Sunday (next Saturday + 1 day)
        next_sunday = next_saturday + datetime.timedelta(days=1)

        # Convert the dates to string in 'YYYY-MM-DD' format
        next_saturday_str = next_saturday.strftime('%Y-%m-%d')
        next_sunday_str = next_sunday.strftime('%Y-%m-%d')

        # Generate URLs for both Saturday and Sunday
        urls = [f"{base_url}{next_saturday_str}", f"{base_url}{next_sunday_str}"]

        # Leagues to include
        target_leagues = ['Premier League', 'Championship', 'League One', 'League Two']

        # Authenticate with Google Sheets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
                r'C:\Users\jwils\Desktop\LMS\lmscred.json', scope
    )
        gc = gspread.authorize(credentials)

        # Open the spreadsheet (replace 'Last Man Standing' and 'Fixtures' with your actual spreadsheet and sheet names)
        spreadsheet = gc.open("Last Man Standing")
        worksheet = spreadsheet.worksheet("Fixtures")

        # Clear the contents of the worksheet before appending new data
        worksheet.clear()

        # Accumulate fixture information in a list
        fixtures_list = []

        # Iterate through URLs
        for url in urls:
            retry_count = 0
            max_retries = 3

            while retry_count < max_retries:
                try:
                    # Fetch HTML content from the current URL
                    response = requests.get(url)

                    # Use BeautifulSoup to parse the HTML
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Find league blocks
                    league_blocks = soup.find_all('div', {'class': 'qa-match-block'})

                    # Iterate through league blocks
                    for league_block in league_blocks:
                        # Extract league information
                        league_elem = league_block.find('h3', {'class': 'gel-minion sp-c-match-list-heading'})
                        league = league_elem.text.strip() if league_elem else "Unknown League"

                        # Check if the league is in the target_leagues
                        if league in target_leagues:
                            # Extract fixtures within the league block
                            fixtures = league_block.find_all('article', {'class': 'sp-c-fixture'})

                            # Iterate through fixtures and accumulate results
                            for fixture in fixtures:
                                home_elem = fixture.select_one('.sp-c-fixture__team--time-home .sp-c-fixture__team-name-trunc')
                                away_elem = fixture.select_one('.sp-c-fixture__team--time-away .sp-c-fixture__team-name-trunc')

                                # Check if home and away elements are not None before accessing the .text attribute
                                if home_elem and away_elem:
                                    home = home_elem.text
                                    away = away_elem.text

                                    # Call helper method to get the fixture info in the desired format
                                    fixture_info = show_fixture_info(league, home, away)

                                    # Append the fixture info to the list
                                    fixtures_list.append(fixture_info)
                                else:
                                    print("Error: Home or away element is None")

                    # If successful, break out of the retry loop
                    break

                except requests.exceptions.RequestException as e:
                    print(f"Error: {e}")
                    retry_count += 1
                    print(f"Retrying... Attempt {retry_count}/{max_retries}")
                    time.sleep(10)
                    continue  # Continue to the next iteration of the while loop

        # Sort fixtures_list based on the order of target_leagues
        sorted_fixtures = sorted(fixtures_list, key=lambda x: target_leagues.index(x[0]))

        # Append all sorted fixture information in a batch to the Google Sheet (Fixtures)
        worksheet.append_rows(sorted_fixtures)
        print("Fixtures added to Google Sheet (Fixtures) for the upcoming weekend.")

    except Exception as e:
        print(f"Error in scrape_and_update_fixture: {e}")

# Function to get team name from the team element
def get_team_name(team_elem):
    if team_elem:
        # Find the team name using the specified class name
        team_name_abbr = team_elem.find('abbr', {'class': 'sp-c-fixture__team-name-trunc'})
        if team_name_abbr:
            return team_name_abbr.get_text(strip=True)  # Use get_text to get the text content

        # If 'abbr' tag is not present, try to find the team name using the team element itself
        team_name = team_elem.find('span', {'class': 'sp-c-fixture__team-name-trunc'})
        if team_name:
            return team_name.get_text(strip=True)

    print("Team Element is None")
    return "Unknown Team"

# Function to show the fixture information
def show_fixture_info(league, home, away) -> list:
    return [league, home, away]

# Function to show the result
def show_result(league, date, home, home_goals, away, away_goals) -> list:
    return [league, date, home, home_goals, away_goals, away]

def copy_winning_teams_to_sheet4():
    try:
        # Authenticate with Google Sheets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
                r'C:\Users\jwils\Desktop\LMS\lmscred.json', scope
    )
        gc = gspread.authorize(credentials)

        # Open the spreadsheet (replace 'Last Man Standing' and 'Sheet2' with your actual spreadsheet and sheet names)
        spreadsheet = gc.open("Last Man Standing")
        sheet2 = spreadsheet.worksheet("Sheet2")
        sheet4 = spreadsheet.worksheet("Sheet4")

        # Get the date from cell B1 in Sheet2
        date_str = sheet2.cell(1, 2).value

        # Parse the date string from Sheet2
        sheet2_date = datetime.datetime.strptime(date_str, "%d/%m/%Y").date()

        # Find the Monday of the corresponding week
        monday_of_week = sheet2_date - datetime.timedelta(days=sheet2_date.weekday())

        # Find the corresponding column in Sheet4
        date_columns = sheet4.row_values(1)
        try:
            column_index = date_columns.index(monday_of_week.strftime("%d/%m/%Y"))
        except ValueError:
            print(f"No matching date found in Sheet4 for {monday_of_week.strftime('%d/%m/%Y')}")
            return

        # Get the value from the 'Winners' column in Sheet2
        winners_column = sheet2.col_values(8)

        # Filter out draws from the winning teams
        winning_teams_no_draws = [team for team in winners_column if team.lower() != "draw"]

        # Reshape the data into a list of lists for gspread update
        data_to_copy = [[team] for team in winning_teams_no_draws]

        # Determine the range to update in Sheet4
        update_range = f"{chr(65 + column_index)}2:{chr(65 + column_index)}{len(data_to_copy) + 1}"

        # Copy the values to the corresponding column in Sheet4
        sheet4.update(update_range, data_to_copy)

        print(f"Winning teams copied to Sheet4 for the week of {monday_of_week.strftime('%d/%m/%Y')} (excluding draws).")

    except Exception as e:
        print(f"Error in copy_winning_teams_to_sheet4: {e}")

@app.route('/')
def index():
    try:
        # Authenticate with Google Sheets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
                r'C:\Users\jwils\Desktop\LMS\lmscred.json', scope
    )
        gc = gspread.authorize(credentials)

        # Open the spreadsheet (replace 'Last Man Standing' and 'Sheet1' with your actual spreadsheet and sheet names)
        spreadsheet = gc.open("Last Man Standing")
        sheet1 = spreadsheet.worksheet("Sheet1")
        fixtures_sheet = spreadsheet.worksheet("Fixtures")

        # Fetch team names from column A in Sheet1
        names = sheet1.col_values(26)  # Assuming names are in column A

        # Remove empty strings, 'TRUE', and 'FALSE' from the list
        names = [name for name in names if name and name not in ['TRUE', 'FALSE']]

        # Call the function to scrape results and update the Google Sheets (Sheet2 and Fixtures)
        scrape_and_update_sheet_with_winners()
        scrape_and_update_fixture()

        # Call the function to copy winning teams to Sheet4
        copy_winning_teams_to_sheet4()

        # Fetch team names from the 'Fixtures' sheet
        teams = get_teams_playing_from_fixtures()

        return render_template('index.html', names=names, teams=teams)

    except Exception as e:
        # Print the exception to the console for debugging
        print(f"Error in index route: {e}")

        # Render an error template or redirect to an error page as needed
        return render_template('error.html')
@app.route('/submit', methods=['POST'])
def submit():
    if request.method == 'POST':
        name = request.form['name']
        team = request.form['team']

        # Define the scope here
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

        creds = ServiceAccountCredentials.from_json_keyfile_name(r'C:\Users\jwils\Desktop\LMS\lmscred.json', scope)
        client = gspread.authorize(creds)

        sheet1 = client.open('Last Man Standing').worksheet('Sheet1')
        sheet2 = client.open('Last Man Standing').worksheet('Sheet2')
        fixtures_sheet = client.open('Last Man Standing').worksheet('Fixtures')


        find_and_update_worksheet_sheet1(sheet1, name, team)  # Call the function for Sheet1
        find_and_update_worksheet_sheet2(sheet2, name, team)  # Call the function for Sheet2
        find_and_update_worksheet_sheet2(fixtures_sheet, name, team)  # Call the function for Fixtures

        return render_template('success.html')  # This renders the success message

if __name__ == "__main__":
    app.run(debug=True)
