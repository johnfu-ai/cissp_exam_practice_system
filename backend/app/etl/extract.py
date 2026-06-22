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


@dataclass
class ExtractError:
    line_no: int | None
    external_id: str | None
    reason: str


def _bilingual(d: dict) -> Bilingual:
    return Bilingual(en=d.get("en", ""), zh=d.get("zh", ""))


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
