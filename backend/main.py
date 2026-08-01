from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import os
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime, timedelta, timezone
import hashlib
import time
import re
import json
import psycopg2
import bcrypt
import jwt
import requests
import xml.etree.ElementTree as ET

load_dotenv()

app = FastAPI(
    title="Medical Literature RAG System",
    description="AI-powered medical literature retrieval with personalized health profiles",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)
LLM_MODEL = "llama-3.3-70b-versatile"

# ==================== Data Models ====================

class SignupRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class HealthProfile(BaseModel):
    user_id: str
    first_name: str
    last_name: str
    age: int
    gender: str
    height_cm: float
    weight_kg: float
    medical_conditions: List[str]
    current_medications: List[str]
    allergies: List[str]
    lifestyle_factors: str
    family_history: List[str]
    created_at: str = None

class MedicalQuery(BaseModel):
    query: str
    include_personalization: bool = True
    language: str = "English"

class RawQueryInput(BaseModel):
    raw_text: str
    language: str = "English"

class RAGResponse(BaseModel):
    query: str
    answer: str
    retrieved_papers: List[dict]
    personalized_insights: Optional[str]
    retrieval_score: float
    response_time: float
    is_emergency: bool = False

# ==================== Profile Storage (SQLite) ====================
# Hosted Postgres (e.g. Neon) instead of SQLite — most free hosting platforms
# wipe local disk on every redeploy/restart, which would silently undo
# persistence. DATABASE_URL is a standard postgres:// connection string.

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            profile_id TEXT PRIMARY KEY,
            owner_id TEXT UNIQUE,
            data TEXT NOT NULL
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())

def create_user(email: str, password: str) -> str:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    if cur.fetchone():
        cur.close()
        conn.close()
        raise ValueError("An account with this email already exists")
    user_id = hashlib.md5(f"{email}{datetime.now()}".encode()).hexdigest()[:12]
    cur.execute(
        "INSERT INTO users (id, email, password_hash, created_at) VALUES (%s, %s, %s, %s)",
        (user_id, email, hash_password(password), datetime.now().isoformat())
    )
    conn.commit()
    cur.close()
    conn.close()
    return user_id

def get_user_by_email(email: str) -> Optional[dict]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, email, password_hash FROM users WHERE email = %s", (email,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return {"id": row[0], "email": row[1], "password_hash": row[2]} if row else None

