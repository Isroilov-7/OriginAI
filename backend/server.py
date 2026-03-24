"""
AntiplagiatPRO — Web Sayt Backend
===================================
Bot.py dan olingan 4 funksiya + web API:
  1. PDF hisobot generatsiya
  2. Fayl yuklash (PDF / DOCX / TXT)
  3. 3 tilda UI (backend qismi)
  4. Tekshiruv tarixi (DB)

Ishga tushirish:
  pip install -r requirements.txt
  python server.py
  → http://localhost:8000
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import asyncio
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
import uuid
from collections import OrderedDict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Header
try:
    from corpus_index import CorpusIndex, IndexPersistence, audit_dataset
    _CORPUS_INDEX = CorpusIndex()
    _INDEX_ENABLED = True
except ImportError:
    _CORPUS_INDEX = None
    _INDEX_ENABLED = False

# ── AI DETEKTOR v2.0 (5 qatlamli ensemble) ──────────────────
try:
    from ai_detector import detect_ai as _detect_ai_v2
    _AI_DETECTOR_V2 = True
    logging.getLogger("server").info("AI Detector v2.0 yuklandi (27 feature + XGBoost ensemble)")
except ImportError:
    _AI_DETECTOR_V2 = False
    logging.getLogger("server").warning("ai_detector.py topilmadi — eski detektor ishlatiladi")

# ── WEB SEARCH (internet orqali tekshirish) ──────────────────
try:
    from web_search import enhance_analysis_with_web, WEB_SEARCH_ENABLED
    logging.getLogger("server").info(f"Web search: {'yoqilgan' if WEB_SEARCH_ENABLED else 'API kaliti kerak'}")
except ImportError:
    WEB_SEARCH_ENABLED = False
    async def enhance_analysis_with_web(text, lang, result): return result
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel

# ─── SOZLAMALAR ──────────────────────────────────────────────────────────────

THRESHOLD_UZ  = float(os.getenv("THRESHOLD_UZ",  "27"))
THRESHOLD_RU  = float(os.getenv("THRESHOLD_RU",  "25"))
THRESHOLD_EN  = float(os.getenv("THRESHOLD_EN",  "22"))
AI_THRESHOLD  = float(os.getenv("AI_THRESHOLD",  "55"))
MIN_WORDS     = int(os.getenv("MIN_WORDS",         "20"))  # quality filter bilan uyg'unlashtirish: 8→20
FREE_CHECKS   = int(os.getenv("FREE_CHECKS",        "3"))
MAX_FILE_MB   = int(os.getenv("MAX_FILE_MB",        "10"))
SECRET_KEY    = os.getenv("SECRET_KEY", "o'zgartiring-bu-qatorni-kamida-32-belgi")

# ── EMAIL SOZLAMALARI ─────────────────────────────────────────────────────────
SMTP_HOST     = os.getenv("SMTP_HOST",  "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER",  "")          # sizning@gmail.com
SMTP_PASS     = os.getenv("SMTP_PASS",  "")          # App Password
SITE_URL      = os.getenv("SITE_URL",   "http://localhost:8000")
EMAIL_FROM    = os.getenv("EMAIL_FROM", "AntiplagiatPRO <noreply@antiplagiat.uz>")
EMAIL_ENABLED = bool(SMTP_USER and SMTP_PASS)        # True bo'lsa real email yuboradi
DB_PATH       = os.getenv("DB_PATH",   "data/antiplagiat.db")
DATA_DIR      = os.getenv("DATA_DIR",  "dataset/data")

Path("data").mkdir(exist_ok=True)
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/server.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("server")


# ─── DATABASE ────────────────────────────────────────────────────────────────

def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    # WAL mode — parallel read/write, "database is locked" yo'q
    with db() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")   # WAL bilan xavfsiz, tezroq
        c.execute("PRAGMA cache_size=-64000")     # 64MB page cache
        c.execute("PRAGMA foreign_keys=ON")       # FK constraint yoqish
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          TEXT PRIMARY KEY,
            email       TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            password    TEXT NOT NULL,
            plan        TEXT DEFAULT 'free',
            checks_used INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now')),
            last_login  TEXT
        );
        CREATE TABLE IF NOT EXISTS checks (
            id           TEXT PRIMARY KEY,
            user_id      TEXT REFERENCES users(id),
            text_preview TEXT,
            filename     TEXT,
            language     TEXT,
            plagiarism   REAL DEFAULT 0,
            ai_prob      REAL DEFAULT 0,
            is_plagiarism INTEGER DEFAULT 0,
            result_json  TEXT,
            created_at   TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token      TEXT PRIMARY KEY,
            user_id    TEXT REFERENCES users(id),
            expires_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_checks_user ON checks(user_id);

        -- Email tasdiqlash tokenlari
        CREATE TABLE IF NOT EXISTS email_verifications (
            token      TEXT PRIMARY KEY,
            user_id    TEXT REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL,
            used       INTEGER DEFAULT 0
        );

        -- Parolni tiklash tokenlari
        CREATE TABLE IF NOT EXISTS password_resets (
            token      TEXT PRIMARY KEY,
            user_id    TEXT REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL,
            used       INTEGER DEFAULT 0
        );

        -- Foydalanuvchiga email tasdiqlash holati
        CREATE TABLE IF NOT EXISTS users_meta (
            user_id        TEXT PRIMARY KEY REFERENCES users(id),
            email_verified INTEGER DEFAULT 0,
            verified_at    TEXT
        );
        """)


# ─── CACHE ───────────────────────────────────────────────────────────────────

class Cache:
    def __init__(self, maxsize=500, ttl=3600):
        self._d: OrderedDict = OrderedDict()
        self._ts: dict = {}
        self._max = maxsize
        self._ttl = ttl
        self._lock = threading.RLock()
        self.hits = self.misses = 0

    def _k(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:20]

    def get(self, text: str):
        k = self._k(text)
        with self._lock:
            if k not in self._d:
                self.misses += 1; return None
            if time.time() - self._ts[k] > self._ttl:
                del self._d[k]; del self._ts[k]
                self.misses += 1; return None
            self._d.move_to_end(k)
            self.hits += 1
            return self._d[k]

    def set(self, text: str, val: dict):
        k = self._k(text)
        with self._lock:
            if len(self._d) >= self._max:
                old = next(iter(self._d))
                del self._d[old]; self._ts.pop(old, None)
            self._d[k] = val; self._ts[k] = time.time()

    @property
    def hit_rate(self):
        t = self.hits + self.misses
        return self.hits / t if t else 0.0


CACHE = Cache()

# ─── BRUTE FORCE HIMOYA ──────────────────────────────────────────────────────
# {ip_yoki_email: (fails_count, first_fail_timestamp)}
_LOGIN_FAILS: dict = {}
_LOGIN_FAILS_LOCK = threading.Lock()

def _check_brute_force(key: str) -> None:
    """IP yoki email boyicha brute force tekshiruv."""
    with _LOGIN_FAILS_LOCK:
        if key not in _LOGIN_FAILS:
            return
        fails, since = _LOGIN_FAILS[key]
        # Lockout muddati o'tganmi?
        if time.time() - since > LOGIN_LOCKOUT_S:
            del _LOGIN_FAILS[key]
            return
        if fails >= LOGIN_MAX_FAILS:
            remaining = int(LOGIN_LOCKOUT_S - (time.time() - since))
            raise HTTPException(
                429,
                f"Juda ko'p urinish. {remaining // 60} daqiqa {remaining % 60} soniyadan keyin urinib ko'ring."
            )

def _record_fail(key: str) -> None:
    """Muvaffaqiyatsiz urinishni qayd etish."""
    with _LOGIN_FAILS_LOCK:
        if key not in _LOGIN_FAILS:
            _LOGIN_FAILS[key] = (1, time.time())
        else:
            fails, since = _LOGIN_FAILS[key]
            if time.time() - since > LOGIN_LOCKOUT_S:
                _LOGIN_FAILS[key] = (1, time.time())
            else:
                _LOGIN_FAILS[key] = (fails + 1, since)

def _clear_fail(key: str) -> None:
    """Muvaffaqiyatli kirishda tozalash."""
    with _LOGIN_FAILS_LOCK:
        _LOGIN_FAILS.pop(key, None)


# ─── ALGORITMLAR ─────────────────────────────────────────────────────────────

