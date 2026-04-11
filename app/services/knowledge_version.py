import hashlib
from pathlib import Path


class KnowledgeVersionResolver:
    REQUIRED_FILES = ("retrieval.db", "faiss.index", "vector_map.json")

    def __init__(self, *, index_dir: Path):
        self.index_dir = index_dir

    def resolve(self) -> str:
        fingerprint_parts: list[str] = []
        for filename in self.REQUIRED_FILES:
            path = self.index_dir / filename
            if not path.exists():
                return "kb:missing"
            stat = path.stat()
            fingerprint_parts.append(f"{filename}:{stat.st_size}:{stat.st_mtime_ns}")

        digest = hashlib.sha256("|".join(fingerprint_parts).encode("utf-8")).hexdigest()[:16]
        return f"kb:{digest}"
