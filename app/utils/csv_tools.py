import csv
import io

CSV_HEADERS = ["email", "password", "proxy", "match_name"]
MAX_CSV_ROWS = 200


def generate_template_csv(match_name: str) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADERS)
    writer.writerow(["", "", "", match_name])
    return buf.getvalue()


class CsvValidationError(Exception):
    pass


def parse_accounts_csv(file_stream, match_name: str) -> list[dict]:
    """file_stream: a text-mode stream (already decoded). Returns a list of
    row dicts: {email, password, proxy, match_name}. match_name is always
    forced to the match this upload is for, regardless of what's in the
    CSV, since the match is selected via the page the file was uploaded
    from - this prevents a stale/edited CSV from silently targeting a
    different match."""
    reader = csv.DictReader(file_stream)

    if not reader.fieldnames:
        raise CsvValidationError("The CSV file appears to be empty.")

    normalized_fields = {f.strip().lower() for f in reader.fieldnames if f}
    required = {"email", "password"}
    missing = required - normalized_fields
    if missing:
        raise CsvValidationError(
            f"Missing required column(s): {', '.join(sorted(missing))}. "
            f"Expected headers: {', '.join(CSV_HEADERS)}"
        )

    rows = []
    for i, raw_row in enumerate(reader, start=2):  # row 1 is the header
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw_row.items()}
        email = row.get("email", "")
        password = row.get("password", "")
        if not email and not password:
            continue  # skip blank rows
        if not email or not password:
            raise CsvValidationError(f"Row {i}: both email and password are required.")

        rows.append(
            {
                "email": email,
                "password": password,
                "proxy": row.get("proxy", "") or None,
                "match_name": match_name,
            }
        )

        if len(rows) > MAX_CSV_ROWS:
            raise CsvValidationError(f"Too many rows - please upload {MAX_CSV_ROWS} accounts or fewer at a time.")

    if not rows:
        raise CsvValidationError("No account rows found in the CSV.")

    return rows
