# extractor/github_pusher.py

import os
import json
import base64
import requests
from config import GITHUB_TOKEN, GITHUB_REPO


class GitHubPusher:

    def __init__(self):
        self.token = (
            GITHUB_TOKEN or os.environ.get('G_TOKEN', '')
        )
        self.repo = (
            GITHUB_REPO or os.environ.get('GITHUB_REPO', '')
        )
        self.in_actions = (
            os.environ.get('GITHUB_ACTIONS') == 'true'
        )
        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json',
        }
        self.api_base = 'https://api.github.com'

    def push_catalog(self, local_path: str, repo_path: str):
        """
        When running in GitHub Actions:
        Do nothing. The workflow yml handles
        git add, commit and push at the end.

        When running locally:
        Use GitHub API to push the file.
        """
        if self.in_actions:
            print(
                "  ℹ️  GitHub Actions detected — "
                "skipping API push."
            )
            print(
                "     Workflow will handle "
                "git commit and push."
            )
            return

        if not self.token:
            print("  ⚠️  G_TOKEN not set.")
            print(f"  ℹ️  File saved at: {local_path}")
            return

        if not self.repo:
            print("  ⚠️  GITHUB_REPO not set.")
            return

        print(
            f"  📤 Pushing {repo_path} "
            f"to {self.repo}..."
        )

        try:
            with open(local_path, 'r', encoding='utf-8') as f:
                content = f.read()

            encoded = base64.b64encode(
                content.encode('utf-8')
            ).decode('utf-8')

            url = (
                f"{self.api_base}/repos/"
                f"{self.repo}/contents/{repo_path}"
            )

            existing = requests.get(
                url, headers=self.headers
            )
            sha = None
            if existing.status_code == 200:
                sha = existing.json().get('sha')

            payload = {
                'message': 'Auto-update catalog_data.json',
                'content': encoded,
            }
            if sha:
                payload['sha'] = sha

            response = requests.put(
                url,
                headers=self.headers,
                json=payload
            )

            if response.status_code in [200, 201]:
                print(f"  ✅ Pushed {repo_path}")
            else:
                raise Exception(
                    f"API error {response.status_code}: "
                    f"{response.text[:200]}"
                )

        except Exception as e:
            print(f"  ⚠️  Push failed: {e}")
            print(f"  ℹ️  File saved at: {local_path}")
