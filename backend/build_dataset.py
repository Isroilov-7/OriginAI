#!/usr/bin/env python3
"""
AntiplagiatPRO — Local Dataset Builder (API kalitsiz)
=======================================================
API kalitlarsiz 5000+ labeled matn yaratadi:
  1. Inson matnlarni template + variatsiya bilan generatsiya
  2. AI matnlarni xarakteristik pattern bilan generatsiya
  3. Parafraz variantlar (sinonim swap, restructure)
  4. Mixed content (inson + AI aralash)

Ishlatish:
  python build_dataset.py              # 5000 ta matn
  python build_dataset.py --target 10000
  python build_dataset.py --retrain    # Dataset + qayta train

Mualliflik: AntiplagiatPRO © 2025-2026
"""

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "ai_detection_dataset"

# ═══════════════════════════════════════════════════════════════════════════════
#  INSON MATN GENERATSIYA (tabiiy uslub)
# ═══════════════════════════════════════════════════════════════════════════════

# Inson matni xususiyatlari: turli uzunlikdagi jumlalar, norasmiy uslub,
# savollar, undovlar, shaxsiy tajriba, grammatik xatolar

HUMAN_TEMPLATES_UZ = [
    # Talaba yozishlari
    [
        "{intro_casual_uz}",
        "{body_casual_uz}",
        "{opinion_uz}",
        "{ending_casual_uz}",
    ],
    # Forum/blog yozishlari
    [
        "{intro_blog_uz}",
        "{experience_uz}",
        "{reflection_uz}",
    ],
    # Oddiy suhbat uslubi
    [
        "{daily_uz}",
        "{story_uz}",
        "{conclusion_casual_uz}",
    ],
]

HUMAN_FRAGMENTS_UZ = {
    "intro_casual_uz": [
        "Bugun bir mavzu haqida o'ylab qoldim.",
        "Bilasizlarmi, {topic_short} haqida gap ketganda ko'pchilik noto'g'ri tushunadi.",
        "Kecha {topic_short} haqida video ko'rdim YouTubeda, qiziq narsa ekan.",
        "Men {topic_short} bilan ko'p shug'ullanganman, tajribamni bo'lishmoqchiman.",
        "Hamma {topic_short} haqida gapiradi lekin hech kim tushuntirmaydi.",
        "Rostini aytsam {topic_short} menga qiyin bo'lgan edi avvaliga.",
    ],
    "body_casual_uz": [
        "Gap shundaki, {topic_detail}. Bunga ko'pchilik e'tibor bermaydi. Lekin bu juda muhim narsa aslida.",
        "Mening fikrimcha {topic_detail}. Ha, boshqalar boshqacha o'ylashi mumkin, lekin men shunday deb o'ylayman.",
        "Bir narsani tushundim — {topic_detail}. Bu hamma uchun foydali bo'lishi mumkin, ayniqsa talabalar uchun.",
        "Aslida {topic_detail}. Buni tushunish qiyin emas, faqat biroz vaqt kerak. Men 2 haftada tushundim.",
    ],
    "opinion_uz": [
        "Menimcha bu to'g'ri yo'l. Balki xato bo'lishim mumkin, lekin hozircha shu fikrdaman.",
        "Nima desam ekan... Bu masala murakkab. Bir tomondan yaxshi, ikkinchi tomondan muammolar bor.",
        "Qisqasi, bu narsani o'rganish kerak. Vaqt bor ekan boshlang, keyin qiyin bo'ladi.",
        "Do'stlarim ham shunday deyishadi, demak men yolg'iz emasman bu fikrda))",
    ],
    "ending_casual_uz": [
        "Xullas, kim nima desa desin, men shu fikrdaman. Fikrlaringizni yozing!",
        "Savol bo'lsa yozing, yordam beraman imkon qadar.",
        "Shu haqida yana yozaman keyinroq. Hozircha shu.",
        "Agar foydali bo'lsa like bosing)) Rahmat o'qiganingiz uchun.",
    ],
    "intro_blog_uz": [
        "Salom hammaga! Bugun {topic_short} haqida yozmoqchiman.",
        "{topic_short} — bu hozirgi kunning eng dolzarb mavzularidan biri.",
        "Ko'pchilik so'raydi: {topic_short} nima o'zi? Keling tushuntirib beraman.",
    ],
    "experience_uz": [
        "O'zim shu soha bilan 3 yildan beri shug'ullanaman. Boshida hech narsa tushunmas edim, hatto asosiy tushunchalarni ham bilmasdim.",
        "Universitet davrida bu mavzuda kurs ishi yozgan edim. O'qituvchim aytgandi — yaxshi mavzu tanlabsan deb. Shu paytdan beri qiziqaman.",
        "Bir tanishim bor, u shu sohada ishlaydi. U aytadi — har kuni yangi narsa o'rganasan deb. Haqiqatan ham shunday ekan.",
    ],
    "reflection_uz": [
        "Endi o'ylab qarasam, o'sha paytda ko'p xato qilgan ekanman. Lekin xatolardan o'rganish — bu ham tajriba.",
        "Bilmasam ham bilaman derdim. Endi tushundimki bilmayman deb tan olish — bu kuchdir.",
        "Hayotda shunday narsalar borki, ularni faqat tajriba orqali o'rganasan. Kitobdan o'qib bo'lmaydi.",
    ],
    "daily_uz": [
        "Bugun ertalab turib choy ichdim, gazeta o'qidim... Keyin ishga bordim. Odatiy kun.",
        "Kecha oilam bilan birga ovqat yedik. Onam palov pishirdi — zo'r bo'ldi. Shunday kunlar yoqadi menga.",
        "Do'stim bilan kafe ga bordik. 2 soat gaplashdik turli mavzularda. Vaqt qanday o'tganini bilmadik.",
    ],
    "story_uz": [
        "Bir kuni shu narsa bo'lgan edi... {topic_short} bilan bog'liq voqea. Hali ham eslayman.",
        "O'tgan yili bir konferensiyada edim. U yerda {topic_short} haqida ma'ruza qilishdi. Juda qiziq edi.",
        "Maktab davridan eslayman — {topic_short} mavzusida birinchi marta referat yozgandim. 4 oldim))",
    ],
    "conclusion_casual_uz": [
        "Shu desam... Hayot davom etadi. Yangi narsalar o'rganamiz.",
        "Xulosa shuki — hech qachon o'rganishdan to'xtamang. Bu eng muhim narsa.",
        "Agar shu yozganlarim kimgadir foydali bo'lsa, maqsadimga yetdim demak.",
    ],
}

