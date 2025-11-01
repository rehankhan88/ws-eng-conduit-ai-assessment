import requests
import zipfile
import os

SUBMISSION_KEY = "a0Bfv000004b0I5EAI"
ZIP_FILE = "submission.zip"
BASE_URL = "https://api.openai.com/v1/chat/completions"  # Replace with actual endpoint if known

# 1. Zip your project files
def zip_project():
    with zipfile.ZipFile(ZIP_FILE, 'w') as zipf:
        for root, dirs, files in os.walk('.'):
            for file in files:
                if file.endswith(('.py', '.json', '.txt', '.md', '.png')):
                    filepath = os.path.join(root, file)
                    zipf.write(filepath)

# 2. Submit (mock request since actual endpoint unknown)
def submit():
    print("Preparing submission...")
    files = {'file': open(ZIP_FILE, 'rb')}
    data = {'submission_key': SUBMISSION_KEY}
    # replace URL below with correct platform endpoint
    response = requests.post("https://api.openai.com/v1/chat/completions", files=files, data=data)
    print("Response:", response.text)

if __name__ == "__main__":
    zip_project()
    submit()
# submit.py
import zipfile
import os
import requests
import config
import sys
from pathlib import Path

SUBMISSION_FOLDER = "submission"
ZIP_NAME = "submission.zip"
TIMEOUT = 30

def make_zip():
    if not os.path.isdir(SUBMISSION_FOLDER):
        print(f"Error: folder '{SUBMISSION_FOLDER}' not found. Put screenshots inside this folder.")
        sys.exit(1)

    # create zip of files directly in submission/ (no nested repo)
    with zipfile.ZipFile(ZIP_NAME, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for item in sorted(os.listdir(SUBMISSION_FOLDER)):
            item_path = os.path.join(SUBMISSION_FOLDER, item)
            if os.path.isfile(item_path):
                print("Adding:", item_path)
                z.write(item_path, arcname=item)

    print(f"Created {ZIP_NAME}")

def submit_zip():
    # Ensure API key present
    api_key = getattr(config, "OPENAI_API_KEY", None)
    if not api_key:
        print("Error: OPENAI_API_KEY not found in config.py")
        sys.exit(1)

    url = getattr(config, "BASE_URL", None)
    if not url:
        print("Error: BASE_URL not set in config.py")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    # If the endpoint expects form-data file upload
    files = {"file": (ZIP_NAME, open(ZIP_NAME, "rb"))}
    data = {"submission_key": "a0Bfv000004b0I5EAI"}  # if required by server

    print("Submitting to:", url)
    try:
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=TIMEOUT)
    except requests.exceptions.RequestException as e:
        print("Network error:", str(e))
        return

    try:
        print("HTTP", resp.status_code)
        print(resp.text)
    except Exception as e:
        print("Failed to read response:", e)

if __name__ == "__main__":
    make_zip()
    submit_zip()
