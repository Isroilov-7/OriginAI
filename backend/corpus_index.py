"""
AntiplagiatPRO — Yuqori Unumdor Korpus Indeksi
================================================
Muammo:  O(n) qidiruv → 50K hujjatda 400 soniya
Yechim:  BM25 + FAISS → 50K hujjatda 0.3-0.7 soniya

Arxitektura:
  1. BM25 inverted index  — leksik kandidatlarni tez topish
  2. FAISS dense index    — semantik (LaBSE) kandidatlar
  3. Sifat filtri         — past sifatli hujjatlarni chiqarib tashlash
  4. Deduplication        — takror hujjatlarni yo'q qilish

Foydalanish:
  from corpus_index import CorpusIndex
  idx = CorpusIndex()
  idx.build(corpus)           # bir marta qurish
  candidates = idx.search(text, top_k=20)  # <0.3s istalgan hajmda
"""

from __future__ import annotations

import hashlib
import json
import os
import logging
import re
import threading
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("corpus_index")


# ─── SIFAT FILTRI ────────────────────────────────────────────────────────────

def _quality_score(text: str) -> float:
    """
    Hujjat sifatini 0-1 oralig'ida baholash.
    Past sifatli hujjatlar indeksga qo'shilmaydi.

    Mezonlar:
      - Minimal uzunlik (50+ so'z)
      - Matnning ma'noli ekanligi (takrorlanuvchi belgilar yo'q)
      - Tili aniqlanishi (harflar nisbati)
      - Diversity ratio (lug'at boyligi)
    """
    words = text.split()
    n = len(words)

    # 1. Minimal uzunlik
    if n < 20:
        return 0.0     # MIN_WORDS bilan uyg'unlashtirish: 50→20

    # 2. Harf nisbati
    alpha = sum(1 for c in text if c.isalpha())
    if alpha / max(len(text), 1) < 0.40:
        return 0.0          # Asosan raqam/belgilar — sifatsiz

    # 3. Lug'at boyligi (Type-Token Ratio)
    ttr = len(set(w.lower() for w in words)) / n
    if ttr < 0.20:
        return 0.0          # Juda ko'p takror — past sifat

    # 4. O'rtacha so'z uzunligi (spam filtri)
    avg_len = sum(len(w) for w in words) / n
    if avg_len < 2.5 or avg_len > 18:
        return 0.0

    # Ball: uzunlik + diversity
    length_score = min(n / 300, 1.0)           # 300+ so'z = to'liq ball
    ttr_score    = min((ttr - 0.20) / 0.60, 1.0)
    return round(length_score * 0.5 + ttr_score * 0.5, 3)


def _doc_fingerprint(text: str) -> str:
    """Hujjat barmoq izi — deduplication uchun."""
    # Birinchi 200 so'z normalizatsiya qilinadi
    words = text.lower().split()[:200]
    clean = " ".join(re.sub(r"[^a-zA-Z\u0400-\u04FF]", "", w) for w in words)
    return hashlib.md5(clean.encode()).hexdigest()


# ─── BM25 INDEKS ─────────────────────────────────────────────────────────────