HUMAN_TEMPLATES_RU = [
    ["{intro_casual_ru}", "{body_casual_ru}", "{opinion_ru}", "{ending_casual_ru}"],
    ["{intro_blog_ru}", "{experience_ru}", "{reflection_ru}"],
]

HUMAN_FRAGMENTS_RU = {
    "intro_casual_ru": [
        "Сегодня задумался о {topic_short}. Странно, что раньше не обращал внимания.",
        "Знаете что? {topic_short} — это не так просто, как кажется на первый взгляд.",
        "Вчера наткнулся на статью про {topic_short}. Решил поделиться мыслями.",
        "Мой друг спросил меня про {topic_short}, и я понял что сам толком не знаю.",
    ],
    "body_casual_ru": [
        "Суть в том, что {topic_detail}. Многие это игнорируют, а зря. Я сам так делал раньше.",
        "По моему опыту {topic_detail}. Может я не прав, но пока думаю именно так.",
        "Главное что надо понять — {topic_detail}. Звучит просто, но на практике всё сложнее.",
    ],
    "opinion_ru": [
        "Как по мне — это правильный подход. Хотя кто-то может не согласиться.",
        "Честно говоря, не знаю точного ответа. Но склоняюсь к тому что это важно.",
        "Друзья говорят то же самое, так что видимо не только мне так кажется))",
    ],
    "ending_casual_ru": [
        "В общем, кто что думает — пишите. Интересно услышать другие мнения.",
        "На этом всё пока. Если будут вопросы — отвечу.",
        "Ладно, хватит философствовать)) Всем хорошего дня.",
    ],
    "intro_blog_ru": [
        "Привет всем! Сегодня поговорим о {topic_short}.",
        "Давно хотел написать про {topic_short}. Наконец дошли руки.",
    ],
    "experience_ru": [
        "Я этим занимаюсь уже пару лет. Сначала вообще ничего не понимал, даже базовые вещи были в новинку.",
        "В универе писал курсовую на эту тему. Препод сказал — тема хорошая. С тех пор интересуюсь.",
    ],
    "reflection_ru": [
        "Сейчас оглядываясь назад, понимаю сколько ошибок наделал. Но без них не научился бы.",
        "Раньше думал что всё знаю. Теперь понимаю — чем больше узнаёшь, тем больше не знаешь.",
    ],
}

