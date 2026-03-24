#!/usr/bin/env python3
"""
AntiplagiatPRO — AI Detection Dataset Generator
==================================================
Maqsad: 100K+ labeled matn yaratish (inson vs AI) — 3 tilda.

Arxitektura:
  1. Inson matnlarini yig'ish (ZiyoNet, arXiv, Wikipedia)
  2. AI matnlarini generatsiya (OpenAI, Anthropic, Google API)
  3. Parafraz variantlar (QuillBot simulation)
  4. Dataset balanslashtirish va saqlash

Ishlatish:
  # Inson matnlarini yig'ish
  python ai_dataset_generator.py --collect-human --target 5000

  # AI matn generatsiya (API kalitlari kerak)
  python ai_dataset_generator.py --generate-ai --target 5000

  # Parafraz variantlar
  python ai_dataset_generator.py --paraphrase --target 3000

  # To'liq pipeline
  python ai_dataset_generator.py --all --target 10000

  # Statistika
  python ai_dataset_generator.py --stats

O'rnatish:
  pip install openai anthropic google-generativeai requests tqdm

Muhim: .env faylda API kalitlarni to'ldiring:
  OPENAI_API_KEY=sk-...
  ANTHROPIC_API_KEY=sk-ant-...
  GOOGLE_API_KEY=...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Optional

# ── SOZLAMALAR ────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "ai_detection_dataset"

# Dataset papka tuzilmasi
# ai_detection_dataset/
#   human/uz/  human/ru/  human/en/
#   ai/gpt4/uz/  ai/gpt4/ru/  ai/gpt4/en/
#   ai/claude/uz/  ai/claude/ru/  ai/claude/en/
#   ai/gemini/uz/  ai/gemini/ru/  ai/gemini/en/
#   paraphrase/quillbot_standard/  paraphrase/quillbot_formal/
#   mixed/50_50/  mixed/30_70/

DELAY = 1.0  # API so'rovlar orasidagi kutish

# ── AKADEMIK MAVZULAR (3 tilda) ──────────────────────────────

TOPICS = {
    "uz": [
        "O'zbekistonda iqtisodiy islohotlarning jamiyatga ta'siri",
        "Zamonaviy ta'lim tizimidagi muammolar va yechimlar",
        "Raqamli texnologiyalarning yoshlar hayotiga ta'siri",
        "Sun'iy intellektning tibbiyotdagi qo'llanilishi",
        "O'zbek tilining zamonaviy holatini saqlash muammolari",
        "Ekologik muammolar va barqaror rivojlanish",
        "Kichik biznesni rivojlantirish strategiyalari",
        "Onlayn ta'limning an'anaviy ta'limdan farqlari",
        "Oilaviy qadriyatlarning zamonaviy jamiyatdagi o'rni",
        "Transport infratuzilmasini modernizatsiya qilish",
        "Qishloq xo'jaligida innovatsion texnologiyalar",
        "Yosh avlodda vatanparvarlikni shakllantirish",
        "Sog'liqni saqlash tizimini isloh qilish",
        "Turizm sohasini rivojlantirish istiqbollari",
        "Axborot xavfsizligi va shaxsiy ma'lumotlar himoyasi",
        "Oliy ta'limda sifat kafolatini ta'minlash",
        "Madaniy merosni asrash va tiklash",
        "Iqtisodiyotni diversifikatsiya qilish yo'llari",
        "Sport va jismoniy tarbiyaning ahamiyati",
        "Ilmiy tadqiqot metodologiyasi asoslari",
        "Korrupsiyaga qarshi kurashning huquqiy asoslari",
        "Gender tenglik masalalari zamonaviy jamiyatda",
        "Suv resurslarini boshqarish muammolari",
        "Energiya samaradorligi va muqobil energiya manbalari",
        "Davlat boshqaruvi tizimini takomillashtirish",
    ],
    "ru": [
        "Влияние искусственного интеллекта на рынок труда",
        "Проблемы современной системы высшего образования",
        "Цифровая трансформация экономики: вызовы и возможности",
        "Экологические проблемы крупных городов",
        "Роль социальных сетей в формировании общественного мнения",
        "Методы повышения качества научных исследований",
        "Реформирование системы здравоохранения",
        "Проблемы малого бизнеса в развивающихся странах",
        "Кибербезопасность в цифровую эпоху",
        "Перспективы развития возобновляемой энергетики",
        "Психологические аспекты дистанционного обучения",
        "Инновации в сельском хозяйстве",
        "Проблемы урбанизации и городского планирования",
        "Международное сотрудничество в сфере науки",
        "Финансовая грамотность населения",
    ],
    "en": [
        "The impact of artificial intelligence on modern education",
        "Climate change mitigation strategies in developing countries",
        "The role of social media in shaping public discourse",
        "Challenges and opportunities in renewable energy adoption",
        "Mental health implications of remote work and digital culture",
        "Ethical considerations in genetic engineering research",
        "The effectiveness of microfinance in poverty reduction",
        "Cybersecurity threats in the era of IoT",
        "Gender inequality in STEM fields: causes and solutions",
        "The future of urban transportation systems",
        "Food security challenges in a growing global population",
        "The influence of culture on business management practices",
        "Academic integrity in the age of generative AI",
        "Public health responses to global pandemics",
        "The economics of space exploration and commercialization",
    ],
}

# ── PROMPT SHABLONLAR ─────────────────────────────────────────

PROMPT_TEMPLATES = {
    "essay": {
        "uz": "'{topic}' mavzusida 500-700 so'zlik ilmiy maqola yozing. Kirish, asosiy qism (3-4 paragraf) va xulosa bo'lsin. Ilmiy uslubda yozing.",
        "ru": "Напишите научную статью на тему '{topic}' объёмом 500-700 слов. Включите введение, основную часть (3-4 абзаца) и заключение. Пишите в научном стиле.",
        "en": "Write an academic essay on '{topic}' of 500-700 words. Include an introduction, body (3-4 paragraphs), and conclusion. Use academic style.",
    },
    "thesis_intro": {
        "uz": "'{topic}' mavzusida dissertatsiya ishining kirish qismini yozing (400-600 so'z). Mavzuning dolzarbligi, tadqiqot maqsadi va vazifalari, ilmiy yangiligi haqida yozing.",
        "ru": "Напишите введение диссертации на тему '{topic}' (400-600 слов). Включите актуальность, цели и задачи исследования, научную новизну.",
        "en": "Write a thesis introduction on '{topic}' (400-600 words). Include relevance, research objectives, and scientific novelty.",
    },
    "course_work": {
        "uz": "'{topic}' mavzusida kurs ishining bir bobini yozing (500-800 so'z). Nazariy asoslar va adabiyotlar tahlili bo'lsin.",
        "ru": "Напишите главу курсовой работы на тему '{topic}' (500-800 слов). Включите теоретические основы и обзор литературы.",
        "en": "Write a chapter of a course paper on '{topic}' (500-800 words). Include theoretical background and literature review.",
    },
    "monograph_section": {
        "uz": "'{topic}' mavzusida monografiya bo'limini yozing (600-900 so'z). Chuqur ilmiy tahlil va misollar keltiring.",
        "ru": "Напишите раздел монографии на тему '{topic}' (600-900 слов). Включите глубокий научный анализ и примеры.",
        "en": "Write a monograph section on '{topic}' (600-900 words). Include deep scientific analysis and examples.",
    },
}

# Parafraz rejimlarini simulyatsiya qilish uchun promptlar
PARAPHRASE_PROMPTS = {
    "synonym_swap": "Quyidagi matnni sinonimlar bilan qayta yozing, lekin tuzilishni saqlang:\n\n{text}",
    "restructure": "Quyidagi matnni gap tuzilishini o'zgartirib qayta yozing, lekin ma'noni saqlang:\n\n{text}",
    "academic_tone": "Quyidagi matnni yanada rasmiy va ilmiy uslubda qayta yozing:\n\n{text}",
    "simplify": "Quyidagi matnni soddaroq tilda qayta yozing:\n\n{text}",
    "humanize": "Quyidagi matnni tabiiyroq, inson yozganday qayta yozing. Turli uzunlikdagi gaplar, savol va undov ishlating, ba'zan norasmiy iboralar qo'shing:\n\n{text}",
}


# ── YORDAMCHI FUNKSIYALAR ─────────────────────────────────────

def doc_hash(text: str) -> str:
    """Matn fingerprint — dublikat oldini olish."""
    return hashlib.md5(text.strip().lower()[:300].encode()).hexdigest()[:12]


def save_sample(
    category: str,    # "human", "ai/gpt4", "paraphrase/synonym", "mixed/50_50"
    lang: str,        # "uz", "ru", "en"
    text: str,
    metadata: dict,
) -> bool:
    """Labeled matnni saqlash."""
    if not text or len(text.split()) < 20:
        return False

    did = doc_hash(text)
    path = DATA_DIR / category / lang / f"{did}.json"

    if path.exists():
        return False  # Dublikat

    path.parent.mkdir(parents=True, exist_ok=True)

    sample = {
        "id": did,
        "text": text.strip(),
        "lang": lang,
        "category": category,
        "label": "human" if category.startswith("human") else "ai",
        "word_count": len(text.split()),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        **metadata,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)

    return True


def count_samples() -> dict:
    """Dataset statistikasi."""
    stats = {}
    if not DATA_DIR.exists():
        return {"total": 0}

    for cat_dir in sorted(DATA_DIR.rglob("*")):
        if not cat_dir.is_dir():
            continue
        jsons = list(cat_dir.glob("*.json"))
        if jsons:
            rel = str(cat_dir.relative_to(DATA_DIR))
            stats[rel] = len(jsons)

    stats["total"] = sum(stats.values())
    return stats


# ── AI MATN GENERATORLAR ──────────────────────────────────────

class OpenAIGenerator:
    """ChatGPT (GPT-4o / GPT-4 / GPT-3.5) dan matn olish."""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.client = None

    def _init(self):
        if self.client:
            return True
        if not self.api_key:
            print("  ⚠ OPENAI_API_KEY topilmadi (.env da o'rnating)")
            return False
        try:
            import openai
            self.client = openai.OpenAI(api_key=self.api_key)
            return True
        except ImportError:
            print("  ⚠ pip install openai")
            return False

    def generate(self, prompt: str, model: str = "gpt-4o-mini") -> Optional[str]:
        if not self._init():
            return None
        try:
            resp = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.7,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"  OpenAI xato: {e}")
            return None


class AnthropicGenerator:
    """Claude (Anthropic) dan matn olish."""

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.client = None

    def _init(self):
        if self.client:
            return True
        if not self.api_key:
            print("  ⚠ ANTHROPIC_API_KEY topilmadi")
            return False
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
            return True
        except ImportError:
            print("  ⚠ pip install anthropic")
            return False

    def generate(self, prompt: str, model: str = "claude-sonnet-4-20250514") -> Optional[str]:
        if not self._init():
            return None
        try:
            resp = self.client.messages.create(
                model=model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text.strip()
        except Exception as e:
            print(f"  Anthropic xato: {e}")
            return None


class GeminiGenerator:
    """Gemini (Google) dan matn olish."""

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY", "")
        self.model = None

    def _init(self):
        if self.model:
            return True
        if not self.api_key:
            print("  ⚠ GOOGLE_API_KEY topilmadi")
            return False
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
            return True
        except ImportError:
            print("  ⚠ pip install google-generativeai")
            return False

    def generate(self, prompt: str) -> Optional[str]:
        if not self._init():
            return None
        try:
            resp = self.model.generate_content(prompt)
            return resp.text.strip()
        except Exception as e:
            print(f"  Gemini xato: {e}")
            return None


class LocalParaphraser:
    """
    API siz parafraz simulyatsiya.

    QuillBot va Humanize AI o'rniga oddiy transformatsiyalar:
      1. Sinonim almashtirish (bir xil pattern)
      2. Gap tuzilishini o'zgartirish
      3. Passiv/aktiv ovoz almashtirish
      4. So'z tartibi o'zgartirish

    Bu real QuillBot output ga to'liq mos kelmaydi,
    lekin training data uchun foydali baseline beradi.
    """

    # Oddiy sinonim juftliklari
    SYNONYMS = {
        "en": {
            "important": "significant", "significant": "crucial",
            "use": "utilize", "utilize": "employ",
            "show": "demonstrate", "big": "substantial",
            "help": "facilitate", "make": "create",
            "good": "beneficial", "bad": "detrimental",
            "many": "numerous", "very": "highly",
            "fast": "rapid", "change": "transform",
            "think": "consider", "begin": "commence",
        },
        "uz": {
            "muhim": "ahamiyatli", "katta": "ulkan",
            "yangi": "zamonaviy", "ko'p": "ko'plab",
            "yaxshi": "samarali", "tez": "jadal",
            "rivojlanish": "taraqqiyot", "masala": "muammo",
            "oshirish": "ko'tarish", "yaratish": "shakllantirish",
        },
        "ru": {
            "важный": "значимый", "большой": "значительный",
            "новый": "современный", "использовать": "применять",
            "показать": "продемонстрировать", "помочь": "содействовать",
            "создать": "сформировать", "быстрый": "стремительный",
        },
    }

    def paraphrase_synonym(self, text: str, lang: str) -> str:
        """Sinonim almashtirish (QuillBot Standard simulyatsiya)."""
        syns = self.SYNONYMS.get(lang, self.SYNONYMS["en"])
        result = text
        for word, syn in syns.items():
            # ~50% ehtimollik bilan almashtirish (real QuillBot kabi)
            if random.random() > 0.5:
                result = re.sub(
                    rf"\b{re.escape(word)}\b",
                    syn,
                    result,
                    flags=re.IGNORECASE,
                    count=1,
                )
        return result

    def paraphrase_restructure(self, text: str, lang: str) -> str:
        """Gap tuzilishini o'zgartirish."""
        sents = re.split(r'(?<=[.!?])\s+', text.strip())
        result = []
        for sent in sents:
            words = sent.split()
            if len(words) > 10 and random.random() > 0.5:
                # Gapni 2 ga bo'lish
                mid = len(words) // 2
                part1 = " ".join(words[:mid]) + "."
                part2 = " ".join(words[mid:])
                if part2 and part2[0].islower():
                    part2 = part2[0].upper() + part2[1:]
                result.extend([part1, part2])
            else:
                result.append(sent)
        return " ".join(result)

    def humanize_basic(self, text: str, lang: str) -> str:
        """
        Oddiy humanizatsiya — burstiness va variatsiya qo'shish.

        Real humanizer kabi kuchli emas, lekin training data uchun foydali.
        """
        sents = re.split(r'(?<=[.!?])\s+', text.strip())
        result = []
        for i, sent in enumerate(sents):
            words = sent.split()
            # Har 3-4 jumladan keyin qisqa jumla qo'shish
            if i > 0 and i % random.randint(3, 5) == 0:
                fillers = {
                    "en": ["Right.", "Makes sense.", "Interesting.", "Well."],
                    "uz": ["To'g'ri.", "Qiziq.", "Ha.", "Albatta."],
                    "ru": ["Верно.", "Интересно.", "Да.", "Пожалуй."],
                }
                filler = random.choice(fillers.get(lang, fillers["en"]))
                result.append(filler)
            result.append(sent)
        return " ".join(result)