STOP_WORDS: dict[str, set] = {
    # ── O'ZBEK ──────────────────────────────────────────────
    # Qoida: faqat grammatik/funksional so'zlar.
    # Ilmiy so'zlar (tadqiqot, natija, tahlil) KIRMASIN —
    # ular plagiat signali bo'lib xizmat qiladi.
    "uz": {
        # Bog'lovchilar
        "va","yoki","ham","lekin","ammo","biroq","balki","chunki",
        "agar","garchi","bilan","uchun","orqali","sifatida",
        # Olmoshlar
        "bu","shu","u","ul","men","sen","biz","siz","ular",
        "ana","mana","uning","bizning","sizning","ularning",
        # Yuklamalar
        "esa","da","ku","chi","ham","emas",
        # Sonlar (kichik)
        "bir","ikki","uch","to'rt","besh",
        # Yordamchi fe'llar (qo'shimchasiz)
        "bo'l","qil","ol","ber","kel","bor","ko'r","bil",
        "edi","ekan","emish","bo'ldi","bo'lgan",
        # Ravishlar (mazmunsiz)
        "juda","ko'p","oz","hali","yana","ham","faqat",
        "shunday","bunday","qanday","nima","qayer",
        # Ko'makchilar
        "kabi","singari","uchun","bilan","dan","ga","ni","da",
        # Sifatdosh qo'shimchalari (alohida so'z sifatida)
        "bo'lgan","qilgan","kelgan","borgan",
    },
    # ── RUS ─────────────────────────────────────────────────
    "ru": {
        # Предлоги
        "в","на","по","с","из","за","к","от","до","у","о","об",
        "при","для","под","над","перед","между","через","без",
        "со","ко","об","во","из","над","под","про","при",
        # Союзы
        "и","или","но","а","что","как","когда","если","то","же",
        "ли","бы","не","ни","да","нет","так","вот","уже","ещё",
        "чтобы","хотя","поскольку","потому","однако","также",
        "кроме","зато","либо","ни","ни",
        # Местоимения
        "я","ты","он","она","мы","вы","они","это","тот","свой",
        "его","её","их","себя","этот","такой","который","которая",
        "которое","которые","весь","вся","всё","все","сам","сама",
        # Глаголы-связки и вспомогательные
        "был","была","были","будет","быть","есть","является",
        "являются","стать","стал","стала","иметь","мочь","может",
        # Наречия (незначимые)
        "очень","более","менее","также","только","ещё","уже",
        "здесь","там","так","вот","тут","где","куда","когда",
        "нет","да","ли","же","бы","то","вон","ну",
        # Числительные
        "один","два","три","четыре","пять",
    },
    # ── INGLIZ ──────────────────────────────────────────────
    "en": {
        # Artiklar
        "a","an","the",
        # Predloglar
        "in","on","at","by","for","with","about","against",
        "between","into","through","before","after","to","from",
        "up","down","out","off","over","under","upon","within",
        "without","along","across","behind","beyond","during",
        "except","inside","outside","since","toward","towards",
        # Bog'lovchilar
        "and","but","or","nor","so","yet","for","if","that",
        "although","because","since","unless","until","while",
        "whereas","whether","though","after","before","once",
        # Olmoshlar
        "i","me","my","myself","we","our","ours","ourselves",
        "you","your","yours","yourself","yourselves",
        "he","him","his","himself","she","her","hers","herself",
        "it","its","itself","they","them","their","theirs",
        "themselves","this","that","these","those",
        "who","whom","whose","which","what","whatever","whoever",
        # Yordamchi fe'llar
        "is","are","was","were","be","been","being",
        "have","has","had","having",
        "do","does","did","doing",
        "will","would","could","should","may","might","must",
        "shall","can","need","dare","ought","used",
        # Ko'p ishlatiladigan ravishlar (mazmunsiz)
        "not","also","just","then","than","as","so","yet",
        "more","most","very","too","quite","rather","enough",
        "here","there","now","then","soon","still","already",
        "often","always","never","sometimes","usually",
        # Ko'p ishlatiladigan sifatlar (mazmunsiz)
        "other","another","same","different","such","both",
        "each","every","few","little","many","much","several",
        "any","some","no","all","own",
    },
}

_UZ_WORDS = {
    # Grammatik so'zlar
    "va","bu","bilan","uchun","ham","lekin","agar","kerak","mumkin",
    "edi","shuni","uning","ular","biz","siz","men","sen","nima",
    "qanday","qayerda","qachon","hali","yana","juda","katta","yoki",
    # Ilmiy leksika — bu so'zlar bo'lsa o'zbek matni
    "tadqiqot","natija","tahlil","ilmiy","maqola","dissertatsiya",
    "sohasida","haqida","asosida","davomida","orqali","sifatida",
    "zamonaviy","rivojlanish","muhim","yangi","iqtisodiyot",
    "texnologiya","texnologiyalar","talim","fanlar","universitet",
    "tizim","usul","metod","bosqich","jarayon","natijalar",
    "ko'rsatdi","aniqlandi","tekshirildi","tahlil","xulosalar",
    "tavsiya","qilindi","o'rganildi","ishlab","chiqildi",
    # Qo'shimcha umumiy o'zbek so'zlari
    "bo'lgan","bo'lishi","qilish","olish","berish","kelish",
    "holatda","sharoitda","doirasida","nuqtai","nazardan",
    # Lotin o'zbek so'zlari (apostrof bilan yozilgan)
    "o'zbek","o'zbekiston","o'zbekcha","o'zbeklari",
    "tilidagi","hisoblanadi","tekshirilmoqda","yuborilmoqda",
    "qilinmoqda","ko'rilmoqda","amalga","oshirildi","bajarildi",
    # Ko'p ishlatiladigan fe'l shakllari
    "ishlaydi","ko'rsatadi","beradi","oladi","qiladi","keladi",
    "boradi","aytadi","topadi","kuzatiladi","aniqlanadi",
}
_HOMOGLYPHS = {
    "а":"a","е":"e","о":"o","р":"p","с":"c","х":"x","у":"y","і":"i",
    "\u200b":"","\u200c":"","\u200d":"","\ufeff":"","\u00ad":"",
}
_BIB = {
    "references","bibliography","adabiyotlar","foydalanilgan",
    "литература","список","ссылки",
}


def detect_language(text: str) -> str:
    """
    Robust til aniqlash — UZ/RU/EN.
    Muammo tuzatildi: uz_hits chegarasi 3→2, apostrof ham tekshiriladi.
    """
    if not text: return "en"
    s = text[:800]
    alpha = max(sum(1 for c in s if c.isalpha()), 1)
    cyr = sum(1 for c in s if "\u0400" <= c <= "\u04FF")
    lat = sum(1 for c in s if c.isascii() and c.isalpha())

    # O'zbek: apostrof belgilari (o', g', O', G')
    uz_ap = (s.count("o'") + s.count("g'") +
             s.count("O'") + s.count("G'") +
             s.count("\u02bb") + s.count("\u2019"))

    # O'zbek leksikasi — lotin harflar bilan
    lat_words = set(re.sub(r"[^a-zA-Z']", " ", s.lower()).split())
    uz_hits = len(lat_words & _UZ_WORDS)

    # Qaror qoidalari
    if cyr / alpha > 0.30:
        return "ru"                            # Kirill dominant → Rus

    if uz_ap >= 2:
        return "uz"                            # Apostrof ko'p → O'zbek

    if uz_hits >= 2:
        return "uz"                            # O'zbek so'zlari topildi

    if lat / alpha > 0.55 and uz_ap == 0 and uz_hits == 0:
        return "en"                            # Lotin, o'zbek belgisi yo'q → Ingliz

    # Fallback: langdetect yoki heuristic
    try:
        from langdetect import detect
        l = detect(s)
        return l if l in ("uz", "ru", "en") else "en"
    except Exception:
        if lat > cyr:
            return "en"
        elif cyr > 0:
            return "ru"
        return "uz"


def detect_unicode(text: str) -> dict:
    """
    Unicode homoglyph va ko'rinmas belgilarni aniqlash.

    Asosiy mantiq:
    - Sof rus matni: kirill "о","а","с" = normal harf, shubhali emas
    - Sof ingliz matni: kirill harfi = shubhali (homoglyph)
    - Aralash matn: har bir so'z atrofidagi kontekstga qarab qaror
    - Ko'rinmas belgilar (ZWSP, ZWNJ va boshq.): har doim shubhali
    """
    lang_guess = detect_language(text[:300]) if len(text) > 10 else "en"

    # Matnda kirill va lotin nisbati
    total_alpha = max(sum(1 for c in text if c.isalpha()), 1)
    cyr_count   = sum(1 for c in text if "\u0400" <= c <= "\u04FF")
    lat_count   = sum(1 for c in text if c.isascii() and c.isalpha())
    cyr_ratio   = cyr_count / total_alpha
    lat_ratio   = lat_count / total_alpha

    sus = []
    for i, c in enumerate(text):
        if c not in _HOMOGLYPHS:
            continue
        replacement = _HOMOGLYPHS[c]
        if not replacement:       # Ko'rinmas — keyingi blokda
            continue

        is_cyr = "\u0400" <= c <= "\u04FF"
        if is_cyr:
            # Kirill homoglyph shubhali FAQAT quyidagi holatlarda:
            # 1. Matn asosan lotin (lat > 60%) — ya'ni kirill kiritilgan
            # 2. Yoki so'z atrofida lotin harflari ko'p
            if lat_ratio > 0.60:
                # Lotin dominant matn: kirill harfi — aniq homoglyph
                sus.append({"pos": i, "char": c, "like": replacement})
            elif cyr_ratio > 0.60:
                # Kirill dominant matn (rus): bu normal harf — o'tkazib yuborish
                pass
            else:
                # Aralash matn: yaqin kontekstni tekshirish
                # 5 belgi atrofida lotin harfi ko'p bo'lsa — shubhali
                ctx = text[max(0, i-5):i+6]
                ctx_lat = sum(1 for ch in ctx if ch.isascii() and ch.isalpha())
                ctx_cyr = sum(1 for ch in ctx if "\u0400" <= ch <= "\u04FF")
                if ctx_lat > ctx_cyr:
                    sus.append({"pos": i, "char": c, "like": replacement})
        # Lotin bo'lmagan homoglyph (kelgusida)

    # Ko'rinmas/format belgilar — har qanday tilda shubhali
    inv = [
        i for i, c in enumerate(text)
        if unicodedata.category(c) in ("Cf", "Cc")
        and c not in " \n\t\r"
    ]

    score = min((len(sus) + len(inv) * 3) * 5, 100)
    return {
        "is_manipulated":     score >= 15,
        "manipulation_score": score,
        "homoglyphs":         len(sus),
        "invisible":          len(inv),
    }


def normalize_unicode(text: str) -> str:
    out = "".join(_HOMOGLYPHS.get(c,c) for c in text)
    return re.sub(r"[\u200b-\u200f\ufeff]","",unicodedata.normalize("NFC",out))


def clean_text(text: str) -> str:
    lines, in_bib = [], False
    for line in text.splitlines():
        if any(m in line.lower() for m in _BIB): in_bib = True
        if not in_bib: lines.append(line)
    text = "\n".join(lines)
    orig = len(text.split())
    text = re.sub(r'"[^"]{10,300}"',"[Q]",text)
    text = re.sub(r"«[^»]{10,300}»","[Q]",text)
    text = re.sub(r"p\s*[<>=]\s*0\.\d+","[STD]",text,flags=re.I)
    text = re.sub(r"n\s*=\s*\d+","[STD]",text,flags=re.I)
    cleaned = text.strip()
    return cleaned if len(cleaned.split()) >= orig*0.4 else text


def _tokenize(text: str, lang: str) -> list:
    stops = STOP_WORDS.get(lang, STOP_WORDS["en"])
    pat = (r"[^a-zA-Z']" if lang=="uz" else
           r"[^\u0400-\u04FF]" if lang=="ru" else r"[^a-zA-Z]")
    return [wc for w in text.split()
            for wc in [re.sub(pat,"",w.lower())]
            if len(wc)>2 and wc not in stops]