HUMAN_TEMPLATES_EN = [
    ["{intro_casual_en}", "{body_casual_en}", "{opinion_en}", "{ending_casual_en}"],
    ["{intro_blog_en}", "{experience_en}", "{reflection_en}"],
]

HUMAN_FRAGMENTS_EN = {
    "intro_casual_en": [
        "So I've been thinking about {topic_short} lately. It's actually more interesting than I expected.",
        "You know what's funny? Everyone talks about {topic_short} but nobody really explains it properly.",
        "Yesterday I watched a video about {topic_short} and it blew my mind. Had to write about it.",
        "My friend asked me about {topic_short} and I realized I don't actually know that much about it.",
    ],
    "body_casual_en": [
        "Here's the thing — {topic_detail}. Most people don't pay attention to this, but it's actually really important.",
        "From what I've seen, {topic_detail}. I might be wrong, but that's my take on it for now.",
        "The way I see it, {topic_detail}. Simple to say, harder to do in practice though.",
    ],
    "opinion_en": [
        "Honestly? I think this is the right approach. Others might disagree and that's fine.",
        "I'm not 100% sure about this. But it feels right based on what I've experienced.",
        "My friends say the same thing so I guess it's not just me thinking this way lol.",
    ],
    "ending_casual_en": [
        "Anyway, what do you guys think? Would love to hear different perspectives.",
        "That's it for now. Hit me up if you have questions.",
        "Ok I'll stop rambling now haha. Thanks for reading if you made it this far!",
    ],
    "intro_blog_en": [
        "Hey everyone! Today I want to talk about {topic_short}.",
        "I've been meaning to write about {topic_short} for a while now. Finally getting around to it.",
    ],
    "experience_en": [
        "I've been into this for about 3 years now. At first I had no clue what I was doing, not gonna lie.",
        "Back in college I wrote a paper on this topic. My professor said it was a good choice. Been hooked since.",
    ],
    "reflection_en": [
        "Looking back, I made so many mistakes. But hey, that's how you learn right?",
        "I used to think I knew everything. Turns out the more you learn, the less you know. Funny how that works.",
    ],
}

# ═══════════════════════════════════════════════════════════════════════════════
#  AI MATN GENERATSIYA (formulaic, bir xil uslub)
# ═══════════════════════════════════════════════════════════════════════════════

AI_TEMPLATES_UZ = [
    [
        "Bugungi kunda {topic_formal} muhim ahamiyatga ega. Zamonaviy dunyoda bu masala tobora dolzarb bo'lib bormoqda.",
        "Shuningdek, {topic_detail_formal} ni ta'kidlash lozim. Bu jarayon bir qator ijobiy natijalarga olib kelmoqda.",
        "Shuni alohida qayd etish joizki, {topic_aspect} sohasida sezilarli yutuqlarga erishilgan. Bundan tashqari, innovatsion yondashuvlar samaradorlikni oshirmoqda.",
        "Xulosa qilib aytganda, {topic_formal} sohasidagi islohotlar jamiyat rivojlanishiga muhim hissa qo'shmoqda. Kelgusida bu yo'nalishda yanada kattaroq yutuqlarga erishilishi kutilmoqda.",
    ],
    [
        "{topic_formal} masalasi zamonaviy ilm-fan va amaliyotda keng o'rganilmoqda. Tadqiqotlar shuni ko'rsatadiki, bu sohada sezilarli o'zgarishlar kuzatilmoqda.",
        "Shuni ta'kidlash joizki, {topic_detail_formal} bo'yicha olib borilayotgan ishlar samarali natijalar bermoqda. Shu bilan birga, bir qator muammolar ham mavjud.",
        "Ilmiy adabiyotlar tahlili shuni ko'rsatadiki, {topic_aspect} sohasida turli xil yondashuvlar mavjud. Har bir yondashuvning o'ziga xos afzalliklari va kamchiliklari bor.",
        "Yuqoridagilardan kelib chiqib, {topic_formal} masalasiga kompleks yondashish zarurligini ta'kidlash lozim. Bu esa fan va amaliyot integratsiyasini talab etadi.",
    ],
]