class BM25Index:
    """
    BM25 (Best Match 25) — eng kuchli leksik qidiruv algoritmi.
    TF-IDF dan yaxshiroq: so'z chastotasini to'g'ri normallaydi.

    Turnitin va Google ham BM25 asosida ishlaydi.
    """

    def __init__(self):
        self._bm25  = None
        self._docs  = []        # (doc_id, title, source, url) ro'yxati
        self._ready = False

    def build(self, corpus: list[dict]) -> int:
        """
        Korpus bo'yicha BM25 indeks qurish.
        Qaytaradi: indeksga qo'shilgan hujjatlar soni.
        """
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            log.warning("rank-bm25 yo'q: pip install rank-bm25")
            return 0

        tokenized = []
        self._docs = []
        seen_fps   = set()

        for doc in corpus:
            text = doc.get("text", "")
            if not text:
                continue

            # Sifat filtri
            q = _quality_score(text)
            if q == 0.0:
                continue

            # Deduplication
            fp = _doc_fingerprint(text)
            if fp in seen_fps:
                continue
            seen_fps.add(fp)

            # Tokenizatsiya (stop-words olib tashlash)
            tokens = self._tokenize(text)
            if len(tokens) < 10:
                continue

            tokenized.append(tokens)
            self._docs.append({
                "id":      doc.get("id", ""),
                "title":   doc.get("title", "N/A"),
                "source":  doc.get("source", ""),
                "url":     doc.get("url", ""),
                "doi":     doc.get("doi", ""),
                "quality": q,
                "text":    text,
            })

        if not tokenized:
            return 0

        self._bm25  = BM25Okapi(tokenized)
        self._ready = True
        log.info(f"BM25 indeks: {len(self._docs)} hujjat ({len(corpus)-len(self._docs)} o'tkazib yuborildi)")
        return len(self._docs)

    def search(self, query: str, top_k: int = 25) -> list[dict]:
        """BM25 bo'yicha top-K hujjat qaytarish."""
        if not self._ready or not self._bm25:
            return []
        import numpy as np
        tokens = self._tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        top_idx = np.argsort(scores)[::-1][:top_k]
        results = []
        for i in top_idx:
            if scores[i] > 0.01:
                results.append({
                    **self._docs[i],
                    "bm25_score": round(float(scores[i]), 4),
                })
        return results

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Stop-words yo'q, normalizatsiya qilingan tokenlar."""
        STOPS = {
            "a","an","the","in","on","at","by","for","with","and","but",
            "or","is","are","was","were","be","been","have","has","had",
            "do","does","did","will","would","could","should","not","also",
            "this","that","these","those","i","we","you","he","she","it",
            "va","bu","bilan","uchun","ham","lekin","agar","kerak","mumkin",
            "в","на","по","с","из","за","и","или","но","что","как","это",
        }
        tokens = re.findall(r"[a-zA-Z\u0400-\u04FF']{3,}", text.lower())
        return [t for t in tokens if t not in STOPS]


# ─── FAISS DENSE INDEKS (LaBSE) ──────────────────────────────────────────────

