"""Generate the labelled extraction dataset (synthetic, seeded, versioned).

Every person, number and address is made up. Each sample is the OCR-style text of
one document plus its ground truth: document type, expected field values, holder
name and expiry date. Samples vary by layout (real cards print the same field in
different ways) and by OCR noise level (clean, light, heavy).

    python -m evals.generate            # writes evals/data/extraction_v1.jsonl
"""
import json
import random
import string
from datetime import date, timedelta
from pathlib import Path

SEED = 20261108
OUT = Path(__file__).parent / "data" / "extraction_v1.jsonl"

FIRST = ["Rahul", "Priya", "Amit", "Sneha", "Vikram", "Anjali", "Rohit", "Kavya", "Arjun", "Meera",
         "Sanjay", "Pooja", "Nikhil", "Divya", "Karan", "Ritu", "Manish", "Neha", "Suresh", "Asha"]
MIDDLE = ["Kumar", "Kumari", "Prasad", "Devi", "Singh", "", "", "", "Lal", "Chandra"]
LAST = ["Sharma", "Verma", "Gupta", "Patel", "Iyer", "Reddy", "Nair", "Joshi", "Mishra", "Yadav",
        "Chauhan", "Mehta", "Rao", "Das", "Pandey"]
STATES = ["MP", "UP", "MH", "KA", "DL", "RJ", "GJ", "TN", "WB", "HR"]
CITIES = [("Indore", "Madhya Pradesh", "452001"), ("Lucknow", "Uttar Pradesh", "226001"),
          ("Pune", "Maharashtra", "411001"), ("Mysuru", "Karnataka", "570001"),
          ("Jaipur", "Rajasthan", "302001"), ("Surat", "Gujarat", "395003")]
FUELS = ["PETROL", "DIESEL", "PETROL/CNG", "ELECTRIC"]
INSURERS = ["Private Car Package Policy", "Two Wheeler Package Policy", "Motor Insurance Policy Schedule"]

# OCR confusions seen on Indian ID scans (letter <-> digit, punctuation drops).
CONFUSIONS = {"O": "0", "0": "O", "I": "1", "1": "I", "S": "5", "5": "S", "B": "8", "8": "B",
              "l": "1", "Z": "2", ":": "", "/": "1"}
NOISE_LEVELS = {"clean": 0.0, "light": 0.02, "heavy": 0.06}


def ddmmyyyy(d: date, sep: str = "/") -> str:
    return d.strftime(f"%d{sep}%m{sep}%Y")


def iso(d: date) -> str:
    return d.isoformat()


def add_ocr_noise(text: str, p: float, rng: random.Random) -> str:
    if p <= 0:
        return text
    out = []
    for ch in text:
        r = rng.random()
        if ch in CONFUSIONS and r < p:
            out.append(CONFUSIONS[ch])
        elif ch == " " and r < p / 3:
            continue  # merged words
        else:
            out.append(ch)
    return "".join(out)


class Person:
    def __init__(self, rng: random.Random):
        self.first = rng.choice(FIRST)
        self.middle = rng.choice(MIDDLE)
        self.last = rng.choice(LAST)
        self.father = f"{rng.choice(['Suresh', 'Ramesh', 'Mahesh', 'Dinesh', 'Rajesh'])} {self.last}"
        self.dob = date(rng.randint(1960, 2004), rng.randint(1, 12), rng.randint(1, 28))
        self.gender = "Female" if self.first in {"Priya", "Sneha", "Anjali", "Kavya", "Meera", "Pooja",
                                                  "Divya", "Ritu", "Neha", "Asha"} else "Male"

    @property
    def full(self) -> str:
        return " ".join(p for p in (self.first, self.middle, self.last) if p)

    @property
    def upper(self) -> str:
        return self.full.upper()


def rand_digits(rng, n):
    return "".join(rng.choice(string.digits) for _ in range(n))


def rand_upper(rng, n):
    return "".join(rng.choice(string.ascii_uppercase) for _ in range(n))


def vehicle_no(rng) -> str:
    return f"{rng.choice(STATES)}{rng.randint(1, 40):02d} {rand_upper(rng, 2)} {rng.randint(1000, 9999)}"


# --- one builder per document type: returns (text, fields, holder, expiry) per layout ---

