"""
AntiplagiatPRO — Trained Feature Classifier (2-qatlam kuchaytirilgan)
=====================================================================
Muammo: HuggingFace modellar yuklanmasligi mumkin (network, GPU yo'q).
Yechim: 27 ta feature ustida sklearn ensemble — 100% lokal, <10ms inference.

Bu modul:
  1. AI vs Human matnlarni ajratuvchi training dataset yaratadi
  2. XGBoost + RandomForest + LogReg ensemble train qiladi
  3. Trained modelni pickle bilan saqlaydi
  4. ai_detector.py dagi transformer o'rnini bosadi

Ishlash tartibi:
  python train_classifier.py          # Train + saqlash
  python train_classifier.py --test   # Test qilish

ai_detector.py bilan integratsiya:
  from train_classifier import FeatureClassifier
  clf = FeatureClassifier.load()
  prob = clf.predict(feature_vector)   # 0.0-1.0
"""

from __future__ import annotations

import json
import os
import pickle
import re
import sys
import time
from pathlib import Path

import numpy as np

# ai_detector.py dan import
sys.path.insert(0, str(Path(__file__).parent))
from ai_detector import (
    extract_features,
    features_to_vector,
    FEATURE_NAMES,
    _split_sentences,
)

MODEL_PATH = Path(__file__).parent / "models" / "feature_classifier.pkl"


# ═══════════════════════════════════════════════════════════════════════════════
#  SYNTHETIC TRAINING DATA — AI vs HUMAN xususiyatlari
# ═══════════════════════════════════════════════════════════════════════════════

# Real matnlardan olingan va kalibratsiya qilingan statistik profillar.
# Har bir profil 27 ta feature uchun (mean, std) juftlik.
# Bu profillardan 10K+ sintetik namuna generatsiya qilinadi.

AI_PROFILE = {
    # AI matn xususiyatlari (GPT-4, Claude, Gemini o'rtachasi)
    "sent_len_mean":     (20.5, 2.5),    # 18-23 so'z, bir xil
    "sent_len_std":      (3.2, 1.5),     # Past variatsiya
    "sent_len_min":      (12.0, 3.0),
    "sent_len_max":      (30.0, 5.0),
    "sent_len_range":    (18.0, 6.0),
    "burstiness":        (0.16, 0.08),   # Past — eng kuchli signal
    "artificial_burst":  (0.05, 0.04),   # Past (humanizer bo'lmasa)
    "ttr":               (0.88, 0.08),   # Real: 0.88-0.98 (qisqa matnlarda yuqori)
    "mattr":             (0.72, 0.08),
    "word_len_mean":     (5.8, 0.7),     # Uzunroq so'zlar
    "word_len_std":      (3.2, 0.5),
    "connector_density": (0.55, 0.25),   # Real: 0.5-0.8 — yuqori
    "hedging_density":   (0.02, 0.03),   # Real: 0.0 — juda past
    "certainty_density": (0.08, 0.08),   # O'rtacha
    "formulaic_count":   (2.0, 1.5),     # Ko'p — "it is worth noting"...
    "formulaic_density": (0.40, 0.25),   # Real: 0.2-0.75
    "passive_ratio":     (0.15, 0.12),   # Real: 0.0-0.25
    "question_ratio":    (0.02, 0.03),   # Past — savol kam
    "exclamation_ratio": (0.01, 0.01),   # Past
    "para_uniformity":   (0.80, 0.10),   # Yuqori — bir xil paragraflar
    "intro_concl_sim":   (0.25, 0.12),   # Yuqori — kirish=xulosa
    "repeated_trigram_ratio": (0.08, 0.05),
    "contraction_ratio": (0.005, 0.005), # Past — to'liq shakl
    "start_repetition":  (0.20, 0.10),
    "uz_apostrophe_error":    (0.08, 0.06),
    "uz_hisoblanadi_density": (0.15, 0.10),
    "uz_template_starts":     (0.20, 0.15),
}

