"""ETL Extract: read a dataset directory into RawQuestion dataclasses.

Pure file I/O + parsing. No DB, no business logic.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Bilingual:
    en: str
    zh: str


@dataclass
class RawSource:
    book: str
    edition: int
    section: str
    chapter: int
    chapter_title: str
    number: int


@dataclass
class RawOption:
    key: str
    text: Bilingual


@dataclass
class RawPromptItem:
    key: str
    text: Bilingual


@dataclass
class RawQuestion:
    id: str
    source: RawSource
    type: str
    stem: Bilingual
    options: list[RawOption]
    correct_keys: list[str]
    explanation: Bilingual
    meta: dict
    prompt_items: list[RawPromptItem] | None = None
    # Enrichment fields (PRD §10 import template / FR-ETL-09). All optional:
    # absence -> None, defaults applied downstream. ETL hardcoding these (#16/#18)
    # is what made CAT ability-matching meaningless and dropped per-option
    # explanations even when the source carried them.
    difficulty: int | None = None
    option_explanations: dict[str, Bilingual] | None = None
    license_status: str | None = None


@dataclass
class ExtractError:
    line_no: int | None
    external_id: str | None
    reason: str


def _bilingual(d: dict) -> Bilingual:
    return Bilingual(en=d.get("en", ""), zh=d.get("zh", ""))


# difficulty label -> int (PRD §11.1 range 1-5). Labels are a convenience for
# the CSV/XLSX/JSON import template (#35); int/numeric-string also accepted.
_DIFFICULTY_LABELS = {
    "very_easy": 1, "easy": 2, "medium": 3, "hard": 4, "very_hard": 5,
}


def _parse_difficulty(value) -> int | None:
    """Parse a source difficulty value to a clamped int in [1, 5], else None.

    Accepts int, numeric string, or label (easy/medium/hard/...). Out-of-range
    values clamp to 1 or 5. Garbage -> None (so the transform fallback applies).
    """
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip().lower()
        if v in _DIFFICULTY_LABELS:
            return _DIFFICULTY_LABELS[v]
        if v == "":
            return None
        try:
            n = int(v)
        except ValueError:
            return None
    elif isinstance(value, bool):  # bool is an int subclass; reject it
        return None
    elif isinstance(value, int):
        n = value
    else:
        return None
    return max(1, min(5, n))


def _parse_option_explanations(rec: dict) -> dict[str, Bilingual] | None:
    """Merge per-option explanations from the PRD §10 template fields.

    Supports two shapes:
      - split: ``option_explanations`` (en, {key: text}) + ``option_explanations_zh``
        (zh, {key: text}) - the documented CSV/XLSX/JSON template format.
      - nested: ``option_explanations`` as {key: {en, zh}}.
    Returns None when neither field is present. Keys with no text on either
    side still yield a Bilingual("", "") - transform treats empty as absent.
    """
    en_map = rec.get("option_explanations")
    zh_map = rec.get("option_explanations_zh")
    if en_map is None and zh_map is None:
        return None
    en_map = en_map or {}
    zh_map = zh_map or {}
    keys = set(en_map.keys()) | set(zh_map.keys())
    out: dict[str, Bilingual] = {}
    for k in keys:
        en_val = en_map.get(k, "")
        zh_val = zh_map.get(k, "")
        # A nested {en, zh} on either side is the alternate single-field shape.
        en_nested = en_val if isinstance(en_val, dict) else None
        zh_nested = zh_val if isinstance(zh_val, dict) else None
        en_str = (en_nested.get("en", "") if en_nested else (str(en_val) if en_val else ""))
        # zh: explicit zh_map wins, else pull from a nested en value, else a nested zh.
        if zh_nested:
            zh_str = zh_nested.get("zh", "")
        elif zh_val and not isinstance(zh_val, dict):
            zh_str = str(zh_val)
        elif en_nested:
            zh_str = en_nested.get("zh", "")
        else:
            zh_str = ""
        out[k] = Bilingual(en=en_str, zh=zh_str)
    return out


def _parse_record(rec: dict) -> RawQuestion:
    src = rec["source"]
    raw = RawQuestion(
        id=rec["id"],
        source=RawSource(
            book=src["book"],
            edition=src["edition"],
            section=src["section"],
            chapter=src["chapter"],
            chapter_title=src["chapter_title"],
            number=src["number"],
        ),
        type=rec["type"],
        stem=_bilingual(rec["stem"]),
        options=[
            RawOption(key=o["key"], text=_bilingual(o["text"]))
            for o in rec["options"]
        ],
        correct_keys=list(rec["correct_keys"]),
        explanation=_bilingual(rec["explanation"]),
        meta=rec.get("meta", {}),
        prompt_items=(
            [
                RawPromptItem(key=p["key"], text=_bilingual(p["text"]))
                for p in rec["prompt_items"]
            ]
            if rec.get("prompt_items")
            else None
        ),
        difficulty=_parse_difficulty(rec.get("difficulty")) or _parse_difficulty(rec.get("meta", {}).get("difficulty")),
        option_explanations=_parse_option_explanations(rec),
        license_status=(
            rec.get("license_status")
            or (rec.get("meta", {}) or {}).get("license_status")
        ),
    )
    return raw


class DatasetReader:
    def __init__(self, dataset_path: str | Path):
        self.path = Path(dataset_path)

    def read(self) -> tuple[list[RawQuestion], list[ExtractError], str]:
        raws: list[RawQuestion] = []
        errors: list[ExtractError] = []
        content_hash = self._content_hash()

        manifest = json.loads((self.path / "manifest.json").read_text())
        expected = manifest.get("total_questions")

        jsonl = self.path / "questions.jsonl"
        with jsonl.open() as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                rec = None
                try:
                    rec = json.loads(line)
                    raws.append(_parse_record(rec))
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    external_id = rec.get("id") if isinstance(rec, dict) else None
                    errors.append(
                        ExtractError(
                            line_no=line_no,
                            external_id=external_id,
                            reason=f"{type(exc).__name__}: {exc}",
                        )
                    )

        if expected is not None and expected != len(raws):
            errors.append(
                ExtractError(
                    line_no=None,
                    external_id=None,
                    reason=f"manifest total_questions={expected} but parsed {len(raws)} records",
                )
            )

        return raws, errors, content_hash

    def _content_hash(self) -> str:
        h = hashlib.sha256()
        for name in ("manifest.json", "questions.jsonl"):
            h.update(name.encode())
            h.update((self.path / name).read_bytes())
        return h.hexdigest()
