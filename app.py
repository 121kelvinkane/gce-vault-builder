import streamlit as st
import os
import tempfile
import cv2
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable, Image as RLImage
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image
import io

# ──────────────────────────────────────────────
# FONT SETUP
# ──────────────────────────────────────────────
try:
    font_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(font_dir, "DejaVuSerif.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join(font_dir, "DejaVuSerif-Bold.ttf")))
    FONT = "DejaVu"
    FONT_B = "DejaVu-Bold"
except:
    FONT = "Helvetica"
    FONT_B = "Helvetica-Bold"

PAGE_W, PAGE_H = A4
MARGIN = 15 * mm

# ──────────────────────────────────────────────
# STYLES
# ──────────────────────────────────────────────
title_style = ParagraphStyle('Title', fontName=FONT_B, fontSize=12, alignment=TA_CENTER, spaceAfter=4)
subtitle = ParagraphStyle('Sub', fontName=FONT, fontSize=10, alignment=TA_CENTER, spaceAfter=2)
body_left = ParagraphStyle('BodyL', fontName=FONT, fontSize=10, alignment=TA_LEFT, spaceAfter=2)
small = ParagraphStyle('Small', fontName=FONT, fontSize=9, alignment=TA_LEFT)
center_bold = ParagraphStyle('CB', fontName=FONT_B, fontSize=11, alignment=TA_CENTER, spaceAfter=4)

# ──────────────────────────────────────────────
# IMAGE PROCESSING
# ──────────────────────────────────────────────
def clean_image(img_pil, top_percent, bottom_percent, left_percent, right_percent):
    img_cv = np.array(img_pil)
    
    if len(img_cv.shape) == 3 and img_cv.shape[2] == 4:
        img_cv = cv2.cvtColor(img_cv, cv2.COLOR_RGBA2RGB)
    elif len(img_cv.shape) == 2:
        img_cv = cv2.cvtColor(img_cv, cv2.COLOR_GRAY2RGB)

    h, w = img_cv.shape[:2]

    # Manual crop from all 4 sides
    top_px = int(h * (top_percent / 100))
    bottom_px = int(h * (1 - bottom_percent / 100))
    left_px = int(w * (left_percent / 100))
    right_px = int(w * (1 - right_percent / 100))
    
    img_cv = img_cv[top_px:bottom_px, left_px:right_px]

    # Scanner filter - removes light gray watermarks
    gray_cropped = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray_cropped, 210, 255, cv2.THRESH_BINARY)

    # Make background transparent so GCE VAULT watermark shows through
    img_rgba = cv2.cvtColor(thresh, cv2.COLOR_GRAY2RGBA)
    img_rgba[:, :, 3] = np.where(thresh == 255, 0, 255).astype(np.uint8)

    return Image.fromarray(img_rgba, 'RGBA')

# ─────────────────────────────────────────────
# PDF WATERMARK (GCE VAULT)
# ──────────────────────────────────────────────
def add_gce_vault_watermark(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica-Bold', 80)
    canvas.setFillColor(colors.Color(0.75, 0.75, 0.75, alpha=0.35))
    canvas.translate(PAGE_W / 2, PAGE_H / 2)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, "GCE VAULT")
    canvas.restoreState()

