"""
DocCheck - a PDF validation website built with Flask.

Run:
    pip install flask pypdf
    python app.py
Then open http://127.0.0.1:5000
"""

import re
from io import BytesIO

from flask import Flask, jsonify, render_template, request
from pypdf import PdfReader

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB upload limit

# "adobe" is left out on purpose: many genuine PDFs are made by Adobe software.
SUSPICIOUS_TOOLS = ["canva", "picsart", "photoshop"]

CHECKS = {
    "College name": r"([A-Za-z.&' ]+?)\s+college of engineering",
     "faculty cadre ratio":r"\d{1}:\d{1}:\d{1}",
    "Date": r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
}


def read_pdf(file_bytes):
    reader = PdfReader(BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        text += (page.extract_text() or "") + "\n"
    return reader, text


def run_checks(text):
    results = []
    for label, pattern in CHECKS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        found = None
        if match:
            found = (match.group(1) if match.groups() else match.group(0)).strip()
        results.append({"label": label, "passed": match is not None, "found": found})
    return results


def read_metadata(reader):
    meta = reader.metadata
    if meta is None:
        return {"found": False, "producer": None, "creator": None, "flagged": []}
    producer = meta.producer or ""
    creator = meta.creator or ""
    combined = (producer + " " + creator).lower()
    return {
        "found": True,
        "producer": producer or None,
        "creator": creator or None,
        "flagged": [t for t in SUSPICIOUS_TOOLS if t in combined],
    }


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/validate", methods=["POST"])
def validate():
    file = request.files.get("pdf")
    if file is None or file.filename == "":
        return jsonify(error="Please choose a PDF file."), 400
    if not file.filename.lower().endswith(".pdf"):
        return jsonify(error="Only PDF files are supported."), 400

    try:
        reader, text = read_pdf(file.read())
    except Exception:
        return jsonify(error="This PDF could not be read. It may be corrupted or password protected."), 400

    if not text.strip():
        return jsonify(error="No text found. This PDF may be a scan or an image."), 400

    checks = run_checks(text)
    meta = read_metadata(reader)
    all_passed = all(c["passed"] for c in checks)

    if all_passed and not meta["flagged"]:
        verdict = "pass"
    elif all_passed:
        verdict = "warn"
    else:
        verdict = "fail"

    return jsonify(verdict=verdict, checks=checks, metadata=meta, filename=file.filename)


@app.errorhandler(413)
def too_large(_):
    return jsonify(error="File is too large. The limit is 10 MB."), 413


if __name__ == "__main__":
    app.run(debug=True)
