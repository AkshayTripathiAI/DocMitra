"""Pull structured fields out of OCR text, per document type.

Deterministic regexes only. Each field is
{"key", "label", "value", "sensitive"} (+ "confidence" when OCR words
are supplied). Sensitive values are masked before leaving the backend.
"""
import re
from datetime import date

_DATE = r"\d{2}[/.-]\d{2}[/.-]\d{4}"
# Names may contain OCR digit-for-letter swaps (RAME5H); _clean_name undoes them.
_NAME = r"[A-Z0-9][A-Za-z0-9 .]{2,60}"

# Which extracted field holds the person's name / the expiry, per type.
HOLDER_FIELD = {
    "AADHAAR": "name",
    "PAN": "name",
    "DRIVING_LICENCE": "name",
    "PASSPORT": "name",
    "RC": "owner_name",
    "VEHICLE_INSURANCE": "insured_name",
}
EXPIRY_FIELD = {
    "DRIVING_LICENCE": "valid_till",
    "PASSPORT": "expiry_date",
    "RC": "valid_upto",
    "VEHICLE_INSURANCE": "policy_end",
    "PUC": "valid_upto",
}


def parse_date(value: str) -> date | None:
    """dd/mm/yyyy, dd-mm-yyyy or dd.mm.yyyy -> date (Indian day-first order)."""
    m = re.fullmatch(r"\s*(\d{2})[/.-](\d{2})[/.-](\d{4})\s*", value or "")
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def mask(value: str) -> str:
    """Keep the last 4 alphanumerics visible: 1234 5678 9012 -> XXXX XXXX 9012."""
    total = sum(c.isalnum() for c in value)
    seen = 0
    out = []
    for c in value:
        if c.isalnum():
            seen += 1
            out.append(c if seen > total - 4 else "X")
        else:
            out.append(c)
    return "".join(out)


_AS_DIGIT = str.maketrans("OoIlSBZ", "0011582")
_AS_LETTER = str.maketrans("0158 2", "OISB Z")


def _digits(value: str) -> str:
    """Undo common OCR letter-for-digit swaps in a part that must be numeric."""
    return value.translate(_AS_DIGIT)


def _mostly_numeric(value: str) -> str:
    """Fix letter-for-digit swaps in IDs that are mostly digits (policy numbers)."""
    alnum = [c for c in value if c.isalnum()]
    if alnum and sum(c.isdigit() for c in alnum) / len(alnum) >= 0.7:
        return _digits(value)
    return value


# --- OCR text normalisation, applied before extraction --------------------------------
# Characters OCR engines commonly swap with digits, used to build fuzzy label patterns.
_CONFUSABLE = {"o": "o0", "i": "il1", "l": "li1", "s": "s5", "b": "b8", "z": "z2"}
_LABEL_WORDS = [
    "DOB", "Date", "Birth", "Valid", "Validity", "Till", "Upto", "Issue", "Expiry", "Policy",
    "Period", "Insurance", "Insured", "Name", "Father's", "Registration", "Regn", "Registered",
    "Owner", "Owner's", "Chassis", "Engine", "Fuel", "Certificate", "Number", "Surname", "Given",
    "Gender", "Address", "Driving", "Licence", "Passport", "Pollution", "Control", "Vehicle",
    "Premium", "Permanent", "Account", "Income", "Department", "Identification", "Authority",
]


def _fuzzy_word(word: str) -> re.Pattern:
    parts = []
    for ch in word:
        if ch.isalpha():
            options = set(_CONFUSABLE.get(ch.lower(), ch.lower()))
            parts.append("[" + "".join(sorted(re.escape(o) for o in options)) + "]")
        else:
            parts.append(re.escape(ch))
    return re.compile(rf"(?<![A-Za-z0-9]){''.join(parts)}(?![A-Za-z0-9])", re.IGNORECASE)


_LABEL_PATTERNS = [(_fuzzy_word(w), w) for w in _LABEL_WORDS]
_FUZZY_DATE = re.compile(
    r"(?<![A-Za-z0-9])([0-9OIlSBZ]{2})([/.\-1])([0-9OIlSBZ]{2})([/.\-1])([0-9OIlSBZ]{4})(?![A-Za-z0-9])"
)
_BILINGUAL = re.compile(r"[ 	]*/[ 	]*[ऀ-ॿ][ऀ-ॿ 	]*")