def get_profile_by_owner(owner_id: str) -> Optional[dict]:
    """Exactly one profile per account — the account IS the profile owner,
    so no profile_id/switching concept is needed at all."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT data FROM profiles WHERE owner_id = %s", (owner_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return json.loads(row[0]) if row else None

def upsert_profile_for_owner(owner_id: str, profile_data: dict):
    conn = get_db_connection()
    cur = conn.cursor()
    profile_id = hashlib.md5(f"{owner_id}{datetime.now()}".encode()).hexdigest()[:12]
    cur.execute("""
        INSERT INTO profiles (profile_id, owner_id, data) VALUES (%s, %s, %s)
        ON CONFLICT (owner_id) DO UPDATE SET data = EXCLUDED.data
    """, (profile_id, owner_id, json.dumps(profile_data)))
    conn.commit()
    cur.close()
    conn.close()

def delete_profile_by_owner(owner_id: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM profiles WHERE owner_id = %s", (owner_id,))
    conn.commit()
    cur.close()
    conn.close()

def count_profiles() -> int:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM profiles")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count

init_db()

# ==================== Authentication (JWT) ====================

JWT_SECRET = os.getenv("SECRET_KEY")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 7

def create_access_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def get_current_user_id(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization[len("Bearer "):].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

@app.post("/api/auth/signup")
async def signup(request: SignupRequest):
    try:
        user_id = create_user(request.email, request.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"access_token": create_access_token(user_id), "user_id": user_id, "email": request.email}

@app.post("/api/auth/login")
async def login(request: LoginRequest):
    user = get_user_by_email(request.email)
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return {"access_token": create_access_token(user["id"]), "user_id": user["id"], "email": user["email"]}

# ==================== Autocomplete (NIH Clinical Tables) ====================
# Docs: https://clinicaltables.nlm.nih.gov/apidoc/conditions/v3/doc.html
# Free, no API key, no rate-limit concerns for this traffic level.

CLINICAL_TABLES_CONDITIONS_URL = "https://clinicaltables.nlm.nih.gov/api/conditions/v3/search"
CLINICAL_TABLES_RXTERMS_URL = "https://clinicaltables.nlm.nih.gov/api/rxterms/v3/search"

COMMON_ALLERGENS = [
    "Peanuts", "Tree Nuts", "Shellfish", "Fish", "Eggs", "Milk", "Soy", "Wheat",
    "Pollen", "Dust Mites", "Latex", "Mold", "Pet Dander", "Bee Stings",
    "Insect Stings", "Sulfa Drugs", "Iodine"
]

def _clinical_tables_search(url: str, term: str, max_results: int = 8) -> List[str]:
    """Query an NLM Clinical Tables endpoint. Response shape is
    [total_count, codes, extra_data, [[display_string], ...]]."""
    term = term.strip()
    if len(term) < 2:
        return []
    try:
        resp = requests.get(url, params={"terms": term, "maxList": max_results}, timeout=5)
        resp.raise_for_status()
        display_strings = resp.json()[3]
        return [row[0] for row in display_strings if row]
    except Exception as e:
        print(f"Autocomplete error ({url}): {e}")
        return []

@app.get("/api/autocomplete/conditions")
async def autocomplete_conditions(q: str = ""):
    return {"suggestions": _clinical_tables_search(CLINICAL_TABLES_CONDITIONS_URL, q)}

@app.get("/api/autocomplete/medications")
async def autocomplete_medications(q: str = ""):
    return {"suggestions": _clinical_tables_search(CLINICAL_TABLES_RXTERMS_URL, q)}

@app.get("/api/autocomplete/allergies")
async def autocomplete_allergies(q: str = ""):
    term = q.strip().lower()
    common_matches = [a for a in COMMON_ALLERGENS if term in a.lower()] if term else []
    drug_matches = _clinical_tables_search(CLINICAL_TABLES_RXTERMS_URL, q, max_results=5)
    combined = common_matches + [d for d in drug_matches if d not in common_matches]
    return {"suggestions": combined[:8]}

# ==================== PubMed Live Search (E-utilities) ====================
# Docs: https://www.ncbi.nlm.nih.gov/books/NBK25501/
# No API key required. Optional NCBI_API_KEY in .env raises rate limit
# from ~3 req/sec to ~10 req/sec — useful if you scale up traffic later.

PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

def _ncbi_params(extra: dict) -> dict:
    """Adds optional API key + polite identification params NCBI recommends."""
    params = dict(extra)
    ncbi_key = os.getenv("NCBI_API_KEY")
    if ncbi_key:
        params["api_key"] = ncbi_key
    params["tool"] = "medical-rag-system"
    contact = os.getenv("CONTACT_EMAIL")
    if contact:
        params["email"] = contact
    return params

def search_pubmed(query: str, max_results: int = 3) -> List[str]:
    """Search PubMed and return a list of PMIDs, ranked by relevance."""
    params = _ncbi_params({
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results,
        "sort": "relevance"
    })
    try:
        resp = requests.get(PUBMED_ESEARCH_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"PubMed search error: {e}")
        return []

def parse_pubmed_xml(xml_text: str) -> List[dict]:
    """Parse PubMed efetch XML into clean paper dicts."""
    papers = []
    try:
        root = ET.fromstring(xml_text)
        for article in root.findall(".//PubmedArticle"):
            pmid_el = article.find(".//PMID")
            pmid = pmid_el.text if pmid_el is not None else ""

            title_el = article.find(".//ArticleTitle")
            title = "".join(title_el.itertext()).strip() if title_el is not None else "Untitled"

            authors = []
            for author in article.findall(".//AuthorList/Author"):
                last = author.find("LastName")
                initials = author.find("Initials")
                if last is not None:
                    name = last.text
                    if initials is not None:
                        name += f" {initials.text}."
                    authors.append(name)
            if not authors:
                authors = ["Unknown"]

            journal_el = article.find(".//Journal/Title")
            journal = journal_el.text if journal_el is not None else "Unknown Journal"

            year_el = article.find(".//Journal/JournalIssue/PubDate/Year")
            if year_el is None:
                year_el = article.find(".//Journal/JournalIssue/PubDate/MedlineDate")
            year = year_el.text[:4] if year_el is not None and year_el.text else "N/A"

            doi = ""
            for eloc in article.findall(".//ELocationID"):
                if eloc.get("EIdType") == "doi":
                    doi = eloc.text
                    break

            abstract_parts = []
            for abst in article.findall(".//Abstract/AbstractText"):
                label = abst.get("Label")
                text = "".join(abst.itertext()).strip()
                abstract_parts.append(f"{label}: {text}" if label else text)
            abstract = " ".join(abstract_parts) if abstract_parts else "No abstract available."
            if len(abstract) > 600:
                abstract = abstract[:600] + "..."

            papers.append({
                "id": pmid,
                "pmid": pmid,
                "title": title,
                "authors": authors,
                "journal": journal,
                "year": year,
                "doi": doi,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "abstract": abstract
            })
    except Exception as e:
        print(f"XML parse error: {e}")
    return papers

def fetch_pubmed_details(pmids: List[str]) -> List[dict]:
    if not pmids:
        return []
    params = _ncbi_params({
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "abstract",
        "retmode": "xml"
    })
    try:
        resp = requests.get(PUBMED_EFETCH_URL, params=params, timeout=15)
        resp.raise_for_status()
        return parse_pubmed_xml(resp.text)
    except Exception as e:
        print(f"PubMed fetch error: {e}")
        return []

def generate_pubmed_search_query(user_query: str) -> str:
    """Distill a conversational health question into PubMed-friendly keywords.
    PubMed's search does poorly with full sentences/questions, so raw user
    phrasing ("i have X, what should I do about Y") often returns zero hits
    even when relevant literature exists."""
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{
                "role": "user",
                "content": f"""Convert this health question into a short PubMed search query. PubMed ANDs every keyword together, so keep it broad: 3-5 keywords maximum, no punctuation, no question marks, prioritizing the core medical condition/topic over minor details. Always output the keywords in English medical terminology regardless of what language the question is in, since this searches an English-language database.

