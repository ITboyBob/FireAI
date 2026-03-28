from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Literal, cast
import re
import unicodedata


KNOWN_DOCUMENT_IDS = {
    "消防法--2019年4月23日": "xiaofangfa_2019",
    "河北省消防条例": "hebei_xiaofang_tiaoli",
    "河北省消防安全责任制实施办法": "hebei_xiaofang_anquan_zerenzhi_shishi_banfa",
    "河北省消防安全责任制规定": "hebei_xiaofang_anquan_zerenzhi_guiding",
    "消防安全责任制实施办法": "xiaofang_anquan_zerenzhi_shishi_banfa",
    "机关、团体、企业、事业单位消防安全管理规定": (
        "jiguan_tuanti_qiye_shiye_danwei_xiaofang_anquan_guanli_guiding"
    ),
}


@dataclass(frozen=True)
class CorpusDocument:
    document_id: str
    source_path: Path
    source_name: str
    file_type: Literal["doc", "docx"]


def _build_document_id(source_name: str) -> str:
    normalized_name = unicodedata.normalize("NFKC", source_name).strip()
    known_id = KNOWN_DOCUMENT_IDS.get(normalized_name)
    if known_id is not None:
        return known_id

    slug = re.sub(r"[^a-z0-9]+", "_", normalized_name.lower()).strip("_")
    if not slug or not slug.isascii():
        digest = sha1(normalized_name.encode("utf-8")).hexdigest()[:12]
        return f"doc_{digest}"
    return re.sub(r"_+", "_", slug)


def discover_documents(raw_dir: Path) -> list[CorpusDocument]:
    documents: list[CorpusDocument] = []
    for path in raw_dir.iterdir():
        if not path.is_file():
            continue

        file_type = path.suffix.lower().lstrip(".")
        if file_type not in {"doc", "docx"}:
            continue

        source_name = path.stem
        literal_file_type = cast(Literal["doc", "docx"], file_type)
        documents.append(
            CorpusDocument(
                document_id=_build_document_id(source_name),
                source_path=path,
                source_name=source_name,
                file_type=literal_file_type,
            )
        )

    return sorted(documents, key=lambda item: item.document_id)