AI_TEMPLATES_RU = [
    [
        "В современном мире {topic_formal} приобретает всё большую актуальность. Данная проблематика привлекает внимание исследователей и практиков.",
        "Необходимо отметить, что {topic_detail_formal} является важным аспектом рассматриваемой проблемы. Кроме того, следует подчеркнуть значимость комплексного подхода.",
        "Таким образом, анализ показывает, что {topic_aspect} требует дальнейшего изучения. Вместе с тем, достигнутые результаты свидетельствуют о положительной динамике.",
        "Подводя итоги, можно констатировать, что {topic_formal} остаётся актуальной задачей. В перспективе ожидается дальнейшее развитие данного направления.",
    ],
]

AI_TEMPLATES_EN = [
    [
        "In today's rapidly evolving world, {topic_formal} has emerged as a critical area of study. The significance of this topic cannot be overstated.",
        "Furthermore, it is worth noting that {topic_detail_formal} plays a pivotal role in shaping modern discourse. Additionally, recent developments have highlighted the importance of comprehensive approaches.",
        "Moreover, research indicates that {topic_aspect} represents a fundamental component of contemporary academic inquiry. The implications of these findings are far-reaching and multifaceted.",
        "In conclusion, {topic_formal} remains a vital area that demands continued attention and scholarly investigation. Moving forward, innovative approaches will be essential for addressing emerging challenges.",
    ],
]

# ── Mavzu ma'lumotlari ───────────────────────────────────────

