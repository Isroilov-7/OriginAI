#!/usr/bin/env python3
"""
AntiplagiatPRO — Dataset Collector
=====================================
Bu skript internet orqali ilmiy hujjatlar yig'adi va
dataset/data/ papkasiga saqlaydi.

Manba:
  - arXiv.org   (bepul, ingliz tilida, 2M+ maqola)
  - PubMed      (bepul, tibbiyot, 35M+ maqola)
  - Semantic Scholar (bepul API, 200M+ hujjat)

O'rnatish:
  pip install requests tqdm

Ishlatish:
  python collector.py --target 1000   # 1000 ta hujjat
  python collector.py --target 5000   # 5000 ta hujjat (30-60 daqiqa)
  python collector.py --lang uz       # faqat o'zbek
  python collector.py --resume        # to'xtatilgandan davom etish
"""

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path

# ── SOZLAMALAR ────────────────────────────────────────────
DATA_DIR    = Path(__file__).parent / "data"
DELAY       = 0.5   # So'rovlar orasidagi kutish (sekund)
MAX_RETRIES = 3

TOPICS = [
    # Akademik mavzular — ko'p plagiat qilinadi
    "plagiarism academic integrity",
    "research methodology education",
    "digital economy innovation",
    "machine learning artificial intelligence",
    "climate change environmental policy",
    "public health medicine",
    "economics finance development",
    "history culture society",
    "literature linguistics language",
    "physics mathematics engineering",
]

# ── YORDAMCHI FUNKSIYALAR ─────────────────────────────────

def safe_get(url: str, params: dict = None, timeout: int = 15):
    """HTTP GET so'rov, xato bo'lsa qayta urinadi."""
    try:
        import requests
    except ImportError:
        raise SystemExit("pip install requests tqdm  qatorini ishga tushiring")

    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, params=params, timeout=timeout,
                             headers={"User-Agent": "AntiplagiatPRO/1.0 (research)"})
            if r.status_code == 200:
                return r
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 30))
                print(f"  Rate limit — {wait}s kutilmoqda...")
                time.sleep(wait)
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(5 * (attempt + 1))
    return None


def doc_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:12]


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def save_doc(lang: str, title: str, text: str,
             source: str, url: str = "", doi: str = "") -> bool:
    """Hujjatni JSON sifatida saqlash. Qayta saqlashni oldini oladi."""
    if not title or not text or len(text.split()) < 20:  # server MIN_WORDS=20 bilan uyg'un
        return False

    did   = doc_id(text[:200])
    path  = DATA_DIR / lang / f"{did}.json"

    if path.exists():
        return False   # Allaqachon bor

    doc = {
        "id":     did,
        "title":  title[:200],
        "source": source,
        "url":    url,
        "doi":    doi,
        "lang":   lang,
        "text":   text[:5000],   # Maksimal 5000 so'z
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return True


def count_docs() -> dict:
    counts = {}
    for lang in ("uz", "ru", "en"):
        d = DATA_DIR / lang
        counts[lang] = len(list(d.glob("*.json"))) if d.exists() else 0
    counts["total"] = sum(counts.values())
    return counts


# ── ARXIV COLLECTOR (ingliz tili) ────────────────────────

def collect_arxiv(topic: str, max_per_topic: int = 50) -> int:
    """arXiv.org dan maqolalar yig'ish."""
    import xml.etree.ElementTree as ET

    url    = "http://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{topic}",
        "max_results":  max_per_topic,
        "sortBy":       "relevance",
    }
    r = safe_get(url, params)
    if not r:
        return 0

    saved = 0
    try:
        ns  = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(r.text)
        for entry in root.findall("atom:entry", ns):
            title   = entry.findtext("atom:title", "", ns).strip()
            summary = entry.findtext("atom:summary", "", ns).strip()
            link_el = entry.find("atom:link[@title='pdf']", ns)
            url_val = link_el.get("href", "") if link_el is not None else ""

            text = clean(f"{title}. {summary}")
            if save_doc("en", title, text, "arxiv", url_val):
                saved += 1
    except Exception as e:
        print(f"  arXiv parse xato: {e}")

    time.sleep(DELAY)
    return saved


# ── PUBMED COLLECTOR (ingliz, tibbiyot) ──────────────────

