import os
import tempfile
import streamlit as st
import fitz  # PyMuPDF
from gtts import gTTS

# Page Configuration
st.set_page_config(
    page_title="PDF to Audiobook Converter",
    page_icon="🎧",
    layout="centered"
)

def extract_text_from_pdf(pdf_file):
    """Extracts text from an uploaded PDF file using PyMuPDF."""
    try:
        # Save uploaded file temporarily so PyMuPDF can read it
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(pdf_file.read())
            tmp_path = tmp_file.name

        doc = fitz.open(tmp_path)
        full_text = ""
        for page_num, page in enumerate(doc):
            text = page.get_text()
            if text:
                full_text += f"\n--- Page {page_num + 1} ---\n" + text
        
        doc.close()
        os.unlink(tmp_path)  # Clean up temp file
        return full_text
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return None

def clean_text(text):
    """Cleans up extra whitespaces and formatting noise."""
    # Basic cleanup: collapse multiple spaces/newlines
    cleaned = " ".join(text.split())
    return cleaned

def text_to_speech(text, lang='en', tpe='com', output_path='audiobook.mp3'):
    """Converts text to speech using gTTS and saves as MP3."""
    # gTTS has a character limit per request, but for a general MVP this works well.
    # Note: gTTS 'slow=True' makes it slower, regular speed can be adjusted on the player side.
    tts = gTTS(text=text, lang=lang, tld=tpe, slow=False)
    tts.save(output_path)
    return output_path

# --- UI Layout ---
st.title("🎧 PDF to Audiobook Converter")
st.markdown("Upload any PDF document, customize your audio settings, and convert it into a downloadable audiobook!")

with st.sidebar:
    st.header("⚙️ Audio Settings")
    
    # Accent / TLD options for gTTS
    accent_options = {
        "English (US)": "com",
        "English (UK)": "co.uk",
        "English (Australia)": "com.au",
        "English (Canada)": "ca",
        "English (India)": "co.in",
        "English (Ireland)": "ie"
    }
    selected_accent_label = st.selectbox("Voice Accent", list(accent_options.keys()))
    selected_tld = accent_options[selected_accent_label]
    
    st.info("💡 **Tip:** Large PDFs might take a minute or two to convert into speech.")

uploaded_file = st.file_uploader("Upload your PDF file", type=["pdf"])

if uploaded_file is not None:
    st.success(f"Successfully uploaded: **{uploaded_file.name}**")
    
    if st.button("🚀 Convert to Audiobook", type="primary"):
        with st.spinner("Extracting text and generating audio... Please wait."):
            # Step 1: Extract Text
            raw_text = extract_text_from_pdf(uploaded_file)
            
            if raw_text and len(raw_text.strip()) > 0:
                # Step 2: Clean Text
                processed_text = clean_text(raw_text)
                
                # Limit text size check to prevent crashes on extremely massive books (optional safety cap)
                if len(processed_text) > 100000:
                    st.warning("⚠️ This PDF is very long. Only the first ~100,000 characters will be converted for performance reasons.")
                    processed_text = processed_text[:100000]

                # Step 3: Generate Audio
                output_filename = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
                text_to_speech(processed_text, lang='en', tpe=selected_tld, output_path=output_filename)
                
                st.session_state['audio_file'] = output_filename
                st.session_state['file_name'] = uploaded_file.name.replace(".pdf", ".mp3")
                st.success("✨ Audiobook generated successfully!")
            else:
                st.error("Could not extract readable text from this PDF. It might be a scanned image-based PDF.")

# Display Audio Player and Download button if audio is ready in session state
if 'audio_file' in st.session_state and os.path.exists(st.session_state['audio_file']):
    st.markdown("---")
    st.subheader("🔊 Listen & Download")
    
    # Audio Player
    st.audio(st.session_state['audio_file'], format='audio/mp3')
    
    # Download Button
    with open(st.session_state['audio_file'], "rb") as file:
        st.download_button(
            label="📥 Download Audiobook (MP3)",
            data=file,
            file_name=st.session_state['file_name'],
            mime="audio/mp3"
        )
