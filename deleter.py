import requests
import base64

# Jira Credentials
JIRA_URL = "https://cwcyprus-sales.atlassian.net"
JIRA_EMAIL = "webadmin@cwcyprus.com"
with open("JiraToken.txt", "r") as file:
    JIRA_API_TOKEN = file.read().strip()

# Project Key
PROJECT_KEY = "SALES"

if input("Are you sure you want to delete all issues in the project? (y/n): ").lower() != "y":
    print("Exiting...")
    exit()

# Auth
auth = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()
headers = {
    "Authorization": f"Basic {auth}",
    "Content-Type": "application/json"
}

# Step 1: Get All Issues
search_url = f"{JIRA_URL}/rest/api/3/search?jql=project={PROJECT_KEY}&maxResults=100"
response = requests.get(search_url, headers=headers)
issues = response.json().get("issues", [])
print(response.text)

# Step 2: Delete Issues One by One
for issue in issues:
    issue_key = issue["key"]
    delete_url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}"
    
    delete_response = requests.delete(delete_url, headers=headers)
    
    if delete_response.status_code == 204:
        print(f"Issue {issue_key} deleted successfully.")
    else:
        print(f"Failed to delete {issue_key}: {delete_response.text}")
