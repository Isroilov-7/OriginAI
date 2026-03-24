"""
AntiplagiatPRO — Internet Text Search Module
==============================================
GPTZero va Turnitin kabi internet orqali matnni tekshirish.

3 ta funksiya:
  1. web_search_check()    — Matndan kalit jumlalarni Google da qidirish
  2. web_fetch_compare()   — Topilgan sahifalar bilan solishtirish
  3. web_ai_cross_check()  — AI detektor natijasini web bilan tasdiqlash

O'rnatish:
  pip install httpx

.env ga qo'shing:
  GOOGLE_API_KEY=...
  GOOGLE_SEARCH_ENGINE_ID=...

Narx: Google Custom Search — $5/1000 so'rov, kuniga 100 ta bepul.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import time
from typing import Optional
from pathlib import Path

log = logging.getLogger("web_search")

# ── SOZLAMALAR ────────────────────────────────────────────────

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CX = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")
WEB_SEARCH_ENABLED = bool(GOOGLE_API_KEY and GOOGLE_CX)

# Alternativ: SerpAPI (qimmatroq lekin osonroq)
SERP_API_KEY = os.getenv("SERP_API_KEY", "")


def _split_key_sentences(text: str, max_sents: int = 5) -> list[str]:
    """Matndan eng xarakterli jumlalarni tanlash (qidiruv uchun)."""
    sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip())
             if 8 <= len(s.split()) <= 30]
    if not sents:
        return []
    # Eng uzun va eng xarakterli jumlalarni tanlash
    scored = []
    for s in sents:
        words = s.lower().split()
        # Stop so'zlar nisbati past = xarakterli
        stops = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
                 "va", "bu", "bilan", "da", "и", "в", "на", "с"}
        stop_ratio = sum(1 for w in words if w in stops) / max(len(words), 1)
        score = len(words) * (1.0 - stop_ratio)
        scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:max_sents]]


async def web_search_check(
    text: str,
    lang: str = "en",
    max_queries: int = 5,
) -> dict:
    """
    Matndan kalit jumlalarni Google Custom Search da qidirish.

    Qaytaradi:
      found:    bool — internet da o'xshash matn topildimi
      matches:  list — topilgan sahifalar
      score:    float — internet o'xshashlik balli (0-100)
      queries:  int — ishlatilgan so'rovlar soni
    """
    if not WEB_SEARCH_ENABLED and not SERP_API_KEY:
        return {
            "enabled": False,
            "found": False,
            "matches": [],
            "score": 0.0,
            "queries": 0,
            "message": "Web search o'chirilgan. .env da GOOGLE_API_KEY ni to'ldiring.",
        }

    try:
        import httpx
    except ImportError:
        return {"enabled": False, "found": False, "matches": [], "score": 0.0,
                "queries": 0, "message": "pip install httpx"}

    sentences = _split_key_sentences(text, max_queries)
    if not sentences:
        return {"enabled": True, "found": False, "matches": [], "score": 0.0, "queries": 0}

    matches = []
    queries_used = 0

    async with httpx.AsyncClient(timeout=15) as client:
        for sent in sentences:
            # Qisqa qidiruv query — exact match uchun qo'shtirnoq
            query = f'"{sent[:120]}"'
            queries_used += 1

            try:
                if GOOGLE_API_KEY and GOOGLE_CX:
                    # Google Custom Search API
                    resp = await client.get(
                        "https://www.googleapis.com/customsearch/v1",
                        params={
                            "key": GOOGLE_API_KEY,
                            "cx": GOOGLE_CX,
                            "q": query,
                            "num": 3,
                            "lr": f"lang_{lang}" if lang != "uz" else "",
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for item in data.get("items", []):
                            matches.append({
                                "title": item.get("title", ""),
                                "url": item.get("link", ""),
                                "snippet": item.get("snippet", ""),
                                "query_sentence": sent,
                            })

                elif SERP_API_KEY:
                    # SerpAPI (alternativ)
                    resp = await client.get(
                        "https://serpapi.com/search.json",
                        params={
                            "api_key": SERP_API_KEY,
                            "engine": "google",
                            "q": query,
                            "num": 3,
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for item in data.get("organic_results", []):
                            matches.append({
                                "title": item.get("title", ""),
                                "url": item.get("link", ""),
                                "snippet": item.get("snippet", ""),
                                "query_sentence": sent,
                            })

            except Exception as e:
                log.debug(f"Web search xato: {e}")
                continue

            # Rate limit
            await asyncio.sleep(0.3)

    # Natija hisoblash
    found = len(matches) > 0
    # Score: nechta jumla internetda topildi
    matched_sents = len(set(m["query_sentence"] for m in matches))
    score = round(matched_sents / max(len(sentences), 1) * 100, 1)

    return {
        "enabled": True,
        "found": found,
        "matches": matches[:10],
        "score": score,
        "queries": queries_used,
        "matched_sentences": matched_sents,
        "total_sentences": len(sentences),
    }


async def web_fetch_compare(
    url: str,
    original_text: str,
    lang: str = "en",
) -> dict:
    """
    URL dagi sahifani yuklash va original matn bilan solishtirish.
    Turnitin kabi: topilgan manbani batafsil tahlil qilish.
    """
    try:
        import httpx
    except ImportError:
        return {"error": "pip install httpx"}

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "AntiplagiatPRO/2.0 (academic research)"
            })
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}

            html = resp.text
            # HTML dan matn ajratish (oddiy)
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.S)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.S)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()

            if len(text) < 50:
                return {"error": "Sahifada matn topilmadi"}

            # Oddiy o'xshashlik hisoblash (Jaccard on words)
            orig_words = set(original_text.lower().split())
            page_words = set(text.lower().split())

            if not orig_words or not page_words:
                return {"similarity": 0.0, "text_length": len(text)}

            intersection = len(orig_words & page_words)
            union = len(orig_words | page_words)
            similarity = round(intersection / max(union, 1) * 100, 1)

            return {
                "similarity": similarity,
                "text_length": len(text.split()),
                "url": url,
                "matched_words": intersection,
            }

    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
#  SERVER.PY INTEGRATSIYA
# ═══════════════════════════════════════════════════════════════════════════════

async def enhance_analysis_with_web(
    text: str,
    lang: str,
    existing_result: dict,
) -> dict:
    """
    Mavjud plagiat/AI natijasini web qidiruv bilan kuchaytirish.

    server.py dan chaqiriladi:
      result = await run_analysis(text, corpus)
      result = await enhance_analysis_with_web(text, lang, result)
    """
    if not WEB_SEARCH_ENABLED and not SERP_API_KEY:
        existing_result["web_search"] = {"enabled": False}
        return existing_result

    try:
        web_result = await web_search_check(text, lang)
        existing_result["web_search"] = web_result

        # Web natijasi plagiat balliga ta'sir qiladi
        if web_result.get("found") and web_result.get("score", 0) > 30:
            # Internetda topildi — plagiat ehtimolini oshirish
            web_boost = min(20, web_result["score"] * 0.3)
            old_plag = existing_result.get("overall_plagiarism", 0)
            existing_result["overall_plagiarism"] = round(
                min(100, old_plag + web_boost), 1
            )

            # Topilgan manbalarni matches ga qo'shish
            for m in web_result.get("matches", [])[:3]:
                existing_result.setdefault("matches", []).append({
                    "document": m.get("title", "Web source"),
                    "source": "internet",
                    "url": m.get("url", ""),
                    "combined_score": round(web_result["score"], 1),
                })

    except Exception as e:
        log.error(f"Web search integration xato: {e}")
        existing_result["web_search"] = {"enabled": True, "error": str(e)}

    return existing_result