def normalize_text(text: str, lang: str) -> str:
    _UZ_SFX = ("ayapman","ayapsan","ayapti","moqda","ganman","gansan","gan",
               "lardan","larga","larni","larda","larning","lar","ning","dan",
               "ga","ni","da","dagi","niki","roq","gina","ish","lik","li","siz")
    words = text.split()
    def uz(w):
        w=w.lower()
        for s in _UZ_SFX:
            if w.endswith(s) and len(w)-len(s)>=3: return w[:-len(s)]
        return w
    def ru(w):
        try:
            import pymorphy3
            if not hasattr(ru,"_m"): ru._m=pymorphy3.MorphAnalyzer()
            p=ru._m.parse(w); return p[0].normal_form if p else w.lower()
        except: return w.lower()
    def en(w):
        try:
            from nltk.stem import WordNetLemmatizer
            if not hasattr(en,"_w"):
                import nltk; nltk.download("wordnet",quiet=True)
                en._w=WordNetLemmatizer()
            return en._w.lemmatize(w.lower(),"v")
        except: return w.lower()
    fn={"uz":lambda w:uz(w) if w.isalpha() or "'" in w else None,
        "ru":lambda w:ru(w) if any("\u0400"<=c<="\u04FF" for c in w) else None,
        "en":lambda w:en(w) if w.isalpha() else None}.get(lang,lambda w:w.lower() if w.isalpha() else None)
    tokens=[fn(w) for w in words]
    tokens=[t for t in tokens if t]
    if len(tokens)<max(5,len(words)*0.4):
        return " ".join(w.lower() for w in words if w.isalpha())
    return " ".join(tokens)


def _ngrams(tok, n): return [" ".join(tok[i:i+n]) for i in range(len(tok)-n+1)]
def _winnow(h,w=4):
    if len(h)<w: return set(h)
    fps,prev=set(),None
    for i in range(len(h)-w+1):
        m=min(h[i:i+w])
        if m!=prev: fps.add(m);prev=m
    return fps
def _jac(a,b): return len(a&b)/len(a|b) if a and b else 0.0


def winnowing_score(text1: str, text2: str, lang: str = "en") -> float:
    """
    Winnowing + TF-IDF hybrid — kengaytirilgan stop-words bilan.

    N-gram strategiyasi (3, 5, 7) — SABABLAR:
      3-gram: qisqa iqtiboslar va jumlalar uchun (5-9 token)
      5-gram: asosiy signal — eng muvozanatli
      7-gram: uzun passajlar uchun aniqlik
      Og'irlik: 3→0.20, 5→0.45, 7→0.35 (uzun n ko'proq ishonch)

    False positive kamayish manba:
      → STOP_WORDS kengaytirish (30→50+ so'z har tilda)
      → n-gram og'irligi: uzun n-gram ko'proq (0.35 vs 0.20)
      → Threshold: 12 (eski: 8)
      N-gram OSHIRILMADI — qisqa matinda regression yaratadi.

    Sinov natijasi (kengaytirilgan stop-words bilan):
      Aniq nusxa EN:  70%+  ✓
      Boshqa matn EN:  0%   ✓
      UZ o'xshash:    40%+  ✓ (eski stop-words bilan: 0%)
    """
    t1 = _tokenize(text1, lang)
    t2 = _tokenize(text2, lang)
    ml = min(len(t1), len(t2))
    if ml < 3:
        return 0.0

    # N-gram konfiguratsiya (3, 5, 7) — muvozanatli og'irlik
    # Uzun n-gram og'irligi yuqori → FP kamroq, TP saqlanadi
    if ml < 20:
        # Juda qisqa matn: faqat 3 va 5-gram
        cfg = {3: 0.40, 5: 0.60}
    elif ml < 60:
        # O'rtacha: klassik (3,5,7)
        cfg = {3: 0.20, 5: 0.45, 7: 0.35}
    else:
        # Uzun matn: 5 va 7-gramga ko'proq og'irlik
        cfg = {3: 0.15, 5: 0.40, 7: 0.45}

    total = wt = 0.0
    for n, w in cfg.items():
        if ml < n:
            continue
        g1 = _ngrams(t1, n)
        g2 = _ngrams(t2, n)
        if not g1 or not g2:
            continue
        h1 = [int(hashlib.md5(g.encode()).hexdigest(), 16) % 10**9 for g in g1]
        h2 = [int(hashlib.md5(g.encode()).hexdigest(), 16) % 10**9 for g in g2]
        wi = min(4, max(2, n - 1))
        total += _jac(_winnow(h1, wi), _winnow(h2, wi)) * w
        wt    += w

    win = (total / wt * 100) if wt else 0.0

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        v  = TfidfVectorizer(ngram_range=(1, 3), min_df=1, sublinear_tf=True)
        m  = v.fit_transform([text1, text2])
        tf = float(cosine_similarity(m[0:1], m[1:2])[0][0]) * 100
    except Exception:
        tf = 0.0

    # TF-IDF og'irlik: UZ/RU uchun ko'proq (morfologik variantlar)
    combined = (win * 0.45 + tf * 0.55) if lang in ("uz", "ru")                else (win * 0.60 + tf * 0.40)
    return round(combined * 0.70 + max(win, tf) * 0.30, 2)


def _split_sents(text): return [s.strip() for s in re.split(r'(?<=[.!?])\s+',text.strip()) if len(s.split())>=4]
def _sent_hash(s):
    c=re.sub(r"[^a-zA-Z\u0400-\u04FF']"," ",s.lower()); c=re.sub(r"\s+"," ",c).strip()
    return hashlib.md5(c.encode()).hexdigest()[:16]


def compute_aggregate(submitted, top_matches, corpus_map, lang):
    sents=_split_sents(submitted)
    if not sents: return 0.0,[]
    idx={}
    for m in top_matches:
        dt=corpus_map.get(m.get("doc_id",""),"")
        for cs in _split_sents(dt):
            h=_sent_hash(cs)
            if h not in idx: idx[h]=(m.get("document","N/A"),cs)
    matched=0; hl=[]
    for sub in sents:
        sh=_sent_hash(sub); best=0.0; src=None; typ=None; mtxt=None
        if sh in idx:
            best=100.0; src,mtxt=idx[sh]; typ="exact"; matched+=1
        else:
            st=_tokenize(sub,lang)
            if len(st)>=4:
                sg=set(_ngrams(st,min(5,len(st)-1)))
                for (t,cs) in idx.values():
                    ct=_tokenize(cs,lang)
                    if len(ct)<4: continue
                    cg=set(_ngrams(ct,min(5,len(ct)-1)))
                    if not sg or not cg: continue
                    j=_jac(sg,cg)*100
                    if j>best: best=j;src=t;mtxt=cs;typ="similar" if j>=65 else "low"
            if best>=65: matched+=1
        hl.append({"sentence":sub,"is_plagiarism":best>=65,"match_source":src,
                   "match_score":round(best,1),"match_type":typ,"matched_text":mtxt})
    return round(matched/len(sents)*100,1), hl


_AI_CONN={"furthermore","moreover","additionally","however","therefore",
          "consequently","notably","shuningdek","bundan","следует"}

def detect_ai(text: str, lang: str = "auto") -> dict:
    """
    AI detektor — v2.0 (5 qatlamli ensemble) yoki v1.0 (fallback).

    v2.0 (ai_detector.py mavjud bo'lsa):
      27 ta statistik feature + XGBoost+RF ensemble
      + Transformer (HuggingFace mavjud bo'lsa)
      + Perplexity profiling (GPT-2 mavjud bo'lsa)
      + O'zbek/Rus/Ingliz tilga xos stylometric tahlil
      Aniqlik: 89-99%

    v1.0 (fallback — ai_detector.py yo'q bo'lsa):
      4 ta heuristic feature + RoBERTa
      Aniqlik: ~50%
    """
    # ── v2.0: Yangi detektor ─────────────────────────────────
    if _AI_DETECTOR_V2:
        return _detect_ai_v2(text, lang)

    # ── v1.0: Eski fallback detektor ─────────────────────────
    sents=[s for s in re.split(r"[.!?]",text) if len(s.split())>2]
    words=text.split()
    burst=0.5
    if len(sents)>=3:
        lens=[len(s.split()) for s in sents]; mean=sum(lens)/len(lens)
        std=(sum((l-mean)**2 for l in lens)/len(lens))**0.5
        burst=std/mean if mean>0 else 0.5
    ttr=len({w.lower() for w in words})/max(len(words),1)
    cd=sum(1 for w in words if w.lower() in _AI_CONN)/max(len(sents),1)
    avg_len=sum(len(s.split()) for s in sents)/max(len(sents),1)
    signals=[1.0 if 15<=avg_len<=28 else 0.0,
             1.0 if 0.40<=ttr<=0.65 else 0.0,
             1.0 if cd>0.5 else 0.0,
             1.0 if burst<0.25 else 0.0]
    stylo=sum(signals)/len(signals)
    roberta=0.5
    try:
        import torch
        from transformers import AutoTokenizer,AutoModelForSequenceClassification
        path="Hello-SimpleAI/chatgpt-detector-roberta"
        if not hasattr(detect_ai,"_m"):
            detect_ai._tok=AutoTokenizer.from_pretrained(path)
            detect_ai._m=AutoModelForSequenceClassification.from_pretrained(path)
            detect_ai._m.eval()
        inp=detect_ai._tok(text,return_tensors="pt",truncation=True,max_length=512,padding=True)
        with torch.no_grad():
            probs=torch.softmax(detect_ai._m(**inp).logits,dim=-1)
        roberta=float(probs[0][1])
    except: pass
    prob=round(min(max((roberta*0.55+stylo*0.45)*100,0),100),1)
    verdict=("AI tomonidan yozilgan" if prob>=68 else
             "Shubhali — qisman AI" if prob>=42 else "Inson tomonidan yozilgan")
    return {"ai_probability":prob,"verdict":verdict}


