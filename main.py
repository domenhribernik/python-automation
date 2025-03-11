import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import base64

# Jira Credentials
JIRA_URL = "https://cwcyprus-sales.atlassian.net"
JIRA_EMAIL = "webadmin@cwcyprus.com"
with open("JiraToken.txt", "r") as file:
    JIRA_API_TOKEN = file.read().strip()
    
# Jira Project and API Endpoint
JIRA_PROJECT_KEY = "SALES"
JIRA_API_ENDPOINT = f"{JIRA_URL}/rest/api/3/issue"

auth = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()

# Google Sheets API Setup
GOOGLE_SHEETS_CREDENTIALS_FILE = "credentials.json"
GOOGLE_SHEET_NAME = "Jira Sales API"
GOOGLE_SHEET_TAB_NAME = "Sheet1"

def authenticate_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    return client

def read_google_sheet(client):
    sheet = client.open(GOOGLE_SHEET_NAME).worksheet(GOOGLE_SHEET_TAB_NAME)
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

# Function to create an issue in Jira
def create_jira_issue(summary, issue_type, description, purchase_date, label):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Basic {auth}"
    }
    
    # Jira issue payload
    issue_data = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": description
                            }
                        ]
                    }
                ]
            },
            "issuetype": {"name": issue_type},
            "customfield_10015": purchase_date,
            "labels": [label] if label else []
        }
    }

    response = requests.post(JIRA_API_ENDPOINT, headers=headers, json=issue_data)
    
    if response.status_code == 201:
        print(f"Issue created: {summary}")
    else:
        print(f"Failed to create issue: {response.text}")

def test():
    headers = {
        "Accept": "application/json",
        "Authorization": f"Basic {auth}"
    }

    response = requests.get(f"{JIRA_URL}/rest/api/3/myself", headers=headers)

    if response.status_code == 200:
        print("Authentication is working!")
        print(response.json())  # Print user info
    else:
        print(f"Failed to authenticate: {response.status_code}")
        print(response.text)

def main():
    df = read_google_sheet(authenticate_google_sheets())
    for _, row in df.iterrows():
        create_jira_issue(row.iloc[0],  # Summary
                          row.iloc[1],  # Issue Type
                          row.iloc[2],  # Description
                          row.iloc[3],  # Purchase Date
                          row.iloc[4])  # Labels

if __name__ == "__main__":
    main()