# ── MIXED CONTENT YARATISH ────────────────────────────────────

def create_mixed_text(human_text: str, ai_text: str, ratio: float = 0.5) -> str:
    """
    Inson va AI matnni aralashtirish.

    ratio: AI jumlalar nisbati (0.5 = 50% AI, 50% inson)
    """
    h_sents = re.split(r'(?<=[.!?])\s+', human_text.strip())
    a_sents = re.split(r'(?<=[.!?])\s+', ai_text.strip())

    if not h_sents or not a_sents:
        return human_text

    total = max(len(h_sents), len(a_sents))
    n_ai = int(total * ratio)
    n_human = total - n_ai

    # Tasodifiy tartibda aralashtirish
    selected = []
    h_idx = a_idx = 0
    for i in range(total):
        if i < n_ai and a_idx < len(a_sents):
            selected.append(a_sents[a_idx])
            a_idx += 1
        elif h_idx < len(h_sents):
            selected.append(h_sents[h_idx])
            h_idx += 1

    random.shuffle(selected)
    return " ".join(selected)


# ── INSON MATN YIG'ISH ───────────────────────────────────────

def collect_human_texts_local(target: int = 1000):
    """
    Mavjud dataset/data/ dan inson matnlarini nusxalash.
    Bu yerda allaqachon collector.py yig'gan matnlar bor.
    """
    source_dir = BASE_DIR / "dataset" / "data"
    if not source_dir.exists():
        source_dir = BASE_DIR.parent / "dataset" / "data"

    if not source_dir.exists():
        print(f"  ⚠ {source_dir} topilmadi")
        return 0

    saved = 0
    for lang_dir in source_dir.iterdir():
        if not lang_dir.is_dir():
            continue
        lang = lang_dir.name
        if lang not in ("uz", "ru", "en"):
            continue
        for f in lang_dir.glob("*.json"):
            if saved >= target:
                return saved
            try:
                with open(f, encoding="utf-8") as fh:
                    doc = json.load(fh)
                text = doc.get("text", "")
                if text and len(text.split()) >= 30:
                    ok = save_sample("human", lang, text, {
                        "source": doc.get("source", "local"),
                        "title": doc.get("title", f.stem),
                        "original_file": str(f.name),
                    })
                    if ok:
                        saved += 1
            except Exception:
                pass

    return saved