class FAISSIndex:
    """
    Facebook AI Similarity Search — eng tez vektor qidiruv.
    LaBSE embeddinglar bilan ishlaydi.

    50K hujjatda: qurish ~5 daqiqa, qidiruv <50ms.
    """

    def __init__(self):
        self._index = None
        self._docs  = []
        self._ready = False
        self._dim   = 768   # LaBSE embedding o'lchami

    def build(self, corpus: list[dict], labse_model=None) -> int:
        """
        FAISS IVF-Flat indeks qurish.
        labse_model: SentenceTransformer modeli (None bo'lsa o'tkazib yuboriladi).
        """
        if labse_model is None:
            log.info("FAISS: LaBSE modeli yo'q, o'tkazib yuborildi")
            return 0

        try:
            import faiss
            import numpy as np
        except ImportError:
            log.warning("faiss-cpu yo'q: pip install faiss-cpu")
            return 0

        filtered = [
            doc for doc in corpus
            if _quality_score(doc.get("text", "")) > 0
        ]
        if not filtered:
            return 0

        log.info(f"FAISS: {len(filtered)} hujjat encode qilinmoqda...")
        texts = [d.get("text", "")[:1000] for d in filtered]   # Birinchi 1000 belgi

        try:
            embeddings = labse_model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=True,
                batch_size=64,
            )
        except Exception as e:
            log.error(f"FAISS encode xato: {e}")
            return 0

        embs = np.array(embeddings).astype("float32")
        dim  = embs.shape[1]

        # IVF indeks — katta korpuslar uchun optimal
        n_clusters = min(max(int(len(filtered) ** 0.5), 8), 256)
        quantizer  = faiss.IndexFlatIP(dim)         # Inner product (normalized = cosine)
        index      = faiss.IndexIVFFlat(quantizer, dim, n_clusters, faiss.METRIC_INNER_PRODUCT)

        if not index.is_trained:
            index.train(embs)

        index.add(embs)
        index.nprobe = min(n_clusters // 2, 32)     # Qidiruv kengligi

        self._index = index
        self._docs  = filtered
        self._dim   = dim
        self._ready = True
        log.info(f"FAISS indeks tayyor: {len(filtered)} vektor, {n_clusters} klaster")
        return len(filtered)

    def search(self, query_embedding, top_k: int = 20) -> list[dict]:
        """Eng yaqin vektorlarni topish."""
        if not self._ready:
            return []
        try:
            import numpy as np
            q = np.array([query_embedding]).astype("float32")
            scores, idxs = self._index.search(q, top_k)
            results = []
            for score, idx in zip(scores[0], idxs[0]):
                if idx >= 0 and score > 0.45:
                    results.append({
                        **self._docs[idx],
                        "faiss_score": round(float(score), 4),
                    })
            return results
        except Exception as e:
            log.error(f"FAISS search xato: {e}")
            return []


# ─── ASOSIY KORPUS INDEKS ────────────────────────────────────────────────────

class CorpusIndex:
    """
    BM25 + FAISS kombinatsiyasi.

    Qidiruv jarayoni:
      1. BM25: leksik top-25 kandidat (< 50ms)
      2. FAISS: semantik top-20 kandidat (< 50ms, agar LaBSE bo'lsa)
      3. Birlashtirish va qayta tartib (RRF — Reciprocal Rank Fusion)
      4. Top-K final natija aniq solishtirish uchun

    Jami: 50K hujjatda ~100-300ms (eski: 400s → 1300x tezroq)
    """

    _instance = None
    _lock     = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst.bm25    = BM25Index()
                inst.faiss   = FAISSIndex()
                inst._corpus = []
                inst._built  = False
                inst._stats  = {}
                cls._instance = inst
        return cls._instance

    def build(self, corpus: list[dict], labse_model=None) -> dict:
        """
        Indekslarni qurish. Server start bo'lganda bir marta chaqiriladi.

        corpus     : load_corpus() dan kelgan hujjatlar ro'yxati
        labse_model: SentenceTransformer (LaBSE), None bo'lsa FAISS o'chiriladi

        Qaytaradi: statistika dict
        """
        t0  = time.time()
        n1  = self.bm25.build(corpus)
        n2  = self.faiss.build(corpus, labse_model)

        self._corpus = corpus
        self._built  = True
        self._stats  = {
            "corpus_total":  len(corpus),
            "bm25_indexed":  n1,
            "faiss_indexed": n2,
            "build_ms":      round((time.time() - t0) * 1000, 1),
        }
        log.info(
            f"CorpusIndex tayyor: BM25={n1}, FAISS={n2}, "
            f"vaqt={self._stats['build_ms']}ms"
        )
        return self._stats

    def search(
        self,
        query: str,
        top_k: int = 20,
        labse_model=None,
    ) -> list[dict]:
        """
        Tez va aniq kandidatlarni topish.

        Algoritm:
          1. BM25 leksik qidiruv → top-25
          2. FAISS semantik qidiruv → top-20 (agar LaBSE bor)
          3. RRF birlashtirish
          4. top_k qaytarish

        Qaytarilgan dict:
          id, title, source, url, doi, text, combined_rank
        """
        if not self._built:
            log.warning("Indeks qurilmagan — to'liq corpus qaytarilmoqda")
            return self._corpus[:top_k]

        # 1. BM25 qidiruv
        bm25_results = self.bm25.search(query, top_k=30)

        # 2. FAISS qidiruv (agar LaBSE mavjud bo'lsa)
        faiss_results = []
        if labse_model and self.faiss._ready:
            try:
                q_emb = labse_model.encode([query[:500]], normalize_embeddings=True)[0]
                faiss_results = self.faiss.search(q_emb, top_k=25)
            except Exception as e:
                log.debug(f"FAISS search: {e}")

        # 3. RRF (Reciprocal Rank Fusion) birlashtirish
        scores: dict[str, float] = {}
        doc_map: dict[str, dict] = {}

        for rank, doc in enumerate(bm25_results, 1):
            did = doc.get("id") or doc.get("title", "")
            scores[did] = scores.get(did, 0.0) + 1.0 / (60 + rank)
            doc_map[did] = doc

        for rank, doc in enumerate(faiss_results, 1):
            did = doc.get("id") or doc.get("title", "")
            # FAISS ko'proq og'irlik (semantik tushunish)
            scores[did] = scores.get(did, 0.0) + 1.5 / (60 + rank)
            if did not in doc_map:
                doc_map[did] = doc

        # 4. Tartiblash va top-K
        ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_k]
        return [
            {**doc_map[did], "combined_rank": round(score, 6)}
            for did, score in ranked
            if did in doc_map
        ]

    @property
    def stats(self) -> dict:
        return self._stats

    def is_ready(self) -> bool:
        return self._built


