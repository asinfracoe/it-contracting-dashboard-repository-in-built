# extractor/github_pusher.py

import os
import json
import base64
import requests
from config import GITHUB_TOKEN, GITHUB_REPO


class GitHubPusher:

    def __init__(self):
        self.token = GITHUB_TOKEN or os.environ.get('G_TOKEN', '')
        self.repo  = GITHUB_REPO  or os.environ.get(
            'GITHUB_REPO', ''
        )
        self.running_in_actions = (
            os.environ.get('GITHUB_ACTIONS') == 'true'
        )

        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept':        'application/vnd.github.v3+json',
        }
        self.api_base = 'https://api.github.com'

    def push_catalog(self, local_path: str, repo_path: str):
        """
        Push catalog_data.json to GitHub.

        When running inside GitHub Actions:
        The file is already saved locally by main.py.
        The workflow yml handles git add, commit and push.
        We skip the API push to avoid conflicts.

        When running locally:
        Use the GitHub API to push the file directly.
        """
        if self.running_in_actions:
            print(
                "  ℹ️  Running in GitHub Actions — "
                "skipping API push."
            )
            print(
                "     The workflow will commit and push "
                "catalog_data.json automatically."
            )
            return

        # Running locally — use API to push
        if not self.token:
            print(
                "  ⚠️  G_TOKEN not set — "
                "cannot push remotely."
            )
            print(
                f"  ℹ️  File saved locally at: {local_path}"
            )
            return

        if not self.repo:
            print(
                "  ⚠️  GITHUB_REPO not set — "
                "cannot push remotely."
            )
            return

        print(f"  📤 Pushing {repo_path} to {self.repo}...")

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

            existing = requests.get(url, headers=self.headers)
            sha = None
            if existing.status_code == 200:
                sha = existing.json().get('sha')
                print(f"  ℹ️  File exists — updating")
            else:
                print(f"  ℹ️  File not found — creating")

            payload = {
                'message': (
                    'Auto-update catalog_data.json'
                ),
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
                print(
                    f"  ✅ Successfully pushed {repo_path}"
                )
            else:
                raise Exception(
                    f"GitHub API error "
                    f"{response.status_code}: "
                    f"{response.text[:200]}"
                )

        except Exception as e:
            print(f"  ⚠️  Push failed: {e}")
            print(
                f"  ℹ️  File saved locally at: {local_path}"
            )

    def push_file(
        self,
        local_path: str,
        repo_path: str,
        commit_message: str = None
    ):
        """
        Generic method to push any file to GitHub.
        Only runs when not in GitHub Actions.
        """
        if self.running_in_actions:
            return

        if not self.token or not self.repo:
            return

        message = commit_message or f'Update {repo_path}'

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

            existing = requests.get(url, headers=self.headers)
            sha = None
            if existing.status_code == 200:
                sha = existing.json().get('sha')

            payload = {'message': message, 'content': encoded}
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
                print(
                    f"  ⚠️  Push failed "
                    f"{response.status_code}"
                )

        except Exception as e:
            print(f"  ⚠️  Push error: {e}")