def aadhaar(rng, p, layout):
    number = f"{rng.randint(2, 9)}{rand_digits(rng, 3)} {rand_digits(rng, 4)} {rand_digits(rng, 4)}"
    city, state, pin = rng.choice(CITIES)
    if layout == 0:  # card front: name on the line above DOB
        text = (f"Government of India\n{p.full}\nDOB: {ddmmyyyy(p.dob)}\n{p.gender}\n{number}\n"
                f"Unique Identification Authority of India\n"
                f"Address: S/O {p.father}, {rng.randint(1, 99)} MG Road, {city}, {state} {pin}")
    else:  # e-Aadhaar print with explicit labels
        text = (f"Unique Identification Authority of India\nGovernment of India\nName: {p.full}\n"
                f"Date of Birth: {ddmmyyyy(p.dob)}\nGender: {p.gender.upper()}\n"
                f"Aadhaar No: {number}\nC/O {p.father}, Ward {rng.randint(1, 30)}, {city}, {state} {pin}")
    fields = {"aadhaar_number": number, "date_of_birth": ddmmyyyy(p.dob), "name": p.full,
              "gender": p.gender}
    return text, fields, p.full, None


def pan(rng, p, layout):
    number = f"{rand_upper(rng, 3)}P{p.last[0]}{rand_digits(rng, 4)}{rand_upper(rng, 1)}"
    if layout == 0:
        text = (f"INCOME TAX DEPARTMENT GOVT. OF INDIA\nPermanent Account Number Card\n{number}\n"
                f"Name\n{p.upper}\nFather's Name\n{p.father.upper()}\nDate of Birth\n{ddmmyyyy(p.dob)}")
    else:
        text = (f"आयकर विभाग INCOME TAX DEPARTMENT\nभारत सरकार GOVT. OF INDIA\n"
                f"Permanent Account Number\n{number}\nName / नाम\n{p.upper}\n"
                f"Father's Name / पिता का नाम\n{p.father.upper()}\nDOB {ddmmyyyy(p.dob)}")
    fields = {"pan_number": number, "name": p.upper, "father_name": p.father.upper(),
              "date_of_birth": ddmmyyyy(p.dob)}
    return text, fields, p.upper, None


def driving_licence(rng, p, layout):
    state = rng.choice(STATES)
    rto = rng.randint(1, 40)
    issued = date(rng.randint(2008, 2022), rng.randint(1, 12), rng.randint(1, 28))
    valid = issued.replace(year=issued.year + 20) - timedelta(days=1)
    number = f"{state}{rto:02d} {issued.year}{rand_digits(rng, 7)}"
    raw_number = number if layout == 0 else number.replace(" ", "-", 1)
    label = "Valid Till" if layout == 0 else "Validity (NT)"
    text = (f"Union of India Driving Licence\nDL No {raw_number}\nName: {p.upper}\n"
            f"DOB: {ddmmyyyy(p.dob)}\nIssue Date: {ddmmyyyy(issued)}\n{label}: {ddmmyyyy(valid)}\nCOV LMV MCWG")
    fields = {"dl_number": number, "name": p.upper, "date_of_birth": ddmmyyyy(p.dob),
              "issue_date": ddmmyyyy(issued), "valid_till": ddmmyyyy(valid)}
    return text, fields, p.upper, iso(valid)


def passport(rng, p, layout):
    number = f"{rand_upper(rng, 1)}{rand_digits(rng, 7)}"
    issued = date(rng.randint(2016, 2024), rng.randint(1, 12), rng.randint(1, 28))
    expiry = issued.replace(year=issued.year + 10) - timedelta(days=1)
    given = " ".join(x for x in (p.first, p.middle) if x).upper()
    text = (f"REPUBLIC OF INDIA\nPassport\nPassport No. {number}\nSurname {p.last.upper()}\n"
            f"Given Name(s) {given}\nDate of Birth {ddmmyyyy(p.dob)}\n"
            f"Date of Issue {ddmmyyyy(issued)}\nDate of Expiry {ddmmyyyy(expiry)}")
    if layout == 0:  # photo page including the machine-readable zone
        mrz_name = f"{p.last.upper()}<<{given.replace(' ', '<')}"
        text += f"\nP<IND{mrz_name}{'<' * max(0, 39 - len(mrz_name))}\n{number}<8IND{p.dob:%y%m%d}"
    fields = {"passport_number": number, "name": f"{given} {p.last.upper()}",
              "date_of_birth": ddmmyyyy(p.dob), "issue_date": ddmmyyyy(issued),
              "expiry_date": ddmmyyyy(expiry)}
    return text, fields, f"{given} {p.last.upper()}", iso(expiry)


