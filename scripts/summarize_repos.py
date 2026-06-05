import json

with open("github_repos.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Total repos: {len(data)}")
for r in data:
    readme_len = len(r["readme"])
    if readme_len > 0:
        print(f"- {r['name']} ({r['language']}): {readme_len} chars README. Desc: {r['description']}")
