"""CSV writing helpers with advisory locks and atomic replacement."""

from __future__ import annotations

import csv
import fcntl
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterable, Iterator, List


@contextmanager
def advisory_lock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def append_csv_row(path: Path, row: Dict[str, object], fieldnames: List[str]) -> None:
    lock_path = path.with_suffix(path.suffix + ".lock")
    with advisory_lock(lock_path):
        exists = path.exists()
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            if not exists:
                writer.writeheader()
            writer.writerow(row)


def atomic_write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    if not rows:
        return
    lock_path = path.with_suffix(path.suffix + ".lock")
    with advisory_lock(lock_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(rows[0].keys())
        with tempfile.NamedTemporaryFile(
            "w",
            newline="",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            temp_name = handle.name
        os.replace(temp_name, path)


def upsert_csv_row(
    path: Path,
    row: Dict[str, object],
    key_fields: Iterable[str],
    fieldnames: List[str],
) -> None:
    key_fields = list(key_fields)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with advisory_lock(lock_path):
        rows: List[Dict[str, object]] = []
        if path.exists():
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        row_key = tuple(str(row[field]) for field in key_fields)
        replaced = False
        filtered_rows: List[Dict[str, object]] = []
        for existing in rows:
            existing_key = tuple(str(existing[field]) for field in key_fields)
            if existing_key == row_key:
                if not replaced:
                    filtered_rows.append(row)
                    replaced = True
                continue
            filtered_rows.append(existing)
        if not replaced:
            filtered_rows.append(row)

        with tempfile.NamedTemporaryFile(
            "w",
            newline="",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(filtered_rows)
            temp_name = handle.name
        os.replace(temp_name, path)
