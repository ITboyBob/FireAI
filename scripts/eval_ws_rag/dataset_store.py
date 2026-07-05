from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path

from scripts.eval_ws_rag.dataset_models import EvaluationDataset, canonical_dataset_payload, compute_dataset_fingerprint


def save_dataset_atomic(dataset: EvaluationDataset, datasets_root: Path) -> Path:
    """Persist dataset atomically under datasets_root/<dataset_id>/dataset.json.

    The dataset_fingerprint is recomputed from canonical content before writing.
    Raises FileExistsError if the target dataset directory already exists.
    """
    payload = canonical_dataset_payload(dataset)
    fingerprint = compute_dataset_fingerprint(payload)
    dataset.dataset_fingerprint = fingerprint

    dataset_dir = datasets_root / dataset.dataset_id
    if dataset_dir.exists():
        raise FileExistsError(f"dataset directory already exists: {dataset_dir}")

    datasets_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = datasets_root / f".{dataset.dataset_id}.tmp-{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=False, exist_ok=False)

    try:
        tmp_file = tmp_dir / "dataset.json.tmp"
        data = dataset.model_dump(mode="json")
        text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
        tmp_file.write_text(text, encoding="utf-8")
        tmp_file.rename(tmp_dir / "dataset.json")

        # fsync directory entries for durability.
        dir_fd = os.open(tmp_dir, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

        tmp_dir.rename(dataset_dir)
        parent_fd = os.open(datasets_root, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except Exception:
        # Best-effort cleanup; re-raise the original error.
        _rm_tree(tmp_dir)
        raise

    return dataset_dir / "dataset.json"


def load_dataset(dataset_path: Path) -> EvaluationDataset:
    """Load dataset from disk and verify its fingerprint."""
    text = dataset_path.read_text(encoding="utf-8")
    data = json.loads(text)
    stored_fingerprint = data.get("dataset_fingerprint")
    dataset = EvaluationDataset.model_validate(data)

    expected = compute_dataset_fingerprint(canonical_dataset_payload(dataset))
    if stored_fingerprint != expected:
        raise ValueError(
            f"dataset fingerprint mismatch: stored={stored_fingerprint}, expected={expected}"
        )
    return dataset


def _rm_tree(path: Path) -> None:
    if not path.exists():
        return
    for item in path.iterdir():
        if item.is_dir():
            _rm_tree(item)
        else:
            item.unlink()
    path.rmdir()
