# extractor/github_pusher.py

import os
import json
import base64
import requests
from config import GITHUB_TOKEN, GITHUB_REPO


class GitHubPusher:

    def __init__(self):
        self.token = GITHUB_TOKEN or os.environ.get('G_TOKEN', '')
        self.repo  = GITHUB_REPO  or os.environ.get('GITHUB_REPO', '')

        if not self.token:
            raise ValueError(
                "G_TOKEN not set. Add it to GitHub Secrets."
            )
        if not self.repo:
            raise ValueError(
                "GITHUB_REPO not set. Add it to GitHub Secrets."
            )

        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept':        'application/vnd.github.v3+json',
        }
        self.api_base = 'https://api.github.com'

    def push_catalog(self, local_path: str, repo_path: str):
        """
        Push a local file to the GitHub repository.
        Creates the file if it does not exist,
        updates it if it does.
        """
        print(f"  📤 Pushing {repo_path} to {self.repo}...")

        # Read local file
        with open(local_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Encode to base64 for GitHub API
        encoded = base64.b64encode(
            content.encode('utf-8')
        ).decode('utf-8')

        # Check if file already exists to get its SHA
        url = f"{self.api_base}/repos/{self.repo}/contents/{repo_path}"
        existing = requests.get(url, headers=self.headers)
        sha = None
        if existing.status_code == 200:
            sha = existing.json().get('sha')
            print(f"  ℹ️  File exists — updating")
        else:
            print(f"  ℹ️  File not found — creating")

        # Prepare commit payload
        payload = {
            'message': 'Auto-update catalog_data.json',
            'content': encoded,
        }
        if sha:
            payload['sha'] = sha

        # Push to GitHub
        response = requests.put(
            url,
            headers=self.headers,
            json=payload
        )

        if response.status_code in [200, 201]:
            print(f"  ✅ Successfully pushed {repo_path}")
        else:
            raise Exception(
                f"GitHub API error {response.status_code}: "
                f"{response.text[:200]}"
            )
