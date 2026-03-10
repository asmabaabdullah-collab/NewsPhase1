from urllib.parse import urlparse

TRUSTED_DOMAINS = {
    "bbc.com",
    "reuters.com",
    "apnews.com",
    "cnn.com",
    "aljazeera.com",
    "skynewsarabia.com",
    "alarabiya.net",
    "nytimes.com",
    "theguardian.com",
    "washingtonpost.com",
    "npr.org"
}

VERIFICATION_REFERENCES = [
    "International Fact-Checking Network (IFCN) Code of Principles",
    "Reuters Fact Check editorial approach",
    "First Draft verification guidance for digital journalism"
]


def extract_domain(url: str):
    """Extract a simplified domain name from a URL so the system can judge source familiarity."""
    return urlparse(url).netloc.replace("www.", "").lower()



def evaluate_source_reliability(domain: str):
    """Return a small reliability signal based on whether the domain belongs to a known news publisher list."""
    if domain in TRUSTED_DOMAINS:
        return 3, "المصدر ضمن قائمة أولية لمؤسسات إخبارية معروفة وواسعة الانتشار."
    return 1, "المصدر غير موجود في القائمة الأولية للمؤسسات المعروفة داخل النظام، لذا يحتاج تحققًا إضافيًا."



def build_credibility_report(article_url: str, comparison_count: int, comparison_summary: dict):
    """Build a transparent credibility assessment using domain reliability, cross-source consistency, and method disclosure."""
    domain = extract_domain(article_url)
    score = 0
    reasons = []

    source_score, source_reason = evaluate_source_reliability(domain)
    score += source_score
    reasons.append(source_reason)

    overlap_count = len(comparison_summary.get("similarities", []))
    difference_count = len(comparison_summary.get("differences", []))

    if comparison_count >= 2:
        score += 3
        reasons.append("تم العثور على تغطية من عدة مصادر حول الخبر نفسه، وهذا يدعم التحقق بالمقارنة العرضية.")
    elif comparison_count == 1:
        score += 2
        reasons.append("تم العثور على مصدر آخر واحد للمقارنة، لكنه لا يكفي وحده لبناء ثقة مرتفعة.")
    else:
        reasons.append("لم يتم العثور على مصادر مقارنة كافية، لذا يبقى الحكم أكثر تحفظًا.")

    if overlap_count >= 2:
        score += 3
        reasons.append("هناك عناصر متكررة بين المصادر مثل الوقائع الأساسية أو الأطراف الرئيسية، ما يدعم اتساق الرواية.")
    elif overlap_count == 1:
        score += 2
        reasons.append("يوجد قدر محدود من التشابه بين المصادر، لكنه يحتاج تدعيمًا بأدلة إضافية.")
    else:
        reasons.append("لا يوجد تشابه كافٍ ظاهر بين المصادر المسترجعة، لذلك يجب التعامل بحذر.")

    if difference_count > 0:
        score += 1
        reasons.append("تم رصد اختلافات بين التغطيات، وتم عرضها بدل إخفائها التزامًا بالشفافية المنهجية.")

    score = min(score, 10)

    if score >= 8:
        level = "مرتفع نسبيًا"
    elif score >= 5:
        level = "متوسط"
    else:
        level = "منخفض"

    method = [
        "تحليل المصدر الأصلي واسم النطاق الإخباري.",
        "البحث عن تغطيات أخرى للخبر نفسه عبر Google News RSS Search.",
        "استخراج النقاط الرئيسية والأحداث والشخصيات من كل مصدر باستخدام LLM.",
        "مقارنة عناصر الاتفاق والاختلاف بين المصادر بصورة صريحة وشفافة.",
        "إظهار المرجع المنهجي المستخدم بدل الاكتفاء بدرجة رقمية فقط."
    ]

    tools_used = [
        "Requests + Readability + BeautifulSoup لاستخراج النصوص من الروابط.",
        "Google News RSS Search للعثور على مصادر إضافية.",
        "OpenAI model للتحليل البنيوي والمقارنة والصياغة."
    ]

    return {
        "credibility_score": score,
        "credibility_level": level,
        "domain": domain,
        "references": VERIFICATION_REFERENCES,
        "verification_method": method,
        "tools_used": tools_used,
        "reasons": reasons
    }