# ── ASOSIY PIPELINE ───────────────────────────────────────────

def run_ai_generation(target_per_model: int = 500):
    """Barcha AI modellardan matn generatsiya qilish."""
    generators = {
        "gpt4": OpenAIGenerator(),
        "claude": AnthropicGenerator(),
        "gemini": GeminiGenerator(),
    }

    paraphraser = LocalParaphraser()
    total_saved = 0

    for model_name, gen in generators.items():
        print(f"\n{'='*50}")
        print(f"Model: {model_name}")
        print(f"{'='*50}")

        saved_model = 0

        for lang, topics in TOPICS.items():
            for topic in topics:
                if saved_model >= target_per_model:
                    break

                for tmpl_name, templates in PROMPT_TEMPLATES.items():
                    if saved_model >= target_per_model:
                        break

                    prompt = templates[lang].format(topic=topic)
                    text = gen.generate(prompt)

                    if not text:
                        continue

                    # 1. Original AI matn
                    ok = save_sample(f"ai/{model_name}", lang, text, {
                        "model": model_name,
                        "template": tmpl_name,
                        "topic": topic,
                        "prompt": prompt[:200],
                    })
                    if ok:
                        saved_model += 1
                        total_saved += 1

                    # 2. Parafraz variantlar (API siz)
                    for method_name, method in [
                        ("synonym", paraphraser.paraphrase_synonym),
                        ("restructure", paraphraser.paraphrase_restructure),
                        ("humanize", paraphraser.humanize_basic),
                    ]:
                        para_text = method(text, lang)
                        save_sample(
                            f"paraphrase/{method_name}", lang, para_text,
                            {
                                "source_model": model_name,
                                "method": method_name,
                                "topic": topic,
                            },
                        )

                    time.sleep(DELAY)

                    # Progress
                    if saved_model % 10 == 0:
                        print(f"  {model_name}/{lang}: {saved_model}/{target_per_model}")

        print(f"  {model_name} jami: {saved_model} ta saqlandi")

    return total_saved