def collect_pubmed(topic: str, max_per_topic: int = 50) -> int:
    """PubMed dan tibbiy va biologik maqolalar."""
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    # 1. ID listi
    r = safe_get(f"{base}/esearch.fcgi", {
        "db": "pubmed", "term": topic,
        "retmax": max_per_topic, "retmode": "json",
    })
    if not r:
        return 0

    try:
        ids = r.json()["esearchresult"]["idlist"]
    except Exception:
        return 0

    if not ids:
        return 0

    # 2. Abstrakt yuklab olish
    r2 = safe_get(f"{base}/efetch.fcgi", {
        "db": "pubmed", "id": ",".join(ids),
        "rettype": "abstract", "retmode": "text",
    })
    if not r2:
        return 0

    saved = 0
    # Har bir abstract alohida
    blocks = re.split(r"\n\n\d+\.", "\n\n" + r2.text)
    for block in blocks:
        lines  = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if len(lines) < 3:
            continue
        title  = lines[0]
        text   = clean(" ".join(lines[1:]))
        if save_doc("en", title, text, "pubmed"):
            saved += 1

    time.sleep(DELAY)
    return saved


# ── SEMANTIC SCHOLAR (ingliz va boshqa tillar) ───────────

def collect_semantic_scholar(topic: str, max_per_topic: int = 50) -> int:
    """Semantic Scholar API — ko'p tilli, bepul."""
    r = safe_get("https://api.semanticscholar.org/graph/v1/paper/search", {
        "query":  topic,
        "limit":  max_per_topic,
        "fields": "title,abstract,year,externalIds",
    })
    if not r:
        return 0

    saved = 0
    try:
        data = r.json()
        for paper in data.get("data", []):
            title    = paper.get("title", "") or ""
            abstract = paper.get("abstract", "") or ""
            doi      = (paper.get("externalIds") or {}).get("DOI", "")

            text = clean(f"{title}. {abstract}")
            if save_doc("en", title, text, "semantic_scholar",
                        doi=doi):
                saved += 1
    except Exception as e:
        print(f"  Semantic Scholar parse xato: {e}")

    time.sleep(DELAY)
    return saved


# ── CROSSREF (ingliz, o'zbek, rus) ───────────────────────

def collect_crossref(topic: str, max_per_topic: int = 30) -> int:
    """CrossRef API — DOI ma'lumotlar bazasi."""
    r = safe_get("https://api.crossref.org/works", {
        "query":      topic,
        "rows":       max_per_topic,
        "filter":     "has-abstract:true",
        "select":     "title,abstract,DOI,language",
    })
    if not r:
        return 0

    saved = 0
    try:
        for item in r.json().get("message", {}).get("items", []):
            title_list = item.get("title", [])
            title      = title_list[0] if title_list else ""
            abstract   = item.get("abstract", "") or ""
            doi        = item.get("DOI", "")
            lang_raw   = item.get("language", "en")
            lang       = lang_raw[:2].lower() if lang_raw else "en"
            if lang not in ("uz", "ru", "en"):
                lang = "en"

            abstract = re.sub(r"<[^>]+>", " ", abstract)
            text     = clean(f"{title}. {abstract}")
            url      = f"https://doi.org/{doi}" if doi else ""

            if save_doc(lang, title, text, "crossref", url, doi):
                saved += 1
    except Exception as e:
        print(f"  CrossRef parse xato: {e}")

    time.sleep(DELAY)
    return saved


# ── O'ZBEK VA RUS QO'SHIMCHA MANBALAR ────────────────────

