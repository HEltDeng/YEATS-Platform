"""Generate synthetic office/PDF files with bundled document libraries, no PII."""
from pathlib import Path
from docx import Document
from docx.shared import Pt
from openpyxl import Workbook
from pptx import Presentation
from reportlab.pdfgen.canvas import Canvas
root=Path(__file__).resolve().parents[1]/'runtime/private-files'
text='YEATS - SYNTHETIC FILE FOR LOCAL ACCEPTANCE ONLY'
if not (root/'fixture.docx').exists():
 d=Document();d.add_heading('YEATS synthetic document',0);d.add_paragraph(text);d.styles['Normal'].font.name='Arial';d.styles['Normal'].font.size=Pt(12);d.save(root/'fixture.docx')
if not (root/'fixture.xlsx').exists():
 w=Workbook();w.active.append(['Environment','Content']);w.active.append(['TEST',text]);w.save(root/'fixture.xlsx')
if not (root/'fixture.pptx').exists():
 p=Presentation();s=p.slides.add_slide(p.slide_layouts[1]);s.shapes.title.text='YEATS synthetic presentation';s.placeholders[1].text=text;p.save(root/'fixture.pptx')
if not (root/'fixture.pdf').exists():
 c=Canvas(str(root/'fixture.pdf'));c.drawString(40,750,text);c.save()
print('Four controlled document fixtures ready; no customer material used.')