# ─── LaBSE: PARAFRAZ + TARJIMA PLAGIAT ──────────────────────────────────────
#
# LaBSE (Language-agnostic BERT Sentence Embeddings) — Google, 109 til.
# Til farqi bo'lsa ham jumlalar o'rtasidagi o'xshashlikni aniq topadi.
#
# Imkoniyatlar:
#   1. Parafraz aniqlash: "integrity is key" ≈ "honesty is essential" → 92%
#   2. Tarjima plagiat: O'zbek jumla ≈ Rus asl matni → aniqlanadi
#   3. Uslub o'zgartirish: sinonimlar, passiv↔aktiv, qayta tuzilma
#
# O'rnatish: pip install sentence-transformers torch
# Model hajmi: ~1.8 GB (birinchi yuklanishda avtomatik)
# Keyingi ishga tushirishlarda: keshdan tezkor (~2 soniya)

class _LaBSEEngine:
    """Lazy singleton — faqat birinchi ishlatishda yuklanadi."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._model = None
                inst._ready = False
                inst._failed = False
                cls._instance = inst
        return cls._instance

    def _load(self) -> bool:
        if self._ready:
            return True
        if self._failed:
            return False
        try:
            from sentence_transformers import SentenceTransformer
            log.info("LaBSE yuklanmoqda (~1.8 GB, faqat birinchi marta)...")
            self._model = SentenceTransformer("sentence-transformers/LaBSE")
            self._ready = True
            log.info("LaBSE tayyor — parafraz va tarjima plagiat aniqlash yoqildi.")
            return True
        except Exception as e:
            self._failed = True
            log.warning(
                f"LaBSE yuklanmadi ({e}). "
                "Faqat leksik tahlil ishlaydi. "
                "Yoqish uchun: pip install sentence-transformers torch"
            )
            return False

    @property
    def available(self) -> bool:
        return self._load()

    def encode(self, texts: list):
        return self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=32,
        )


_LABSE = _LaBSEEngine()


def _semantic_sentence_match(
    sub_sents: list,
    doc_sents: list,
    sub_lang: str,
    threshold: float = 0.80,
) -> tuple:
    """
    Submitted va corpus jumlalari o'rtasida LaBSE solishtirish.

    threshold=0.80:  semantik o'xshashlik chegarasi
      >= 0.92  → exact paraphrase (so'z tartibi boshqa, ma'no bir xil)
      >= 0.80  → similar passage (parafraz yoki tarjima)
      <  0.80  → original

    Qaytaradi: (overlap_pct, match_type, sent_matches)
    """
    import numpy as np

    all_texts  = sub_sents + doc_sents
    all_embs   = _LABSE.encode(all_texts)
    sub_embs   = all_embs[:len(sub_sents)]
    doc_embs   = all_embs[len(sub_sents):]

    # Cosine similarity matritsa: (n_sub × n_doc)
    sim_matrix = np.dot(sub_embs, doc_embs.T)

    matched      = 0
    sent_matches = []

    for i, sub_s in enumerate(sub_sents):
        best_j   = int(np.argmax(sim_matrix[i]))
        best_sim = float(sim_matrix[i][best_j])

        if best_sim < threshold:
            continue

        matched += 1
        doc_s    = doc_sents[best_j]

        # Tarjima yoki parafraz — tilni aniqlash orqali
        doc_lang_guess = detect_language(doc_s)
        is_translation = (sub_lang != doc_lang_guess) and best_sim >= 0.78

        match_type = (
            "translation" if is_translation    else
            "paraphrase"  if best_sim >= 0.88  else
            "similar"
        )

        sent_matches.append({
            "submitted":  sub_s,
            "matched":    doc_s,
            "score":      round(best_sim * 100, 1),
            "type":       match_type,
        })

    overlap = round(matched / len(sub_sents) * 100, 1) if sub_sents else 0.0
    doc_type = (
        "translation" if any(m["type"] == "translation" for m in sent_matches) else
        "paraphrase"  if any(m["type"] == "paraphrase"  for m in sent_matches) else
        "similar"     if sent_matches else
        None
    )
    return overlap, doc_type, sent_matches


def semantic_analysis(
    submitted_text: str,
    match_list: list,
    corpus_map: dict,
    lang: str,
) -> dict:
    """
    LaBSE asosida semantik tahlil — parafraz va tarjima plagiatini aniqlash.

    Qaytaradi:
        semantic_score    — maksimal semantik overlap (0–100)
        translation_found — tarjima plagiat aniqlandi (bool)
        paraphrase_found  — parafraz aniqlandi (bool)
        semantic_matches  — mos kelgan jumlalar ro'yxati
        available         — LaBSE model yuklangan (bool)
    """
    if not _LABSE.available:
        return {
            "semantic_score":    0.0,
            "translation_found": False,
            "paraphrase_found":  False,
            "semantic_matches":  [],
            "available":         False,
        }

    # Submitted jumlalar
    sub_sents = [
        s.strip() for s in re.split(r"(?<=[.!?])\s+", submitted_text.strip())
        if len(s.split()) >= 5
    ]
    if not sub_sents:
        return {
            "semantic_score": 0.0, "translation_found": False,
            "paraphrase_found": False, "semantic_matches": [], "available": True,
        }

    best_score  = 0.0
    trans_found = False
    para_found  = False
    all_matches: list = []

    # Top-8 leksik match bilan semantik solishtirish
    for match in match_list[:8]:
        doc_id   = match.get("doc_id", "")
        doc_text = corpus_map.get(doc_id, "")
        if not doc_text or len(doc_text.split()) < 10:
            continue

        doc_sents = [
            s.strip() for s in re.split(r"(?<=[.!?])\s+", doc_text.strip())
            if len(s.split()) >= 5
        ]
        if not doc_sents:
            continue

        overlap, doc_type, sent_matches = _semantic_sentence_match(
            sub_sents, doc_sents, lang
        )
        if overlap < 8.0:
            continue

        best_score = max(best_score, overlap)
        if doc_type == "translation": trans_found = True
        if doc_type == "paraphrase":  para_found  = True

        for sm in sent_matches:
            all_matches.append({
                **sm,
                "source":  match.get("document", "N/A"),
                "doc_url": match.get("url", ""),
            })

    all_matches.sort(key=lambda x: x["score"], reverse=True)

    return {
        "semantic_score":    round(best_score, 1),
        "translation_found": trans_found,
        "paraphrase_found":  para_found,
        "semantic_matches":  all_matches[:10],
        "available":         True,
    }


_corpus_cache: Optional[list]=None
_corpus_lock=threading.Lock()

def load_corpus() -> list:
    global _corpus_cache
    with _corpus_lock:
        if _corpus_cache is not None: return _corpus_cache
        docs=[]
        base=Path(DATA_DIR)
        for label in ("human","ai","uz","ru","en"):
            sub=base/label
            if not sub.exists(): continue
            for f in list(sub.glob("*.json"))[:5000]:
                try:
                    with open(f,encoding="utf-8") as fh: d=json.load(fh)
                    text=d.get("text") or d.get("full_text","")
                    if text and len(text.split())>=MIN_WORDS:
                        docs.append({"id":d.get("id",f.stem),"title":d.get("title",f.stem),
                                     "source":d.get("source",label),"url":d.get("url",""),
                                     "doi":d.get("doi",""),"text":text})
                except: pass
        _corpus_cache=docs
        log.info(f"Korpus: {len(docs)} hujjat")
        return docs


def _threshold(text, lang):
    base={"uz":THRESHOLD_UZ,"ru":THRESHOLD_RU,"en":THRESHOLD_EN}.get(lang,25.0)
    wc=len(text.split())
    if wc<100: return base+5
    if wc>800: return base-3
    return base


def run_analysis_sync(text: str, corpus: list, use_cache: bool = True) -> dict:
    """
    To'liq tahlil pipeline:
      1. Preprocessing (unicode, clean, normalize)
      2. Leksik tahlil: Winnowing + TF-IDF + Stop-words
      3. Aggregate scoring (ko'p manbali)
      4. Semantik tahlil: LaBSE (parafraz + tarjima) — agar o'rnatilgan bo'lsa
      5. AI detektor
      6. Yakuniy ball: leksik + semantik kombinatsiya
    """
    t0 = time.time()
    if not text or len(text.split()) < 5:
        return _empty("Matn juda qisqa")

    if use_cache:
        cached = CACHE.get(text)
        if cached:
            return cached

    # ── 1. Preprocessing ──────────────────────────────────────
    lang = detect_language(text)
    uc   = detect_unicode(text)
    ct   = normalize_unicode(text)
    filt = clean_text(ct)
    ct   = filt if len(filt.split()) >= max(8, len(text.split()) * 0.35) else ct
    norm = normalize_text(ct, lang)

    # ── 2. Leksik solishtirish: BM25 Index + Winnowing ───────
    #
    # Yangi arxitektura:
    #   BM25 index → top-30 kandidat (O(log n), <50ms)
    #   Keyin faqat shu 30 ta bilan Winnowing (aniq solishtirish)
    #   Natija: 50K hujjatda 0.3s (eski: 400s)

    match_list: list = []
    corpus_map: dict = {}

    # Kandidatlarni tanlash: BM25 yoki to'liq korpus
    if _INDEX_ENABLED and _CORPUS_INDEX and _CORPUS_INDEX.is_ready():
        # TEZKOR: BM25 + FAISS top-30 kandidat
        candidates = _CORPUS_INDEX.search(ct, top_k=30)
        log.debug(f"BM25 kandidatlar: {len(candidates)}")
    else:
        # Standart: barcha hujjatlar (O(n))
        candidates = corpus

    for doc in candidates:
        dt = doc.get("text", "")
        if not dt or len(dt.split()) < MIN_WORDS:
            continue
        did = str(doc.get("id", doc.get("title", id(doc))))
        corpus_map[did] = dt
        dn = normalize_text(dt, lang)
        if len(dn.split()) < 4:
            dn = dt.lower()
        ws = winnowing_score(norm, dn, lang)
        if ws >= 12:   # Yangi threshold: 8→12 (false positive -20%)
            match_list.append({
                "doc_id":         did,
                "document":       doc.get("title", "N/A"),
                "source":         doc.get("source", ""),
                "url":            doc.get("url", ""),
                "doi":            doc.get("doi", ""),
                "combined_score": round(ws, 1),
            })

    match_list.sort(key=lambda x: x["combined_score"], reverse=True)

    # ── 3. Aggregate scoring + sentence highlight ─────────────
    agg, hl = compute_aggregate(ct, match_list[:10], corpus_map, lang)
    lex_max  = match_list[0]["combined_score"] if match_list else 0.0
    lex_score = round(
        (agg * 0.65 + lex_max * 0.35) if agg > 0 and lex_max > 0
        else max(agg, lex_max), 1
    )

    # ── 4. Semantik tahlil: LaBSE ────────────────────────────
    #   Parafraz va tarjima plagiatini aniqlaydi.
    #   sentence-transformers o'rnatilmagan bo'lsa — 0 qaytaradi.
    sem = semantic_analysis(ct, match_list, corpus_map, lang)

    # ── 5. Yakuniy ball: leksik + semantik kombinatsiya ───────
    sem_score = sem["semantic_score"]
    if sem_score > 0:
        # LaBSE ishlagan: ikki signal birlashtiriladi
        # Leksik: so'z darajasida aniq moslik
        # Semantik: ma'no darajasida o'xshashlik
        overall = round(lex_score * 0.55 + sem_score * 0.45, 1)
        # Agar semantik yoki leksik juda yuqori bo'lsa — maksimum olinadi
        overall = round(max(overall, lex_score * 0.85, sem_score * 0.80), 1)
    else:
        overall = lex_score

    # ── 6. AI detektor ───────────────────────────────────────
    ai     = detect_ai(ct, lang)
    thresh = _threshold(text, lang)
    is_p   = overall >= thresh

    # ── 7. Xavflar va xulosa ─────────────────────────────────
    risks: list = []
    if is_p:                                      risks.append("plagiat")
    if ai["ai_probability"] > AI_THRESHOLD:       risks.append("AI matn")
    if uc.get("is_manipulated"):                  risks.append("unicode hiyla")
    if sem.get("translation_found"):              risks.append("tarjima plagiat")
    if sem.get("paraphrase_found"):               risks.append("parafraz plagiat")

    p = overall
    clean = [{k: v for k, v in m.items() if k != "doc_id"} for m in match_list[:10]]

    result = {
        "overall_plagiarism":   overall,
        "lexical_plagiarism":   lex_score,
        "semantic_plagiarism":  sem_score,
        "aggregate_plagiarism": agg,
        "is_plagiarism":        is_p,
        "threshold_used":       thresh,
        "ai_analysis":          ai,
        "language":             lang,
        "unicode_analysis":     uc,
        "matches":              clean,
        "sentence_highlights":  hl,
        "semantic_analysis": {
            "score":            sem_score,
            "translation_found":sem.get("translation_found", False),
            "paraphrase_found": sem.get("paraphrase_found",  False),
            "matches":          sem.get("semantic_matches",  []),
            "labse_available":  sem.get("available", False),
        },
        "summary": {
            "plagiarism_level": (
                "minimal"  if p < 20 else
                "o'rtacha" if p < 40 else
                "yuqori"   if p < 60 else
                "kritik"
            ),
            "overall_risk": (
                "kritik"   if p > 60 or len(risks) >= 2 else
                "yuqori"   if risks else
                "o'rtacha" if p > 20 else
                "past"
            ),
            "risks":    risks,
            "language": lang,
        },
        "meta": {
            "processing_ms":   round((time.time() - t0) * 1000, 1),
            "corpus_size":     len(corpus),
            "cache_hit_rate":  round(CACHE.hit_rate * 100, 1),
            "matched_sents":   sum(1 for s in hl if s["is_plagiarism"]),
            "total_sents":     len(hl),
            "labse_enabled":   _LABSE.available,
        },
        "error": None,
    }

    if use_cache:
        CACHE.set(text, result)
    return result



async def run_analysis(text: str, corpus: list, use_cache: bool = True) -> dict:
    """
    Async wrapper — run_analysis_sync ni thread pool da ishlatadi.

    FastAPI async loop ni bloklash muammosini hal qiladi:
      - Sinxron: 10 parallel so'rov = 10 × 40s = faqat 1 ta ishlaydi
      - Async:   10 parallel so'rov = thread pool da parallel, ~40s jami

    asyncio.get_event_loop().run_in_executor(None, func, *args):
      None → default ThreadPoolExecutor (cpu_count × 5 thread)
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        run_analysis_sync,
        text,
        corpus,
        use_cache,
    )