Question: {user_query}

Search query:"""
            }],
            max_tokens=40,
            temperature=0.3
        )
        return response.choices[0].message.content.strip().strip('"')
    except Exception as e:
        print(f"Search query generation error: {e}")
        return user_query

def retrieve_relevant_papers(query: str, top_k: int = 3) -> List[dict]:
    """Live PubMed search — always current, nothing to maintain.
    Tries a keyword-refined query first, then falls back to the raw query,
    since either phrasing can succeed where the other fails."""
    search_query = generate_pubmed_search_query(query)
    pmids = search_pubmed(search_query, max_results=top_k)
    if not pmids and search_query != query:
        pmids = search_pubmed(query, max_results=top_k)
    return fetch_pubmed_details(pmids)

# ==================== Health Profile Endpoints ====================

@app.get("/api/my-profile")
async def get_my_profile(current_user_id: str = Depends(get_current_user_id)):
    profile = get_profile_by_owner(current_user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="No profile created yet")
    return profile

@app.put("/api/my-profile")
async def save_my_profile(profile: HealthProfile, current_user_id: str = Depends(get_current_user_id)):
    existing = get_profile_by_owner(current_user_id)
    profile.created_at = existing.get("created_at") if existing else datetime.now().isoformat()
    upsert_profile_for_owner(current_user_id, profile.model_dump())
    return {"status": "success", "message": "Health profile saved successfully"}

@app.delete("/api/my-profile")
async def delete_my_profile(current_user_id: str = Depends(get_current_user_id)):
    if get_profile_by_owner(current_user_id) is None:
        raise HTTPException(status_code=404, detail="No profile to delete")
    delete_profile_by_owner(current_user_id)
    return {"status": "success", "message": "Health profile deleted successfully"}

# ==================== Health Metrics (BMI + TDEE) ====================
# TDEE uses the Mifflin-St Jeor equation — the modern standard, more accurate
# across body types than the older Harris-Benedict formula it replaced.

ACTIVITY_MULTIPLIERS = {
    "Sedentary": 1.2,
    "Moderately Active": 1.55,
    "Very Active": 1.725,
}

def calculate_bmi(weight_kg: float, height_cm: float) -> dict:
    height_m = height_cm / 100
    bmi = round(weight_kg / (height_m ** 2), 1)
    if bmi < 18.5:
        category = "Underweight"
    elif bmi < 25:
        category = "Normal weight"
    elif bmi < 30:
        category = "Overweight"
    else:
        category = "Obese"
    return {"value": bmi, "category": category}

def calculate_tdee(weight_kg: float, height_cm: float, age: int, gender: str, lifestyle_factors: str) -> dict:
    # Mifflin-St Jeor requires a biological-sex term; for non-binary/unspecified
    # gender we average the male and female formulas rather than force a choice.
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    if gender.strip().lower() == "male":
        bmr = base + 5
    elif gender.strip().lower() == "female":
        bmr = base - 161
    else:
        bmr = base + (5 + -161) / 2

    multiplier = ACTIVITY_MULTIPLIERS.get(lifestyle_factors, 1.2)
    tdee = bmr * multiplier
    return {
        "bmr": round(bmr),
        "tdee": round(tdee),
        "activity_multiplier": multiplier
    }

@app.get("/api/my-profile/metrics")
async def health_metrics(current_user_id: str = Depends(get_current_user_id)):
    profile = get_profile_by_owner(current_user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    height_cm = profile.get("height_cm")
    weight_kg = profile.get("weight_kg")
    if not height_cm or not weight_kg:
        raise HTTPException(status_code=400, detail="Height and weight are required to calculate metrics")

    bmi = calculate_bmi(weight_kg, height_cm)
    tdee = calculate_tdee(weight_kg, height_cm, profile.get("age", 30), profile.get("gender", ""), profile.get("lifestyle_factors", "Sedentary"))
    return {
        "bmi": bmi,
        "tdee": tdee,
        "disclaimer": "Estimates only, based on standard formulas (BMI, Mifflin-St Jeor equation). Not a substitute for professional medical or nutritional advice."
    }

# ==================== Safety Check (RxNorm + RxClass + openFDA) ====================
# NLM's old drug-drug interaction API (RxNav /interaction) was discontinued —
# its DrugBank/NDF-RT source data was retired. So drug-drug interactions are
# checked against openFDA's structured product labeling instead (the actual
# FDA-approved "Drug Interactions" label section), and allergy conflicts are
# checked via RxNorm name matching + RxClass drug-class membership — all
# deterministic lookups, not LLM inference, since correctness here matters
# more than fluency.

def _clean_drug_name(name: str) -> str:
    """Strip RxTerms-style formulation suffixes like '(Oral Pill)' or
    '(Chewable)' that come from the autocomplete dropdown — RxNorm/openFDA
    lookups match on the bare ingredient name, not the display string."""
    return re.sub(r'\s*\([^)]*\)\s*$', '', name).strip()

RXNAV_RXCUI_URL = "https://rxnav.nlm.nih.gov/REST/rxcui.json"
RXNAV_APPROX_URL = "https://rxnav.nlm.nih.gov/REST/approximateTerm.json"
RXNAV_CLASS_URL = "https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json"
OPENFDA_LABEL_URL = "https://api.fda.gov/drug/label.json"

def _resolve_rxcui(drug_name: str) -> Optional[str]:
    """Exact RxNorm name match first, falling back to fuzzy matching since
    user-entered drug names don't always match RxNorm's canonical spelling."""
    try:
        resp = requests.get(RXNAV_RXCUI_URL, params={"name": drug_name}, timeout=5)
        resp.raise_for_status()
        ids = resp.json().get("idGroup", {}).get("rxnormId")
        if ids:
            return ids[0]
    except Exception as e:
        print(f"RxCUI lookup error for '{drug_name}': {e}")

    try:
        resp = requests.get(RXNAV_APPROX_URL, params={"term": drug_name, "maxEntries": 1}, timeout=5)
        resp.raise_for_status()
        candidates = resp.json().get("approximateGroup", {}).get("candidate") or []
        if candidates:
            return candidates[0].get("rxcui")
    except Exception as e:
        print(f"RxCUI approximate lookup error for '{drug_name}': {e}")
    return None

def _drug_classes(rxcui: str, sources=("ATC", "VA")) -> List[str]:
    """ATC gives formal pharmacological classes (e.g. 'Vitamin K antagonists');
    VA gives the plainer clinical terms FDA labels tend to use in prose
    (e.g. 'ANTICOAGULANTS') — checking both catches more real label text."""
    classes = set()
    for source in sources:
        try:
            resp = requests.get(RXNAV_CLASS_URL, params={"rxcui": rxcui, "relaSource": source}, timeout=5)
            resp.raise_for_status()
            items = resp.json().get("rxclassDrugInfoList", {}).get("rxclassDrugInfo") or []
            classes.update(
                item["rxclassMinConceptItem"]["className"]
                for item in items if "rxclassMinConceptItem" in item
            )
        except Exception as e:
            print(f"Drug class lookup error for rxcui {rxcui} ({source}): {e}")
    return list(classes)

def _drug_family_terms(name: str) -> List[str]:
    """Words worth matching against a drug class name. A specific compound
    like 'Penicillin V potassium' won't literally appear inside a class name
    like 'Beta-lactamase sensitive penicillins' — but the family root word
    'penicillin' will, so pull out words instead of comparing whole strings.
    4+ letters avoids matching on short, overly generic words."""
    return [w.lower() for w in re.findall(r"[a-zA-Z]+", name) if len(w) >= 4]

def check_allergy_conflicts(medications: List[str], allergies: List[str]) -> List[dict]:
    conflicts = []
    for allergy in allergies:
        allergy_clean = _clean_drug_name(allergy)
        allergy_lower = allergy_clean.lower().strip()
        if not allergy_lower:
            continue
        allergy_terms = _drug_family_terms(allergy_clean)
        for medication in medications:
            med_clean = _clean_drug_name(medication)
            med_lower = med_clean.lower().strip()
            if not med_lower:
                continue
            if allergy_lower in med_lower or med_lower in allergy_lower:
                conflicts.append({
                    "allergy": allergy,
                    "medication": medication,
                    "reason": f'"{medication}" directly matches your listed allergy "{allergy}".'
                })
                continue
            rxcui = _resolve_rxcui(med_clean)
            if not rxcui:
                continue
            for class_name in _drug_classes(rxcui):
                class_lower = class_name.lower()
                term_hit = next((t for t in allergy_terms if t in class_lower), None)
                if allergy_lower in class_lower or term_hit:
                    conflicts.append({
                        "allergy": allergy,
                        "medication": medication,
                        "reason": f'"{medication}" belongs to the drug class "{class_name}", which matches your listed allergy "{allergy}".'
                    })
                    break
    return conflicts

def _fda_interaction_text(drug_name: str) -> Optional[str]:
    try:
        resp = requests.get(OPENFDA_LABEL_URL, params={
            "search": f'openfda.generic_name:"{drug_name}" OR openfda.brand_name:"{drug_name}"',
            "limit": 1
        }, timeout=8)
        resp.raise_for_status()
        results = resp.json().get("results") or []
        if results:
            text = results[0].get("drug_interactions")
            if text:
                return " ".join(text)
    except Exception as e:
        print(f"openFDA label lookup error for '{drug_name}': {e}")
    return None

def check_drug_interactions(medications: List[str]) -> List[dict]:
    """For each medication, pull its FDA label 'Drug Interactions' section and
    check whether another listed medication is named in that real label text —
    either by its own name, or by its drug class, since labels often say
    'Oral Anticoagulants' rather than naming 'Warfarin' directly."""
    interactions = []
    meds = [(m.strip(), _clean_drug_name(m.strip())) for m in medications if m.strip()]
    for med_orig, med_clean in meds:
        text = _fda_interaction_text(med_clean)
        if not text:
            continue
        text_lower = text.lower()
        for other_orig, other_clean in meds:
            if other_clean.lower() == med_clean.lower():
                continue

            idx = text_lower.find(other_clean.lower())
            if idx != -1:
                excerpt = text[max(0, idx - 100): idx + 200].strip()
                interactions.append({
                    "medication": med_orig,
                    "interacts_with": other_orig,
                    "matched_via": other_clean,
                    "excerpt": f"...{excerpt}..."
                })
                continue

            rxcui = _resolve_rxcui(other_clean)
            if not rxcui:
                continue
            for class_name in _drug_classes(rxcui):
                class_lower = class_name.lower()
                if len(class_lower) < 5:
                    continue
                match = re.search(r'\b' + re.escape(class_lower) + r'\b', text_lower)
                if match:
                    idx = match.start()
                    excerpt = text[max(0, idx - 100): idx + 200].strip()
                    interactions.append({
                        "medication": med_orig,
                        "interacts_with": other_orig,
                        "matched_via": f"drug class: {class_name}",
                        "excerpt": f"...{excerpt}..."
                    })
                    break
    return interactions

@app.get("/api/my-profile/safety-check")
async def safety_check(current_user_id: str = Depends(get_current_user_id)):
    profile = get_profile_by_owner(current_user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    medications = profile.get("current_medications", [])
    allergies = profile.get("allergies", [])

    allergy_conflicts = check_allergy_conflicts(medications, allergies)
    drug_interactions = check_drug_interactions(medications) if len(medications) > 1 else []

    return {
        "allergy_conflicts": allergy_conflicts,
        "drug_interactions": drug_interactions,
        "disclaimer": "Based on RxNorm drug classifications and FDA label data. Absence of a flagged conflict does not guarantee safety — always consult a pharmacist or doctor before starting or stopping any medication."
    }

# ==================== Free / Low-Cost Care Locator ====================
# Federally Qualified Health Centers (FQHCs) are required by federal law to
# offer sliding-scale fees based on income, regardless of insurance status —
# a real option for people who can't afford or reach a hospital. Looked up
# via CMS's official NPPES provider registry (free, no key required).

NPPES_API_URL = "https://npiregistry.cms.hhs.gov/api/"

NATIONAL_HOTLINES = [
    {"name": "988 Suicide & Crisis Lifeline", "contact": "Call or text 988", "for_": "Mental health crisis, suicidal thoughts, emotional distress"},
    {"name": "Poison Control", "contact": "1-800-222-1222", "for_": "Suspected poisoning or overdose"},
    {"name": "SAMHSA National Helpline", "contact": "1-800-662-4357", "for_": "Substance use and mental health treatment referrals"},
    {"name": "HRSA Find a Health Center", "contact": "https://findahealthcenter.hrsa.gov", "for_": "Search all free/sliding-scale clinics near you"},
]

def find_low_cost_clinics(zip_code: str, limit: int = 8) -> List[dict]:
    try:
        resp = requests.get(NPPES_API_URL, params={
            "version": "2.1",
            "taxonomy_description": "Federally Qualified Health Center",
            "postal_code": zip_code,
            "limit": limit
        }, timeout=8)
        resp.raise_for_status()
        results = resp.json().get("results") or []
        clinics = []
        for r in results:
            basic = r.get("basic", {})
            addresses = [a for a in r.get("addresses", []) if a.get("address_purpose") == "LOCATION"]
            addr = (addresses or r.get("addresses") or [{}])[0]
            raw_zip = addr.get("postal_code") or ""
            formatted_zip = f"{raw_zip[:5]}-{raw_zip[5:]}" if len(raw_zip) > 5 else raw_zip
            clinics.append({
                "name": basic.get("organization_name") or "Unnamed Health Center",
                "address": ", ".join(filter(None, [
                    addr.get("address_1"), addr.get("city"), addr.get("state"), formatted_zip
                ])),
                "phone": addr.get("telephone_number", "")
            })
        return clinics
    except Exception as e:
        print(f"NPPES lookup error: {e}")
        return []

@app.get("/api/care-locator")
async def care_locator(zip_code: str):
    return {
        "zip_code": zip_code,
        "clinics": find_low_cost_clinics(zip_code),
        "hotlines": NATIONAL_HOTLINES,
        "note": "Federally Qualified Health Centers offer sliding-scale fees based on income, regardless of insurance or immigration status."
    }

# ==================== Query Interpretation ====================
# Cleans up messy input — rambling voice transcripts, run-on descriptions,
# filler words — into a single clear question before it hits retrieval/
# emergency detection, without adding information the user didn't say.

@app.post("/api/interpret-query")
async def interpret_query(input_data: RawQueryInput):
    try:
        prompt = f"""A user is asking a health question. Their input may be a rambling voice transcript with filler words, false starts, or informal phrasing. Rewrite it as a single, clear, well-structured medical question in {input_data.language}, preserving every symptom or detail they mentioned. Do not add information they did not say. Do not answer the question. Output ONLY the rewritten question, nothing else.

