import requests
from datetime import date
import json
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
TRANSITIONS = {
    "Follow-up": 45
}

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
def create_jira_issues(df):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Basic {auth}"
    }

    bulk_issue_data = {
        "issueUpdates": []
    }

    for _, row in df.iterrows():
        summary = row.iloc[0]
        description = row.iloc[1]
        purchase_date = row.iloc[2]
    
        issue_payload = {
            "fields": {
                "project": {"key": JIRA_PROJECT_KEY},
                "summary": str(summary),
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
                "issuetype": {"id": 10003}, # Task hardcoded
                "customfield_10015": str(purchase_date)
            }
        }

        bulk_issue_data["issueUpdates"].append(issue_payload)
    # print(json.dumps(bulk_issue_data, indent=4))
    response = requests.post(f"{JIRA_URL}/rest/api/3/issue/bulk", headers=headers, json=bulk_issue_data)
    
    if response.status_code == 201:
        print(f"Issues created: {len(bulk_issue_data["issueUpdates"])}")
    else:
        print(f"Failed to create issue: {response.text}")

    keys = [issue['key'] for issue in response.json()['issues']]
    print(keys)
    return keys

def get_transitions(key):
    headers = {
        "Accept": "application/json",
        "Authorization": f"Basic {auth}"
    }

    response = requests.get(f"{JIRA_URL}/rest/api/3/issue/{key}/transitions", headers=headers)

    if response.status_code == 200:
        print(f"Transitions for issue {key}:")
        print(response.json())
    else:
        print(f"Failed to get transitions: {response.text}")


def transition_to_needs_follow_up(transition, keys):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Basic {auth}"
    }

    transition_payload = {
        "transition": {"id": transition}
    }

    for key in keys:
        response = requests.post(f"{JIRA_URL}/rest/api/3/issue/{key}/transitions", json=transition_payload, headers=headers)

        if response.status_code == 204:
            print(f"Issue {key} moved to 'Needs Follow Up'")
        else:
            print(f"Failed to transition issue: {response.text}")

def main():
    df = read_google_sheet(authenticate_google_sheets())
    keys = create_jira_issues(df)
    transition_to_needs_follow_up(TRANSITIONS.get("Follow-up", 0), keys)

if __name__ == "__main__":
    main()
