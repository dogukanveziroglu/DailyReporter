from __future__ import annotations
import re
import unicodedata

def _strip_accents(s: str) -> str:
    """NFKD ile aksanları ayırıp birleşik işaretleri düşürür."""
    s_norm = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s_norm if not unicodedata.combining(ch))

def make_username(full_name: str, max_len: int = 40) -> str:
    """
    Ad Soyad -> username
    - Türkçe karakterler ASCII'ye indirilir.
    - 'ı' kesinlikle 'i' olur (artık silinmez).
    - Boşluk ve noktalama kaldırılır; sadece [a-z0-9] kalır.
    """
    if not full_name:
        return ""

    s = full_name.strip()

    # Türkçe i/ı ikilisi için güvenli normalizasyon:
    # 'İ'.lower() Python'da 'i̇' (i + combining dot) üretebildiği için önce sabitleyelim.
    s = s.replace("İ", "I").replace("ı", "i")

    # Küçük harfe çevir
    s = s.lower()

    # Yaygın TR ve bazı aksanlı karakterleri doğrudan eşle (TEK karakter anahtarlar!)
    direct_map = str.maketrans({
        "ç": "c", "ğ": "g", "ö": "o", "ş": "s", "ü": "u",
        "â": "a", "î": "i", "û": "u",
        "ä": "a", "ë": "e", "ï": "i",
        "á": "a", "à": "a", "ê": "e",
        "é": "e", "è": "e", "ó": "o", "ò": "o", "ô": "o",
        "ú": "u", "ù": "u",
        "ñ": "n", "ß": "ss",
    })
    s = s.translate(direct_map)

    # Kalan aksanları ayır ve düşür (combining işaretleri temizler)
    s = _strip_accents(s)

    # Harf/rakam dışını temizle
    s = re.sub(r"[^a-z0-9]", "", s)

    # Uzun ise kırp
    if max_len and len(s) > max_len:
        s = s[:max_len]

    return s
