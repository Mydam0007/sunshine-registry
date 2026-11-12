"""Build a one-page project summary DOCX for the Sunshine Registry project."""
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BLUE = RGBColor(0x1F, 0x4E, 0x79)
DARK = RGBColor(0x1A, 0x1A, 0x1A)
GREY = RGBColor(0x55, 0x55, 0x55)

doc = Document()
sec = doc.sections[0]
sec.page_width = Inches(8.5)
sec.page_height = Inches(11)
sec.top_margin = Inches(0.35)
sec.bottom_margin = Inches(0.35)
sec.left_margin = Inches(0.6)
sec.right_margin = Inches(0.6)

style = doc.styles["Normal"]
style.font.name = "Calibri"
style.font.size = Pt(9)
style.font.color.rgb = DARK
style.paragraph_format.space_after = Pt(2)
style.paragraph_format.space_before = Pt(0)
style.paragraph_format.line_spacing = 1.1


def add_hyperlink(paragraph, url, text):
    part = paragraph.part
    r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    rFonts = OxmlElement("w:rFonts")
    rFonts.set(qn("w:ascii"), "Calibri")
    rFonts.set(qn("w:hAnsi"), "Calibri")
    rPr.append(rFonts)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "18")
    rPr.append(sz)
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "1F4E79")
    rPr.append(color)
    run.append(rPr)
    t = OxmlElement("w:t")
    t.text = text
    run.append(t)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def heading(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(2)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "1F4E79")
    pBdr.append(bottom)
    pPr.append(pBdr)
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(11)
    r.font.color.rgb = BLUE
    return p