TOPICS_DATA = {
    "uz": [
        {"topic_short": "sun'iy intellekt", "topic_formal": "sun'iy intellekt texnologiyalari", "topic_detail": "AI hamma joyda — telefondan tortib mashinagacha", "topic_detail_formal": "sun'iy intellekt tizimlarining zamonaviy ta'limga integratsiyasi", "topic_aspect": "mashinali o'rganish algoritmlari"},
        {"topic_short": "ta'lim tizimi", "topic_formal": "zamonaviy ta'lim tizimini isloh qilish", "topic_detail": "maktabda o'qitish usullari juda eskirgan", "topic_detail_formal": "ta'lim sifatini oshirishda innovatsion pedagogik texnologiyalar", "topic_aspect": "masofaviy ta'lim platformalari"},
        {"topic_short": "iqtisodiyot", "topic_formal": "milliy iqtisodiyotni modernizatsiya qilish", "topic_detail": "narxlar oshyapti lekin maosh o'sha-o'sha", "topic_detail_formal": "kichik biznes va tadbirkorlikni rivojlantirish strategiyalari", "topic_aspect": "raqamli iqtisodiyot infratuzilmasi"},
        {"topic_short": "ekologiya", "topic_formal": "ekologik muammolar va barqaror rivojlanish", "topic_detail": "havo iflosligi juda kuchaydi shaharlarida", "topic_detail_formal": "atrof-muhit muhofazasida zamonaviy texnologiyalarning roli", "topic_aspect": "iqlim o'zgarishiga moslashish"},
        {"topic_short": "sog'liqni saqlash", "topic_formal": "sog'liqni saqlash tizimini takomillashtirish", "topic_detail": "kasalxonalarda navbat 3 soat kutasan", "topic_detail_formal": "tibbiy xizmatlar sifatini oshirishda raqamli texnologiyalar", "topic_aspect": "teletibbiyot va masofaviy diagnostika"},
        {"topic_short": "yoshlar muammosi", "topic_formal": "yoshlar bandligini ta'minlash masalalari", "topic_detail": "universitet bitirasan lekin ish topolmaysan", "topic_detail_formal": "yoshlar orasida kasbiy ko'nikmalarni rivojlantirish dasturlari", "topic_aspect": "yoshlarning ijtimoiy faolligini oshirish"},
        {"topic_short": "raqamli texnologiya", "topic_formal": "raqamli transformatsiya jarayonlari", "topic_detail": "hamma narsa onlayn bo'lib ketdi", "topic_detail_formal": "davlat boshqaruvida elektron hukumat tizimlarining tatbiq etilishi", "topic_aspect": "axborot xavfsizligi va kiberhimoya"},
        {"topic_short": "qishloq xo'jaligi", "topic_formal": "qishloq xo'jaligida innovatsion texnologiyalar", "topic_detail": "dehqonchilik oson ish emas, bugun bilib oldim", "topic_detail_formal": "suv resurslarini samarali boshqarish metodlari", "topic_aspect": "organik dehqonchilik va oziq-ovqat xavfsizligi"},
        {"topic_short": "transport", "topic_formal": "transport infratuzilmasini modernizatsiya qilish", "topic_detail": "probka shaharning eng katta muammosi", "topic_detail_formal": "shahar transporti tizimini optimallashtirish yondashuvlari", "topic_aspect": "elektr transport vositalari"},
        {"topic_short": "madaniyat", "topic_formal": "milliy madaniy merosni asrash va tiklash", "topic_detail": "yoshlar o'z tarixini bilmaydi", "topic_detail_formal": "madaniy qadriyatlarni kelajak avlodlarga yetkazish strategiyalari", "topic_aspect": "raqamli muhitda madaniy identitetni saqlash"},
    ],
    "ru": [
        {"topic_short": "искусственный интеллект", "topic_formal": "технологии искусственного интеллекта", "topic_detail": "ИИ сейчас везде — от телефона до машины", "topic_detail_formal": "интеграция систем искусственного интеллекта в образование", "topic_aspect": "алгоритмы машинного обучения"},
        {"topic_short": "образование", "topic_formal": "реформирование системы образования", "topic_detail": "методы преподавания устарели", "topic_detail_formal": "инновационные педагогические технологии", "topic_aspect": "платформы дистанционного обучения"},
        {"topic_short": "экономика", "topic_formal": "модернизация национальной экономики", "topic_detail": "цены растут а зарплата нет", "topic_detail_formal": "стратегии развития малого бизнеса", "topic_aspect": "цифровая экономика"},
        {"topic_short": "экология", "topic_formal": "экологические проблемы и устойчивое развитие", "topic_detail": "загрязнение воздуха в городах ужасное", "topic_detail_formal": "роль технологий в охране окружающей среды", "topic_aspect": "адаптация к изменению климата"},
        {"topic_short": "здравоохранение", "topic_formal": "совершенствование системы здравоохранения", "topic_detail": "в больницах очереди по 3 часа", "topic_detail_formal": "цифровые технологии в медицине", "topic_aspect": "телемедицина и дистанционная диагностика"},
    ],
    "en": [
        {"topic_short": "artificial intelligence", "topic_formal": "artificial intelligence technologies", "topic_detail": "AI is literally everywhere now — phones, cars, you name it", "topic_detail_formal": "the integration of AI systems into modern education", "topic_aspect": "machine learning algorithms"},
        {"topic_short": "education system", "topic_formal": "modern education system reform", "topic_detail": "teaching methods in schools are so outdated", "topic_detail_formal": "innovative pedagogical technologies for quality enhancement", "topic_aspect": "distance learning platforms"},
        {"topic_short": "the economy", "topic_formal": "national economic modernization", "topic_detail": "prices keep going up but salaries dont", "topic_detail_formal": "strategies for small business development", "topic_aspect": "digital economy infrastructure"},
        {"topic_short": "the environment", "topic_formal": "environmental challenges and sustainable development", "topic_detail": "air pollution in cities is getting crazy bad", "topic_detail_formal": "the role of modern technologies in environmental protection", "topic_aspect": "climate change adaptation strategies"},
        {"topic_short": "healthcare", "topic_formal": "healthcare system improvement", "topic_detail": "waiting 3 hours at the hospital is ridiculous", "topic_detail_formal": "digital technologies in improving healthcare quality", "topic_aspect": "telemedicine and remote diagnostics"},
    ],
}


def _fill_template(template_str: str, topic: dict) -> str:
    """Template ichiga mavzu ma'lumotlarini qo'yish."""
    result = template_str
    for key, val in topic.items():
        result = result.replace("{" + key + "}", val)
    return result