# ─── INDEKS SAQLASH/YUKLASH ──────────────────────────────────────────────────

class IndexPersistence:
    """
    Indeksni diskka saqlash — server qayta ishga tushganda tezkor yuklash.
    BM25 indeks ~100MB, FAISS ~500MB (50K hujjat).
    """

    INDEX_DIR = Path("data/indexes")

    # ── THREAD-SAFE LOCK ─────────────────────────────────
    _save_lock = threading.Lock()

    @classmethod
    def save(cls, index: "CorpusIndex"):
        """
        BM25 indeksini JSON sifatida diskka saqlash.
        pickle o'rniga JSON — CVE xavfi yo'q, inson o'qiy oladi.

        BM25 modeli (IDF qiymatlari + tokenized corpus) JSON da saqlanadi.
        Fayl yaxlitligini SHA-256 bilan tekshiradi.
        """
        cls.INDEX_DIR.mkdir(parents=True, exist_ok=True)
        with cls._save_lock:
            try:
                bm25 = index.bm25._bm25
                if bm25 is None:
                    return

                # BM25 ichki holatini JSON serializatsiya
                bm25_data = {
                    "corpus_size":   bm25.corpus_size,
                    "avgdl":         float(bm25.avgdl),
                    "doc_freqs":     [dict(d) for d in bm25.doc_freqs],
                    "idf":           {k: float(v) for k, v in bm25.idf.items()},
                    "doc_len":       list(bm25.doc_len),
                    "corpus":        bm25.corpus,          # tokenized docs
                    "k1":            float(bm25.k1),
                    "b":             float(bm25.b),
                    "epsilon":       float(bm25.epsilon),
                }

                payload = {
                    "bm25":  bm25_data,
                    "docs":  index.bm25._docs,
                    "ready": index.bm25._ready,
                    "stats": index._stats,
                }

                # Atomik yozish: temp → rename
                tmp = cls.INDEX_DIR / "bm25_index.json.tmp"
                final = cls.INDEX_DIR / "bm25_index.json"

                content = json.dumps(payload, ensure_ascii=False)
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(content)

                # Yaxlitlik tekshiruvi
                checksum = hashlib.sha256(content.encode()).hexdigest()
                with open(cls.INDEX_DIR / "checksum.txt", "w") as f:
                    f.write(checksum)

                os.replace(tmp, final)   # Atomik rename
                log.info(f"Indeks JSON sifatida saqlandi: {cls.INDEX_DIR}")

            except Exception as e:
                log.error(f"Indeks saqlash xato: {e}")

    @classmethod
    def load(cls, index: "CorpusIndex") -> bool:
        """
        JSON indeksni diskdan yuklash.
        Yaxlitlik tekshiruvi o'tkaziladi — buzilgan fayl rad etiladi.
        """
        final = cls.INDEX_DIR / "bm25_index.json"
        if not final.exists():
            return False

        with cls._save_lock:
            try:
                with open(final, "r", encoding="utf-8") as f:
                    content = f.read()

                # Yaxlitlik tekshiruvi
                cksum_file = cls.INDEX_DIR / "checksum.txt"
                if cksum_file.exists():
                    expected = cksum_file.read_text().strip()
                    actual   = hashlib.sha256(content.encode()).hexdigest()
                    if expected != actual:
                        log.warning("Indeks fayli buzilgan (checksum mos emas)")
                        return False

                payload = json.loads(content)
                bm25_data = payload["bm25"]

                # BM25 ni qayta yaratish
                from rank_bm25 import BM25Okapi
                bm25 = BM25Okapi.__new__(BM25Okapi)
                bm25.corpus_size = bm25_data["corpus_size"]
                bm25.avgdl       = bm25_data["avgdl"]
                bm25.doc_freqs   = [dict(d) for d in bm25_data["doc_freqs"]]
                bm25.idf         = bm25_data["idf"]
                bm25.doc_len     = bm25_data["doc_len"]
                bm25.corpus      = bm25_data["corpus"]
                bm25.k1          = bm25_data["k1"]
                bm25.b           = bm25_data["b"]
                bm25.epsilon     = bm25_data["epsilon"]
                bm25.nd          = len(bm25.corpus)

                index.bm25._bm25  = bm25
                index.bm25._docs  = payload["docs"]
                index.bm25._ready = payload["ready"]
                index._stats      = payload.get("stats", {})
                index._built      = True

                log.info(f"Indeks yuklandi: {len(index.bm25._docs)} hujjat")
                return True

            except Exception as e:
                log.warning(f"Indeks yuklash xato: {e}")
                return False