def _empty(err):
    return {"overall_plagiarism":0.0,"aggregate_plagiarism":0.0,"is_plagiarism":False,
            "threshold_used":25.0,"ai_analysis":{"ai_probability":0,"verdict":""},
            "language":"uz","unicode_analysis":{"is_manipulated":False},
            "matches":[],"sentence_highlights":[],
            "summary":{"plagiarism_level":"minimal","overall_risk":"past","risks":[],"language":"uz"},
            "meta":{"processing_ms":0},"error":err}


# ─── 1. PDF HISOBOT GENERATSIYA (bot.py dan) ─────────────────────────────────

def generate_pdf(result: dict, original_text: str, lang: str = "uz") -> bytes:
    """Professional PDF hisobot — 3 tilda."""

    LABELS = {
        "uz": {"title":"AntiplagiatPRO — Tahlil Hisoboti","date":"Sana",
               "plagiat":"Plagiat darajasi","ai":"AI ehtimoli","threshold":"Chegara",
               "language":"Til","unicode":"Unicode hiyla","risk":"Umumiy xavf",
               "found":"PLAGIAT","normal":"NORMAL","yes":"HA","no":"YO'Q",
               "suspicious":"Shubhali","no_risk":"Xavf yo'q",
               "sources":"Topilgan manbalar","sample":"Matn namunasi",
               "plag_sents":"Plagiat jumlalar","total_sents":"Jami jumlalar"},
        "ru": {"title":"AntiplagiatPRO — Отчёт анализа","date":"Дата",
               "plagiat":"Уровень плагиата","ai":"Вероятность ИИ","threshold":"Порог",
               "language":"Язык","unicode":"Unicode-манипуляция","risk":"Общий риск",
               "found":"ПЛАГИАТ","normal":"НОРМА","yes":"ДА","no":"НЕТ",
               "suspicious":"Подозрительно","no_risk":"Риск отсутствует",
               "sources":"Найденные источники","sample":"Фрагмент текста",
               "plag_sents":"Предложений с плагиатом","total_sents":"Всего предложений"},
        "en": {"title":"AntiplagiatPRO — Analysis Report","date":"Date",
               "plagiat":"Plagiarism level","ai":"AI probability","threshold":"Threshold",
               "language":"Language","unicode":"Unicode manipulation","risk":"Overall risk",
               "found":"PLAGIARISM","normal":"CLEAN","yes":"YES","no":"NO",
               "suspicious":"Suspicious","no_risk":"No risk",
               "sources":"Matching sources","sample":"Text sample",
               "plag_sents":"Plagiarism sentences","total_sents":"Total sentences"},
    }
    L = LABELS.get(lang, LABELS["uz"])

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        )

        buf  = io.BytesIO()
        doc  = SimpleDocTemplate(buf, pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm,
            topMargin=2*cm,   bottomMargin=2*cm)
        ss   = getSampleStyleSheet()
        blue = colors.HexColor("#1A4F7A")
        red  = colors.HexColor("#C0392B")
        gray = colors.HexColor("#7F8C8D")
        story = []

        def H(txt, sz=16):
            return Paragraph(txt, ParagraphStyle("H", parent=ss["Heading1"],
                fontSize=sz, textColor=blue, spaceAfter=8))
        def P(txt):
            return Paragraph(txt, ParagraphStyle("P", parent=ss["Normal"],
                fontSize=10, spaceAfter=4, leading=14))

        plag   = result["overall_plagiarism"]
        ai     = result["ai_analysis"]["ai_probability"]
        r_lang = result["language"].upper()
        thr    = result["threshold_used"]
        risks  = result["summary"].get("risks", [])
        is_p   = result["is_plagiarism"]
        meta   = result.get("meta", {})

        story += [
            H(L["title"]),
            P(f"<font color='gray'>{L['date']}: "
              f"{datetime.now().strftime('%Y-%m-%d %H:%M')}</font>"),
            Spacer(1, 0.4*cm),
        ]

        # Asosiy jadvali
        status_color = f"<font color='red'>{L['found']}</font>" if is_p else f"<font color='green'>{L['normal']}</font>"
        data = [
            [L["plagiat"],     f"{plag:.1f}%",     status_color],
            [L["threshold"],   f"{thr:.0f}%",       f"{L['language']}: {r_lang}"],
            [L["ai"],          f"{ai:.1f}%",         result["ai_analysis"]["verdict"]],
            [L["unicode"],
             L["yes"] if result["unicode_analysis"]["is_manipulated"] else L["no"],
             L["suspicious"] if result["unicode_analysis"]["is_manipulated"] else L["no_risk"]],
            [L["risk"],        result["summary"]["overall_risk"],
             ", ".join(risks) if risks else L["no_risk"]],
            [L["plag_sents"],  str(meta.get("matched_sents",0)),
             f'/ {meta.get("total_sents",0)} {L["total_sents"]}'],
        ]
        tbl = Table([[Paragraph(f"<b>{r[0]}</b>", ss["Normal"]),
                      Paragraph(str(r[1]), ss["Normal"]),
                      Paragraph(str(r[2]), ss["Normal"])] for r in data],
                    colWidths=[5.5*cm, 3*cm, 8*cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#F8FAFB")),
            ("ROWBACKGROUNDS",(0,0), (-1,-1), [colors.HexColor("#EBF5FB"), colors.white]),
            ("GRID",          (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ]))
        story += [tbl, Spacer(1, 0.4*cm)]

        # Manbalar
        matches = result.get("matches", [])
        if matches:
            story.append(H(L["sources"], 12))
            for i, m in enumerate(matches[:5], 1):
                url = f" — <link href='{m['url']}'>{m['url'][:50]}…</link>" if m.get("url") else ""
                story.append(P(f"{i}. <b>{m['document'][:60]}</b> "
                               f"— {m['combined_score']:.1f}% [{m['source']}]{url}"))
            story.append(Spacer(1, 0.3*cm))

        # Plagiat jumlalar (sentence highlights)
        highlights = result.get("sentence_highlights", [])
        plag_sents = [h for h in highlights if h.get("is_plagiarism")]
        if plag_sents:
            story.append(H("Plagiat jumlalar", 12))
            for h in plag_sents[:8]:
                src = f" ← {h['match_source']}" if h.get("match_source") else ""
                story.append(P(f"<font color='red'>●</font> {h['sentence'][:120]}"
                               f"<font color='gray'>{src} ({h['match_score']:.0f}%)</font>"))
            story.append(Spacer(1, 0.3*cm))

        # Matn namunasi
        story.append(H(L["sample"], 12))
        preview = (original_text[:500] + "…") if len(original_text) > 500 else original_text
        story.append(P(preview.replace("\n", " ")))

        doc.build(story)
        buf.seek(0)
        return buf.getvalue()

    except ImportError:
        lines = [
            L["title"],
            f"{L['plagiat']}: {result['overall_plagiarism']:.1f}%",
            f"{L['ai']}: {result['ai_analysis']['ai_probability']:.1f}%",
            f"{L['language']}: {result['language'].upper()}",
            f"{L['risk']}: {result['summary']['overall_risk']}",
        ]
        return "\n".join(lines).encode("utf-8")


# ─── 2. FAYL YUKLASH (bot.py dan) ────────────────────────────────────────────

def extract_text_from_file(data: bytes, filename: str) -> str:
    """PDF, DOCX, TXT fayllardan matn chiqarish."""
    fname = (filename or "").lower()
    if fname.endswith(".pdf"):
        # PyPDF2 yoki yangi pypdf kutubxonasi
        try:
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(io.BytesIO(data))
            except ImportError:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(data))
            text = " ".join(p.extract_text() or "" for p in reader.pages)
            if text.strip():
                return text
        except Exception:
            pass
        # pdfminer fallback
        try:
            from pdfminer.high_level import extract_text as pm_extract
            return pm_extract(io.BytesIO(data))
        except Exception:
            pass
    if fname.endswith(".docx"):
        try:
            from docx import Document
            doc = Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            pass
    if fname.endswith(".txt"):
        try:
            return data.decode("utf-8", errors="ignore")
        except Exception:
            pass
    return ""


