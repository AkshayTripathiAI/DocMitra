"""Checklists for common paperwork tasks.

Kept deliberately high-level: rules and fees change, so every procedure
points to the official portal and the assistant is told to say so.
"""

PROCEDURES: dict[str, dict] = {
    "passport_renewal": {
        "title": "Passport renewal / re-issue",
        "keywords": ["passport"],
        "portal": "https://www.passportindia.gov.in",
        "needs": ["PASSPORT", "AADHAAR"],
        "steps": [
            "Register / log in on the Passport Seva portal and fill the re-issue form.",
            "Pay the fee online and book a Passport Seva Kendra appointment.",
            "Carry your current passport and an address proof (e.g. Aadhaar) in original.",
        ],
    },
    "dl_renewal": {
        "title": "Driving licence renewal",
        "keywords": ["driving", "licence", "license", "dl"],
        "portal": "https://sarathi.parivahan.gov.in",
        "needs": ["DRIVING_LICENCE", "AADHAAR"],
        "steps": [
            "Apply for DL renewal on the Sarathi portal for your state.",
            "Upload your current licence, address proof and photo.",
            "If you are 40 or older, a medical certificate (Form 1A) is usually needed.",
            "Pay the fee; some RTOs ask you to visit for biometrics.",
        ],
    },
    "pan_aadhaar_link": {
        "title": "Link PAN with Aadhaar",
        "keywords": ["pan", "link"],
        "portal": "https://www.incometax.gov.in",
        "needs": ["PAN", "AADHAAR"],
        "steps": [
            "On the Income Tax e-filing portal, open 'Link Aadhaar'.",
            "Enter PAN and Aadhaar; your name and DOB must match on both.",
            "Pay the late fee if the portal asks for it, then verify with the OTP sent to your Aadhaar mobile.",
        ],
    },
    "aadhaar_address_update": {
        "title": "Update address on Aadhaar",
        "keywords": ["aadhaar", "address", "update"],
        "portal": "https://myaadhaar.uidai.gov.in",
        "needs": ["AADHAAR"],
        "steps": [
            "Log in on myAadhaar with the OTP on your registered mobile.",
            "Choose address update and upload a proof of address in your name.",
            "Pay the fee and keep the update request number (URN) to track it.",
        ],
    },
    "vehicle_insurance_renewal": {
        "title": "Vehicle insurance renewal",
        "keywords": ["insurance", "vehicle", "car", "bike"],
        "portal": "https://parivahan.gov.in",
        "needs": ["RC", "VEHICLE_INSURANCE", "PUC"],
        "steps": [
            "Renew with your insurer (or compare insurers) before the policy end date.",
            "Keep your RC and previous policy handy; a valid PUC is generally expected.",
            "Renewing before expiry protects your no-claim bonus.",
        ],
    },
}


def find_procedure(task: str) -> tuple[str, dict] | None:
    """Best keyword match for a free-text task, or None."""
    words = set(task.lower().replace("-", " ").split())
    if task in PROCEDURES:
        return task, PROCEDURES[task]
    best, best_hits = None, 0
    for key, proc in PROCEDURES.items():
        hits = sum(1 for k in proc["keywords"] if k in words)
        if hits > best_hits:
            best, best_hits = key, hits
    return (best, PROCEDURES[best]) if best else None