def _fix_date(m: re.Match) -> str:
    raw = m.group(0)
    if m.group(2) == "1" and m.group(4) == "1":
        return raw  # no real separator: probably an ID number, not a date
    dd, mm, yyyy = (_digits(m.group(i)) for i in (1, 3, 5))
    try:
        date(int(yyyy), int(mm), int(dd))
    except ValueError:
        return raw
    return f"{dd}/{mm}/{yyyy}"


def normalize_ocr_text(text: str) -> str:
    """Repair common OCR damage so the per-type patterns match.

    - drop the Hindi half of bilingual labels ("Name / नाम" -> "Name")
    - repair known label words ("D0B" -> "DOB", "Va1id" -> "Valid")
    - canonicalise dates with letter-for-digit swaps ("0I/O9/1984" -> "01/09/1984")
    """
    text = _BILINGUAL.sub("", text)
    for pattern, word in _LABEL_PATTERNS:
        text = pattern.sub(word, text)
    return _FUZZY_DATE.sub(_fix_date, text)


_REG = re.compile(
    r"(?<![A-Za-z0-9])([A-Z]{2})\s?([0-9OIl]{1,2})\s?([A-Z]{1,3})\s?([0-9OIlSB]{1,4})(?![A-Za-z0-9])"
)
_PAN = re.compile(r"(?<![A-Za-z0-9])([A-Z0-9]{3}[PCHFATBLJG][A-Z0-9])([0-9OIlSBZ]{4})([A-Z0-9])(?![A-Za-z0-9])")
_VIN_FIX = str.maketrans("OIQ", "010")  # VINs never contain I, O or Q


def _registration_number(text: str) -> str:
    """Vehicle number like MP09 AB 1234, tolerant of OCR swaps in the numeric parts."""
    for m in _REG.finditer(text):
        state, rto, series, num = m.groups()
        if sum(c.isdigit() for c in rto + num) >= 2:
            return f"{state}{_digits(rto)} {series} {_digits(num)}"
    return ""


def _pan_number(text: str) -> str:
    """PAN is AAAAA9999A: repair letter/digit swaps by position."""
    for m in _PAN.finditer(text):
        letters, digits, last = m.groups()
        if sum(c.isdigit() for c in digits) >= 2:
            return letters.translate(_AS_LETTER) + _digits(digits) + last.translate(_AS_LETTER)
    return ""


def _clean_name(value: str) -> str:
    value = re.sub(
        r"\s+(DOB|D\.O\.B\.?|Date|Year|Father|Mother|Husband|S/O|W/O|D/O|C/O|"
        r"Address|Gender|Male|Female|Sex|UID|Aadhaar|Valid|Chassis|Engine).*$",
        "", value.strip(), flags=re.IGNORECASE | re.DOTALL,
    )
    value = re.sub(r"\s+", " ", value).strip(" .")
    letters = sum(c.isalpha() for c in value)
    digits = sum(c.isdigit() for c in value)
    if letters < 2 or digits > letters / 3:
        return ""  # mostly digits: not a name (e.g. a date or ID grabbed by mistake)
    return value.translate(_AS_LETTER) if digits else value


def _grab(text: str, label: str, value: str, flags=re.IGNORECASE) -> str:
    m = re.search(rf"(?:{label})\s*[:\-]*\s*({value})", text, flags)
    return m.group(1).strip() if m else ""


def _field_confidence(words: list[dict], value: str) -> float | None:
    """Mean OCR confidence of the words that make up an extracted value."""
    tokens = [t.lower() for t in re.split(r"\s+", value) if len(t) > 2]
    confs = []
    for w in words:
        wt = str(w.get("text", "")).strip(",.:; ").lower()
        if len(wt) > 2 and any(wt in tok or tok in wt for tok in tokens):
            confs.append(float(w.get("confidence", 0.0)))
    return round(sum(confs) / len(confs), 3) if confs else None