User's input: {input_data.raw_text}

Rewritten question:"""
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3
        )
        return {"interpreted_question": response.choices[0].message.content.strip().strip('"')}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Emergency Triage ====================
# Deliberately over-cautious: someone using this tool instead of going to a
# hospital is exactly who a missed emergency hurts most, so false alarms are
# an acceptable cost. Keyword matching runs first (fast, deterministic, works
# even if the LLM is down); an LLM classification pass catches phrasings the
# keyword list doesn't anticipate.

EMERGENCY_PATTERNS = [
    (r"chest pain|chest pressure|chest tightness", "Possible cardiac emergency symptoms"),
    (r"can'?t breathe|difficulty breathing|shortness of breath|trouble breathing|turning blue", "Severe breathing difficulty"),
    (r"suicidal|kill myself|want to die|end my life|hurt myself", "Suicidal ideation or self-harm risk"),
    (r"unconscious|unresponsive|passed out|fainted|won'?t wake up", "Loss of consciousness"),
    (r"severe bleeding|won'?t stop bleeding|bleeding a lot|bleeding heavily", "Severe uncontrolled bleeding"),
    (r"stroke|face (is )?drooping|slurred speech|sudden numbness|sudden weakness.*side|can'?t move (one|my) side", "Possible stroke symptoms"),
    (r"throat (is |feels )?closing|swelling.*throat|can'?t swallow|anaphylaxis|allergic reaction.*swelling", "Possible severe allergic reaction (anaphylaxis)"),
    (r"seizure|convulsion", "Seizure"),
    (r"overdose|took too many pills|swallowed too many", "Possible overdose"),
    (r"worst headache of my life|sudden severe headache|thunderclap headache", "Possible neurological emergency"),
    (r"coughing up blood|vomiting blood", "Signs of internal bleeding"),
    (r"can'?t feel (my|legs|arms)|paraly", "Sudden paralysis or loss of sensation"),
]

def _detect_emergency_keywords(text: str) -> Optional[str]:
    text_lower = text.lower()
    for pattern, label in EMERGENCY_PATTERNS:
        if re.search(pattern, text_lower):
            return label
    return None

def _detect_emergency_llm(query: str) -> bool:
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{
                "role": "user",
                "content": f"""Determine if this message describes a potential medical emergency needing immediate professional care (e.g. heart attack, stroke, severe allergic reaction, suicidal intent, breathing difficulty, severe bleeding, loss of consciousness, major trauma). When uncertain, err toward EMERGENCY. Respond with exactly one word: EMERGENCY or ROUTINE.