def rc(rng, p, layout):
    reg = vehicle_no(rng)
    vin_letters = [c for c in string.ascii_uppercase if c not in "IOQ"]  # VIN alphabet
    chassis = ("".join(rng.choice(vin_letters) for _ in range(3)) + rand_digits(rng, 5)
               + "".join(rng.choice(vin_letters) for _ in range(2)) + rand_digits(rng, 7))
    engine = rand_upper(rng, 2) + rand_digits(rng, 10)
    registered = date(rng.randint(2010, 2023), rng.randint(1, 12), rng.randint(1, 28))
    valid = registered.replace(year=registered.year + 15) - timedelta(days=1)
    fuel = rng.choice(FUELS)
    if layout == 0:
        text = (f"Certificate of Registration\nRegistration No {reg}\nRegistered Owner: {p.upper}\n"
                f"Chassis No: {chassis}\nEngine No: {engine}\nRegistration Date: {ddmmyyyy(registered)}\n"
                f"Regn Valid Upto: {ddmmyyyy(valid)}\nFuel: {fuel}")
    else:  # smart-card RC layout
        text = (f"FORM 23A REGISTRATION CERTIFICATE\nRegn. No. {reg}\nOwner's Name {p.upper}\n"
                f"Chassis Number {chassis}\nEngine Number {engine}\nDate of Registration {ddmmyyyy(registered)}\n"
                f"Registration Valid Upto {ddmmyyyy(valid)}\nFuel Type {fuel}")
    fields = {"registration_number": reg, "owner_name": p.upper, "chassis_number": chassis,
              "engine_number": engine, "registration_date": ddmmyyyy(registered),
              "valid_upto": ddmmyyyy(valid), "fuel_type": fuel}
    return text, fields, p.upper, iso(valid)


def insurance(rng, p, layout):
    policy = f"{rand_digits(rng, 4)}/{rand_digits(rng, 8)}/{rand_digits(rng, 2)}/000"
    start = date(rng.randint(2024, 2026), rng.randint(1, 12), rng.randint(1, 28))
    end = start.replace(year=start.year + 1) - timedelta(days=1)
    reg = vehicle_no(rng)
    if layout == 0:
        text = (f"{rng.choice(INSURERS)} - Certificate of Insurance\nPolicy No: {policy}\n"
                f"Insured Name: {p.upper}\nPeriod of Insurance: {ddmmyyyy(start)} to {ddmmyyyy(end)}\n"
                f"Vehicle {reg}\nIDV Rs 4,50,000  Premium Rs {rng.randint(3000, 25000):,}")
    else:
        text = (f"Motor Insurance - Policy Schedule\nPolicy Number {policy}\n"
                f"Name of the Insured {p.upper}\nRegistration No {reg}\n"
                f"Policy Period From {ddmmyyyy(start)} To {ddmmyyyy(end)}\nTotal Premium Rs {rng.randint(3000, 25000)}")
    fields = {"policy_number": policy, "insured_name": p.upper, "policy_start": ddmmyyyy(start),
              "policy_end": ddmmyyyy(end), "registration_number": reg}
    return text, fields, p.upper, iso(end)


def puc(rng, p, layout):
    reg = vehicle_no(rng)
    cert = f"{reg[:2]}{rand_digits(rng, 10)}"
    tested = date(2026, rng.randint(1, 12), rng.randint(1, 28))
    valid = tested + timedelta(days=rng.choice([180, 365]))
    if layout == 0:
        text = (f"Pollution Under Control Certificate\nPUC No: {cert}\nVehicle {reg}\n"
                f"CO % 0.{rng.randint(10, 40)}  HC (ppm) {rng.randint(50, 200)}\nValid Upto: {ddmmyyyy(valid)}")
    else:
        text = (f"PUCC - Emission Test Report\nCertificate No {cert}\nRegistration No {reg}\n"
                f"Test Date {ddmmyyyy(tested)}\nValidity {ddmmyyyy(valid)}\nResult PASS")
    fields = {"registration_number": reg, "certificate_number": cert, "valid_upto": ddmmyyyy(valid)}
    return text, fields, None, iso(valid)


BUILDERS = {
    "AADHAAR": (aadhaar, 2), "PAN": (pan, 2), "DRIVING_LICENCE": (driving_licence, 2),
    "PASSPORT": (passport, 2), "RC": (rc, 2), "VEHICLE_INSURANCE": (insurance, 2), "PUC": (puc, 2),
}
PEOPLE_PER_LAYOUT = 5


def generate() -> list[dict]:
    rng = random.Random(SEED)
    samples = []
    for doc_type, (builder, layouts) in BUILDERS.items():
        for layout in range(layouts):
            for i in range(PEOPLE_PER_LAYOUT):
                person = Person(rng)
                text, fields, holder, expiry = builder(rng, person, layout)
                for noise, p in NOISE_LEVELS.items():
                    samples.append({
                        "id": f"{doc_type.lower()}-l{layout}-{i}-{noise}",
                        "doc_type": doc_type,
                        "layout": layout,
                        "noise": noise,
                        "text": add_ocr_noise(text, p, rng),
                        "expected": {"fields": fields, "holder_name": holder, "expiry_date": expiry},
                    })
    return samples


def main():
    samples = generate()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"Wrote {len(samples)} samples to {OUT}")


if __name__ == "__main__":
    main()