UZ_MANUAL_TEXTS = [
    {
        "title":  "Ilmiy tadqiqot natijalari va ularni taqdim etish",
        "source": "manual_uz",
        "text": (
            "Ilmiy tadqiqot natijalari to'g'ri va aniq bayon etilishi zarur. "
            "Tadqiqotchi o'z xulosalarini dalillar asosida himoya qilishi kerak. "
            "Ilmiy maqola tuzilishi kirish, metodologiya, natijalar va muhokamadan iborat. "
            "Adabiyotlar ro'yxati barcha manbalarga havolalar o'z ichiga oladi. "
            "Ilmiy muloqot tengdoshlar o'rtasida bilim almashishni ta'minlaydi. "
            "Eksperimental ma'lumotlar statistik usullar bilan tahlil qilinadi."
        ),
    },
    {
        "title":  "Raqamli texnologiyalar va jamiyat rivojlanishi",
        "source": "manual_uz",
        "text": (
            "Zamonaviy jamiyat tez sur'atda raqamlashib bormoqda. "
            "Axborot-kommunikatsiya texnologiyalari hayotning barcha sohalarini qamrab olmoqda. "
            "Mobil ilovalar va dasturiy ta'minotlar inson hayotini yanada qulay qilmoqda. "
            "Kiberhavfsizlik masalasi raqamli asrning eng dolzarb muammolaridan biriga aylandi. "
            "Ma'lumotlarni himoya qilish va shaxsiy hayot daxlsizligi zamonaviy huquqning muhim qismidir. "
            "Raqamli savodxonlik barcha fuqarolar uchun zarur ko'nikma bo'lib qolmoqda."
        ),
    },
    {
        "title":  "Sog'liqni saqlash va profilaktik tibbiyot",
        "source": "manual_uz",
        "text": (
            "Sog'liqni saqlash sohasida profilaktik yondashuv tobora muhim ahamiyat kasb etmoqda. "
            "Kasalliklarni erta aniqlash va oldini olish davolashdan samaraliroq hisoblanadi. "
            "Sog'lom turmush tarzi yurak-qon tomir kasalliklarining oldini olishda muhim rol o'ynaydi. "
            "Tibbiy texnologiyalar tashxis qo'yish va davolash sifatini sezilarli oshiryapti. "
            "Telemedisin xizmatlar bemorlarning shifokorlarga murojaat qilishini osonlashtirmoqda. "
            "Aholining sog'liq ko'rsatkichlari mamlakatning ijtimoiy-iqtisodiy rivojlanish darajasini aks ettiradi."
        ),
    },
    {
        "title":  "Qishloq xo'jaligi va oziq-ovqat xavfsizligi",
        "source": "manual_uz",
        "text": (
            "Oziq-ovqat xavfsizligini ta'minlash global siyosatning ustuvor yo'nalishlaridan biridir. "
            "Qishloq xo'jaligida zamonaviy texnologiyalar hosildorlikni oshirishga imkon bermoqda. "
            "Iqlim o'zgarishi qishloq xo'jaligi ishlab chiqarishiga katta ta'sir ko'rsatmoqda. "
            "Organik dehqonchilik usullari atrof-muhitga zarar etkazmasdan mahsulot yetishtirishni ta'minlaydi. "
            "Suv resurslarini tejamkorlik bilan boshqarish qishloq xo'jaligida muhim vazifadir. "
            "Qishloq xo'jaligi innovatsiyalari kambag'allikni kamaytirish va rivojlanishni ta'minlashda hal qiluvchi rol o'ynaydi."
        ),
    },
    {
        "title":  "Huquq va adolat tizimi",
        "source": "manual_uz",
        "text": (
            "Qonun ustuvorligi demokratik jamiyatning asosiy tamoyili hisoblanadi. "
            "Sud mustaqilligi adolatli huquq tizimining kafolatidir. "
            "Fuqarolar huquqlari va erkinliklari konstitutsiya bilan himoya qilinadi. "
            "Korrupsiyaga qarshi kurash samarali davlet boshqaruvining muhim shartidir. "
            "Jinoyatchilikka qarshi kurashda profilaktik chora-tadbirlar muhim ahamiyat kasb etadi. "
            "Xalqaro huquq normlari davlatlar o'rtasidagi munosabatlarni tartibga soladi."
        ),
    },
]

RU_MANUAL_TEXTS = [
    {
        "title":  "Экономическое развитие и инновации",
        "source": "manual_ru",
        "text": (
            "Инновационное развитие является ключевым фактором экономического роста в современном мире. "
            "Инвестиции в исследования и разработки определяют конкурентоспособность национальных экономик. "
            "Технологические стартапы создают новые рабочие места и стимулируют экономический рост. "
            "Цифровая трансформация промышленности повышает производительность труда и эффективность. "
            "Государственно-частное партнёрство способствует реализации масштабных инновационных проектов. "
            "Развитие человеческого капитала является основой устойчивого экономического роста."
        ),
    },
    {
        "title":  "Здравоохранение и медицинские технологии",
        "source": "manual_ru",
        "text": (
            "Современная медицина переживает революцию благодаря технологическим инновациям. "
            "Персонализированная медицина адаптирует лечение к индивидуальным особенностям пациента. "
            "Телемедицина расширяет доступ к медицинской помощи в отдалённых районах. "
            "Искусственный интеллект помогает врачам точнее диагностировать заболевания. "
            "Биотехнологии открывают новые возможности для создания эффективных лекарств. "
            "Профилактическая медицина снижает нагрузку на систему здравоохранения."
        ),
    },
    {
        "title":  "Социальные науки и общество",
        "source": "manual_ru",
        "text": (
            "Социология изучает закономерности функционирования и развития общества. "
            "Социальное неравенство остаётся одной из ключевых проблем современного общества. "
            "Глобализация меняет культурные и социальные нормы по всему миру. "
            "Гражданское общество играет важную роль в развитии демократических институтов. "
            "Социальные движения оказывают значительное влияние на политические изменения. "
            "Демографические тенденции определяют будущее развитие государств и регионов."
        ),
    },
]


