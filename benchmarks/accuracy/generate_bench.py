"""
Generate PromptVeil-Bench v1, the in-repo labelled accuracy dataset.

Values follow each identifier's published format (checksums included), not
PromptVeil's detector regexes, so the set measures the detectors rather than
mirroring them. Spans are recorded while values are inserted, so labels are
correct by construction.

Run ``python -m benchmarks.accuracy.generate_bench`` to rewrite the JSONL file.
"""

from __future__ import annotations

import json
import random
import string
from typing import Callable

from benchmarks.accuracy.loaders import BENCH_PATH, DEFAULT_SEED

POSITIVES_PER_TYPE = 50
NEGATIVES_PER_CATEGORY = 50

DIGITS = string.digits
UPPER = string.ascii_uppercase
ALNUM = string.ascii_letters + string.digits

# ---------------------------------------------------------------------------
# Checksums
# ---------------------------------------------------------------------------

_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6], [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4], [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2], [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]
_VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def verhoeff_check_digit(digits: str) -> str:
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[(i + 1) % 8][int(ch)]]
    return str(_VERHOEFF_INV[c])


def verhoeff_valid(digits: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    return c == 0


def luhn_check_digit(digits: str) -> str:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - total % 10) % 10)


_GST_CHARS = string.digits + UPPER


def gstin_check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        v = _GST_CHARS.index(ch) * (2 if i % 2 else 1)
        total += v // 36 + v % 36
    return _GST_CHARS[(36 - total % 36) % 36]


# ---------------------------------------------------------------------------
# Value generators (one per PromptVeil type)
# ---------------------------------------------------------------------------


def _pick(rng: random.Random, chars: str, n: int) -> str:
    return "".join(rng.choice(chars) for _ in range(n))


def _sep(rng: random.Random, options: str = " -") -> str:
    return rng.choice(list(options) + [""])


def _maybe_lower(rng: random.Random, value: str, p: float = 0.1) -> str:
    return value.lower() if rng.random() < p else value


_FIRST = ["priya", "rahul", "anita", "john", "maria", "wei", "fatima", "arjun", "emily", "sanjay"]
_LAST = ["sharma", "patel", "iyer", "smith", "garcia", "chen", "khan", "reddy", "jones", "nair"]
_DOMAINS = [
    "gmail.com", "outlook.com", "yahoo.co.in", "acme-corp.com", "mail.example.org",
    "tcs.co.in", "dept.university.edu", "proton.me", "company.io", "rediffmail.com",
]


def gen_email(rng: random.Random) -> str:
    first, last = rng.choice(_FIRST), rng.choice(_LAST)
    local = rng.choice([
        f"{first}.{last}", f"{first}{rng.randint(1, 99)}", f"{first[0]}{last}",
        f"{first}_{last}", f"{first}+billing", f"{last}.{first}{rng.randint(1970, 2005)}",
    ])
    if rng.random() < 0.15:
        local = local.capitalize()
    return f"{local}@{rng.choice(_DOMAINS)}"


def gen_phone(rng: random.Random) -> str:
    area = f"{rng.randint(2, 9)}{rng.randint(0, 8)}{rng.randint(0, 9)}"
    exch = f"{rng.randint(2, 9)}{_pick(rng, DIGITS, 2)}"
    line = _pick(rng, DIGITS, 4)
    return rng.choice([
        f"({area}) {exch}-{line}", f"{area}-{exch}-{line}", f"{area}.{exch}.{line}",
        f"+1 {area} {exch} {line}", f"+1-{area}-{exch}-{line}", f"{area}{exch}{line}",
    ])


def gen_in_phone(rng: random.Random) -> str:
    num = f"{rng.randint(6, 9)}{_pick(rng, DIGITS, 9)}"
    return rng.choice([
        f"+91 {num[:5]} {num[5:]}", f"+91-{num}", f"+91{num}", f"0{num}",
        f"{num[:5]} {num[5:]}", f"+91 {num[:5]}-{num[5:]}",
    ])


def gen_credit_card(rng: random.Random) -> str:
    brand = rng.choice(["visa", "mc", "mc2", "amex", "discover"])
    if brand == "amex":
        body = rng.choice(["34", "37"]) + _pick(rng, DIGITS, 12)
        number = body + luhn_check_digit(body)
        s = _sep(rng)
        return f"{number[:4]}{s}{number[4:10]}{s}{number[10:]}"
    prefix = {
        "visa": "4",
        "mc": f"5{rng.randint(1, 5)}",
        "mc2": str(rng.randint(2221, 2720)),
        "discover": rng.choice(["6011", "65"]),
    }[brand]
    body = prefix + _pick(rng, DIGITS, 15 - len(prefix))
    number = body + luhn_check_digit(body)
    s = _sep(rng)
    return s.join(number[i:i + 4] for i in range(0, 16, 4))


