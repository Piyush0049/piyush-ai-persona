"""
RAG Service using LIVE GitHub API - NO file caching!
Fetches data on-demand from GitHub API for always-fresh results
"""
import os
import json
import math
import re
import subprocess
from typing import List, Dict, Any
from github_api_service import github_api

class RAGService:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.chunks: List[Dict[str, Any]] = []
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.doc_vectors: List[Dict[int, float]] = []

        print("[*] Starting RAG with LIVE GitHub API (no file caching, instant startup)...")

        # Extract resume from PDF (only file we save)
        self._extract_resume_from_pdf()

        # Load and index data using GitHub API
        self.load_and_index()

        print(f"[OK] RAG ready with {len(self.chunks)} chunks (all from live API)!")

    def clean_text(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        return text

    def tokenize(self, text: str) -> List[str]:
        cleaned = self.clean_text(text)
        return [w for w in cleaned.split() if len(w) > 1]

    def _extract_resume_from_pdf(self):
        """Extract resume text from PDF"""
        resume_path = os.path.join(self.data_dir, "resume.txt")
        pdf_path = os.path.join(self.data_dir, "piyush_joshi_resume.pdf")

        if os.path.exists(resume_path):
            return  # Already extracted

        if os.path.exists(pdf_path):
            try:
                result = subprocess.run(
                    ["python", "scripts/extract_resumes.py"],
                    capture_output=True,
                    timeout=10
                )
                if result.returncode == 0:
                    print("  [OK] Resume extracted from PDF")
            except:
                print("  [WARN]  Using fallback resume")

    def load_and_index(self):
        """Load data from resume.txt and GitHub API (NO JSON files!)"""
        # 1. Load resume from text file
        resume_path = os.path.join(self.data_dir, "resume.txt")
        if os.path.exists(resume_path):
            with open(resume_path, "r", encoding="utf-8") as f:
                resume_text = f.read()

            sections = re.split(r'\n(?=Education|Experience|Projects|Technical Skills)', resume_text)
            for idx, sec in enumerate(sections):
                sec = sec.strip()
                if not sec:
                    continue
                if len(sec) > 1000:
                    subsections = sec.split("\n\n")
                    for s_idx, sub in enumerate(subsections):
                        sub = sub.strip()
                        if sub:
                            self.chunks.append({
                                "id": f"resume_sec_{idx}_sub_{s_idx}",
                                "source": "Resume",
                                "title": f"Resume Section: {sub.splitlines()[0]}",
                                "content": sub,
                                "url": "resume"
                            })
                else:
                    self.chunks.append({
                        "id": f"resume_sec_{idx}",
                        "source": "Resume",
                        "title": f"Resume Section: {sec.splitlines()[0]}",
                        "content": sec,
                        "url": "resume"
                    })

        # 2. Fetch repositories from GitHub API WITH READMEs for accurate search
        print("  -> Fetching repository list from GitHub API...")
        repos = github_api.get_repos()
        print(f"  [OK] Found {len(repos)} repositories")

        print("  -> Fetching READMEs + dependencies for deep tech indexing...")
        readme_count = 0
        deps_count = 0

        # Add repo metadata + README + dependencies to chunks
        for idx, repo in enumerate(repos):
            name = repo["name"]
            desc = repo["description"]
            lang = repo["language"]
            url = repo["url"]
            stars = repo["stars"]
            forks = repo["forks"]
            updated = repo["updated_at"]

            # Fetch README for this repo
            readme = github_api.get_readme(name)
            if readme:
                readme_count += 1

            # Fetch dependencies based on language
            dependencies_text = ""

            # JavaScript/TypeScript - fetch package.json
            if lang in ["JavaScript", "TypeScript"]:
                pkg_json = github_api.get_package_json(name)
                if pkg_json:
                    deps_count += 1
                    dependencies_text += "\n\nDependencies (package.json):\n"
                    if "dependencies" in pkg_json:
                        for dep, ver in pkg_json["dependencies"].items():
                            dependencies_text += f"  - {dep}: {ver}\n"
                    if "devDependencies" in pkg_json:
                        dependencies_text += "Dev Dependencies:\n"
                        for dep, ver in pkg_json["devDependencies"].items():
                            dependencies_text += f"  - {dep}: {ver}\n"

            # Python - fetch requirements.txt
            elif lang == "Python":
                reqs_txt = github_api.get_requirements_txt(name)
                if reqs_txt:
                    deps_count += 1
                    dependencies_text += "\n\nDependencies (requirements.txt):\n"
                    dependencies_text += reqs_txt[:1000]  # First 1000 chars

            # Build searchable content with README + dependencies
            meta_content = f"Repository Name: {name}\n"
            meta_content += f"Primary Language: {lang}\n"
            meta_content += f"Description: {desc}\n"
            if readme:
                # Include first 3000 chars of README for indexing
                meta_content += f"\n\nREADME Content:\n{readme[:3000]}"
            if dependencies_text:
                meta_content += dependencies_text
            meta_content += f"\n\nURL: {url}\n"
            meta_content += f"Stars: {stars}, Forks: {forks}\n"
            meta_content += f"Last Updated: {updated}"

            self.chunks.append({
                "id": f"github_meta_{name}",
                "source": f"GitHub Repository: {name}",
                "title": f"GitHub Repo: {name}",
                "content": meta_content,
                "url": url
            })

            # Progress indicator every 10 repos
            if (idx + 1) % 10 == 0:
                print(f"  -> Processed {idx + 1}/{len(repos)} repositories...")

        print(f"  [OK] Indexed {readme_count} READMEs + {deps_count} dependency files")

        # Build TF-IDF index
        self.build_tfidf()

    def build_tfidf(self):
        """Build TF-IDF vectors for all chunks"""
        doc_tokens_list = []
        for chunk in self.chunks:
            content = chunk.get("content", "")
            tokens = self.tokenize(content)
            doc_tokens_list.append(tokens)

        # Build vocabulary
        for tokens in doc_tokens_list:
            for tok in set(tokens):
                if tok not in self.vocab:
                    self.vocab[tok] = len(self.vocab)

        # Calculate IDF
        N = len(doc_tokens_list)
        for tok in self.vocab:
            df = sum(1 for doc_tokens in doc_tokens_list if tok in doc_tokens)
            self.idf[tok] = math.log((N + 1) / (df + 1))

        # Build document vectors
        for tokens in doc_tokens_list:
            tf = {}
            for tok in tokens:
                tf[tok] = tf.get(tok, 0) + 1

            vec = {}
            for tok, freq in tf.items():
                if tok in self.vocab:
                    vec[self.vocab[tok]] = freq * self.idf[tok]

            # Normalize
            norm = math.sqrt(sum(v**2 for v in vec.values()))
            if norm > 0:
                vec = {k: v/norm for k, v in vec.items()}

            self.doc_vectors.append(vec)

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search chunks using TF-IDF (READMEs already indexed at startup)"""
        q_tokens = self.tokenize(query)

        # Build query vector
        q_tf = {}
        for tok in q_tokens:
            q_tf[tok] = q_tf.get(tok, 0) + 1

        q_vec = {}
        for tok, freq in q_tf.items():
            if tok in self.vocab:
                q_vec[self.vocab[tok]] = freq * self.idf.get(tok, 0)

        norm = math.sqrt(sum(v**2 for v in q_vec.values()))
        if norm > 0:
            q_vec = {k: v/norm for k, v in q_vec.items()}

        # Calculate scores
        scores = []
        for d_idx, doc_vec in enumerate(self.doc_vectors):
            dot_product = sum(q_vec.get(k, 0) * v for k, v in doc_vec.items())
            scores.append((d_idx, dot_product))

        # Sort and get top results
        scores.sort(key=lambda x: x[1], reverse=True)
        top_results = scores[:limit]

        results = []
        for d_idx, score in top_results:
            chunk = self.chunks[d_idx].copy()
            chunk["score"] = score
            results.append(chunk)

        return results

# Global instance
rag_service = RAGService()