def add_manual_docs(lang: str, docs: list) -> int:
    saved = 0
    for doc in docs:
        if save_doc(lang, doc["title"], doc["text"], doc["source"]):
            saved += 1
    return saved


# ── ASOSIY FUNKSIYA ───────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AntiplagiatPRO Dataset Collector")
    parser.add_argument("--target",  type=int, default=500,  help="Nechta hujjat yig'ish")
    parser.add_argument("--lang",    default="all",           help="uz|ru|en|all")
    parser.add_argument("--resume",  action="store_true",     help="Davom etish")
    parser.add_argument("--manual",  action="store_true",     help="Faqat manual hujjatlar")
    args = parser.parse_args()

    # Papkalar yaratish
    for lang in ("uz", "ru", "en"):
        (DATA_DIR / lang).mkdir(parents=True, exist_ok=True)

    print("=" * 55)
    print("AntiplagiatPRO — Dataset Collector")
    print("=" * 55)

    counts = count_docs()
    print(f"\nHozirgi holat: {counts['total']} ta hujjat")
    for lang in ("uz", "ru", "en"):
        print(f"  {lang.upper()}: {counts[lang]} ta")

    if args.manual:
        print("\nManual hujjatlar qo'shilmoqda...")
        saved_uz = add_manual_docs("uz", UZ_MANUAL_TEXTS)
        saved_ru = add_manual_docs("ru", RU_MANUAL_TEXTS)
        print(f"  UZ: +{saved_uz}  RU: +{saved_ru}")
        counts = count_docs()
        print(f"\nYakuniy: {counts['total']} ta hujjat")
        return

    # Birinchi manual hujjatlarni qo'shamiz
    print("\n[1/4] Manual hujjatlar...")
    s1 = add_manual_docs("uz", UZ_MANUAL_TEXTS)
    s2 = add_manual_docs("ru", RU_MANUAL_TEXTS)
    print(f"  +{s1+s2} ta (UZ:{s1}, RU:{s2})")

    target    = args.target
    collected = count_docs()["total"]
    remaining = max(0, target - collected)
    per_topic = max(10, remaining // max(len(TOPICS), 1))

    print(f"\n[2/4] arXiv.org ({per_topic} maqola/mavzu)...")
    try:
        from tqdm import tqdm
        topic_iter = tqdm(TOPICS, desc="arXiv")
    except ImportError:
        topic_iter = TOPICS

    for topic in topic_iter:
        if count_docs()["total"] >= target:
            break
        n = collect_arxiv(topic, per_topic)
        if not isinstance(topic_iter, list):
            pass
        else:
            print(f"  '{topic[:30]}': +{n}")

    print(f"\n[3/4] PubMed ({per_topic//2} maqola/mavzu)...")
    for topic in TOPICS[:5]:
        if count_docs()["total"] >= target:
            break
        n = collect_pubmed(topic, per_topic // 2)
        print(f"  '{topic[:30]}': +{n}")

    print(f"\n[4/4] Semantic Scholar ({per_topic//2} maqola/mavzu)...")
    for topic in TOPICS[5:]:
        if count_docs()["total"] >= target:
            break
        n = collect_semantic_scholar(topic, per_topic // 2)
        print(f"  '{topic[:30]}': +{n}")

    # Yakuniy statistika
    final = count_docs()
    print(f"\n{'='*55}")
    print(f"YAKUNIY: {final['total']} ta hujjat")
    for lang in ("uz", "ru", "en"):
        print(f"  {lang.upper()}: {final[lang]} ta")
    print("="*55)
    print("\nKeyingi qadam: python server.py  →  http://localhost:8000")


if __name__ == "__main__":
    main()