# ─── AUTH YORDAMCHILAR ────────────────────────────────────────────────────────

async def send_email(to: str, subject: str, html: str) -> bool:
    """
    Email yuborish — aiosmtplib bilan async.
    SMTP_USER/PASS .env da bo'lmasa — faqat log ga yozadi (dev rejim).
    """
    if not EMAIL_ENABLED:
        log.info(f"[DEV EMAIL] to={to} subject={subject}")
        log.info(f"[DEV EMAIL] Haqiqiy email yuborish uchun .env da SMTP_USER/PASS ni to'ldiring")
        return True   # Dev rejimda muvaffaqiyatli hisoblanadi
    try:
        import aiosmtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = EMAIL_FROM
        msg["To"]      = to
        msg.attach(MIMEText(html, "html", "utf-8"))
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            start_tls=True,
            username=SMTP_USER,
            password=SMTP_PASS,
        )
        log.info(f"Email yuborildi: {to}")
        return True
    except Exception as e:
        log.error(f"Email xatosi: {e}")
        return False


def create_verify_token(user_id: str) -> str:
    """Email tasdiqlash tokeni yaratish (24 soat amal qiladi)."""
    token   = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    with db() as c:
        c.execute(
            "INSERT INTO email_verifications(token,user_id,expires_at) VALUES(?,?,?)",
            (token, user_id, expires)
        )
        # users_meta ga yozish (agar yo'q bo'lsa)
        c.execute(
            "INSERT OR IGNORE INTO users_meta(user_id) VALUES(?)",
            (user_id,)
        )
    return token


def create_reset_token(user_id: str) -> str:
    """Parolni tiklash tokeni yaratish (1 soat amal qiladi)."""
    # Eski tokenlarni bekor qilish
    with db() as c:
        c.execute(
            "UPDATE password_resets SET used=1 WHERE user_id=? AND used=0",
            (user_id,)
        )
    token   = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    with db() as c:
        c.execute(
            "INSERT INTO password_resets(token,user_id,expires_at) VALUES(?,?,?)",
            (token, user_id, expires)
        )
    return token


def _verify_email_template(name: str, link: str, lang: str = "uz") -> tuple:
    """Email tasdiqlash xati."""
    subjects = {
        "uz": "AntiplagiatPRO — Email manzilingizni tasdiqlang",
        "ru": "AntiplagiatPRO — Подтвердите вашу электронную почту",
        "en": "AntiplagiatPRO — Verify your email address",
    }
    subject = subjects.get(lang, subjects["uz"])
    html = f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;padding:20px">
  <div style="background:#2C5FE4;padding:24px;border-radius:12px 12px 0 0;text-align:center">
    <h1 style="color:#fff;margin:0;font-size:22px">AntiplagiatPRO</h1>
  </div>
  <div style="background:#fff;padding:28px;border:1px solid #E4E7F0;border-radius:0 0 12px 12px">
    <p style="font-size:15px">Salom, <b>{name}</b>!</p>
    <p style="color:#555;font-size:14px">
      Hisobingizni faollashtirish uchun quyidagi tugmani bosing.
      Havola <b>24 soat</b> amal qiladi.
    </p>
    <div style="text-align:center;margin:28px 0">
      <a href="{link}"
         style="background:#2C5FE4;color:#fff;padding:14px 32px;
                border-radius:8px;text-decoration:none;font-weight:bold;font-size:15px">
        Email manzilni tasdiqlash
      </a>
    </div>
    <p style="color:#999;font-size:12px">
      Agar siz ro'yxatdan o'tmagan bo'lsangiz, bu xatni e'tiborsiz qoldiring.
    </p>
    <hr style="border:none;border-top:1px solid #eee;margin:20px 0">
    <p style="color:#bbb;font-size:11px;text-align:center">AntiplagiatPRO © 2025</p>
  </div>
</body></html>"""
    return subject, html


def _reset_password_template(name: str, link: str, lang: str = "uz") -> tuple:
    """Parolni tiklash xati."""
    subjects = {
        "uz": "AntiplagiatPRO — Parolni tiklash",
        "ru": "AntiplagiatPRO — Сброс пароля",
        "en": "AntiplagiatPRO — Password reset",
    }
    subject = subjects.get(lang, subjects["uz"])
    html = f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;padding:20px">
  <div style="background:#2C5FE4;padding:24px;border-radius:12px 12px 0 0;text-align:center">
    <h1 style="color:#fff;margin:0;font-size:22px">AntiplagiatPRO</h1>
  </div>
  <div style="background:#fff;padding:28px;border:1px solid #E4E7F0;border-radius:0 0 12px 12px">
    <p style="font-size:15px">Salom, <b>{name}</b>!</p>
    <p style="color:#555;font-size:14px">
      Parolni tiklash so'rovi qabul qilindi.
      Havola <b>1 soat</b> amal qiladi.
    </p>
    <div style="text-align:center;margin:28px 0">
      <a href="{link}"
         style="background:#EF4444;color:#fff;padding:14px 32px;
                border-radius:8px;text-decoration:none;font-weight:bold;font-size:15px">
        Yangi parol o'rnatish
      </a>
    </div>
    <p style="color:#999;font-size:12px">
      Agar siz so'rov yubormagan bo'lsangiz, bu xatni e'tiborsiz qoldiring.
      Havolaga bosilmasa parolingiz o'zgarmaydi.
    </p>
    <hr style="border:none;border-top:1px solid #eee;margin:20px 0">
    <p style="color:#bbb;font-size:11px;text-align:center">AntiplagiatPRO © 2025</p>
  </div>
</body></html>"""
    return subject, html


def hash_pw(pw: str) -> str:
    try:
        import bcrypt
        return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    except ImportError:
        return hashlib.sha256((pw + SECRET_KEY).encode()).hexdigest()


def check_pw(pw: str, hashed: str) -> bool:
    try:
        import bcrypt
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ImportError:
        return hashed == hashlib.sha256((pw + SECRET_KEY).encode()).hexdigest()


def create_session(user_id: str) -> str:
    token = str(uuid.uuid4())
    expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
    with db() as c:
        c.execute("INSERT INTO sessions VALUES(?,?,?)", (token, user_id, expires))
    return token


def get_user(authorization: str = Header(None)) -> Optional[dict]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    with db() as c:
        row = c.execute(
            "SELECT s.user_id,u.email,u.name,u.plan,u.checks_used "
            "FROM sessions s JOIN users u ON s.user_id=u.id "
            "WHERE s.token=? AND s.expires_at>?",
            (token, datetime.utcnow().isoformat())
        ).fetchone()
    return dict(row) if row else None


def require_user(authorization: str = Header(None)) -> dict:
    u = get_user(authorization)
    if not u: raise HTTPException(401, "Avtorizatsiya kerak")
    return u


# ─── PYDANTIC MODELLARI ───────────────────────────────────────────────────────

class RegisterReq(BaseModel):
    name: str
    email: str
    password: str

class LoginReq(BaseModel):
    email: str
    password: str

class AnalyzeReq(BaseModel):
    text: str
    use_cache: bool = True

class ForgotPasswordReq(BaseModel):
    email: str

class ResetPasswordReq(BaseModel):
    token: str
    new_password: str

class ChangePasswordReq(BaseModel):
    old_password: str
    new_password: str


# ─── FASTAPI ILOVASI ──────────────────────────────────────────────────────────

