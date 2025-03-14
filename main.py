import requests
from datetime import date, datetime
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import base64
import schedule
import json

# Jira Credentials
JIRA_URL = "https://cwcyprus-sales.atlassian.net"
JIRA_EMAIL = "webadmin@cwcyprus.com"
with open("JiraToken.txt", "r") as file:
    JIRA_API_TOKEN = file.read().strip()

# Jira Project and API Endpoint
JIRA_PROJECT_KEY = "SALES"
TRANSITIONS = {
    "Lapsed": 2,
    "New Web Orders": 3,
    "In Progress": 4,
    "Outcome": 5,
    "New lead": 6
}

auth = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()

# Google Sheets API Setup
GOOGLE_SHEETS_CREDENTIALS_FILE = "credentials.json"
GOOGLE_SHEET_NAME = "Jira Sales API"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = "domen.hribernik4@gmail.com"
with open("GmailToken.txt", "r") as file:
    EMAIL_PASSWORD = file.read().strip()


HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Basic {auth}"
}

def authenticate_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    return client

def read_google_sheet(client, sheet):
    sheet = client.open(GOOGLE_SHEET_NAME).worksheet(sheet)
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

def formate_date(date):
    parsed_date = datetime.strptime(date, "%m/%d/%Y")
    return parsed_date.strftime("%Y-%m-%d")

# Function to create an issue in Jira
def create_jira_issues(df, check_date=True):
    bulk_issue_data = {
        "issueUpdates": []
    }

    for _, row in df.iterrows():
        last_date = formate_date(row['Last Transaction Date'])
        days_diff = (date.today() - datetime.strptime(last_date, "%Y-%m-%d").date()).days
        if days_diff < 90 and check_date:
            continue
        print(f"Days since last transaction: {days_diff}")

        company_name = row['Customer Name']
        customer_name = row['Customer Name']
        transaction_amount = row['Last Transaction Amount']
        email = row['Email']
        sms = row['SMS']
    
        issue_payload = {
            "fields": {
                "issuetype": {"id": 10001}, # Lead hardcoded
                "project": {"key": JIRA_PROJECT_KEY},
                "summary": str(customer_name),
                "customfield_10050": str(last_date), 
                "customfield_10052": str(transaction_amount),
                "customfield_10041": str(company_name),
                "customfield_10043": str(customer_name),
                "customfield_10042": str(sms),
                "customfield_10039": str(email)
            }
        }

        bulk_issue_data["issueUpdates"].append(issue_payload)
    # print(json.dumps(bulk_issue_data, indent=4))

    if bulk_issue_data["issueUpdates"] == []:
        print("No issues to create.")
        return []

    response = requests.post(f"{JIRA_URL}/rest/api/3/issue/bulk", headers=HEADERS, json=bulk_issue_data)
    
    if response.ok:
        print(f"Issues created: {len(bulk_issue_data["issueUpdates"])}")
    else:
        print(f"Failed to create issue: {response.text}")

    keys = [issue['key'] for issue in response.json()['issues']]
    print(keys)
    return keys

def get_transitions(key):
    response = requests.get(f"{JIRA_URL}/rest/api/3/issue/{key}/transitions", headers=HEADERS)

    if response.ok:
        print(f"Transitions for issue {key}:")
        print(response.json())
    else:
        print(f"Failed to get transitions: {response.text}")


def transition_jira_issues(transition, keys):
    transition_payload = {
        "bulkTransitionInputs": [
            { 
                "selectedIssueIdsOrKeys": keys, 
                "transitionId": transition
            }
        ],
        "sendBulkNotification": False
    }

    for key in keys:
        response = requests.post(f"{JIRA_URL}/rest/api/3/bulk/issues/transition", json=transition_payload, headers=HEADERS)

        if response.ok:
            print(f"Issue {key} moved to 'Lapsed'")
        else:
            print(f"Failed to transition issue: {response.text} status: {response.status_code}")