_URLSAFE = ALNUM + "-_"


def gen_api_key(rng: random.Random) -> str:
    return rng.choice([
        lambda: "sk-" + _pick(rng, ALNUM, 48),
        lambda: "sk-proj-" + _pick(rng, _URLSAFE, 64),
        lambda: "sk-ant-api03-" + _pick(rng, _URLSAFE, 93) + "AA",
        lambda: "ghp_" + _pick(rng, ALNUM, 36),
        lambda: "github_pat_" + _pick(rng, ALNUM, 22) + "_" + _pick(rng, ALNUM, 59),
        lambda: "AKIA" + _pick(rng, UPPER + DIGITS, 16),
        lambda: f"xoxb-{_pick(rng, DIGITS, 12)}-{_pick(rng, DIGITS, 13)}-{_pick(rng, ALNUM, 24)}",
        lambda: "AIza" + _pick(rng, _URLSAFE, 35),
        lambda: "sk_live_" + _pick(rng, ALNUM, 24),
    ])()


def gen_ssn(rng: random.Random) -> str:
    area = rng.choice([a for a in range(1, 900) if a != 666])
    group, serial = rng.randint(1, 99), rng.randint(1, 9999)
    s = rng.choice(["-", "-", " ", ""])
    return f"{area:03d}{s}{group:02d}{s}{serial:04d}"


_EIN_PREFIXES = (
    [1, 2, 3, 4, 5, 6] + list(range(10, 17)) + list(range(20, 28)) + list(range(30, 49))
    + list(range(50, 69)) + list(range(71, 78)) + list(range(80, 89)) + list(range(90, 96)) + [98, 99]
)


def gen_us_ein(rng: random.Random) -> str:
    prefix = rng.choice(_EIN_PREFIXES)
    sep = "-" if rng.random() < 0.8 else ""
    return f"{prefix:02d}{sep}{_pick(rng, DIGITS, 7)}"


def gen_us_passport(rng: random.Random) -> str:
    # Older books are 9 digits; Next Generation books are a letter + 8 digits.
    if rng.random() < 0.5:
        return str(rng.randint(1, 9)) + _pick(rng, DIGITS, 8)
    return rng.choice(UPPER) + _pick(rng, DIGITS, 8)


def gen_in_aadhaar(rng: random.Random) -> str:
    body = str(rng.randint(2, 9)) + _pick(rng, DIGITS, 10)
    number = body + verhoeff_check_digit(body)
    s = rng.choice([" ", " ", "-", ""])
    return f"{number[:4]}{s}{number[4:8]}{s}{number[8:]}"


_PAN_HOLDER_TYPES = "PCHFATBLJG"


def _pan(rng: random.Random) -> str:
    return _pick(rng, UPPER, 3) + rng.choice(_PAN_HOLDER_TYPES) + rng.choice(UPPER) + _pick(rng, DIGITS, 4) + rng.choice(UPPER)


def gen_in_pan(rng: random.Random) -> str:
    return _maybe_lower(rng, _pan(rng))


_IN_PASSPORT_LETTERS = "".join(c for c in UPPER if c not in "QXZ")


def gen_in_passport(rng: random.Random) -> str:
    return rng.choice(_IN_PASSPORT_LETTERS) + str(rng.randint(1, 9)) + _pick(rng, DIGITS, 6)


def gen_in_voter_id(rng: random.Random) -> str:
    return _maybe_lower(rng, _pick(rng, UPPER, 3) + _pick(rng, DIGITS, 7))


_BANK_CODES = ["SBIN", "HDFC", "ICIC", "UTIB", "PUNB", "KKBK", "BARB", "CNRB", "IDIB", "YESB"]


def gen_in_ifsc(rng: random.Random) -> str:
    branch = _pick(rng, DIGITS, 6) if rng.random() < 0.8 else _pick(rng, UPPER + DIGITS, 6)
    return _maybe_lower(rng, rng.choice(_BANK_CODES) + "0" + branch)