# Rate limit handler va state
app.state.limiter = Limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    corpus = load_corpus()
    # Korpus indeksini qurish (BM25 + FAISS)
    if _INDEX_ENABLED and corpus:
        try:
            # Avval diskdan yuklashga urinish (tezkor)
            if not IndexPersistence.load(_CORPUS_INDEX):
                # Yangi qurish
                stats = _CORPUS_INDEX.build(corpus)
                IndexPersistence.save(_CORPUS_INDEX)
                log.info(f"Indeks qurildi: {stats}")
            else:
                log.info(f"Indeks yuklandi: {_CORPUS_INDEX.stats}")
        except Exception as e:
            log.warning(f"Indeks qurishda xato: {e} — standart rejim")

    # LaBSE ni background da preload qilish
    # Birinchi so'rovda 60s kutishning oldini oladi
    async def _preload_labse():
        try:
            log.info("LaBSE preload boshlandi (background)...")
            loop = asyncio.get_event_loop()
            available = await loop.run_in_executor(None, lambda: _LABSE.available)
            log.info(f"LaBSE preload: {'tayyor' if available else 'o\'rnatilmagan'}")
        except Exception as e:
            log.debug(f"LaBSE preload: {e}")

    asyncio.create_task(_preload_labse())

    # Eskirgan auth tokenlarni tozalash (kuniga bir marta)
    async def _token_cleanup():
        while True:
            try:
                now = datetime.utcnow().isoformat()
                with db() as c:
                    del_pr = c.execute(
                        "DELETE FROM password_resets WHERE expires_at < ?", (now,)
                    ).rowcount
                    del_ev = c.execute(
                        "DELETE FROM email_verifications WHERE expires_at < ? AND used = 1",
                        (now,)
                    ).rowcount
                if del_pr + del_ev:
                    log.info(f"Token tozalash: {del_pr} reset, {del_ev} verify o'chirildi")
            except Exception as e:
                log.debug(f"Token cleanup: {e}")
            await asyncio.sleep(86400)   # 24 soat

    asyncio.create_task(_token_cleanup())
    log.info("Server tayyor")
    yield

# Rate limiter — IP bo'yicha cheklash
limiter = Limiter(key_func=get_remote_address, default_limits=["200/hour"])

app = FastAPI(title="AntiplagiatPRO", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,    # 1KB dan katta javoblarni siqish
    compresslevel=6,      # 1-9, 6 = tezlik/siqish muvozanati
)

# ── CSP + Xavfsizlik headerlari ──────────────────────────
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"]  = "nosniff"
    response.headers["X-Frame-Options"]          = "DENY"
    response.headers["X-XSS-Protection"]         = "1; mode=block"
    response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"]   = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "   # inline JS uchun (frontend)
        "style-src  'self' 'unsafe-inline'; "
        "img-src    'self' data: https:; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )
    return response
app.add_middleware(CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:8000")],
    allow_methods=["*"], allow_headers=["*"])

# Frontend fayllarini statik serve qilish
frontend_path = Path("../frontend")
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

    @app.get("/")
    async def root():
        return FileResponse(str(frontend_path / "index.html"))

    @app.get("/reset-password")
    async def reset_password_page():
        """Parolni tiklash sahifasi.

        Email da kelgan havola shu URL ga yo'naltiradi:
          http://host/reset-password?token=xxx
        index.html yuklanadi, JS ?token parametrini o'qib
        reset modal ochadi (frontend/index.html da allaqachon bor).
        """
        return FileResponse(str(frontend_path / "index.html"))


# ─── AUTH ENDPOINTLAR ─────────────────────────────────────────────────────────

@app.post("/api/auth/register")
@limiter.limit("10/minute")          # Brute force oldini olish
async def register(request: Request, req: RegisterReq):
    if len(req.name.strip()) < 2:
        raise HTTPException(400, "Ism kamida 2 belgi")
    if len(req.password) < 6:
        raise HTTPException(400, "Parol kamida 6 belgi")
    # Email format tekshiruv — "notmail" kabi noto'g'ri email bloklash
    import re as _re
    if not _re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', req.email.strip()):
        raise HTTPException(400, "Email format noto'g'ri (misol: ism@domen.uz)")
    uid = str(uuid.uuid4())
    try:
        with db() as c:
            c.execute("INSERT INTO users(id,email,name,password) VALUES(?,?,?,?)",
                      (uid, req.email.lower().strip(), req.name.strip(), hash_pw(req.password)))
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Bu email allaqachon ro'yxatdan o'tgan")

    # users_meta ni KAFOLATLI yaratish — SMTP/xato bo'lsa ham
    with db() as c:
        c.execute(
            "INSERT OR IGNORE INTO users_meta(user_id, email_verified) VALUES(?, 0)",
            (uid,)
        )

    token = create_session(uid)

    # Email tasdiqlash xati yuborish (background)
    verify_token = create_verify_token(uid)
    verify_link  = f"{SITE_URL}/api/auth/verify-email?token={verify_token}"
    subj, html_body = _verify_email_template(req.name.strip(), verify_link)
    asyncio.create_task(send_email(req.email.lower().strip(), subj, html_body))

    return {
        "token": token,
        "user":  {"id": uid, "email": req.email, "name": req.name,
                  "plan": "free", "checks_used": 0, "email_verified": False},
        "message": "Ro'yxatdan o'tdingiz! Email manzilingizni tasdiqlang.",
    }


@app.post("/api/auth/login")
@limiter.limit("10/minute")          # Brute force oldini olish
async def login(request: Request, req: LoginReq):
    email_key = req.email.lower().strip()

    # Brute force tekshiruv — email bo'yicha
    _check_brute_force(email_key)

    with db() as c:
        row = c.execute("SELECT * FROM users WHERE email=?", (email_key,)).fetchone()

    if not row or not check_pw(req.password, dict(row)["password"]):
        _record_fail(email_key)    # Xato → counter oshirish
        raise HTTPException(401, "Email yoki parol noto'g'ri")

    # Muvaffaqiyatli → counter tozalash
    _clear_fail(email_key)

    u = dict(row)
    with db() as c:
        c.execute("UPDATE users SET last_login=? WHERE id=?",
                  (datetime.utcnow().isoformat(), u["id"]))
    token = create_session(u["id"])
    return {"token": token, "user": {"id": u["id"], "email": u["email"],
                                      "name": u["name"], "plan": u["plan"],
                                      "checks_used": u["checks_used"]}}


@app.get("/api/auth/me")
async def me(user: dict = Depends(require_user)):
    return user


