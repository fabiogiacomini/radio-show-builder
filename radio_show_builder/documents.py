"""Export a readable Word script and a portable JSON rundown."""
from pathlib import Path
import re
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def export_docx(project, destination):
    doc = Document()
    doc.core_properties.author = "Radio Show Builder"
    doc.core_properties.last_modified_by = "Radio Show Builder"
    doc.core_properties.title = project["title"]
    section = doc.sections[0]
    section.top_margin = section.bottom_margin = Inches(.75)
    section.left_margin = section.right_margin = Inches(.8)
    for name in ("Normal", "Title", "Heading 1", "Heading 2"):
        doc.styles[name].font.name = "Calibri"
        doc.styles[name].font.color.rgb = RGBColor(0, 0, 0)
    doc.styles["Normal"].font.size = Pt(10.5)
    doc.styles["Normal"].paragraph_format.space_after = Pt(5)
    doc.styles["Title"].font.size = Pt(28)
    for border in doc.styles.element.xpath(".//w:pBdr"):
        border.getparent().remove(border)
    heading = re.sub(r"[^\w\s]", " ", project["title"], flags=re.UNICODE)
    doc.add_paragraph(" ".join(heading.split()) or "Radio show script", "Title")
    doc.add_paragraph(
        f"Target: {project['settings']['target_seconds']/60:g} minutes. "
        f"Language: {project['language']}. Export: {project['settings']['bitrate_kbps']} kbps MP3."
    )
    if project["idea"]:
        doc.add_paragraph(project["idea"])
    doc.add_paragraph("Rundown", "Heading 1")
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for cell, value in zip(table.rows[0].cells, ("Order", "Type", "Segment", "Estimate")):
        cell.text = value
    for i, entry in enumerate(project["entries"], 1):
        cells = table.add_row().cells
        for cell, value in zip(cells, (str(i), entry["kind"].title(), entry["title"],
                                      f"{entry['estimated_seconds']/60:.1f} min")):
            cell.text = value
    for row_index, row in enumerate(table.rows):
        for cell in row.cells:
            properties = cell._tc.get_or_add_tcPr()
            borders = OxmlElement("w:tcBorders")
            for side in ("top", "left", "bottom", "right"):
                edge = OxmlElement("w:"+side)
                for key, value in (("val", "single"), ("sz", "4"), ("color", "D9D9D9")):
                    edge.set(qn("w:"+key), value)
                borders.append(edge)
            properties.append(borders)
            shade = OxmlElement("w:shd")
            shade.set(qn("w:fill"), "E8ECE8" if row_index == 0 else "FFFFFF")
            properties.append(shade)
            margins = OxmlElement("w:tcMar")
            for side in ("top", "left", "bottom", "right"):
                margin = OxmlElement("w:"+side)
                margin.set(qn("w:w"), "80")
                margin.set(qn("w:type"), "dxa")
                margins.append(margin)
            properties.append(margins)
            if row_index == 0:
                for run in cell.paragraphs[0].runs:
                    run.bold = True
    repeat = OxmlElement("w:tblHeader")
    table.rows[0]._tr.get_or_add_trPr().append(repeat)
    doc.add_paragraph("Spoken script and music notes", "Heading 1")
    for i, e in enumerate(project["entries"], 1):
        clean = " ".join(re.sub(r"[^\w\s]", " ", e["title"], flags=re.UNICODE).split())
        doc.add_paragraph(f"{i} {e['kind'].title()} {clean}", "Heading 2")
        if e["text"]:
            for paragraph in e["text"].split("\n\n"):
                doc.add_paragraph(paragraph)
        if e["notes"]:
            doc.add_paragraph(e["notes"])
    if project.get("verification_notes"):
        doc.add_paragraph("Editorial checks", "Heading 1")
        doc.add_paragraph(project["verification_notes"])
    doc.add_paragraph("Production notes", "Heading 1")
    doc.add_paragraph(
        "Review the script, track versions and factual claims before recording. "
        "Track durations are estimates until audio is uploaded. "
        "The uploaded recordings determine the spoken delivery. "
        "Edits made in Word can be copied into the app before saving the project."
    )
    path = Path(destination)
    doc.save(path)
    return path