def _fill_fragments(template_list: list, fragments: dict, topic: dict) -> str:
    """Fragment ro'yxatidan matn yaratish."""
    parts = []
    for tmpl in template_list:
        # {fragment_name} ni tanlash
        match = re.match(r"\{(\w+)\}", tmpl)
        if match:
            key = match.group(1)
            if key in fragments:
                chosen = random.choice(fragments[key])
                parts.append(_fill_template(chosen, topic))
            else:
                parts.append(_fill_template(tmpl, topic))
        else:
            parts.append(_fill_template(tmpl, topic))
    return " ".join(parts)


def _add_human_noise(text: str, lang: str) -> str:
    """Inson matnga tabiiy shovqin qo'shish."""
    sents = re.split(r'(?<=[.!?])\s+', text)
    result = []
    for i, s in enumerate(sents):
        # Ba'zan qisqa jumla qo'shish
        if random.random() < 0.15:
            fillers = {
                "uz": ["Ha.", "To'g'ri.", "Qiziq.", "Hmm.", "Nima desam ekan...", "Bir so'z bilan aytganda."],
                "ru": ["Да.", "Верно.", "Хм.", "Ну вот.", "Короче.", "Как бы сказать..."],
                "en": ["Yeah.", "Right.", "Hmm.", "Honestly.", "I mean.", "Like."],
            }
            result.append(random.choice(fillers.get(lang, fillers["en"])))
        result.append(s)

    # Ba'zan so'roq yoki undov qo'shish
    if random.random() < 0.2:
        questions = {
            "uz": ["Nima deysiz?", "Siz qanday o'ylaysiz?", "To'g'rimi?"],
            "ru": ["Как думаете?", "Правда ведь?", "Согласны?"],
            "en": ["Right?", "What do you think?", "Makes sense?"],
        }
        result.append(random.choice(questions.get(lang, questions["en"])))

    return " ".join(result)


def generate_human_text(lang: str) -> str:
    """Inson uslubida matn generatsiya."""
    topics = TOPICS_DATA[lang]
    topic = random.choice(topics)

    if lang == "uz":
        tmpl = random.choice(HUMAN_TEMPLATES_UZ)
        text = _fill_fragments(tmpl, HUMAN_FRAGMENTS_UZ, topic)
    elif lang == "ru":
        tmpl = random.choice(HUMAN_TEMPLATES_RU)
        text = _fill_fragments(tmpl, HUMAN_FRAGMENTS_RU, topic)
    else:
        tmpl = random.choice(HUMAN_TEMPLATES_EN)
        text = _fill_fragments(tmpl, HUMAN_FRAGMENTS_EN, topic)

    return _add_human_noise(text, lang)


def generate_ai_text(lang: str) -> str:
    """AI uslubida matn generatsiya (formulaic, bir xil)."""
    topics = TOPICS_DATA[lang]
    topic = random.choice(topics)

    if lang == "uz":
        tmpl = random.choice(AI_TEMPLATES_UZ)
    elif lang == "ru":
        tmpl = random.choice(AI_TEMPLATES_RU)
    else:
        tmpl = random.choice(AI_TEMPLATES_EN)

    parts = [_fill_template(s, topic) for s in tmpl]
    return " ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
#  PARAFRAZ VA MIXED
# ═══════════════════════════════════════════════════════════════════════════════

SYNONYMS = {
    "uz": [("muhim", "ahamiyatli"), ("katta", "ulkan"), ("yangi", "zamonaviy"),
           ("rivojlanish", "taraqqiyot"), ("masala", "muammo"), ("oshirish", "ko'tarish"),
           ("yaratish", "shakllantirish"), ("samarali", "natijali"), ("ko'p", "ko'plab")],
    "ru": [("важный", "значимый"), ("большой", "значительный"), ("новый", "современный"),
           ("показать", "продемонстрировать"), ("создать", "сформировать")],
    "en": [("important", "significant"), ("use", "utilize"), ("show", "demonstrate"),
           ("big", "substantial"), ("help", "facilitate"), ("make", "create")],
}


def paraphrase_text(text: str, lang: str) -> str:
    """Sinonim almashtirish bilan parafraz."""
    result = text
    for old, new in SYNONYMS.get(lang, []):
        if random.random() > 0.4:
            result = re.sub(rf"\b{re.escape(old)}\b", new, result, count=1, flags=re.I)
    return result