Message: {query}"""
            }],
            max_tokens=5,
            temperature=0
        )
        return "EMERGENCY" in response.choices[0].message.content.strip().upper()
    except Exception as e:
        print(f"Emergency LLM classification error: {e}")
        return False

def detect_emergency(query: str) -> Optional[dict]:
    keyword_hit = _detect_emergency_keywords(query)
    if keyword_hit:
        return {"reason": keyword_hit}
    if _detect_emergency_llm(query):
        return {"reason": "Potential emergency symptoms detected"}
    return None

EMERGENCY_RESPONSE_TEMPLATE = (
    "This may describe a medical emergency ({reason}).\n\n"
    "## Seek Immediate Care\n"
    "Please call your local emergency number (911 in the US) or go to the nearest emergency room right now. "
    "This tool cannot safely evaluate emergency symptoms and should not be used in place of emergency care.\n\n"
    "If this is a mental health crisis, you can also call or text **988** (Suicide & Crisis Lifeline) any time."
)

def format_emergency_message(reason: str, language: str) -> str:
    """Translates the emergency message when needed, but always keeps the
    English original visible underneath as a redundant fallback — this is
    the single highest-stakes message in the app, so a translation glitch
    must never be the only version the user sees."""
    english_message = EMERGENCY_RESPONSE_TEMPLATE.format(reason=reason)
    if language.strip().lower() in ("english", "en"):
        return english_message
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{
                "role": "user",
                "content": f"""Translate this emergency medical message into {language}. Keep it clear and urgent. Do not translate or alter "911" or "988" — keep them as literal numbers. Keep the Markdown "##" heading.