def search_issues(status):
    params = {
        "jql": f"project = 'SALES' AND status = '{status}'",
        "fields": "id,key"  # Request only the 'id' and 'key' fields
    }
    
    response = requests.get(f"{JIRA_URL}/rest/api/2/search", params=params, headers=HEADERS)

    if response.ok:
        issues = response.json().get("issues", [])

        issue_ids = [issue["id"] for issue in issues]  # List of issue IDs
        issue_keys = [issue["key"] for issue in issues]  # List of issue Keys
        
        print(f"Found {len(issue_ids)} issues")
        return issue_ids, issue_keys
    else:
        print(f"Failed to search issues: {response.text} status: {response.status_code}")
        return []

def get_issue(id):
    response = requests.get(f"{JIRA_URL}/rest/api/3/issue/{id}", headers=HEADERS)

    if response.ok:
        return response.json()["fields"]["summary"]
    else:
        print(f"Failed to get issue: {response.text} status: {response.status_code}")

    return ""

def clear_google_sheet(client, sheet):
    sheet = client.open(GOOGLE_SHEET_NAME).worksheet(sheet)
    all_data = sheet.get_all_values()
    if len(all_data) > 1:
        num_columns = len(all_data[0]) 
        sheet.batch_clear([f"A2:{chr(64+num_columns)}"])
        print(f"Sheet '{sheet}' cleared except for header.")

def check_for_new_orders(sheet):
    print("Checking for new orders...")
    client = authenticate_google_sheets()
    df = read_google_sheet(client, sheet)

    if df is not None and not df.empty:
        keys = create_jira_issues(df, check_date=False)
        transition_jira_issues(TRANSITIONS.get("New Web Orders", 0), keys)
        clear_google_sheet(client, sheet)
    else:
        print("No new orders found.")

def send_email(key, message, email_receiver):

    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = email_receiver
    msg["Subject"] = f"Jira Issue {key}"
    msg.attach(MIMEText(message, "plain"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Secure the connection
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, email_receiver, msg.as_string())
            print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def schedule_in_progress_emails():
    issues, keys  = search_issues("In Progress")
    message = "Please contact the customer about this purchese."
    email_receiver = ""

    for i in range(0, len(keys)):

        response = requests.get(f"{JIRA_URL}/rest/api/3/issue/{keys[i]}/changelog", headers=HEADERS)

        if response.ok:
            issue_response = requests.get(f"{JIRA_URL}/rest/api/3/issue/{issues[i]}", headers=HEADERS)

            if issue_response.ok:
                if len(issue_response.json()['fields']['labels']) > 0:
                    continue
            else:
                print(f"Failed to get issue: {response.text} status: {response.status_code}")

            
            date = response.json()['values'][-1]['created']
            email_receiver = response.json()['values'][-1]['author']['emailAddress']
            last_change_date = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%f%z")
            last_change = (datetime.now(last_change_date.tzinfo) - last_change_date)
            seconds_since_last_change = last_change.total_seconds()
            print(3 * 24 * 60 * 60 - seconds_since_last_change)

            payload = {
                "update": {
                    "labels": ["email scheduled"]
                }
            }

            label_response = requests.put(f"{JIRA_URL}/rest/api/3/issue/{keys[i]}", headers=HEADERS, data=json.dumps(payload))

            if label_response.status_code == 204:
                print(f"✅ Labels updated successfully for {keys[i]}")
            else:
                print(f"❌ Failed to update labels: {label_response.status_code}, {label_response.text}")
            
        else:
            print(f"Failed to search issues: {response.text} status: {response.status_code}")

    # send_email(key, message, email_receiver)

def main():
    # * bulk create issues and transition them
    # df = read_google_sheet(authenticate_google_sheets(), "Lapsed")
    # keys = create_jira_issues(df)
    # transition_jira_issues(TRANSITIONS.get("Lapsed", 0), keys)

    # * print issues in Lapsed status
    # time.sleep(2)
    # issues, keys = search_issues("In Progress")
    # for issue in issues:
    #     print(get_issue(issue["id"]))

    # * check for new orders
    # schedule.every(15).minutes.do(check_for_new_orders, "New Web Orders")
    # schedule.every().day.at("00:00").do(schedule_in_progress_emails)
    # while True:
    #     schedule.run_pending()
    #     time.sleep(15 * 60)

    
    schedule_in_progress_emails()
    print("Exited...")
    

if __name__ == "__main__":
    main()
