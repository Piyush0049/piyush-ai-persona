import os
import json
import math
import re
from typing import List, Dict, Any

class RAGService:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.chunks: List[Dict[str, Any]] = []
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.doc_vectors: List[Dict[int, float]] = []
        self.load_and_index()

    def clean_text(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        return text

    def tokenize(self, text: str) -> List[str]:
        cleaned = self.clean_text(text)
        return [w for w in cleaned.split() if len(w) > 1]

    def load_and_index(self):
        resume_path = os.path.join(self.data_dir, "resume.txt")
        github_path = os.path.join(self.data_dir, "github_repos.json")
        
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
        else:
            print("Warning: resume.txt not found in data directory.")

        if os.path.exists(github_path):
            with open(github_path, "r", encoding="utf-8") as f:
                repos = json.load(f)
            
            for repo in repos:
                name = repo.get("name", "")
                desc = repo.get("description", "")
                lang = repo.get("language", "Unknown")
                url = repo.get("url", "")
                readme = repo.get("readme", "")
                
                self.chunks.append({
                    "id": f"github_meta_{name}",
                    "source": f"GitHub Repository: {name}",
                    "title": f"GitHub Repo metadata: {name}",
                    "content": f"Repository Name: {name}\nPrimary Language: {lang}\nDescription: {desc}\nURL: {url}",
                    "url": url
                })
                
                if readme:
                    readme_clean = re.sub(r'#+\s+', '', readme)
                    chunk_size = 800
                    overlap = 200
                    start = 0
                    c_idx = 0
                    while start < len(readme_clean):
                        end = start + chunk_size
                        chunk_text = readme_clean[start:end].strip()
                        if chunk_text:
                            self.chunks.append({
                                "id": f"github_readme_{name}_{c_idx}",
                                "source": f"GitHub Repository: {name} (README)",
                                "title": f"README section of {name}",
                                "content": f"Repository Name: {name}\nREADME Context:\n{chunk_text}",
                                "url": url
                            })
                        start += (chunk_size - overlap)
                        c_idx += 1
        else:
            print("Warning: github_repos.json not found in data directory.")

        if not self.chunks:
            return

        df: Dict[str, int] = {}
        tf_docs: List[Dict[str, int]] = []
        
        for chunk in self.chunks:
            tokens = self.tokenize(chunk["content"] + " " + chunk["title"])
            tf: Dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            tf_docs.append(tf)
            
            for t in set(tokens):
                df[t] = df.get(t, 0) + 1

        n_docs = len(self.chunks)
        vocab_set = set(df.keys())
        self.vocab = {word: idx for idx, word in enumerate(vocab_set)}
        
        for word, count in df.items():
            self.idf[word] = math.log((1 + n_docs) / (1 + count)) + 1

        self.doc_vectors = []
        for tf in tf_docs:
            doc_vec: Dict[int, float] = {}
            length_sq = 0.0
            for word, term_freq in tf.items():
                w_idx = self.vocab[word]
                val = term_freq * self.idf[word]
                doc_vec[w_idx] = val
                length_sq += val * val
            
            length = math.sqrt(length_sq)
            if length > 0:
                for w_idx in doc_vec:
                    doc_vec[w_idx] /= length
            
            self.doc_vectors.append(doc_vec)

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        if not self.chunks or not self.vocab:
            return []

        q_tokens = self.tokenize(query)
        if not q_tokens:
            return self.chunks[:limit]

        q_tf: Dict[str, int] = {}
        for t in q_tokens:
            q_tf[t] = q_tf.get(t, 0) + 1

        q_vec: Dict[int, float] = {}
        length_sq = 0.0
        for word, term_freq in q_tf.items():
            if word in self.vocab:
                w_idx = self.vocab[word]
                val = term_freq * self.idf[word]
                q_vec[w_idx] = val
                length_sq += val * val
        
        q_length = math.sqrt(length_sq)
        if q_length > 0:
            for w_idx in q_vec:
                q_vec[w_idx] /= q_length

        scores = []
        for d_idx, doc_vec in enumerate(self.doc_vectors):
            dot_product = 0.0
            for w_idx, q_val in q_vec.items():
                if w_idx in doc_vec:
                    dot_product += q_val * doc_vec[w_idx]
            
            chunk = self.chunks[d_idx]
            boost = 0.0
            for word in q_tokens:
                if word in chunk["title"].lower() or word in chunk["source"].lower():
                    boost += 0.1
            
            scores.append((d_idx, dot_product + boost))

        scores.sort(key=lambda x: x[1], reverse=True)
        results = []
        for d_idx, score in scores[:limit]:
            results.append({
                "chunk": self.chunks[d_idx],
                "score": score
            })
            
        return [r["chunk"] for r in results if r["score"] > 0.0] or self.chunks[:limit]

rag_service = RAGService()