{english_message}"""
            }],
            max_tokens=400,
            temperature=0.2
        )
        translated = response.choices[0].message.content.strip()
        return f"{translated}\n\n---\n*English (shown as a safety backup in case of translation error):*\n\n{english_message}"
    except Exception as e:
        print(f"Emergency translation error: {e}")
        return english_message

# ==================== RAG Query Endpoint ====================

def generate_personalized_insights(health_profile: dict, answer: str, language: str = "English") -> str:
    if not health_profile:
        return None
    try:
        conditions = ", ".join(health_profile.get("medical_conditions", []))
        medications = ", ".join(health_profile.get("current_medications", []))
        allergies = ", ".join(health_profile.get("allergies", []))
        prompt = f"""Based on this health profile:
Age: {health_profile.get('age')}
Conditions: {conditions}
Medications: {medications}
Allergies: {allergies}
Lifestyle: {health_profile.get('lifestyle_factors')}

Medical Information: {answer}

Respond entirely in {language}. Provide personalized insights (2-3 sentences)."""
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Personalization error: {e}")
        return None

def generate_general_answer(query: str, language: str = "English") -> str:
    """Fallback when no PubMed literature matches: answer from the model's
    general medical knowledge instead of a dead-end 'not found' message,
    clearly labeled so it's never mistaken for literature-backed output."""
    try:
        prompt = f"""You are a medical information assistant. No specific PubMed literature matched this question, so answer using established general medical knowledge instead. Be accurate and comprehensive.

Question: {query}

Respond entirely in {language}. Format your answer in Markdown: use ## for section headings and ### for subheadings, and bullet points where they aid readability. Provide a clear, evidence-based answer."""
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.5
        )
        return "[No specific PubMed literature matched this query — answer based on general medical knowledge]\n\n" + response.choices[0].message.content
    except Exception as e:
        return f"Error generating answer: {str(e)}"

