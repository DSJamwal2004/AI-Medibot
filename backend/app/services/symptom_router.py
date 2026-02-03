import re
from typing import Dict, List, Tuple, Optional

# Domain keyword rules (deterministic)
DOMAIN_RULES: Dict[str, List[str]] = {
    # Existing + improved
    "cardiology": [
        "heart", "cardiac", "myocard", "arrhythm", "angina", "stroke",
        "hypertension", "blood pressure", "cholesterol", "artery", "aorta",
        "atrial", "ventric", "tachy", "brady"
    ],
    "endocrinology": [
        "diabetes", "insulin", "glucose", "blood sugar", "thyroid", "tsh",
        "hypothy", "hyperthy", "adrenal", "cortisol", "hormone", "pituitary"
    ],
    "neurology": [
        "brain", "neuro", "seizure", "epilep", "parkinson", "alzheimer",
        "migraine", "stroke", "nerve", "spinal cord", "multiple sclerosis",
        "ms ", "dementia"
    ],
    "gastroenterology": [
        "stomach", "gastric", "liver", "hepat", "pancreas", "pancreatic",
        "colon", "bowel", "intestin", "ulcer", "crohn", "colitis",
        "diarrhea", "constipation", "ibs", "reflux", "gerd"
    ],
    "dermatology": [
        "skin", "rash", "eczema", "psoriasis", "acne", "itch", "hives",
        "dermatitis", "lesion", "melanoma"
    ],
    "orthopedics": [
        "bone", "joint", "fracture", "arthritis", "osteoporosis", "spine",
        "knee", "hip", "shoulder", "sprain", "ligament", "tendon"
    ],
    "pulmonology": [
        "lung", "asthma", "copd", "bronch", "pneumonia", "breath",
        "respirat", "cough", "oxygen", "tuberculosis", "tb "
    ],

    # NEW DOMAINS
    "nephrology": [
        "kidney", "renal", "nephro", "dialysis", "creatinine", "urea",
        "proteinuria", "hematuria", "glomerul"
    ],
    "hematology": [
        "anemia", "hemoglobin", "platelet", "bleeding", "clot", "leukemia",
        "lymphoma", "blood disorder", "sickle", "thalassemia"
    ],
    "oncology": [
        "cancer", "tumor", "carcinoma", "chemotherapy", "radiation",
        "metast", "malignant", "oncolog"
    ],
    "infectious_disease": [
        "infection", "virus", "viral", "bacterial", "fever", "sepsis",
        "hiv", "aids", "influenza", "covid", "malaria", "dengue"
    ],
    "obstetrics_gynecology": [
        "pregnan", "menstrual", "period", "uterus", "ovary", "ovarian",
        "cervix", "cervical", "vaginal", "gyne", "labor", "delivery"
    ],
    "urology": [
        "urine", "urinary", "bladder", "prostate", "kidney stone",
        "erectile", "incontinence", "uti "
    ],
    "ophthalmology": [
        "eye", "vision", "retina", "glaucoma", "cataract", "blind",
        "ocular", "macular"
    ],
    "ent": [
        "ear", "nose", "throat", "sinus", "hearing", "tonsil", "larynx",
        "vertigo"
    ],
    "psychiatry": [
        "depression", "anxiety", "bipolar", "schizophrenia", "panic",
        "ptsd", "suicide", "mental health", "adhd"
    ],
    "pediatrics": [
        "child", "children", "infant", "newborn", "pediatric", "toddler"
    ],
    "immunology_allergy": [
        "allergy", "allergic", "immune", "autoimmune", "lupus",
        "rheumatoid", "anaphylaxis"
    ],
    "rheumatology": [
        "rheumatoid", "lupus", "vasculitis", "gout", "fibromyalgia",
        "scleroderma", "sjogren"
    ],
}

def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()

def infer_medical_domains(text: str) -> List[dict]:
    """
    Returns sorted domain matches:
    [
      {"domain": "...", "score": int, "matched_keywords": [...]},
      ...
    ]
    """
    normalized = normalize_text(text)

    results = []
    for domain, keywords in DOMAIN_RULES.items():
        matched = [kw for kw in keywords if kw in normalized]
        if matched:
            results.append({
                "domain": domain,
                "score": len(matched),
                "matched_keywords": matched[:10],  # keep short
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results

def infer_medical_domain(text: str) -> Tuple[Optional[str], Optional[str]]:
    normalized = normalize_text(text)

    # Strong priority override (diabetes should never go to neurology etc.)
    endocrine_priority = ["diabetes", "insulin", "glucose", "blood sugar"]
    if any(t in normalized for t in endocrine_priority):
        return "endocrinology", "Priority rule: diabetes/endocrine keywords detected"

    results = infer_medical_domains(text)

    if not results:
        return "general", "No keywords matched; defaulted to general"

    top = results[0]
    return top["domain"], f"Matched keywords: {top['matched_keywords']}"