def shade(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def set_cell_text(cell, text, bold=False, size=9, color=DARK):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.space_before = Pt(1)
    r = p.add_run(text)
    r.bold = bold
    r.font.size = Pt(size)
    r.font.color.rgb = color
    return p


# Title
p = doc.add_paragraph()
p.paragraph_format.space_after = Pt(1)
r = p.add_run("Sunshine Registry")
r.bold = True
r.font.size = Pt(14)
r.font.color.rgb = BLUE

# Subtitle
p = doc.add_paragraph()
p.paragraph_format.space_after = Pt(0)
r = p.add_run("Florida Parkinson's Disease Registry pipeline")
r.font.size = Pt(9)
r.font.color.rgb = GREY
r.italic = True

# Contact line
p = doc.add_paragraph()
p.paragraph_format.space_after = Pt(3)
r = p.add_run("Nagaraju Mydam  ·  MS Data Science, Clarkson University (2025)  ·  AI Engineer, SANQUEST Inc.  ·  ")
r.font.size = Pt(9)
r.font.color.rgb = GREY
add_hyperlink(p, "https://github.com/Mydam0007", "github.com/Mydam0007")
r = p.add_run("  ·  ")
r.font.size = Pt(9)
r.font.color.rgb = GREY
add_hyperlink(p, "https://www.linkedin.com/in/nagaraju-mydam-160979259", "linkedin.com/in/nagaraju-mydam-160979259")

# Intro
p = doc.add_paragraph()
r = p.add_run(
    "I built this pipeline to show how I handle registry data: take in reports from three "
    "providers, each in its own shape, clean them up, match the same person across providers, "
    "and build one registry with a report on top. It covers the full data lifecycle the role "
    "asks for: integration, curation, quality checks, reporting, and governance."
)
r.font.size = Pt(9)

# Flow line
p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(2)
p.paragraph_format.space_after = Pt(2)
r = p.add_run("Generate, ingest, validate, integrate, report, plus a registry report and audit log")
r.bold = True
r.font.size = Pt(9)
r.font.color.rgb = BLUE

# How it works
heading("How it works")
rows = [
    ("Generate", "Three provider files for 5,000 fake patients (about 6,300 reports). Each provider sends the same kind of data differently: different column names, different date formats, an extra notes column. About a quarter of the patients show up in two providers' files."),
    ("Ingest", "Each file is mapped onto one shared schema and loaded into a staging table in SQLite. Nothing is cleaned at this step."),
    ("Validate", "Rows with no patient name, a bad date of birth, a missing or future diagnosis date, a diagnosis code the registry does not accept, or an age at diagnosis outside 20 to 100 get dropped and counted. County spellings get standardized and bad sex values become Unknown."),
    ("Integrate", "Patients are matched on a salted hash of name plus date of birth, so no raw identifiers land in the registry tables. Each patient gets one record with the earliest diagnosis date and a count of reporting providers."),
    ("Report", "SQL queries against the registry, kept in sql/reporting_queries.sql so they can be read on their own: new patients by month, acceptance by provider, patients by county, diagnosis code counts. Outputs are a report plus three CSVs and a self-contained HTML dashboard with the monthly chart and the quality numbers, and an audit log with one event per stage."),
]
t = doc.add_table(rows=1, cols=2)
t.style = "Table Grid"
t.alignment = WD_TABLE_ALIGNMENT.CENTER
hdr = t.rows[0].cells
set_cell_text(hdr[0], "Stage", bold=True, color=BLUE)
set_cell_text(hdr[1], "What happens", bold=True, color=BLUE)
shade(hdr[0], "E8EEF4")
shade(hdr[1], "E8EEF4")
for stage, desc in rows:
    cells = t.add_row().cells
    set_cell_text(cells[0], stage, bold=True)
    set_cell_text(cells[1], desc)
t.columns[0].width = Inches(1.1)
t.columns[1].width = Inches(6.2)

# What came out
heading("What came out of the run (seed 42)")
res = doc.add_table(rows=1, cols=4)
res.style = "Table Grid"
res.alignment = WD_TABLE_ALIGNMENT.CENTER
hdr = res.rows[0].cells
for i, h in enumerate(["Rows in / accepted", "Patients", "Reported twice", "Rows excluded"]):
    set_cell_text(hdr[i], h, bold=True, color=BLUE)
    shade(hdr[i], "E8EEF4")
vals = res.add_row().cells
for i, v in enumerate(["6,271 / 6,003", "4,845", "1,158", "268"]):
    set_cell_text(vals[i], v)
p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(2)
for text, bold in [
    ("Excluded (268): ", True),
    ("36 missing patient name, 36 duplicate report ID, 18 dates of birth that did not parse, 53 missing diagnosis date, 34 future diagnosis date, 72 invalid diagnosis code, 19 age outside 20 to 100.  ", False),
    ("Standardized: ", True),
    ("323 county spellings fixed, 36 sex values set to Unknown. Acceptance by provider: Tampa 95.7%, Gulf Coast 95.9%, Central Florida 95.6%.  ", False),
    ("Verification: ", True),
    ("verify_outputs.py runs 28 checks on its own (tables exist, hashes are 64-char hex and unique, no raw names or dates of birth in any output, row counts add up, codes and counties valid, dashboard is self-contained HTML with a monthly bar chart). All 28 pass, and the same seed gives identical reports and dashboard. Pipeline time 1.01 s.", False),
]:
    r = p.add_run(text)
    r.bold = bold
    r.font.size = Pt(9)

# Why it maps
heading("What this shows for the Data Engineer II role")
for lead, rest in [
    ("Data integration from diverse sources: ", "three providers, three shapes, one shared schema, one staging table."),
    ("Data quality: ", "validation that drops bad rows by reason, standardizes what can be fixed, and counts everything."),
    ("Data modeling: ", "an explicit staging schema and two registry tables in SQLite, with a data dictionary for both."),
    ("SQL programs: ", "the reporting queries live in sql/reporting_queries.sql as a file of their own, not buried in code, so they can be reviewed, changed, and reused on their own."),
    ("Reporting and dashboards: ", "SQL reporting queries plus a self-contained HTML dashboard with the monthly chart and the quality numbers, and CSVs ready to feed a dashboard."),
    ("Governance and reproducibility: ", "a written SOP for the monthly load, an audit log with one event per stage, and identical reports from the same seed."),
]:
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(1)
    r = p.add_run(lead)
    r.bold = True
    r.font.size = Pt(9)
    r2 = p.add_run(rest)
    r2.font.size = Pt(9)

# Stack
p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(3)
r = p.add_run("Stack: ")
r.bold = True
r.font.size = Pt(9)
r = p.add_run("Python 3.12, pandas, SQLite, Docker. Nothing else.   Run it: ")
r.font.size = Pt(9)
r = p.add_run("pip install -r requirements.txt && python run_pipeline.py")
r.italic = True
r.font.size = Pt(9)
r = p.add_run("  ·  ")
r.font.size = Pt(9)
r = p.add_run("python verify_outputs.py")
r.italic = True
r.font.size = Pt(9)

# Footer disclaimer
p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(3)
pPr = p._p.get_or_add_pPr()
pBdr = OxmlElement("w:pBdr")
top = OxmlElement("w:top")
top.set(qn("w:val"), "single")
top.set(qn("w:sz"), "6")
top.set(qn("w:space"), "4")
top.set(qn("w:color"), "CCCCCC")
pBdr.append(top)
pPr.append(pBdr)
r = p.add_run(
    "All the data is made up. Every record is fake, generated with a fixed seed, so there are no "
    "real people and no real patient data here. This is my own project, not affiliated with the "
    "University of South Florida. Hashing with a salt is pseudonymization, not anonymization. "
    "This shows the technique; it is not a compliance certification and does not claim to be one."
)
r.font.size = Pt(8)
r.font.color.rgb = GREY

doc.save("/home/hatch/workspace/your_files/florida-parkinsons-registry-pipeline/PROJECT_SUMMARY.docx")
print("saved")