def create_mixed(human_text: str, ai_text: str) -> str:
    """50/50 aralash matn."""
    h_sents = re.split(r'(?<=[.!?])\s+', human_text)
    a_sents = re.split(r'(?<=[.!?])\s+', ai_text)
    combined = []
    for i in range(max(len(h_sents), len(a_sents))):
        if i < len(h_sents) and random.random() > 0.5:
            combined.append(h_sents[i])
        if i < len(a_sents) and random.random() > 0.5:
            combined.append(a_sents[i])
    return " ".join(combined) if combined else human_text


# ═══════════════════════════════════════════════════════════════════════════════
#  SAQLASH VA PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def save(category: str, lang: str, text: str, meta: dict = None) -> bool:
    """Matnni saqlash."""
    if not text or len(text.split()) < 15:
        return False
    did = hashlib.md5(text.strip()[:300].encode()).hexdigest()[:12]
    path = DATA_DIR / category / lang / f"{did}.json"
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    label = "human" if "human" in category else "ai"
    doc = {
        "id": did, "text": text.strip(), "lang": lang,
        "category": category, "label": label,
        "word_count": len(text.split()),
        **(meta or {}),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return True


def build_dataset(target: int = 5000):
    """To'liq dataset yaratish."""
    t0 = time.time()
    per_type = target // 10  # har bir tip uchun

    stats = {"human": 0, "ai": 0, "paraphrase": 0, "mixed": 0}

    for lang in ("uz", "ru", "en"):
        print(f"\n{'='*40}")
        print(f"Til: {lang.upper()}")
        print(f"{'='*40}")

        # 1. Inson matnlari
        for i in range(per_type):
            text = generate_human_text(lang)
            if save(f"human/{lang}_gen", lang, text):
                stats["human"] += 1

        # 2. AI matnlari
        for i in range(per_type):
            text = generate_ai_text(lang)
            if save(f"ai/local_gen", lang, text):
                stats["ai"] += 1

        # 3. Parafraz (AI → paraphrase)
        for i in range(per_type // 2):
            ai_text = generate_ai_text(lang)
            para = paraphrase_text(ai_text, lang)
            if save("paraphrase/synonym", lang, para):
                stats["paraphrase"] += 1

        # 4. Mixed
        for i in range(per_type // 3):
            h = generate_human_text(lang)
            a = generate_ai_text(lang)
            m = create_mixed(h, a)
            if save("mixed/50_50", lang, m):
                stats["mixed"] += 1

        print(f"  Human: {stats['human']}, AI: {stats['ai']}, Para: {stats['paraphrase']}, Mixed: {stats['mixed']}")

    elapsed = time.time() - t0
    total = sum(stats.values())
    print(f"\n{'='*40}")
    print(f"YAKUNLANDI: {total} ta matn, {elapsed:.1f} soniya")
    print(f"  Human:     {stats['human']}")
    print(f"  AI:        {stats['ai']}")
    print(f"  Paraphrase:{stats['paraphrase']}")
    print(f"  Mixed:     {stats['mixed']}")
    print(f"{'='*40}")

    return total


def export_jsonl(output: str = "training_data.jsonl"):
    """Training formatga eksport."""
    count = 0
    with open(DATA_DIR.parent / output, "w", encoding="utf-8") as f:
        for jf in DATA_DIR.rglob("*.json"):
            try:
                with open(jf) as fh:
                    d = json.load(fh)
                cat = d.get("category", "")
                label = 0 if "human" in cat else (0.5 if "mixed" in cat else 1)
                f.write(json.dumps({
                    "text": d["text"], "label": label,
                    "label_str": "human" if label == 0 else ("mixed" if label == 0.5 else "ai"),
                    "lang": d.get("lang", "en"), "category": cat,
                }, ensure_ascii=False) + "\n")
                count += 1
            except Exception:
                pass
    print(f"✅ Eksport: {count} ta → {output}")
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=5000)
    parser.add_argument("--retrain", action="store_true", help="Dataset + qayta train")
    args = parser.parse_args()

    n = build_dataset(args.target)
    export_jsonl()

    if args.retrain:
        print("\n🔄 Model qayta train qilinmoqda...")
        os.system(f"python {BASE_DIR / 'train_classifier.py'} --samples 3000")
