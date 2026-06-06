"""
Direct GitHub API service - NO file caching, pure API calls
Fetches data on-demand from GitHub API in real-time
"""
import os
import json
import urllib.request
from typing import Dict, List, Any, Optional

class GitHubAPIService:
    def __init__(self):
        self.username = "Piyush0049"
        self.token = os.environ.get("GITHUB_TOKEN", "")
        self.headers = {"User-Agent": "Mozilla/5.0"}
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def _fetch(self, url: str, timeout: int = 10) -> Optional[Any]:
        """Fetch data from GitHub API"""
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read())
        except Exception as e:
            print(f"API error: {e}")
            return None

    def get_repos(self) -> List[Dict[str, Any]]:
        """Get all public repositories (lightweight, no README)"""
        url = f"https://api.github.com/users/{self.username}/repos?per_page=100&sort=updated"
        repos = self._fetch(url)
        if not repos:
            return []

        # Return lightweight repo data
        return [{
            "name": r.get("name", ""),
            "description": r.get("description", ""),
            "language": r.get("language", "Unknown"),
            "url": r.get("html_url", ""),
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
            "updated_at": r.get("updated_at", ""),
            "size": r.get("size", 0),
            "fork": r.get("fork", False)
        } for r in repos]

    def get_readme(self, repo_name: str) -> str:
        """Fetch README for specific repo on-demand"""
        for branch in ["master", "main"]:
            url = f"https://raw.githubusercontent.com/{self.username}/{repo_name}/{branch}/README.md"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as response:
                    return response.read().decode('utf-8')
            except:
                continue
        return ""

    def get_commits(self, repo_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent commits for specific repo"""
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/commits?per_page={limit}"
        commits = self._fetch(url)
        if not commits:
            return []

        return [{
            "date": c["commit"]["author"]["date"],
            "message": c["commit"]["message"],
            "author": c["commit"]["author"]["name"]
        } for c in commits]

    def get_languages(self, repo_name: str) -> Dict[str, int]:
        """Get programming languages used in repo"""
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/languages"
        return self._fetch(url) or {}

    def get_package_json(self, repo_name: str) -> Optional[Dict]:
        """Fetch package.json for dependency analysis"""
        url = f"https://raw.githubusercontent.com/{self.username}/{repo_name}/master/package.json"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                return json.loads(response.read())
        except:
            # Try main branch
            url = f"https://raw.githubusercontent.com/{self.username}/{repo_name}/main/package.json"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as response:
                    return json.loads(response.read())
            except:
                return None

    def get_requirements_txt(self, repo_name: str) -> Optional[str]:
        """Fetch requirements.txt for Python projects"""
        for branch in ["master", "main"]:
            url = f"https://raw.githubusercontent.com/{self.username}/{repo_name}/{branch}/requirements.txt"
            headers = {"User-Agent": "Mozilla/5.0"}
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=5) as response:
                    return response.read().decode('utf-8')
            except:
                continue
        return None

    def search_repos(self, query: str) -> List[str]:
        """Search repos by keyword (returns repo names)"""
        repos = self.get_repos()
        query_lower = query.lower()

        matching = []
        for repo in repos:
            # Search in name, description, and language
            searchable = f"{repo['name']} {repo['description']} {repo['language']}".lower()
            if query_lower in searchable:
                matching.append(repo['name'])

        return matching

# Global instance
github_api = GitHubAPIService()