def run_mixed_generation(target: int = 500):
    """Mixed content yaratish (inson + AI aralashtirish)."""
    print("\nMixed content yaratish...")
    saved = 0

    # Human va AI matnlarni yuklash
    human_texts = {}
    ai_texts = {}

    for lang in ("uz", "ru", "en"):
        h_dir = DATA_DIR / "human" / lang
        a_dir = DATA_DIR / "ai" / "gpt4" / lang

        human_texts[lang] = []
        if h_dir.exists():
            for f in h_dir.glob("*.json"):
                try:
                    with open(f) as fh:
                        human_texts[lang].append(json.load(fh)["text"])
                except Exception:
                    pass

        ai_texts[lang] = []
        if a_dir.exists():
            for f in a_dir.glob("*.json"):
                try:
                    with open(f) as fh:
                        ai_texts[lang].append(json.load(fh)["text"])
                except Exception:
                    pass

    for lang in ("uz", "ru", "en"):
        h_list = human_texts.get(lang, [])
        a_list = ai_texts.get(lang, [])
        if not h_list or not a_list:
            continue

        for ratio in [0.3, 0.5, 0.7]:
            ratio_name = f"{int(ratio*100)}_{int((1-ratio)*100)}"
            for _ in range(min(target // 9, len(h_list), len(a_list))):
                h = random.choice(h_list)
                a = random.choice(a_list)
                mixed = create_mixed_text(h, a, ratio)
                ok = save_sample(f"mixed/{ratio_name}", lang, mixed, {
                    "ai_ratio": ratio,
                    "mix_type": ratio_name,
                })
                if ok:
                    saved += 1

    print(f"  Mixed: {saved} ta saqlandi")
    return saved


# ── DATASET TO TRAINING FORMAT ────────────────────────────────

def export_training_data(output_path: str = "training_data.jsonl"):
    """
    Datasetni training formatga eksport qilish.

    Format (JSONL):
      {"text": "...", "label": "human", "lang": "uz", "category": "human"}
      {"text": "...", "label": "ai", "lang": "en", "category": "ai/gpt4"}

    Ishlatish:
      HuggingFace datasets bilan yuklash mumkin
      Fine-tuning uchun tayyor format
    """
    out = Path(output_path)
    count = 0

    with open(out, "w", encoding="utf-8") as f:
        for json_file in DATA_DIR.rglob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as jf:
                    sample = json.load(jf)

                # Label normalizatsiya
                cat = sample.get("category", "")
                if cat.startswith("human"):
                    label = 0  # human
                elif cat.startswith("mixed"):
                    label = 0.5  # mixed (soft label)
                else:
                    label = 1  # ai

                row = {
                    "text": sample["text"],
                    "label": label,
                    "label_str": "human" if label == 0 else ("mixed" if label == 0.5 else "ai"),
                    "lang": sample.get("lang", "en"),
                    "category": cat,
                    "word_count": sample.get("word_count", len(sample["text"].split())),
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1

            except Exception:
                pass

    print(f"\n✅ Training data eksport: {count} ta → {out}")
    print(f"   Format: JSONL (HuggingFace datasets bilan mos)")

    # Statistika
    stats = {"human": 0, "ai": 0, "mixed": 0}
    lang_stats = {}
    with open(out, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            stats[row["label_str"]] = stats.get(row["label_str"], 0) + 1
            l = row["lang"]
            lang_stats[l] = lang_stats.get(l, 0) + 1

    print(f"   Balans: {stats}")
    print(f"   Tillar: {lang_stats}")

    return count


# ── CLI ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AntiplagiatPRO AI Detection Dataset Generator"
    )
    parser.add_argument("--collect-human", action="store_true",
                        help="Inson matnlarini yig'ish")
    parser.add_argument("--generate-ai", action="store_true",
                        help="AI matnlarini generatsiya")
    parser.add_argument("--paraphrase", action="store_true",
                        help="Parafraz variantlar yaratish")
    parser.add_argument("--mixed", action="store_true",
                        help="Mixed content yaratish")
    parser.add_argument("--export", action="store_true",
                        help="Training data eksport")
    parser.add_argument("--all", action="store_true",
                        help="To'liq pipeline")
    parser.add_argument("--stats", action="store_true",
                        help="Dataset statistikasi")
    parser.add_argument("--target", type=int, default=1000,
                        help="Maqsad matnlar soni (default: 1000)")

    args = parser.parse_args()

    # .env yuklash
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    if args.stats or (not any([
        args.collect_human, args.generate_ai, args.paraphrase,
        args.mixed, args.export, args.all
    ])):
        stats = count_samples()
        print("\n📊 Dataset statistikasi:")
        print(f"{'='*40}")
        for k, v in sorted(stats.items()):
            if k != "total":
                print(f"  {k:30s}  {v:>6d}")
        print(f"{'='*40}")
        print(f"  {'JAMI':30s}  {stats.get('total', 0):>6d}")
        return

    if args.all or args.collect_human:
        print("\n📥 Inson matnlarini yig'ish...")
        n = collect_human_texts_local(args.target)
        print(f"  ✅ {n} ta inson matni saqlandi")

    if args.all or args.generate_ai:
        print("\n🤖 AI matnlarini generatsiya...")
        n = run_ai_generation(args.target)
        print(f"  ✅ {n} ta AI matni saqlandi")

    if args.all or args.mixed:
        print("\n🔀 Mixed content yaratish...")
        n = run_mixed_generation(args.target)
        print(f"  ✅ {n} ta mixed matni saqlandi")

    if args.all or args.export:
        export_training_data()

    # Yakuniy statistika
    stats = count_samples()
    print(f"\n📊 Jami dataset: {stats.get('total', 0)} ta matn")


if __name__ == "__main__":
    main()
