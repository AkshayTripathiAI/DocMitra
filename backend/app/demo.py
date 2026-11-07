"""Synthetic documents for the public demo.

Everything here is made up: the person, the numbers and the addresses. Dates are
relative to today so the demo always shows an expired, an expiring and a valid
document, plus a name mismatch across documents.
"""
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import services
from .agents.ingest import ingest_text
from .models import Document


def _d(days: int) -> str:
    return (date.today() + timedelta(days=days)).strftime("%d/%m/%Y")


def _samples() -> list[tuple[str, str]]:
    return [
        ("aadhaar-sample.txt", """Government of India
Rahul Kumar Sharma
DOB: 14/08/1990
Male
2345 6789 0123
Unique Identification Authority of India
Address: S/O Suresh Sharma, 12 MG Road, Indore, Madhya Pradesh 452001"""),
        ("pan-sample.txt", """INCOME TAX DEPARTMENT GOVT. OF INDIA
Permanent Account Number Card
ABCPS1234K
Name
RAHUL KUMAR SHARMA
Father's Name
SURESH SHARMA
Date of Birth
14/08/1990"""),
        ("driving-licence-sample.txt", f"""Union of India Driving Licence
DL No MP09 20150012345
Name: R KUMAR SHARMA
DOB: 14/08/1990
Issue Date: 03/02/2015
Valid Till: {_d(4 * 365)}
COV LMV"""),
        ("passport-sample.txt", f"""REPUBLIC OF INDIA
Passport
Surname SHARMA
Given Name(s) RAHUL KUMAR
Date of Birth 14/08/1990
Date of Issue 10/01/2018
Date of Expiry {_d(21)}"""),
        ("rc-sample.txt", f"""Certificate of Registration
Registration No MP09 AB 1234
Registered Owner: RAHUL KUMAR SHARMA
Chassis No: MA3EYD81S00123456
Engine No: K12MN1234567
Registration Date: 05/06/2019
Regn Valid Upto: {_d(8 * 365)}
Fuel: PETROL/CNG"""),
        ("insurance-sample.txt", f"""Private Car Package Policy - Certificate of Insurance
Policy No: 3001/12345678/00/000
Insured Name: RAHUL KUMAR
Period of Insurance: {_d(-375)} to {_d(-10)}
Vehicle MP09 AB 1234
IDV Rs 4,50,000  Premium Rs 9,876"""),
        ("puc-sample.txt", f"""Pollution Under Control Certificate
PUC No: MP0090012345
Vehicle MP09 AB 1234
CO % 0.12  HC (ppm) 80
Valid Upto: {_d(120)}"""),
    ]


def seed_demo(session: Session) -> int:
    """Load the sample documents once (no-op when documents already exist)."""
    if session.scalar(select(func.count()).select_from(Document)):
        return 0
    for filename, text in _samples():
        result = ingest_text(text)
        services.create_document(
            session, filename=filename, mime_type="text/plain", stored_path="", result=result,
        )
    return len(_samples())
