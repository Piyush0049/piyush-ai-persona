import urllib.request
import json
import os

def fetch_repos():
    url = "https://api.github.com/users/Piyush0049/repos"
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            repos = json.loads(response.read())
            return repos
    except Exception as e:
        print(f"Error fetching repos: {e}")
        return []

def fetch_readme(repo_name):
    # GitHub README URL
    url = f"https://raw.githubusercontent.com/Piyush0049/{repo_name}/master/README.md"
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
    except Exception:
        # try main branch
        url_main = f"https://raw.githubusercontent.com/Piyush0049/{repo_name}/main/README.md"
        req_main = urllib.request.Request(url_main, headers=headers)
        try:
            with urllib.request.urlopen(req_main) as response:
                return response.read().decode('utf-8')
        except Exception:
            return ""

if __name__ == "__main__":
    repos = fetch_repos()
    print(f"Found {len(repos)} repositories:")
    data = []
    for r in repos:
        name = r["name"]
        desc = r["description"] or "No description"
        lang = r["language"] or "Unknown"
        created = r["created_at"]
        url = r["html_url"]
        print(f"- {name} ({lang})")
        
        # Fetch README
        readme = fetch_readme(name)
        
        data.append({
            "name": name,
            "description": desc,
            "language": lang,
            "url": url,
            "created_at": created,
            "readme": readme
        })
        
    with open("github_repos.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("Saved metadata and READMEs to github_repos.json")
