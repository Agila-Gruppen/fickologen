"""Konverterar behandlingsmodulerna (Word) till markdown enligt reglerna i README.md.

Använder bara standardbiblioteket. Resultatet hamnar i chat-engine/knowledge/data/,
som är avstängd i .gitignore, så att materialet inte hamnar i git av misstag.

Kör:
    python chat-engine/knowledge/convert_docx.py "C:/sökväg/till/mappen/med/modulerna"

Rensas bort automatiskt (och redovisas i data/_rapport.txt):
  - menytext och deltagar-ID från webbplattformen ("Meny", "Logga ut", "1245hgcf" ...)
  - svarsfält och formulär ("Redigera ditt svar", "Berätta om följande", "Kontakt med behandlare")
  - sidfötter ("Kom ihåg!", "Bra jobbat med modulen!")
  - ALLA tabeller (många är ifyllda blanketter med personers egna svar) och bilder
"""
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
OUT_DIR = Path(__file__).parent / "data"

# Rubriker vars hela avsnitt är formulär eller kontakt, inte kunskap.
DROP_HEADINGS = {"kontakt med behandlare", "berätta om följande:", "berätta om följande"}
# Rader som ska bort var de än står.
DROP_LINES = re.compile(
    r"^(meny|logga ut|behandlingsmoduler|redigera ditt svar|bra jobbat med modulen!?)$"
    r"|^\d{3,}[a-z0-9]*$"                      # deltagar-ID, t.ex. 1245hgcf
    r"|^[📎📊💡🧠✅✏]"                             # sidfötter och instruktioner med emoji
    r"|klicka här|skriv dina svar direkt|knappen \"?spara", re.I)
# Efter dessa rader kommer ett svarsfält, och allt till nästa rubrik hoppas över.
ANSWER_FIELD = {"redigera ditt svar"}


def clean(text: str) -> str:
    text = text.replace("\u00ad", "").replace("\u200b", "").replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


def paragraph_text(p) -> str:
    out = []
    for node in p.iter():
        if node.tag == f"{W}t" and node.text:
            out.append(node.text)
        elif node.tag in (f"{W}tab", f"{W}br"):
            out.append(" ")
    return clean("".join(out))


def convert(docx: Path) -> tuple[str, dict]:
    with zipfile.ZipFile(docx) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        images = len([n for n in z.namelist() if n.startswith("word/media/")])
    body = root.find(f"{W}body")
    lines: list[str] = []
    stats = {"tabeller": 0, "tabeller_under": [], "bilder": images, "borttagna_rader": 0, "borttagna_avsnitt": []}
    current_heading = "(början)"
    skipping_until_heading = False
    seen_heading = False  # allt före första rubriken är webbplattformens meny och titelrad
    for child in body:
        if child.tag == f"{W}tbl":
            stats["tabeller"] += 1
            stats["tabeller_under"].append(current_heading)
            continue
        if child.tag != f"{W}p":
            continue
        text = paragraph_text(child)
        if not text:
            continue
        style_el = child.find(f"{W}pPr/{W}pStyle")
        style = style_el.get(f"{W}val", "") if style_el is not None else ""
        m = re.match(r"(?:Heading|Rubrik)\s*(\d)", style, re.I)
        if m:
            level = max(1, min(int(m.group(1)), 4))
            current_heading = text
            seen_heading = True
            skipping_until_heading = False
            if text.lower() in DROP_HEADINGS:
                skipping_until_heading = True
                stats["borttagna_avsnitt"].append(text)
                continue
            lines += ["", f"{'#' * level} {text}", ""]
            continue
        if text.lower() in ANSWER_FIELD:
            skipping_until_heading = True
            stats["borttagna_rader"] += 1
            continue
        if not seen_heading or skipping_until_heading or DROP_LINES.search(text):
            stats["borttagna_rader"] += 1
            continue
        ilvl_el = child.find(f"{W}pPr/{W}numPr/{W}ilvl")
        in_list = child.find(f"{W}pPr/{W}numPr") is not None
        if in_list:
            indent = "  " * int(ilvl_el.get(f"{W}val", "0")) if ilvl_el is not None else ""
            lines.append(f"{indent}- {text}")
        else:
            lines += ["", text, ""]
    md = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"
    return md, stats


def front_matter(name: str) -> tuple[str, str]:
    m = re.match(r"Modul\s+(\d+)\s*-\s*(.+?)\.docx$", name, re.I)
    number, title = (int(m.group(1)), m.group(2)) if m else (0, Path(name).stem)
    from chunker import slug
    doc_id = f"modul-{number:02d}-{slug(title)}"
    return doc_id, (
        "---\n"
        f"id: {doc_id}\n"
        f'titel: "Modul {number}: {title}"\n'
        f"modul: {number}\n"
        'källa: "CHAI-behandlingsmoduler"\n'
        'licens: "internt studentprojekt, ej publicerat"\n'
        "språk: sv\n"
        "version: 1\n"
        "granskad_av: \n"
        "---\n\n"
    )


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.path.insert(0, str(Path(__file__).parent))
    source = Path(sys.argv[1])
    files = sorted(f for f in source.glob("Modul *.docx") if not f.name.startswith("~$"))
    if not files:
        sys.exit(f"Hittade inga filer som heter 'Modul N - ....docx' i {source}")
    OUT_DIR.mkdir(exist_ok=True)
    report = ["Konverteringsrapport (granska innan materialet används)\n"]
    for f in files:
        md, stats = convert(f)
        doc_id, header = front_matter(f.name)
        (OUT_DIR / f"{doc_id}.md").write_text(header + md, encoding="utf-8")
        report.append(
            f"{doc_id}: {len(md.split())} ord | tabeller borttagna: {stats['tabeller']} | "
            f"bilder ignorerade: {stats['bilder']} | rader borttagna: {stats['borttagna_rader']} | "
            f"avsnitt borttagna: {len(stats['borttagna_avsnitt'])}"
        )
        if stats["tabeller_under"]:
            report.append("    tabeller fanns under: " + "; ".join(dict.fromkeys(stats["tabeller_under"]))[:400])
        print(report[-2] if stats["tabeller_under"] else report[-1])
    (OUT_DIR / "_rapport.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"\n{len(files)} filer skrivna till {OUT_DIR}")


if __name__ == "__main__":
    main()