def gen_in_gstin(rng: random.Random) -> str:
    state = f"{rng.randint(1, 38):02d}"
    entity = rng.choice("123456789" + UPPER[:5])
    first14 = state + _pan(rng) + entity + "Z"
    return _maybe_lower(rng, first14 + gstin_check_char(first14))


GENERATORS: dict[str, Callable[[random.Random], str]] = {
    "email": gen_email,
    "phone": gen_phone,
    "in_phone": gen_in_phone,
    "credit_card": gen_credit_card,
    "api_key": gen_api_key,
    "ssn": gen_ssn,
    "us_passport": gen_us_passport,
    "us_ein": gen_us_ein,
    "in_aadhaar": gen_in_aadhaar,
    "in_pan": gen_in_pan,
    "in_passport": gen_in_passport,
    "in_voter_id": gen_in_voter_id,
    "in_ifsc": gen_in_ifsc,
    "in_gstin": gen_in_gstin,
}

NOUNS: dict[str, list[str]] = {
    "email": ["email", "email address", "e-mail"],
    "phone": ["phone number", "cell number", "contact number"],
    "in_phone": ["mobile number", "phone no", "WhatsApp number"],
    "credit_card": ["card number", "credit card", "card no"],
    "api_key": ["API key", "token", "secret key"],
    "ssn": ["SSN", "social security number"],
    "us_passport": ["US passport number", "passport no"],
    "us_ein": ["EIN", "employer ID number", "federal tax ID"],
    "in_aadhaar": ["Aadhaar number", "Aadhaar", "Aadhaar no"],
    "in_pan": ["PAN", "PAN number", "PAN card no"],
    "in_passport": ["passport number", "Indian passport no"],
    "in_voter_id": ["voter ID", "EPIC number"],
    "in_ifsc": ["IFSC code", "IFSC", "branch IFSC"],
    "in_gstin": ["GSTIN", "GST number", "GST no"],
}

# ``{v}`` is the value; ``{noun}``/``{Noun}``/``{key}``/``{KEY}`` name the field.
POSITIVE_TEMPLATES = [
    # chat prompts
    "Hi, my {noun} is {v}. Can you check my account?",
    "Please update my {noun} to {v} in your records.",
    "{v} is my {noun}, use that for the KYC.",
    "Can you draft an email confirming the {noun} {v} for the client?",
    "Summarize this: customer called, gave {noun} {v}, wants a refund.",
    "Mera {noun} {v} hai, please verify kar dijiye.",
    "my {noun} - {v}",
    "Is this {noun} valid? {v}",
    "Translate to Hindi: 'Your {noun} ({v}) has been registered.'",
    "I typed {v} as the {noun} but the form rejected it, why?",
    # support tickets
    "Ticket #48213\nSubject: Login issue\nCustomer {noun}: {v}\nPriority: High",
    "Escalation from support:\n- {Noun}: {v}\n- Issue: duplicate charge",
    "[Support] User reports the {noun} '{v}' was saved incorrectly.",
    "Hello team,\nKindly re-verify the {noun} {v} provided by the applicant.\nRegards,\nPriya",
    'Customer says: "{v}" is the right {noun}, not the old one.',
    # forms
    "Name: R. Sharma\n{Noun}: {v}\nCity: Pune",
    "{key}={v}",
    "| Field | Value |\n|---|---|\n| {Noun} | {v} |",
    '{{"{key}": "{v}", "verified": false}}',
    "{Noun}:\n{v}",
    # logs and config
    "INFO user.update field={key} value={v}",
    "WARN request payload contained {key}={v}",
    "DEBUG headers: {{'X-User': 'u_481', '{key}': '{v}'}}",
    "export {KEY}={v}",
    "error: validation failed for {key} ({v})",
    # misc
    "Note to self -> {noun}: {v}",
    "Forwarding the {noun} {v}; please keep it confidential.",
    "Applicant details below.\n\n{v}\n\n(above is the {noun})",
    "Pls send OTP. {noun} {v} thx",
    "We received {v} as {noun} from the vendor portal yesterday.",
]

# ---------------------------------------------------------------------------
# Hard negatives: text that must not be flagged
# ---------------------------------------------------------------------------


def neg_order_id(rng: random.Random) -> str:
    return rng.choice([
        f"ORD-2026-{_pick(rng, DIGITS, 6)}", f"INV-{rng.randint(2020, 2026)}-{_pick(rng, DIGITS, 5)}",
        f"PO-{_pick(rng, DIGITS, 5)}/{_pick(rng, DIGITS, 2)}", f"#{_pick(rng, DIGITS, 7)}",
    ])