HUMAN_PROFILE = {
    # Inson matni xususiyatlari
    "sent_len_mean":     (16.0, 5.0),    # Turli xil uzunlik
    "sent_len_std":      (8.5, 3.0),     # YUQORI variatsiya
    "sent_len_min":      (4.0, 3.0),     # Ba'zan juda qisqa
    "sent_len_max":      (38.0, 10.0),   # Ba'zan juda uzun
    "sent_len_range":    (34.0, 12.0),   # Katta farq
    "burstiness":        (0.35, 0.15),   # Real: 0.26-0.35 — tabiiy
    "artificial_burst":  (0.20, 0.18),   # Real: 0.0-0.39 — qisqa matnlarda yuqori bo'lishi mumkin!
    "ttr":               (0.92, 0.06),   # Real: 0.80-0.96 — yuqori (qisqa matnlarda)
    "mattr":             (0.75, 0.08),
    "word_len_mean":     (4.8, 0.8),     # Qisqaroq so'zlar
    "word_len_std":      (2.8, 0.6),
    "connector_density": (0.05, 0.08),   # Real: 0.0 — past
    "hedging_density":   (0.05, 0.08),   # Real: 0.0 — qisqa matnlarda kam
    "certainty_density": (0.02, 0.03),   # Past
    "formulaic_count":   (0.1, 0.3),     # Kam
    "formulaic_density": (0.02, 0.05),   # Real: 0.0
    "passive_ratio":     (0.03, 0.06),   # Real: 0.0 — past
    "question_ratio":    (0.06, 0.07),   # Real: 0.0-0.11
    "exclamation_ratio": (0.05, 0.05),   # YUQORI
    "para_uniformity":   (0.50, 0.20),   # Past — turli paragraflar
    "intro_concl_sim":   (0.08, 0.08),   # Past
    "repeated_trigram_ratio": (0.03, 0.03),
    "contraction_ratio": (0.02, 0.015),  # Yuqori — don't, isn't
    "start_repetition":  (0.10, 0.08),
    "uz_apostrophe_error":    (0.01, 0.02),
    "uz_hisoblanadi_density": (0.03, 0.04),
    "uz_template_starts":     (0.05, 0.06),
}

# Humanized AI profili — eng qiyin holat
HUMANIZED_PROFILE = {
    "sent_len_mean":     (17.5, 4.0),
    "sent_len_std":      (6.5, 2.5),     # Sun'iy oshirilgan
    "sent_len_min":      (5.0, 3.0),
    "sent_len_max":      (35.0, 8.0),
    "sent_len_range":    (30.0, 10.0),
    "burstiness":        (0.38, 0.12),   # Sun'iy oshirilgan (lekin periodlik)
    "artificial_burst":  (0.28, 0.12),   # YUQORI — periodiklik belgisi!
    "ttr":               (0.58, 0.10),
    "mattr":             (0.58, 0.07),
    "word_len_mean":     (5.3, 0.7),
    "word_len_std":      (3.0, 0.5),
    "connector_density": (0.30, 0.18),   # O'rtacha — bir qismi o'chirilgan
    "hedging_density":   (0.10, 0.08),   # Sun'iy kiritilgan
    "certainty_density": (0.08, 0.06),
    "formulaic_count":   (1.0, 1.0),
    "formulaic_density": (0.18, 0.15),
    "passive_ratio":     (0.20, 0.12),
    "question_ratio":    (0.05, 0.05),
    "exclamation_ratio": (0.03, 0.03),
    "para_uniformity":   (0.65, 0.15),
    "intro_concl_sim":   (0.15, 0.10),
    "repeated_trigram_ratio": (0.05, 0.04),
    "contraction_ratio": (0.01, 0.01),
    "start_repetition":  (0.15, 0.08),
    "uz_apostrophe_error":    (0.05, 0.05),
    "uz_hisoblanadi_density": (0.08, 0.07),
    "uz_template_starts":     (0.10, 0.10),
}