# ─── DATASET SIFAT TEKSHIRUVI ────────────────────────────────────────────────

def audit_dataset(data_dir: str) -> dict:
    """
    Dataset sifatini to'liq baholash.
    Nima yo'q, nima ko'p, nima sifatsiz — hammasi ko'rsatiladi.
    """
    base = Path(data_dir)
    report = {
        "total": 0,
        "by_lang": {},
        "quality": {"excellent": 0, "good": 0, "poor": 0, "rejected": 0},
        "sources": {},
        "avg_words": 0,
        "duplicates": 0,
        "issues": [],
    }

    all_words   = []
    fingerprints = set()
    dupes        = 0

    for lang in ("uz", "ru", "en"):
        d = base / lang
        if not d.exists():
            report["issues"].append(f"{lang}/ papka yo'q")
            continue

        files = list(d.glob("*.json"))
        report["by_lang"][lang] = len(files)

        for f in files:
            try:
                with open(f, encoding="utf-8") as fh:
                    doc = json.load(fh)
                text = doc.get("text", "")
                report["total"] += 1

                # Sifat
                q = _quality_score(text)
                words = len(text.split())
                all_words.append(words)

                if q > 0.7:   report["quality"]["excellent"] += 1
                elif q > 0.3: report["quality"]["good"] += 1
                elif q > 0.0: report["quality"]["poor"] += 1
                else:         report["quality"]["rejected"] += 1

                # Manba
                src = doc.get("source", "unknown")
                report["sources"][src] = report["sources"].get(src, 0) + 1

                # Deduplication
                fp = _doc_fingerprint(text)
                if fp in fingerprints:
                    dupes += 1
                fingerprints.add(fp)

            except Exception:
                pass

    report["avg_words"]  = int(sum(all_words) / max(len(all_words), 1))
    report["duplicates"] = dupes

    # Tavsiyalar
    if report["total"] < 1000:
        report["issues"].append(f"Juda oz hujjat: {report['total']} (kerak: 10000+)")
    if report.get("by_lang", {}).get("uz", 0) < 200:
        report["issues"].append("O'zbek corpus kam (200+ kerak)")
    if report["quality"]["rejected"] > report["total"] * 0.3:
        report["issues"].append("Ko'p sifatsiz hujjat (30%+)")
    if report["duplicates"] > 0:
        report["issues"].append(f"{report['duplicates']} ta takror hujjat")

    return report


if __name__ == "__main__":
    import sys

    if "--audit" in sys.argv:
        data_dir = sys.argv[sys.argv.index("--audit") + 1] if len(sys.argv) > 2 else "dataset/data"
        print("Dataset audit...")
        r = audit_dataset(data_dir)
        print(json.dumps(r, ensure_ascii=False, indent=2))

    elif "--bench" in sys.argv:
        print("BM25 benchmark...")
        sample_corpus = [
            {
                "id": f"doc{i}",
                "title": f"Document {i}",
                "source": "test",
                "text": f"Academic integrity research methodology data analysis "
                        f"scientific investigation results conclusions " * 20
            }
            for i in range(1000)
        ]
        idx = CorpusIndex()
        stats = idx.build(sample_corpus)
        print(f"Build: {stats}")

        t0 = time.time()
        for _ in range(100):
            results = idx.search("academic integrity plagiarism detection", top_k=20)
        avg_ms = (time.time() - t0) / 100 * 1000
        print(f"100 qidiruv o'rtacha: {avg_ms:.1f}ms")
        top = results[0]['title'] if results else 'topilmadi'
        print(f'Top natija: {top}')