def neg_timestamp(rng: random.Random) -> str:
    y, mo, d = rng.randint(2020, 2026), rng.randint(1, 12), rng.randint(1, 28)
    h, mi, s = rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59)
    return rng.choice([
        f"{y}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}Z",
        f"{d:02d}/{mo:02d}/{y} {h:02d}:{mi:02d}",
        f"{y}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}:{s:02d}.{rng.randint(0, 999):03d}",
    ])


def neg_version(rng: random.Random) -> str:
    a, b, c = rng.randint(0, 9), rng.randint(0, 30), rng.randint(0, 40)
    return rng.choice([f"v{a}.{b}.{c}", f"{a}.{b}.{c}-rc.{rng.randint(1, 5)}", f"{a}.{b}.{c}+build.{rng.randint(100, 9999)}"])


def neg_invalid_aadhaar(rng: random.Random) -> str:
    while True:
        number = str(rng.randint(2, 9)) + _pick(rng, DIGITS, 11)
        if not verhoeff_valid(number):
            return f"{number[:4]} {number[4:8]} {number[8:]}"


def neg_nine_digit(rng: random.Random) -> str:
    return _pick(rng, DIGITS, 9)


def neg_lookalike_id(rng: random.Random) -> str:
    pan = _pan(rng)
    return rng.choice([
        pan[:9],                                     # PAN missing its last letter
        pan[:3] + "Q" + pan[4:],                     # invalid PAN holder-type char
        pan[:9] + rng.choice(DIGITS),                # digit where a letter belongs
        "27" + pan + "1X" + rng.choice(DIGITS),      # GSTIN without the fixed 'Z'
    ])


NEGATIVES: dict[str, tuple[Callable[[random.Random], str], list[str]]] = {
    "order_id": (neg_order_id, [
        "Your order {v} has shipped.", "Refund for {v} processed.", "Invoice {v} is overdue, please pay.",
    ]),
    "timestamp": (neg_timestamp, [
        "Meeting moved to {v}.", "Last login: {v}", "Job finished at {v} with status OK.",
    ]),
    "version": (neg_version, [
        "Upgrade to {v} fixes the bug.", "Running build {v} on staging.", "pip install promptveil=={v}",
    ]),
    "invalid_aadhaar": (neg_invalid_aadhaar, [
        "Reference number {v} for your request.", "Booking ref: {v}", "Consignment {v} dispatched.",
    ]),
    "nine_digit": (neg_nine_digit, [
        "Tracking number {v}, arriving Friday.", "Your ticket ID is {v}.", "Batch {v} passed QA.",
    ]),
    "lookalike_id": (neg_lookalike_id, [
        "Product SKU {v} is out of stock.", "Coupon code {v} expired yesterday.", "Part no. {v} ordered.",
    ]),
}

# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def _fill(template: str, value: str, **fields: str) -> tuple[str, int]:
    """Render *template*; return the text and where ``{v}`` landed."""
    before, after = template.split("{v}")
    prefix = before.format(**fields)
    return prefix + value + after.format(**fields), len(prefix)


def generate(seed: int = DEFAULT_SEED) -> list[dict]:
    rng = random.Random(seed)
    rows: list[dict] = []

    for label, gen in GENERATORS.items():
        for i in range(POSITIVES_PER_TYPE):
            value = gen(rng)
            noun = rng.choice(NOUNS[label])
            key = noun.lower().replace(" ", "_").replace("-", "_")
            text, start = _fill(
                rng.choice(POSITIVE_TEMPLATES), value,
                noun=noun, Noun=noun[0].upper() + noun[1:], key=key, KEY=key.upper(),
            )
            rows.append({
                "id": f"pos-{label}-{i:02d}",
                "text": text,
                "spans": [{"start": start, "end": start + len(value), "label": label}],
            })

    for category, (gen, templates) in NEGATIVES.items():
        for i in range(NEGATIVES_PER_CATEGORY):
            text, _ = _fill(rng.choice(templates), gen(rng))
            rows.append({"id": f"neg-{category}-{i:02d}", "text": text, "spans": []})

    return sorted(rows, key=lambda r: r["id"])


def serialize(rows: list[dict]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)


def main() -> None:
    BENCH_PATH.parent.mkdir(parents=True, exist_ok=True)
    BENCH_PATH.write_text(serialize(generate()), encoding="utf-8")
    print(f"Wrote {BENCH_PATH}")


if __name__ == "__main__":
    main()