def generate_synthetic_samples(
    profile: dict, n: int, label: int, noise: float = 0.1
) -> tuple:
    """
    Profildan sintetik feature vektorlar generatsiya qilish.

    noise: qo'shimcha tasodifiy shovqin (0.0-0.3)
    """
    X = []
    for _ in range(n):
        vec = []
        for fname in FEATURE_NAMES:
            mean, std = profile.get(fname, (0.5, 0.1))
            val = np.random.normal(mean, std * (1 + noise * np.random.random()))
            val = max(0, val)  # Manfiy bo'lmasin
            vec.append(val)
        X.append(vec)
    y = [label] * n
    return np.array(X), np.array(y)


# ═══════════════════════════════════════════════════════════════════════════════
#  FEATURE CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════════════

class FeatureClassifier:
    """
    27-feature asosida AI/Human classifier.

    Ensemble:
      1. XGBoost (nonlinear patterns, feature interactions)
      2. RandomForest (robust, overfitting ga chidamli)
      3. LogisticRegression (interpretable baseline)

    Voting: soft (ehtimolliklar o'rtachasi)
    """

    def __init__(self):
        self.model = None
        self.scaler = None
        self.trained = False
        self.metrics = {}

    def train(self, n_samples: int = 5000):
        """
        Sintetik dataset ustida train qilish.

        n_samples: har bir klass uchun namunalar soni
        """
        from sklearn.ensemble import (
            RandomForestClassifier,
            VotingClassifier,
            GradientBoostingClassifier,
        )
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import cross_val_score

        try:
            from xgboost import XGBClassifier
            has_xgb = True
        except ImportError:
            has_xgb = False

        print(f"Training dataset generatsiya: {n_samples} x 3 klass...")
        t0 = time.time()

        # 3 klass: human (0), humanized_ai (1), pure_ai (1)
        # Humanized ham AI sifatida label lanadi, lekin boshqa profil
        X_human, y_human = generate_synthetic_samples(HUMAN_PROFILE, n_samples, 0)
        X_ai, y_ai = generate_synthetic_samples(AI_PROFILE, n_samples, 1)
        X_hum, y_hum = generate_synthetic_samples(HUMANIZED_PROFILE, n_samples // 2, 1)

        # Turli noise levellari bilan augmentatsiya
        X_ai_noisy, y_ai_noisy = generate_synthetic_samples(
            AI_PROFILE, n_samples // 3, 1, noise=0.25
        )
        X_human_noisy, y_human_noisy = generate_synthetic_samples(
            HUMAN_PROFILE, n_samples // 3, 0, noise=0.25
        )

        X = np.vstack([X_human, X_ai, X_hum, X_ai_noisy, X_human_noisy])
        y = np.concatenate([y_human, y_ai, y_hum, y_ai_noisy, y_human_noisy])

        # Shuffle
        idx = np.random.permutation(len(X))
        X, y = X[idx], y[idx]

        print(f"  Dataset: {len(X)} namuna ({(y==0).sum()} human, {(y==1).sum()} ai)")

        # Scale
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # Ensemble
        estimators = [
            ("rf", RandomForestClassifier(
                n_estimators=200, max_depth=12, min_samples_leaf=5,
                random_state=42, n_jobs=-1
            )),
            ("lr", LogisticRegression(C=1.0, max_iter=1000, random_state=42)),
            ("gb", GradientBoostingClassifier(
                n_estimators=150, max_depth=6, learning_rate=0.1,
                random_state=42
            )),
        ]

        if has_xgb:
            estimators.append(("xgb", XGBClassifier(
                n_estimators=200, max_depth=8, learning_rate=0.1,
                eval_metric="logloss", random_state=42,
                use_label_encoder=False,
            )))

        self.model = VotingClassifier(estimators, voting="soft", n_jobs=-1)

        # Cross-validation
        print("  Cross-validation (5-fold)...")
        cv_scores = cross_val_score(self.model, X_scaled, y, cv=5, scoring="accuracy")
        print(f"  CV accuracy: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")

        # Final train
        print("  Final training...")
        self.model.fit(X_scaled, y)
        self.trained = True

        # Feature importance (RandomForest dan)
        rf = self.model.named_estimators_["rf"]
        importances = rf.feature_importances_
        top_features = sorted(
            zip(FEATURE_NAMES, importances), key=lambda x: -x[1]
        )[:10]

        train_time = time.time() - t0
        self.metrics = {
            "cv_accuracy": round(float(cv_scores.mean()), 4),
            "cv_std": round(float(cv_scores.std()), 4),
            "n_samples": len(X),
            "n_features": len(FEATURE_NAMES),
            "train_time_s": round(train_time, 2),
            "top_features": [(f, round(float(v), 4)) for f, v in top_features],
        }

        print(f"\n  Training yakunlandi: {train_time:.1f}s")
        print(f"  Accuracy: {self.metrics['cv_accuracy']*100:.1f}%")
        print(f"\n  Top 10 feature (eng muhim):")
        for fname, imp in top_features:
            bar = "█" * int(imp * 100)
            print(f"    {fname:28s} {imp:.4f}  {bar}")

        return self.metrics

    def predict(self, feature_vector: np.ndarray) -> float:
        """
        AI ehtimollik qaytarish (0.0 — inson, 1.0 — AI).

        feature_vector: 27 ta feature (features_to_vector() dan)
        """
        if not self.trained or self.model is None:
            return 0.5

        vec = feature_vector.reshape(1, -1)
        vec_scaled = self.scaler.transform(vec)
        prob = self.model.predict_proba(vec_scaled)[0][1]
        return float(prob)

    def predict_from_text(self, text: str, lang: str = "en") -> float:
        """Matndan to'g'ridan-to'g'ri predict."""
        features = extract_features(text, lang)
        vec = features_to_vector(features)
        return self.predict(vec)

    def save(self, path: str = None):
        """Trained modelni saqlash."""
        p = Path(path or MODEL_PATH)
        p.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "model": self.model,
            "scaler": self.scaler,
            "metrics": self.metrics,
            "feature_names": FEATURE_NAMES,
            "version": "2.0",
        }
        with open(p, "wb") as f:
            pickle.dump(data, f)

        size_kb = p.stat().st_size / 1024
        print(f"\n  Model saqlandi: {p} ({size_kb:.0f} KB)")

    @classmethod
    def load(cls, path: str = None) -> "FeatureClassifier":
        """Saqlangan modelni yuklash."""
        p = Path(path or MODEL_PATH)
        if not p.exists():
            raise FileNotFoundError(f"Model topilmadi: {p}")

        with open(p, "rb") as f:
            data = pickle.load(f)

        obj = cls()
        obj.model = data["model"]
        obj.scaler = data["scaler"]
        obj.metrics = data.get("metrics", {})
        obj.trained = True
        return obj


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI: TRAIN VA TEST
# ═══════════════════════════════════════════════════════════════════════════════

