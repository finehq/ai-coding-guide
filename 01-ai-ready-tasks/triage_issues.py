import os
import requests
import logging
import argparse
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

LINEAR_API_KEY = os.getenv('LINEAR_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

LINEAR_API_URL = "https://api.linear.app/graphql"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

HEADERS_LINEAR = {
    "Authorization": LINEAR_API_KEY,
    "Content-Type": "application/json"
}

HEADERS_OPENAI = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json"
}

def fetch_issues():
    query = """
    query {
      issues(first: 10) {
        nodes {
          id
          title
          description
        }
      }
    }
    """
    logging.debug("Sending request to Linear API to fetch issues.")
    try:
        response = requests.post(LINEAR_API_URL, json={'query': query}, headers=HEADERS_LINEAR)
        logging.info(f"Response status code: {response.status_code}")
        logging.info(f"Response content: {response.text}")
        response.raise_for_status()
        issues = response.json()['data']['issues']['nodes']
        logging.info(f"Fetched {len(issues)} issues from Linear.")
        return issues
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching issues: {str(e)}")
        raise

def format_issue(issue):
    comments = "\n".join(comment['body'] for comment in issue.get('comments', {}).get('nodes', []))
    return f"Title: {issue['title']}\nDescription: {issue['description']}\nComments:\n{comments}"

def analyze_issue_with_openai(issue_text):
    prompt = (
        "You are an AI assistant tasked with analyzing the following issue. "
        "Determine if this issue can be delegated to AI based on its complexity, "
        "clarity, and the presence of well-defined tasks. Provide a clear decision. "
        f"Issue details: {issue_text}"
    )
    data = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": prompt}]
    }
    logging.debug("Sending request to OpenAI API for issue analysis.")
    response = requests.post(OPENAI_API_URL, json=data, headers=HEADERS_OPENAI)
    response.raise_for_status()
    ai_response = response.json()['choices'][0]['message']['content']
    logging.info("Received response from OpenAI API.")
    return ai_response

def update_issue_label(issue_id):
    mutation = """
    mutation($id: String!) {
      issueUpdate(id: $id, input: {labelIds: ["ai-ready"]}) {
        success
      }
    }
    """
    variables = {"id": issue_id}
    response = requests.post(LINEAR_API_URL, json={'query': mutation, 'variables': variables}, headers=HEADERS_LINEAR)
    response.raise_for_status()
    return response.json()['data']['issueUpdate']['success']

def main():
    parser = argparse.ArgumentParser(description="Triage issues and analyze them with OpenAI.")
    parser.add_argument('--verbosity', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], default='INFO', help='Set the logging verbosity level')
    parser.add_argument('--project', type=str, help='Filter issues by project')
    parser.add_argument('--status', type=str, help='Filter issues by status')
    args = parser.parse_args()

    logging.getLogger().setLevel(args.verbosity)

    logging.info("Fetching issues...")
    issues = fetch_issues()
    if args.project:
        issues = [issue for issue in issues if issue.get('project', {}).get('name') == args.project]
        logging.info(f"Filtered issues by project: {args.project}. Remaining issues: {len(issues)}")
    if args.status:
        issues = [issue for issue in issues if issue.get('state', {}).get('name') == args.status]
        logging.info(f"Filtered issues by status: {args.status}. Remaining issues: {len(issues)}")
    for issue in issues:
        formatted_issue = format_issue(issue)
        ai_response = analyze_issue_with_openai(formatted_issue)
        if '"ai_ready": "true"' in ai_response:
            success = update_issue_label(issue['id'])
            if success:
                logging.info(f"Issue {issue['id']} labeled as AI-ready.")
            else:
                logging.error(f"Failed to update issue {issue['id']}.")

if __name__ == "__main__":
    logging.info("Script started.")
    main()
    logging.info("Script finished.")