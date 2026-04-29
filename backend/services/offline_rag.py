from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


def _split_markdown_sections(md: str) -> List[Tuple[str, str]]:
    """
    Splits markdown into (heading, section_text) pairs.

    We treat lines like `## some-heading` or `### some-heading` as section boundaries.
    """
    lines = md.splitlines()
    sections: List[Tuple[str, List[str]]] = []
    current_heading = "root"
    current_buf: List[str] = []

    heading_re = re.compile(r"^#{2,3}\s+(.+?)\s*$")

    for line in lines:
        m = heading_re.match(line.strip())
        if m:
            # Flush previous section
            if current_buf:
                sections.append((current_heading, current_buf))
            current_heading = m.group(1).strip()
            current_buf = []
        else:
            current_buf.append(line)

    if current_buf:
        sections.append((current_heading, current_buf))

    return [(heading, "\n".join(buf).strip()) for heading, buf in sections if "\n".join(buf).strip()]


def _split_sentences(text: str) -> List[str]:
    # Simple sentence splitter good enough for short KB chunks.
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []
    # Split on period/question/exclamation while keeping it simple.
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


@dataclass(frozen=True)
class RetrievalChunk:
    source: str
    heading: str
    text: str


class OfflineRagManualKB:
    """
    Lightweight RAG: offline TF-IDF retriever + grounded answer extraction.

    This intentionally avoids external model/API keys for the prototype.
    """

    def __init__(self) -> None:
        self._chunks: List[RetrievalChunk] = []
        self._idf: Dict[str, float] = {}
        self._doc_vecs: List[Dict[str, float]] = []
        self._doc_norms: List[float] = []
        self._built = False

    def _kb_paths(self) -> List[Path]:
        # backend/services -> backend -> ninjavan root
        repo_root = Path(__file__).resolve().parents[2]
        return [
            repo_root / "backend" / "knowledge_base" / "customer_support_kb.md",
            repo_root / "USER_MANUAL.md",
        ]

    def _load_chunks(self) -> List[RetrievalChunk]:
        chunks: List[RetrievalChunk] = []
        for path in self._kb_paths():
            if not path.exists():
                continue
            md = path.read_text(encoding="utf-8")
            for heading, section_text in _split_markdown_sections(md):
                # Use heading as a stable "source" for the UI response.
                source = f"{path.stem}:{heading}".lower().replace(" ", "-")
                chunks.append(
                    RetrievalChunk(
                        source=source,
                        heading=heading,
                        text=section_text,
                    )
                )
        return chunks

    def _build_index(self) -> None:
        self._chunks = self._load_chunks()
        if not self._chunks:
            # Keep index empty; retrieval will degrade gracefully.
            self._built = True
            return

        doc_tokens: List[List[str]] = [_tokenize(c.text) for c in self._chunks]
        vocab: Dict[str, int] = {}
        for toks in doc_tokens:
            for t in set(toks):
                vocab[t] = vocab.get(t, 0) + 1

        n_docs = len(doc_tokens)
        self._idf = {t: math.log((n_docs + 1) / (df + 1)) + 1.0 for t, df in vocab.items()}

        self._doc_vecs = []
        self._doc_norms = []
        for toks in doc_tokens:
            tf: Dict[str, int] = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            vec: Dict[str, float] = {}
            for t, count in tf.items():
                if t in self._idf:
                    vec[t] = float(count) * self._idf[t]

            norm = math.sqrt(sum(v * v for v in vec.values())) or 1e-12
            self._doc_vecs.append(vec)
            self._doc_norms.append(norm)

        self._built = True

    def _ensure_built(self) -> None:
        if not self._built:
            self._build_index()

    def _query_vec(self, query: str) -> Tuple[Dict[str, float], float]:
        toks = _tokenize(query)
        tf: Dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        vec: Dict[str, float] = {}
        for t, count in tf.items():
            if t in self._idf:
                vec[t] = float(count) * self._idf[t]
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1e-12
        return vec, norm

    def retrieve_top_k(self, query: str, k: int = 2) -> List[Tuple[RetrievalChunk, float]]:
        self._ensure_built()
        if not self._chunks:
            return []
        q_vec, q_norm = self._query_vec(query)
        if not q_vec:
            return []

        scored: List[Tuple[RetrievalChunk, float]] = []
        for idx, chunk in enumerate(self._chunks):
            d_vec = self._doc_vecs[idx]
            dot = 0.0
            # Compute dot over shared terms only.
            if len(d_vec) < len(q_vec):
                for t, dv in d_vec.items():
                    qv = q_vec.get(t)
                    if qv is not None:
                        dot += dv * qv
            else:
                for t, qv in q_vec.items():
                    dv = d_vec.get(t)
                    if dv is not None:
                        dot += dv * qv

            sim = dot / (q_norm * self._doc_norms[idx])
            scored.append((chunk, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def answer_from_top_chunks(self, query: str, top_chunks: List[Tuple[RetrievalChunk, float]]) -> str:
        if not top_chunks:
            return (
                "I found relevant guidance and can connect you to a live agent for complex cases."
            )

        # Use the highest-scoring chunk for grounding.
        top_chunk, _ = top_chunks[0]
        query_tokens = set(_tokenize(query))
        sentences = _split_sentences(top_chunk.text)
        if not sentences:
            return top_chunk.text.strip()[:400]

        def score_sentence(s: str) -> float:
            toks = set(_tokenize(s))
            if not toks:
                return 0.0
            overlap = len(toks & query_tokens)
            # Slightly prefer shorter sentences to keep answers tight.
            return overlap / (1.0 + len(toks))

        ranked = sorted(sentences, key=score_sentence, reverse=True)
        best = ranked[0]

        # If the best sentence is too generic, fallback to first sentence.
        if score_sentence(best) <= 0.01 and sentences:
            best = sentences[0]

        # Return up to two grounded sentences to capture both the "context" and the "example response"
        # when the KB chunk contains multiple relevant sentences.
        if len(ranked) >= 2:
            second = ranked[1]
            candidate = f"{best} {second}".strip()
            if len(candidate) <= 420:
                return candidate
        return best


# Module-level singleton to avoid rebuilding the TF-IDF index per request.
_RAG_SINGLETON = OfflineRagManualKB()


def rag_chatbot_query(query: str, top_k: int = 2) -> Dict[str, object]:
    """
    Returns:
      - answer: grounded answer string
      - retrieval: list of {source, confidence}
      - top_confidence: float (for escalation logic)
    """
    top_chunks = _RAG_SINGLETON.retrieve_top_k(query, k=top_k)
    retrieval: List[Dict[str, float | str]] = []
    for chunk, sim in top_chunks:
        # Cosine similarity over TF-IDF is often < 1.0; we rescale so the existing
        # `confidence_threshold` (default 0.65) behaves reasonably for strong matches.
        confidence = float(1.0 - math.exp(-5.0 * max(sim, 0.0)))
        confidence = float(max(0.0, min(1.0, confidence)))
        retrieval.append({"source": chunk.source, "confidence": confidence})

    answer = _RAG_SINGLETON.answer_from_top_chunks(query, top_chunks)
    top_confidence = float(retrieval[0]["confidence"]) if retrieval else 0.0
    return {"answer": answer, "retrieval": retrieval, "top_confidence": top_confidence}

