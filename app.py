
import io
import csv
import re
import zipfile
from datetime import datetime
from pathlib import Path

import segno
from PIL import Image, ImageOps
import streamlit as st

# ----------------------------
# App Config
# ----------------------------
st.set_page_config(page_title="Instant QR Code Generator", page_icon="🔳", layout="centered")
st.title("🔳 Instant QR Code Generator")
st.caption("Generate customized QR codes (PNG, SVG, PDF), add logos, and download individually or in batch.")

if "qr_history" not in st.session_state:
    st.session_state.qr_history = []  # list of dicts

# ----------------------------
# Helper Functions
# ----------------------------
def sanitize_filename(s: str, max_len: int = 50) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", s.strip())
    base = re.sub(r"_+", "_", base).strip("_")
    return base[:max_len] or "qr_code"

def add_logo_to_png(png_bytes: bytes, logo_img: Image.Image, ratio: float = 0.2, add_white_bg: bool = True) -> bytes:
    """Composite a centered logo onto the QR PNG. ratio is fraction of QR width used by logo."""
    qr_img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    W, H = qr_img.size
    target_w = int(W * ratio)
    logo_img = logo_img.convert("RGBA")
    logo_img = ImageOps.contain(logo_img, (target_w, target_w))

    # Optional white background behind logo
    if add_white_bg:
        pad = max(4, target_w // 20)
        bg_w, bg_h = logo_img.size[0] + pad * 2, logo_img.size[1] + pad * 2
        bg = Image.new("RGBA", (bg_w, bg_h), (255, 255, 255, 255))
        bg.paste(logo_img, (pad, pad), logo_img)
        logo_img = bg

    # Center placement
    pos = ((W - logo_img.size[0]) // 2, (H - logo_img.size[1]) // 2)
    qr_img.alpha_composite(logo_img, dest=pos)

    out = io.BytesIO()
    qr_img.save(out, format="PNG")
    out.seek(0)
    return out.getvalue()

def generate_qr(text: str,
                error: str = "m",
                micro: bool = False,
                version: int | None = None,
                mask: int | None = None,
                boost_error: bool = False,
                scale: int = 6,
                border: int = 4,
                dark: str = "#000000",
                light: str = "#FFFFFF",
                transparent: bool = False):
    """
    Returns dict of {png: bytes, svg: bytes, pdf: bytes}
    """
    qr = segno.make(text, error=error, micro=micro, version=version, mask=mask, boost_error=boost_error)

    # PNG
    png_buffer = io.BytesIO()
    qr.save(png_buffer, kind="png", scale=scale, border=border, dark=dark, light=light, transparent=transparent)
    png_buffer.seek(0)

    # SVG
    svg_buffer = io.BytesIO()
    qr.save(svg_buffer, kind="svg", scale=scale, border=border, dark=dark, light=light)
    svg_buffer.seek(0)

    # PDF
    pdf_buffer = io.BytesIO()
    qr.save(pdf_buffer, kind="pdf", border=border, dark=dark, light=light)
    pdf_buffer.seek(0)

    return {"png": png_buffer.getvalue(), "svg": svg_buffer.getvalue(), "pdf": pdf_buffer.getvalue()}

def build_project_zip():
    """Create an in-memory ZIP of the project files."""
    project_dir = Path(__file__).resolve().parent
    files = ["app.py", "requirements.txt", "README.md", "Dockerfile"]

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname in files:
            fpath = project_dir / fname
            if fpath.exists():
                zf.write(fpath, arcname=fname)
    zip_buf.seek(0)
    return zip_buf

# ----------------------------
# UI: Input & Options
# ----------------------------
text = st.text_input("Text / URL", placeholder="https://example.com", help="Enter any text, URL, vCard, WiFi settings, etc.")

with st.expander("⚙️ Advanced options", expanded=False):
    colA, colB, colC = st.columns(3)
    with colA:
        error = st.selectbox("Error correction", options=["l", "m", "q", "h"], index=1,
                             help="L (low), M (medium), Q (quartile), H (high)")
        micro = st.checkbox("Micro QR", value=False, help="Use Micro QR when suitable for very short content")
        boost_error = st.checkbox("Boost error level", value=False, help="Automatically use higher error level if required")

    with colB:
        version_opt = st.selectbox("Version", options=["auto"] + list(range(1, 40)), index=0,
                                   help="Auto selects the smallest version that fits. 1–40 for standard QR.")
        mask_opt = st.selectbox("Mask", options=["auto"] + list(range(0, 8)), index=0,
                                help="Auto mask generally works best.")

    with colC:
        scale = st.number_input("Scale (pixel size)", min_value=1, max_value=40, value=6, step=1)
        border = st.number_input("Quiet zone (modules)", min_value=0, max_value=20, value=4, step=1)

    col1, col2, col3 = st.columns(3)
    with col1:
        dark = st.color_picker("Dark color", value="#000000")
    with col2:
        light = st.color_picker("Light color", value="#FFFFFF")
    with col3:
        transparent = st.checkbox("PNG transparent background", value=False)

logo_file = st.file_uploader("Optional logo (PNG/JPG)", type=["png", "jpg", "jpeg"], accept_multiple_files=False)
logo_ratio = st.slider("Logo size (% of QR width)", min_value=10, max_value=30, value=20, step=1)

# ----------------------------
# Generate
# ----------------------------
generate = st.button("Generate QR Code", type="primary", use_container_width=True)

if generate and text:
    version = None if version_opt == "auto" else int(version_opt)
    mask = None if mask_opt == "auto" else int(mask_opt)

    result = generate_qr(
        text=text,
        error=error,
        micro=micro,
        version=version,
        mask=mask,
        boost_error=boost_error,
        scale=scale,
        border=border,
        dark=dark,
        light=light,
        transparent=transparent
    )

    png_bytes = result["png"]

    # Add logo if provided
    if logo_file is not None:
        try:
            logo_img = Image.open(logo_file)
            png_bytes = add_logo_to_png(png_bytes, logo_img, ratio=logo_ratio / 100.0, add_white_bg=True)
        except Exception as e:
            st.warning(f"Logo processing failed: {e}")

    # Use updated png_bytes if logo was applied
    result["png"] = png_bytes

    # Preview
    st.image(Image.open(io.BytesIO(result["png"])), caption="Generated QR Code", use_column_width=False)

    # Filename base
    filename_base = sanitize_filename(text)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Downloads
    colD, colE, colF = st.columns(3)
    with colD:
        st.download_button(
            "⬇️ Download PNG",
            data=result["png"],
            file_name=f"{filename_base}_{timestamp}.png",
            mime="image/png",
            use_container_width=True
        )
    with colE:
        st.download_button(
            "⬇️ Download SVG",
            data=result["svg"],
            file_name=f"{filename_base}_{timestamp}.svg",
            mime="image/svg+xml",
            use_container_width=True
        )
    with colF:
        st.download_button(
            "⬇️ Download PDF",
            data=result["pdf"],
            file_name=f"{filename_base}_{timestamp}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    # Save to history
    st.session_state.qr_history.append({
        "text": text,
        "png": result["png"],
        "svg": result["svg"],
        "pdf": result["pdf"],
        "filename_base": filename_base,
        "ts": timestamp
    })

elif generate and not text:
    st.error("Please enter some text or a URL.")

# ----------------------------
# Batch Generation (CSV/TXT -> ZIP)
# ----------------------------
st.subheader("📦 Batch generate QR codes")
batch_file = st.file_uploader("Upload a CSV or TXT (one value per line, or CSV with 'value' column).", type=["csv", "txt"], accept_multiple_files=False)

def build_zip_from_values(values: list[str],
                          error, micro, version, mask, boost_error, scale, border, dark, light, transparent):
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for v in values:
            if not v.strip():
                continue
            files = generate_qr(v.strip(), error, micro, version, mask, boost_error, scale, border, dark, light, transparent)
            base = sanitize_filename(v.strip())
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            zf.writestr(f"{base}_{ts}.png", files["png"])
            zf.writestr(f"{base}_{ts}.svg", files["svg"])
            zf.writestr(f"{base}_{ts}.pdf", files["pdf"])
    zip_buf.seek(0)
    return zip_buf

if batch_file is not None:
    values = []
    try:
        if batch_file.name.lower().endswith(".txt"):
            for line in batch_file.getvalue().decode("utf-8", errors="ignore").splitlines():
                values.append(line.strip())
        else:
            # CSV: try 'value' column; fallback to first column
            content = batch_file.getvalue().decode("utf-8", errors="ignore").splitlines()
            reader = csv.DictReader(content)
            if reader.fieldnames:
                if "value" in [f.lower() for f in reader.fieldnames]:
                    # map case-insensitively
                    key = [f for f in reader.fieldnames if f.lower() == "value"][0]
                    for row in reader:
                        values.append(str(row.get(key, "")).strip())
                else:
                    # fallback first column
                    reader2 = csv.reader(content)
                    for row in reader2:
                        if row:
                            values.append(str(row[0]).strip())
            else:
                st.warning("CSV has no header/columns. Make sure it's a valid CSV.")
    except Exception as e:
        st.error(f"Failed to parse file: {e}")

    if values:
        st.info(f"Parsed {len(values)} entries.")
        zip_buf = build_zip_from_values(
            values, error, micro,
            None if version_opt == "auto" else int(version_opt),
            None if mask_opt == "auto" else int(mask_opt),
            boost_error, scale, border, dark, light, transparent
        )
        st.download_button(
            "⬇️ Download ZIP of QR Codes",
            data=zip_buf,
            file_name=f"qr_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip",
            use_container_width=True
        )
    else:
        st.warning("No valid values found in the uploaded file.")

# ----------------------------
# History
# ----------------------------
st.subheader("🕘 History (this session)")
if st.session_state.qr_history:
    clear = st.button("Clear history")
    if clear:
        st.session_state.qr_history.clear()
        st.experimental_rerun()

    for i, item in enumerate(reversed(st.session_state.qr_history), start=1):
        st.markdown(f"**{i}.** {item['text']}")
        st.image(Image.open(io.BytesIO(item["png"])), use_column_width=False)
        colH1, colH2, colH3 = st.columns(3)
        with colH1:
            st.download_button("PNG", data=item["png"], file_name=f"{item['filename_base']}_{item['ts']}.png", mime="image/png")
        with colH2:
            st.download_button("SVG", data=item["svg"], file_name=f"{item['filename_base']}_{item['ts']}.svg", mime="image/svg+xml")
        with colH3:
            st.download_button("PDF", data=item["pdf"], file_name=f"{item['filename_base']}_{item['ts']}.pdf", mime="application/pdf")
else:
    st.caption("No history yet. Generate a QR to see it here.")

# ----------------------------
# Download Project ZIP
# ----------------------------
st.subheader("📁 Download Project as ZIP")
project_zip = build_project_zip()
st.download_button(
    "⬇️ Download instant-qr.zip",
    data=project_zip,
    file_name="instant-qr.zip",
    mime="application/zip",
    use_container_width=True
)