def run_full_test():
    """Trained model bilan to'liq test."""

    print("\n" + "=" * 60)
    print("MODEL YUKLASH VA TEST")
    print("=" * 60)

    try:
        clf = FeatureClassifier.load()
        print(f"Model yuklandi: {MODEL_PATH}")
        print(f"Metrics: {clf.metrics.get('cv_accuracy', '?')}")
    except FileNotFoundError:
        print("Model topilmadi — avval train qiling!")
        return

    test_cases = [
        ("AI EN", "en", "Artificial intelligence has fundamentally transformed the landscape of modern technology. Furthermore, the integration of machine learning algorithms into various sectors has significantly enhanced operational efficiency. Additionally, the development of natural language processing capabilities has revolutionized how humans interact with computational systems. It is worth noting that these advancements have also raised important ethical considerations that must be carefully addressed. Moreover, the rapid pace of innovation continues to present both opportunities and challenges for society as a whole."),

        ("Human EN", "en", "I tried using AI for my essay last week and honestly? It was weird. The text looked perfect — too perfect, actually. Every sentence was about the same length, like a robot wrote it. Which, I guess, it did. My professor would definitely notice something was off. So I scrapped it and just wrote the damn thing myself. Took longer, sure, but at least it sounds like me. With all my run-on sentences and questionable comma usage."),

        ("AI UZ", "uz", "Bugungi kunda zamonaviy axborot texnologiyalari barcha sohalarda keng qo'llanilmoqda. Shuningdek, sun'iy intellekt tizimlarining rivojlanishi iqtisodiyot va ta'lim sohasida muhim ahamiyatga ega. Shuni ta'kidlash joizki, raqamli texnologiyalarning jamiyatga ta'siri kun sayin ortib bormoqda. Bundan tashqari, ilmiy tadqiqotlar shuni ko'rsatadiki, innovatsion yondashuvlar samaradorlikni sezilarli darajada oshiradi."),

        ("Human UZ", "uz", "Kecha kursga borib berdim lekin hech narsa tushunmadim. O'qituvchi shunday tez gapirdiki... Keyin do'stlarimdan so'radim, ular ham tushunmagan ekan. Uyga kelib YouTubedan qaradim — o'sha mavzuni boshqa odam tushuntirgan, ancha oson ekan. Endi imtihonga tayyorlanishim kerak, 3 kunim qoldi. Qo'rqyapman bir oz, lekin harakat qilaman inshaalloh."),

        ("AI RU", "ru", "В современном мире информационные технологии играют важную роль во всех сферах жизни общества. Необходимо отметить, что развитие искусственного интеллекта существенно повлияло на экономические процессы. Кроме того, цифровизация образования открывает новые перспективы для повышения качества обучения. Таким образом, комплексный подход к внедрению инновационных технологий является ключевым фактором устойчивого развития."),

        ("Human RU", "ru", "Вчера сидел до трёх ночи — пытался разобраться с курсовой. Вроде тема простая, но как начну писать — всё из головы вылетает. Позвонил однокурснику, он говорит \"я вообще ещё не начинал\". Ну хоть не один такой)) Ладно, сегодня попробую ещё раз, может кофе поможет."),

        ("Mixed", "en", "Artificial intelligence has fundamentally transformed the landscape of modern technology. Furthermore, the integration of machine learning algorithms has significantly enhanced efficiency. But honestly I still dont get why everyone is so hyped about it. My friend tried ChatGPT for his homework and got caught lol. The professor knew right away because every sentence was the same length. Moreover, the development of natural language processing continues to present important challenges."),

        ("Akademik UZ", "uz", "Tadqiqotning maqsadi zamonaviy pedagogik texnologiyalarning ta'lim samaradorligiga ta'sirini o'rganishdan iborat. Tadqiqot doirasida 200 nafar talaba ishtirok etdi. Natijalar shuni ko'rsatdiki, innovatsion usullar qo'llanilgan guruhda o'zlashtirish 15% ga oshgan. Shu bilan birga, an'anaviy usullar ham o'z samaradorligini saqlab qolmoqda."),
    ]

    print(f"\n{'Test':14s}  {'AI%':>6s}  {'Natija':30s}  {'Kutilgan'}")
    print("-" * 75)

    for name, lang, text in test_cases:
        prob = clf.predict_from_text(text, lang)
        pct = prob * 100
        verdict = (
            "AI tomonidan yozilgan" if pct >= 65
            else "Shubhali" if pct >= 38
            else "Inson yozgan"
        )
        expected = "AI" if "AI" in name or "Akademik" in name else ("Mixed" if "Mixed" in name else "Human")
        ok = "✅" if (
            (expected == "AI" and pct >= 55) or
            (expected == "Human" and pct < 40) or
            (expected == "Mixed" and 35 <= pct <= 70)
        ) else "❌"

        print(f"{name:14s}  {pct:5.1f}%  {verdict:30s}  {expected:8s} {ok}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--samples", type=int, default=5000)
    args = parser.parse_args()

    if args.test:
        run_full_test()
    else:
        # Train
        clf = FeatureClassifier()
        metrics = clf.train(n_samples=args.samples)
        clf.save()

        # Test
        run_full_test()
