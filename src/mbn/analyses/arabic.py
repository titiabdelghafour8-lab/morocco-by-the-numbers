"""Arabic text normalisation for topic modelling (same conventions as CAMeL Tools' normalisers).

- remove diacritics and the tatweel stretching character;
- alef variants (إ أ آ ٱ) -> ا, alef maqsura ى -> ي, teh marbuta ة -> ه;
- remove the formulae MPs open questions with ("نسائلكم السيد الوزير عن ...").
"""

from __future__ import annotations

import re

DIACRITICS = re.compile("[ً-ْٰـ]")
ALEF = re.compile("[آأإٱ]")
WORD = re.compile(r"[ء-ي]+")
OPENING = re.compile(
    r"^(?:نسايلكم|نساءلكم|نسالكم|نسائلكم)?\s*(?:السيد(?:ه)?\s+(?:الوزير(?:ه)?|رييس الحكومه|الوزير المنتدب))?\s*(?:عن|حول)?\s+"
)

_BASE_STOP = """
في من الي علي عن مع بين حول ان او و ثم لا ما لم لن هذا هذه ذلك تلك التي الذي الذين كل بعض اي غير عند لدي لدن قد كان
وضعيه الوضعيه حصيله ماال مال واقع تفعيل اجراءات الاجراءات التدابير تدابير برنامج مشروع خطه استراتيجيه سياسه
الحكومه الوزاره وزاره قطاع مجال ظاهره عدم ضروره ضعف تاخر غياب اشكاليه مشكل مشاكل معاناه مطالب مطلب
اقليم عماله جماعه جهه مدينه دوار مركز منطقه ببلادنا بلادنا المغرب المغربيه المملكه الوطني الوطنيه سيدي رقم
بالنسبه لفائده المتعلقه الخاصه العموميه العمومي
"""
_PREFIXES = ("", "و", "ب", "ل", "وب", "ول", "ف", "فب", "لل")
STOPWORDS = frozenset(p + w for w in _BASE_STOP.split() for p in _PREFIXES)


def normalise(text: str) -> str:
    s = DIACRITICS.sub("", str(text))
    s = ALEF.sub("ا", s).replace("ى", "ي").replace("ة", "ه")
    s = " ".join(s.split())
    while (m := OPENING.match(s)) and m.end() > 0:
        s = s[m.end() :].strip()
    return s


def tokens(text: str) -> list[str]:
    """Words of a normalised subject, without stop words, administrative filler or one-letter tokens."""
    return [w for w in WORD.findall(normalise(text)) if len(w) > 1 and w not in STOPWORDS]