def filter_relevant_papers(query: str, retrieved_papers: List[dict]) -> List[dict]:
    """PubMed's AND-based search can return papers that technically contain
    every keyword but aren't actually about the question (e.g. a generic
    lifestyle question ANDed with a condition name can surface an unrelated
    comorbidity study). Papers that pass this gate are what the answer
    prompt is allowed to cite — this exists specifically to stop the LLM
    from attaching a real PMID to a claim that paper doesn't support."""
    try:
        titles = "\n".join([f"{i+1}. {p['title']}" for i, p in enumerate(retrieved_papers)])
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{
                "role": "user",
                "content": f"""Question: {query}

Retrieved paper titles:
{titles}

For each paper, is it directly relevant to answering this specific question (not just sharing a keyword)? Respond with ONLY the numbers of the relevant papers, comma-separated (e.g. "1,3"). If none are relevant, respond with "none"."""
            }],
            max_tokens=20,
            temperature=0
        )
        result = response.choices[0].message.content.strip().lower()
        if result == "none" or not result:
            return []
        keep_indices = {int(n.strip()) - 1 for n in result.split(",") if n.strip().isdigit()}
        return [p for i, p in enumerate(retrieved_papers) if i in keep_indices]
    except Exception as e:
        print(f"Relevance filter error: {e}")
        return retrieved_papers  # fail open — don't silently discard real results on an API hiccup