def extract_fields(doc_type: str, text: str, words: list[dict] | None = None) -> list[dict]:
    fields: list[dict] = []
    if not text.strip():
        return fields
    text = normalize_ocr_text(text)

    def add(key: str, label: str, value: str, sensitive: bool = False):
        value = re.sub(r"\s+", " ", value or "").strip()
        if value and not any(f["key"] == key for f in fields):
            fields.append({"key": key, "label": label, "value": value, "sensitive": sensitive})

    if doc_type == "AADHAAR":
        m = re.search(r"\b(\d{4})\s?(\d{4})\s?(\d{4})\b", text)
        if m:
            add("aadhaar_number", "Aadhaar number", " ".join(m.groups()), sensitive=True)
        add("date_of_birth", "Date of birth",
            _grab(text, r"DOB|Date of Birth|D\.O\.B|जन्म तिथि", _DATE), sensitive=True)
        if not any(f["key"] == "date_of_birth" for f in fields):
            add("year_of_birth", "Year of birth", _grab(text, r"Year of Birth", r"\d{4}"))
        m = re.search(rf"(?:Name|नाम)\s*[:\-]*\s*({_NAME})", text)
        if m:
            add("name", "Name", _clean_name(m.group(1)))
        else:
            # Card fronts often print the name on the line above the DOB.
            m = re.search(rf"(?:^|\n)\s*({_NAME})\s*\n[^\n]*(?:DOB|Date of Birth|Year of Birth)", text)
            if m:
                add("name", "Name", _clean_name(m.group(1)))
        m = re.search(r"\b(MALE|FEMALE|TRANSGENDER)\b", text, re.IGNORECASE)
        if m:
            add("gender", "Gender", m.group(1).title())
        m = re.search(r"(?:S/O|D/O|W/O|C/O|Address)\s*[:\-]?\s*(.{10,200}?\b\d{6}\b)",
                      text, re.IGNORECASE | re.DOTALL)
        if m:
            add("address", "Address", m.group(1), sensitive=True)

    elif doc_type == "PAN":
        add("pan_number", "PAN", _pan_number(text), sensitive=True)
        m = re.search(rf"(?<!Father's )(?<!Father )Name\s*[:\-/]*\s*({_NAME})", text)
        if m:
            add("name", "Name", _clean_name(m.group(1)))
        add("father_name", "Father's name",
            _clean_name(_grab(text, r"Father'?s?\s*Name", _NAME, 0)))
        add("date_of_birth", "Date of birth",
            _grab(text, r"Date of Birth|DOB", _DATE), sensitive=True)

    elif doc_type == "DRIVING_LICENCE":
        m = re.search(r"\b([A-Z]{2})[-\s]?([\dOI]{2})[-\s]?([\dOI]{4})\s?([\dOI]{7})\b", text)
        if m:
            add("dl_number", "DL number",
                f"{m.group(1)}{_digits(m.group(2))} {_digits(m.group(3) + m.group(4))}",
                sensitive=True)
        add("name", "Name", _clean_name(_grab(text, r"(?<!Father's )Name", _NAME, 0)))
        add("date_of_birth", "Date of birth", _grab(text, r"DOB|Date of Birth", _DATE),
            sensitive=True)
        add("issue_date", "Issued on", _grab(text, r"Issue\s*Date|Date of Issue|DOI", _DATE))
        add("valid_till", "Valid till",
            _grab(text, r"Valid\s*Till|Validity\s*\(NT\)|Valid\s*Upto|NT\s*Valid\s*Till", _DATE))

    elif doc_type == "PASSPORT":
        # The machine-readable zone is the most reliable source when present.
        mrz = re.search(r"P<IND([A-Z<]+)\s*\n?\s*([A-Z]\d{7})", text.replace(" ", ""))
        if mrz:
            surname, _, given = mrz.group(1).partition("<<")
            add("name", "Name", f"{given.replace('<', ' ')} {surname.replace('<', ' ')}")
            add("passport_number", "Passport number", mrz.group(2), sensitive=True)
        else:
            m = re.search(r"\b([A-Z]\d{7})\b", text)
            if m:
                add("passport_number", "Passport number", m.group(1), sensitive=True)
            surname = _grab(text, r"Surname", r"[A-Z][A-Z ]{1,40}", 0)
            given = _grab(text, r"Given\s*Name\(?s?\)?", r"[A-Z][A-Z ]{1,40}", 0)
            if surname or given:
                add("name", "Name", _clean_name(f"{given} {surname}"))
        add("date_of_birth", "Date of birth", _grab(text, r"Date of Birth", _DATE),
            sensitive=True)
        add("issue_date", "Issued on", _grab(text, r"Date of Issue", _DATE))
        add("expiry_date", "Expires on", _grab(text, r"Date of Expiry", _DATE))

    elif doc_type == "RC":
        add("registration_number", "Registration number", _registration_number(text))
        add("owner_name", "Owner",
            _clean_name(_grab(text, r"Registered\s*Owner|Owner'?s?\s*Name|Name\s*of\s*Owner",
                              _NAME, 0)))
        add("chassis_number", "Chassis number",
            _grab(text, r"Chassis\s*(?:No\.?|Number)?", r"[A-Z0-9]{6,25}").translate(_VIN_FIX),
            sensitive=True)
        add("engine_number", "Engine number",
            _grab(text, r"Engine\s*(?:No\.?|Number)?", r"[A-Z0-9]{6,25}"), sensitive=True)
        add("registration_date", "Registered on",
            _grab(text, r"Registration\s*Date|Date\s*of\s*Registration|Regn\.?\s*Date", _DATE))
        add("valid_upto", "Registration valid till",
            _grab(text, r"Regn\.?\s*Valid(?:\s*Upto)?|Registration\s*Valid(?:\s*Upto)?|"
                        r"Valid\s*Upto|Fitness\s*Valid", _DATE))
        fuel = _grab(text, r"Fuel(?:\s*Type)?", r"[A-Za-z0-9/|]+").upper()
        add("fuel_type", "Fuel", re.sub(r"^(PETROL|DIESEL)[I1L|/](CNG|LPG)$", r"\1/\2", fuel))
        add("maker_model", "Make / model",
            _grab(text, r"Maker'?s?\s*(?:Name|Class)?|Make", r"[A-Z][A-Za-z0-9 .&/\-]{1,40}"))

    elif doc_type == "VEHICLE_INSURANCE":
        add("policy_number", "Policy number",
            _mostly_numeric(_grab(text, r"Policy\s*(?:No\.?|Number)", r"[A-Z0-9][A-Z0-9/\-]{5,30}")),
            sensitive=True)
        add("insured_name", "Insured",
            _clean_name(_grab(text, r"Insured'?s?\s*Name|Name\s*of\s*(?:the\s*)?Insured",
                              _NAME, 0)))
        m = re.search(rf"(?:Period of (?:Insurance|Cover)|Policy Period)[^\n]*?({_DATE})"
                      rf"[^\n]*?({_DATE})", text, re.IGNORECASE)
        if m:
            add("policy_start", "Cover from", m.group(1))
            add("policy_end", "Cover till", m.group(2))
        else:
            add("policy_end", "Cover till",
                _grab(text, r"(?:Policy\s*)?(?:Expiry|End)\s*Date|Valid\s*(?:Till|Upto)", _DATE))
        add("registration_number", "Vehicle", _registration_number(text))

    elif doc_type == "PUC":
        add("registration_number", "Vehicle", _registration_number(text))
        add("certificate_number", "Certificate number",
            _grab(text, r"(?:PUC|Certificate)\s*(?:No\.?|Number)", r"[A-Z0-9/\-]{5,30}"))
        add("valid_upto", "Valid till", _grab(text, r"Valid\s*(?:Till|Upto)|Validity", _DATE))

    if words:
        for f in fields:
            conf = _field_confidence(words, f["value"])
            if conf is not None:
                f["confidence"] = conf
    return fields


def field_value(fields: list[dict], key: str) -> str:
    return next((f["value"] for f in fields if f["key"] == key), "")


def masked_fields(fields: list[dict]) -> list[dict]:
    return [{**f, "value": mask(f["value"])} if f.get("sensitive") else f for f in fields]