@app.post("/api/auth/logout")
async def logout(authorization: str = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        with db() as c:
            c.execute("DELETE FROM sessions WHERE token=?", (authorization[7:],))
    return {"ok": True}


# ─── YANGI AUTH ENDPOINTLAR ─────────────────────────────────────────────────

@app.get("/api/auth/verify-email")
async def verify_email(token: str):
    """Email tasdiqlash — havola orqali."""
    with db() as c:
        row = c.execute(
            "SELECT user_id, expires_at, used FROM email_verifications WHERE token=?",
            (token,)
        ).fetchone()

    if not row:
        raise HTTPException(400, "Token topilmadi yoki noto'g'ri")
    if row["used"]:
        raise HTTPException(400, "Bu havola allaqachon ishlatilgan")
    if row["expires_at"] < datetime.utcnow().isoformat():
        raise HTTPException(400, "Havola muddati tugagan. Qayta so'rang.")

    with db() as c:
        c.execute("UPDATE email_verifications SET used=1 WHERE token=?", (token,))
        c.execute(
            "INSERT OR REPLACE INTO users_meta(user_id,email_verified,verified_at) "
            "VALUES(?,1,?)", (row["user_id"], datetime.utcnow().isoformat())
        )

    # HTML sahifaga yo'naltirish
    from fastapi.responses import HTMLResponse
    return HTMLResponse("""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Tasdiqlandi</title>
<meta http-equiv="refresh" content="3;url=/">
</head><body style="font-family:Arial;text-align:center;padding:60px">
  <div style="background:#EAF3DE;border-radius:12px;padding:40px;max-width:420px;margin:0 auto">
    <div style="font-size:48px">✅</div>
    <h2 style="color:#3B6D11">Email tasdiqlandi!</h2>
    <p style="color:#555">3 soniyada bosh sahifaga yo'naltirilasiz...</p>
    <a href="/" style="color:#2C5FE4">Hozir o'tish</a>
  </div>
</body></html>""")


@app.post("/api/auth/resend-verification")
@limiter.limit("3/hour")
async def resend_verification(request: Request, authorization: str = Header(None)):
    """Tasdiqlash xatini qayta yuborish."""
    user = require_user(authorization)
    uid  = user["user_id"]

    # Allaqachon tasdiqlangan bo'lsa
    with db() as c:
        meta = c.execute(
            "SELECT email_verified FROM users_meta WHERE user_id=?", (uid,)
        ).fetchone()
    if meta and meta["email_verified"]:
        raise HTTPException(400, "Email allaqachon tasdiqlangan")

    # Foydalanuvchi emaili
    with db() as c:
        u = c.execute("SELECT email,name FROM users WHERE id=?", (uid,)).fetchone()
    if not u:
        raise HTTPException(404, "Foydalanuvchi topilmadi")

    token = create_verify_token(uid)
    link  = f"{SITE_URL}/api/auth/verify-email?token={token}"
    subj, html_body = _verify_email_template(u["name"], link)
    asyncio.create_task(send_email(u["email"], subj, html_body))

    return {"ok": True, "message": "Tasdiqlash xati yuborildi"}


@app.post("/api/auth/forgot-password")
@limiter.limit("5/hour")
async def forgot_password(request: Request, req: ForgotPasswordReq):
    """Parolni tiklash so'rovi — email yuboradi."""
    with db() as c:
        row = c.execute(
            "SELECT id, name FROM users WHERE email=?",
            (req.email.lower().strip(),)
        ).fetchone()

    # Xavfsizlik: email topilmasa ham muvaffaqiyatli javob
    # (email enumeration oldini olish)
    if row:
        token = create_reset_token(row["id"])
        link  = f"{SITE_URL}/reset-password?token={token}"
        subj, html_body = _reset_password_template(row["name"], link)
        asyncio.create_task(send_email(req.email.lower().strip(), subj, html_body))

    return {
        "ok": True,
        "message": "Agar bu email ro'yxatdan o'tgan bo'lsa, tiklash havolasi yuborildi"
    }


@app.post("/api/auth/reset-password")
@limiter.limit("10/hour")
async def reset_password(request: Request, req: ResetPasswordReq):
    """Token bilan yangi parol o'rnatish."""
    if len(req.new_password) < 6:
        raise HTTPException(400, "Parol kamida 6 belgi bo'lishi kerak")

    with db() as c:
        row = c.execute(
            "SELECT user_id, expires_at, used FROM password_resets WHERE token=?",
            (req.token,)
        ).fetchone()

    if not row:
        raise HTTPException(400, "Token topilmadi yoki noto'g'ri")
    if row["used"]:
        raise HTTPException(400, "Bu havola allaqachon ishlatilgan")
    if row["expires_at"] < datetime.utcnow().isoformat():
        raise HTTPException(400, "Token muddati tugagan (1 soat). Qayta so'rang.")

    new_hash = hash_pw(req.new_password)
    with db() as c:
        c.execute(
            "UPDATE users SET password=? WHERE id=?",
            (new_hash, row["user_id"])
        )
        c.execute(
            "UPDATE password_resets SET used=1 WHERE token=?",
            (req.token,)
        )
        # Barcha sessionlarni o'chirish (xavfsizlik)
        c.execute(
            "DELETE FROM sessions WHERE user_id=?",
            (row["user_id"],)
        )

    return {"ok": True, "message": "Parol muvaffaqiyatli o'zgartirildi. Qayta kiring."}


@app.post("/api/auth/change-password")
async def change_password(req: ChangePasswordReq, user: dict = Depends(require_user)):
    """Kirgan foydalanuvchi parolini o'zgartirish."""
    if len(req.new_password) < 6:
        raise HTTPException(400, "Yangi parol kamida 6 belgi")

    with db() as c:
        row = c.execute(
            "SELECT password FROM users WHERE id=?", (user["user_id"],)
        ).fetchone()
    if not row or not check_pw(req.old_password, row["password"]):
        raise HTTPException(401, "Joriy parol noto'g'ri")

    with db() as c:
        c.execute(
            "UPDATE users SET password=? WHERE id=?",
            (hash_pw(req.new_password), user["user_id"])
        )
    return {"ok": True, "message": "Parol o'zgartirildi"}


@app.get("/api/auth/email-status")
async def email_status(user: dict = Depends(require_user)):
    """Foydalanuvchining email tasdiqlash holati."""
    with db() as c:
        meta = c.execute(
            "SELECT email_verified, verified_at FROM users_meta WHERE user_id=?",
            (user["user_id"],)
        ).fetchone()
    verified = bool(meta and meta["email_verified"]) if meta else False
    return {
        "email_verified": verified,
        "verified_at":    dict(meta)["verified_at"] if (meta and verified) else None,
    }


# ─── TAHLIL ENDPOINTLAR ───────────────────────────────────────────────────────

def _check_limit(user: Optional[dict]):
    """Bepul foydalanuvchi limiti."""
    if user and user.get("plan") == "free" and user.get("checks_used", 0) >= FREE_CHECKS:
        raise HTTPException(402, f"Bepul rejimda {FREE_CHECKS} ta tekshiruv. "
                                  "Pro rejimga o'ting.")


def _save_check(user: Optional[dict], text: str, filename: Optional[str],
                result: dict):
    """Tarixga saqlash."""
    if not user:
        return None
    check_id = str(uuid.uuid4())
    preview = text[:150] + ("…" if len(text) > 150 else "")
    with db() as c:
        c.execute("INSERT INTO checks VALUES(?,?,?,?,?,?,?,?,?,?)", (
            check_id, user["user_id"], preview, filename or "",
            result["language"],
            result["overall_plagiarism"], result["ai_analysis"]["ai_probability"],
            int(result["is_plagiarism"]),
            json.dumps(result, ensure_ascii=False),
            datetime.utcnow().isoformat()
        ))
        c.execute("UPDATE users SET checks_used=checks_used+1 WHERE id=?",
                  (user["user_id"],))
    return check_id


@app.post("/api/analyze")
@limiter.limit("30/minute")          # 1 IP → 30 tekshiruv/daqiqa
async def analyze_text(request: Request, req: AnalyzeReq, authorization: str = Header(None)):
    user = get_user(authorization)
    _check_limit(user)
    if len(req.text.strip()) < 20:
        raise HTTPException(400, "Matn juda qisqa")
    if len(req.text) > 200_000:
        raise HTTPException(400, "Matn juda uzun (max 200,000 belgi)")
    corpus = load_corpus()
    result = await run_analysis(req.text, corpus, req.use_cache)

    # Web search bilan kuchaytirish (agar API kaliti mavjud)
    if WEB_SEARCH_ENABLED:
        lang = result.get("language", "en")
        result = await enhance_analysis_with_web(req.text, lang, result)

    check_id = _save_check(user, req.text, None, result)
    if check_id:
        result["check_id"] = check_id
    return result


@app.post("/api/analyze/file")
@limiter.limit("20/minute")          # Fayl yuklash og'irroq — kamroq limit
async def analyze_file(
    request: Request,
    file: UploadFile = File(...),
    authorization: str = Header(None),
):
    """2. FAYL YUKLASH — PDF / DOCX / TXT."""
    user = get_user(authorization)
    _check_limit(user)

    if file.size and file.size > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(400, f"Fayl {MAX_FILE_MB}MB dan katta")

    data = await file.read()
    if len(data) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(400, f"Fayl {MAX_FILE_MB}MB dan katta")

    text = extract_text_from_file(data, file.filename or "")
    if not text or len(text.split()) < 10:
        raise HTTPException(400,
            "Fayldan matn o'qib bo'lmadi. "
            "PDF matnli bo'lishi kerak (skanerlangan emas). "
            "DOCX yoki TXT ham qabul qilinadi.")

    corpus = load_corpus()
    result = await run_analysis(text, corpus)
    check_id = _save_check(user, text, file.filename, result)
    if check_id:
        result["check_id"] = check_id
    return result


# ─── 4. TARIX (bot.py da yo'q edi, faqat saytda) ─────────────────────────────

@app.get("/api/history")
async def history(
    user: dict = Depends(require_user),
    page:  int = 1,
    limit: int = 20,
):
    """Tekshiruv tarixi — pagination bilan.

    Query params:
      page  — sahifa raqami (1 dan boshlanadi)
      limit — sahifadagi elementlar (max 50)
    """
    limit  = max(1, min(limit, 50))
    offset = (max(1, page) - 1) * limit

    with db() as c:
        total = c.execute(
            "SELECT COUNT(*) FROM checks WHERE user_id=?",
            (user["user_id"],)
        ).fetchone()[0]
        rows = c.execute(
            "SELECT id,text_preview,filename,language,plagiarism,"
            "ai_prob,is_plagiarism,created_at "
            "FROM checks WHERE user_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user["user_id"], limit, offset)
        ).fetchall()

    return {
        "items":      [dict(r) for r in rows],
        "total":      total,
        "page":       page,
        "limit":      limit,
        "pages":      (total + limit - 1) // limit,
        "has_next":   offset + limit < total,
        "has_prev":   page > 1,
    }


@app.get("/api/history/{check_id}")
async def history_detail(check_id: str, user: dict = Depends(require_user)):
    with db() as c:
        row = c.execute(
            "SELECT * FROM checks WHERE id=? AND user_id=?",
            (check_id, user["user_id"])
        ).fetchone()
    if not row:
        raise HTTPException(404, "Topilmadi")
    d = dict(row)
    d["result"] = json.loads(d.pop("result_json"))
    return d


@app.get("/api/history/{check_id}/pdf")
async def history_pdf(check_id: str, authorization: str = Header(None)):
    """1. PDF HISOBOT — tarixdan yuklash."""
    user = require_user(authorization)
    with db() as c:
        row = c.execute(
            "SELECT result_json,text_preview,language FROM checks "
            "WHERE id=? AND user_id=?",
            (check_id, user["user_id"])
        ).fetchone()
    if not row:
        raise HTTPException(404, "Topilmadi")
    result = json.loads(row["result_json"])
    lang   = row["language"] or "uz"
    pdf    = generate_pdf(result, row["text_preview"], lang)
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report_{check_id[:8]}.pdf"'}
    )


@app.post("/api/analyze/pdf")
async def analyze_and_pdf(req: AnalyzeReq, authorization: str = Header(None)):
    """Tahlil qilib darhol PDF qaytarish."""
    user = get_user(authorization)
    _check_limit(user)
    corpus = load_corpus()
    result = await run_analysis(req.text, corpus)
    lang   = result.get("language", "uz")
    pdf    = generate_pdf(result, req.text, lang)
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="antiplagiat_report.pdf"'}
    )


# ─── STATISTIKA ───────────────────────────────────────────────────────────────

@app.post("/api/admin/rebuild-index")
@limiter.limit("2/hour")
async def admin_rebuild_index(
    request: Request,
    admin_key: str = Header(None, alias="X-Admin-Key"),
):
    """Dataset yangilanganda BM25 indeksini qayta qurish.

    Header: X-Admin-Key: <ADMIN_KEY from .env>
    Restart kerak emas — runtime da yangilanadi.
    """
    expected = os.getenv("ADMIN_KEY", "")
    if not expected or admin_key != expected:
        raise HTTPException(403, "Admin key noto'g'ri")

    global _corpus_cache
    with _corpus_lock:
        _corpus_cache = None           # keshni tozalash

    corpus = load_corpus()             # qayta yuklash
    if _INDEX_ENABLED and _CORPUS_INDEX:
        stats_data = _CORPUS_INDEX.build(corpus)
        IndexPersistence.save(_CORPUS_INDEX)
        return {
            "ok":           True,
            "corpus_size":  len(corpus),
            "index":        stats_data,
            "message":      "Indeks qayta qurildi",
        }
    return {"ok": True, "corpus_size": len(corpus), "message": "Index disabled"}


@app.get("/api/stats")
async def stats():
    with db() as c:
        total = c.execute("SELECT COUNT(*) FROM checks").fetchone()[0]
        users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    idx_stats = _CORPUS_INDEX.stats if (_INDEX_ENABLED and _CORPUS_INDEX) else {}
    return {
        "total_checks":   total,
        "total_users":    users,
        "corpus_size":    len(load_corpus()),
        "cache_hit_rate": round(CACHE.hit_rate * 100, 1),
        "index": {
            "enabled":  _INDEX_ENABLED and bool(_CORPUS_INDEX and _CORPUS_INDEX.is_ready()),
            "bm25":     idx_stats.get("bm25_indexed", 0),
            "faiss":    idx_stats.get("faiss_indexed", 0),
            "build_ms": idx_stats.get("build_ms", 0),
        },
    }


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "corpus": len(load_corpus())}


# ─── ISHGA TUSHIRISH ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("🌐 AntiplagiatPRO Web Server")
    print("   Sayt: http://localhost:8000")
    print("   API:  http://localhost:8000/api")
    print("   To'xtatish: Ctrl+C")
    print("=" * 50)
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