def generate_rag_answer(query: str, retrieved_papers: List[dict], language: str = "English") -> str:
    """Expects retrieved_papers to already be relevance-filtered — see
    filter_relevant_papers(), called once by the /api/query endpoint so the
    same filtered set is both cited here and shown in the response."""
    if not retrieved_papers:
        return generate_general_answer(query, language)
    try:
        context = "\n\n".join([
            f"Paper {i+1}: {p['title']}\nAuthors: {', '.join(p['authors'])}\nJournal: {p['journal']} ({p['year']})\nPMID: {p['pmid']}"
            + (f"\nDOI: {p['doi']}" if p['doi'] else "")
            + f"\nAbstract: {p['abstract']}"
            for i, p in enumerate(retrieved_papers)
        ])
        prompt = f"""You are a medical information assistant. Based on this real PubMed literature, answer the question and cite papers by their PMID:

{context}

Question: {query}

Only cite a paper's PMID when that paper's abstract genuinely and directly supports the specific claim you are attaching it to. Never attach a PMID to a claim just because the paper was retrieved — if none of the papers actually support a point you want to make, state it as general medical knowledge without a citation instead of forcing one.

Respond entirely in {language}, but keep citations in the exact untranslated format "PMID: <number>" (do not translate the word PMID or the numbers). Format your answer in Markdown: use ## for section headings and ### for subheadings, and bullet points where they aid readability. Provide a comprehensive, evidence-based answer."""
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating answer: {str(e)}"

def build_profile_context(profile: dict) -> str:
    """Compact summary of a health profile, injected into the search/answer
    pipeline so references like 'these conditions' or 'my medications'
    resolve to the patient's actual data instead of being meaningless to
    a query that only sees raw question text."""
    conditions = ", ".join(profile.get("medical_conditions", [])) or "none reported"
    medications = ", ".join(profile.get("current_medications", [])) or "none reported"
    allergies = ", ".join(profile.get("allergies", [])) or "none reported"
    return (
        f"Patient context — Age: {profile.get('age')}, "
        f"Conditions: {conditions}, Medications: {medications}, "
        f"Allergies: {allergies}, Lifestyle: {profile.get('lifestyle_factors')}"
    )

@app.post("/api/query", response_model=RAGResponse)
async def medical_query(query_data: MedicalQuery, current_user_id: str = Depends(get_current_user_id)):
    try:
        start_time = time.time()

        emergency = detect_emergency(query_data.query)
        if emergency:
            return RAGResponse(
                query=query_data.query,
                answer=format_emergency_message(emergency["reason"], query_data.language),
                retrieved_papers=[],
                personalized_insights=None,
                retrieval_score=0.0,
                response_time=time.time() - start_time,
                is_emergency=True
            )

        profile = None
        if query_data.include_personalization:
            profile = get_profile_by_owner(current_user_id)

        # Retrieval query stays narrow (question + condition names only) —
        # PubMed ANDs every keyword together, so stuffing in medications/age/
        # lifestyle too easily produces an over-specific query with zero hits.
        retrieval_query = query_data.query
        if profile and profile.get("medical_conditions"):
            retrieval_query = f"{query_data.query} ({', '.join(profile['medical_conditions'])})"

        # Answer query gets the full profile so the LLM's response (not the
        # PubMed search) resolves references like 'these conditions'.
        answer_query = query_data.query
        if profile:
            answer_query = f"{query_data.query}\n\n({build_profile_context(profile)})"

        raw_retrieved_papers = retrieve_relevant_papers(retrieval_query, top_k=3)
        # Filtered before generation so the model can only cite papers that
        # actually address the question — PubMed's AND-search can otherwise
        # return papers sharing keywords but not actually relevant, which the
        # model would then cite as if they supported an unrelated claim.
        retrieved_papers = filter_relevant_papers(query_data.query, raw_retrieved_papers) if raw_retrieved_papers else []
        answer = generate_rag_answer(answer_query, retrieved_papers, query_data.language)

        personalized_insights = None
        if profile:
            personalized_insights = generate_personalized_insights(profile, answer, query_data.language)

        response_time = time.time() - start_time
        # Reflects how many *relevant* papers were found vs. requested — not
        # a claim of AI "accuracy". 1.0 = full relevant result set found.
        retrieval_score = min(1.0, len(retrieved_papers) / 3)

        return RAGResponse(
            query=query_data.query,
            answer=answer,
            retrieved_papers=retrieved_papers,
            personalized_insights=personalized_insights,
            retrieval_score=retrieval_score,
            response_time=response_time
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health-info")
async def get_health_info():
    return {
        "medical_conditions": ["Hypertension", "Type 2 Diabetes", "Cardiovascular Disease", "Obesity", "Asthma", "Depression", "Arthritis"],
        "medications_categories": ["ACE Inhibitors", "Beta Blockers", "Statins", "Metformin", "Antidepressants", "Antihistamines", "Pain Relievers"],
        "common_allergies": ["Penicillin", "NSAIDs", "Peanuts", "Shellfish", "Pollen", "Dust Mites", "Latex"],
        "lifestyle_factors": ["Sedentary", "Moderately Active", "Very Active", "Smoker", "Former Smoker", "Non-Smoker"]
    }

@app.get("/api/stats")
async def get_statistics():
    return {
        "total_users": count_profiles(),
        "data_source": "PubMed (live, National Library of Medicine)",
        "system_status": "operational"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/")
async def root():
    return {"message": "Medical Literature RAG System API", "version": "1.0.0", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))