# ──────────────────────────────────────────────
# PDF GENERATION
# ──────────────────────────────────────────────
def generate_pdf(subject, code, paper_no, level, date, uploaded_files, top_crop, bottom_crop, left_crop, right_crop):
    buffer = io.BytesIO()
    
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, 
        leftMargin=MARGIN, rightMargin=MARGIN, 
        topMargin=15*mm, bottomMargin=20*mm,
        onFirstPage=add_gce_vault_watermark,
        onLaterPages=add_gce_vault_watermark
    )
    story = []

    # Cover Page
    story.append(Paragraph(f"{subject.upper()} {paper_no.upper()}", title_style))
    story.append(Paragraph(code, title_style))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("GENERAL CERTIFICATE OF EDUCATION BOARD", title_style))
    story.append(Paragraph("General Certificate of Education Examination", subtitle))
    story.append(Spacer(1, 5*mm))

    info = Table([
        [Paragraph(f"<b>{date}</b>", body_left), Paragraph(f"<b>{level}</b>", ParagraphStyle('R', fontName=FONT_B, fontSize=10, alignment=TA_RIGHT))]
    ], colWidths=[90*mm, 80*mm])
    story.append(info)
    story.append(Spacer(1, 5*mm))

    subj = Table([
        [Paragraph("Subject Title", small), Paragraph(subject, small)],
        [Paragraph("Paper No.", small), Paragraph(paper_no, small)],
        [Paragraph("Subject Code No.", small), Paragraph(code, small)],
    ], colWidths=[45*mm, 55*mm])
    subj.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('TOPPADDING', (0,0), (-1,-1), 3), ('BOTTOMPADDING', (0,0), (-1,-1), 3), ('LEFTPADDING', (0,0), (-1,-1), 4)]))
    story.append(subj)
    story.append(Spacer(1, 5*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("<b>Two and a half hours</b>", center_bold))
    story.append(Spacer(1, 5*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    story.append(PageBreak())

    max_w = A4[0] - 2 * MARGIN
    max_h = A4[1] - 2 * MARGIN - 15*mm 
    temp_files = [] 

    for i, uploaded_file in enumerate(uploaded_files):
        img_pil = Image.open(uploaded_file)
        cleaned_img = clean_image(img_pil, top_crop, bottom_crop, left_crop, right_crop)
        
        w, h = cleaned_img.size
        
        if w > max_w:
            ratio = max_w / w
            w = max_w
            h = h * ratio
        if h > max_h:
            ratio = max_h / h
            h = max_h
            w = w * ratio

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            cleaned_img.save(tmp.name, format='PNG')
            temp_files.append(tmp.name)
            
            story.append(RLImage(tmp.name, width=w, height=h))
            story.append(PageBreak())

    story.append(Paragraph("<b>END</b>", center_bold))

    doc.build(story)

    for f in temp_files:
        try: os.remove(f)
        except: pass

    return buffer.getvalue()

# ──────────────────────────────────────────────
# STREAMLIT UI
# ──────────────────────────────────────────────
st.set_page_config(page_title="GCE Vault Builder", page_icon="📄", layout="centered")

st.title("📄 GCE Vault PDF Builder")
st.markdown("Upload screenshots. Adjust crop sliders to remove ALL phone UI, then generate your watermarked PDF.")

with st.sidebar:
    st.header("📝 Paper Details")
    subject = st.text_input("Subject", "Additional Mathematics")
    code = st.text_input("Paper Code", "0575")
    paper_no = st.text_input("Paper Number", "Paper 2")
    level = st.text_input("Level", "ORDINARY LEVEL")
    date = st.text_input("Date", "JUNE 2021")
    
    st.divider()
    st.header("✂️ Crop Settings")
    st.caption("Adjust to remove phone UI completely")
    top_crop = st.slider("Top Crop (%)", 0, 40, 20)
    bottom_crop = st.slider("Bottom Crop (%)", 0, 40, 20)
    left_crop = st.slider("Left Crop (%)", 0, 30, 5)
    right_crop = st.slider("Right Crop (%)", 0, 30, 5)

st.markdown("---")
uploaded_files = st.file_uploader(" Upload Exam Screenshots", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

if uploaded_files:
    st.success(f"✅ {len(uploaded_files)} image(s) loaded successfully!")
    
    if st.button("🚀 Clean, Watermark & Generate PDF", type="primary"):
        with st.spinner("Processing images and building PDF..."):
            pdf_bytes = generate_pdf(subject, code, paper_no, level, date, uploaded_files, top_crop, bottom_crop, left_crop, right_crop)
            
            st.success(" PDF Generated Successfully!")
            st.download_button(
                label="⬇️ Download PDF Now",
                data=pdf_bytes,
                file_name=f"{code}_{subject.replace(' ', '_')}_{date.replace(' ', '_')}.pdf",
                mime="application/pdf"
            )