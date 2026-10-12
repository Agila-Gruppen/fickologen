"""Delar upp kunskapsmaterial (markdown) i sökbara bitar ("chunks") för RAG.

Ren Python utan beroenden, så att den går att testa utan nyckel och utan databas.
Reglerna beskrivs i README.md i den här mappen. Bygget av vektordatabasen (PLAN-113)
ska anropa chunk_directory() och sedan lägga varje bit i ChromaDB.

Kör för statistik:   python chat-engine/knowledge/chunker.py chat-engine/knowledge/data
"""
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

MIN_WORDS = 40       # kortare avsnitt slås ihop med nästa avsnitt
MAX_WORDS = 450      # längre avsnitt delas vid styckegränser
TARGET_WORDS = 350   # ungefärlig storlek på delarna när ett avsnitt delas
EXCLUDED_TYPES = {"arbetsblad"}  # blanketter indexeras inte


@dataclass
class Chunk:
    id: str
    text: str          # det som bäddas in och skickas till Gemini (inkl. rubrikväg)
    doc_id: str
    titel: str
    path: list[str]    # rubrikväg, t.ex. ["Tankefällor", "Tankeläsning"]
    typ: str           # begrepp | övning | exempel | arbetsblad
    words: int
    meta: dict = field(default_factory=dict)


def slug(text: str) -> str:
    text = text.lower()
    for a, b in (("å", "a"), ("ä", "a"), ("ö", "o"), ("é", "e")):
        text = text.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def parse_front_matter(raw: str) -> tuple[dict, str]:
    """Läser '---'-blocket överst (enkla 'nyckel: värde'-rader). Returnerar (metadata, resten)."""
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("\n---", 3)
    if end == -1:
        return {}, raw
    meta = {}
    for line in raw[3:end].strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip('"')
    return meta, raw[end + 4:].lstrip("\n")


def detect_type(path: list[str]) -> str:
    if not path:
        return "begrepp"
    lower = [p.lower() for p in path]
    if any("arbetsblad" in p for p in lower):
        return "arbetsblad"
    if any(p.startswith("övning") for p in lower):
        return "övning"
    if "exempel" in lower[-1]:
        return "exempel"
    return "begrepp"


def _sections(body: str) -> list[tuple[list[str], str]]:
    """Delar texten vid rubriker (## till ####). Returnerar [(rubrikväg, text)]."""
    stack: list[tuple[int, str]] = []
    out: list[tuple[list[str], list[str]]] = [([], [])]
    for line in body.splitlines():
        m = re.match(r"^(#{2,4})\s+(.*\S)\s*$", line)
        if m:
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, m.group(2)))
            out.append(([t for _, t in stack], []))
        else:
            out[-1][1].append(line)
    return [(path, "\n".join(lines).strip()) for path, lines in out if "\n".join(lines).strip()]


def _words(text: str) -> int:
    return len(text.split())


def _merge_small(sections: list[tuple[list[str], str]]) -> list[tuple[list[str], str]]:
    """Slår ihop korta avsnitt med nästa (eller, för det sista, med föregående)."""
    result: list[tuple[list[str], str]] = []
    carry: tuple[list[str], str] | None = None
    for path, text in sections:
        if carry:
            carried_path, carried_text = carry
            label = f"{path[-1]}\n" if path else ""
            path, text = carried_path, f"{carried_text}\n\n{label}{text}"  # behåll den första rubrikvägen
            carry = None
        if _words(text) < MIN_WORDS:
            carry = (path, text)
        else:
            result.append((path, text))
    if carry:
        if result:
            ppath, ptext = result[-1]
            result[-1] = (ppath, f"{ptext}\n\n{carry[1]}")
        else:
            result.append(carry)
    return result


def _split_large(text: str) -> list[str]:
    """Delar långa avsnitt vid styckegränser i delar om ca TARGET_WORDS ord."""
    if _words(text) <= MAX_WORDS:
        return [text]
    parts, current, size = [], [], 0
    for para in re.split(r"\n\s*\n", text):
        n = _words(para)
        if current and size + n > TARGET_WORDS:
            parts.append("\n\n".join(current))
            current, size = [], 0
        current.append(para)
        size += n
    if current:
        tail = "\n\n".join(current)
        if parts and _words(tail) < MIN_WORDS:
            parts[-1] += "\n\n" + tail
        else:
            parts.append(tail)
    return parts


def chunk_markdown(raw: str, fallback_id: str = "dokument") -> list[Chunk]:
    meta, body = parse_front_matter(raw)
    doc_id = meta.get("id", fallback_id)
    titel = meta.get("titel", doc_id)
    chunks: list[Chunk] = []
    seen: dict[str, int] = {}
    for path, text in _merge_small(_sections(body)):
        typ = detect_type(path) if path else "begrepp"
        if typ in EXCLUDED_TYPES:
            continue
        for i, part in enumerate(_split_large(text), start=1):
            base = f"{doc_id}#{slug(' '.join(path)) or 'intro'}"
            n = seen.get(base, 0) + 1
            seen[base] = n
            cid = base if n == 1 else f"{base}-{n}"
            heading = " > ".join([titel] + path)
            chunks.append(Chunk(
                id=cid, text=f"{heading}\n\n{part}", doc_id=doc_id, titel=titel, path=path,
                typ=typ, words=_words(part),
                meta={"källa": meta.get("källa", ""), "modul": meta.get("modul", "")},
            ))
    return chunks


def chunk_directory(directory: str | Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for file in sorted(Path(directory).glob("*.md")):
        if file.name.startswith("_") or file.name.lower() == "readme.md":
            continue
        chunks += chunk_markdown(file.read_text(encoding="utf-8"), fallback_id=file.stem)
    return chunks


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "data"
    found = chunk_directory(folder)
    if not found:
        sys.exit(f"Inga markdown-filer hittades i {folder}")
    sizes = sorted(c.words for c in found)
    per_doc: dict[str, int] = {}
    for c in found:
        per_doc[c.doc_id] = per_doc.get(c.doc_id, 0) + 1
    print(f"{len(found)} bitar från {len(per_doc)} filer")
    print(f"ord per bit: min {sizes[0]}, median {sizes[len(sizes) // 2]}, max {sizes[-1]}")
    print(f"bitar över {MAX_WORDS} ord: {sum(1 for s in sizes if s > MAX_WORDS)}, under {MIN_WORDS} ord: {sum(1 for s in sizes if s < MIN_WORDS)}")
    types: dict[str, int] = {}
    for c in found:
        types[c.typ] = types.get(c.typ, 0) + 1
    print("typer:", types)
    for doc, n in per_doc.items():
        print(f"  {n:3} bitar  {doc}")
