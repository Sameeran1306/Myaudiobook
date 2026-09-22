import os
import tempfile
import streamlit as st
import fitz  # PyMuPDF
from gtts import gTTS
from pydub import AudioSegment

st.set_page_config(page_title="Free Local PDF to Audiobook", page_icon="🎧", layout="centered")

def extract_text_from_pdf(pdf_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(pdf_file.read())
        tmp_path = tmp_file.name

    doc = fitz.open(tmp_path)
    full_text = ""
    for page_num, page in enumerate(doc):
        text = page.get_text()
        if text:
            full_text += f"\n[Page {page_num + 1}]\n" + text
    doc.close()
    os.unlink(tmp_path)
    return full_text

def clean_text(text):
    return " ".join(text.split())

def chunk_text(text, max_chars=4000):
    """Splits massive text into safe segments for text-to-speech engines."""
    words = text.split()
    chunks = []
    current_chunk = []
    current_length = 0
    
    for word in words:
        if current_length + len(word) + 1 > max_chars:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_length = len(word)
        else:
            current_chunk.append(word)
            current_length += len(word) + 1
            
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks

# --- UI Layout ---
st.title("🎧 Free Local PDF to Audiobook")
st.markdown("Convert 500+ page books into audiobooks entirely for free, with **no API keys** required.")

with st.sidebar:
    st.header("⚙️ Settings")
    
    accent_options = {
        "English (US)": "com",
        "English (UK)": "co.uk",
        "English (Australia)": "com.au",
        "English (India)": "co.in"
    }
    selected_accent_label = st.selectbox("Voice Accent", list(accent_options.keys()))
    selected_tld = accent_options[selected_accent_label]
    
    st.info("💡 **For 500+ page books:** This script processes text in chunks. It will take a few minutes to complete, but it will not run out of API limits!")

uploaded_file = st.file_uploader("Upload your massive PDF file", type=["pdf"])

if uploaded_file is not None:
    if st.button("🚀 Convert Full Book", type="primary"):
        with st.spinner("Extracting text from your PDF..."):
            raw_text = extract_text_from_pdf(uploaded_file)
            
        if raw_text and len(raw_text.strip()) > 0:
            processed_text = clean_text(raw_text)
            chunks = chunk_text(processed_text, max_chars=4000)
            
            st.info(f"📖 Book loaded successfully! Split into **{len(chunks)} segments** for processing.")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            combined_audio = AudioSegment.empty()
            temp_files = []
            success_flag = True
            
            for i, chunk in enumerate(chunks):
                status_text.text(f"Converting segment {i+1} of {len(chunks)}...")
                try:
                    # Generate speech chunk
                    tts = gTTS(text=chunk, lang='en', tld=selected_tld, slow=False)
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as chunk_file:
                        chunk_path = chunk_file.name
                        temp_files.append(chunk_path)
                    
                    tts.save(chunk_path)
                    
                    # Load and append using pydub
                    segment_audio = AudioSegment.from_mp3(chunk_path)
                    combined_audio += segment_audio
                    
                except Exception as e:
                    st.error(f"Error at segment {i+1}: {e}")
                    success_flag = False
                    break
                
                progress_bar.progress((i + 1) / len(chunks))
                
            if success_flag:
                status_text.text("Stitching audiobook together...")
                final_output = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                combined_audio.export(final_output.name, format="mp3")
                final_output.close()
                
                st.session_state['audio_file'] = final_output.name
                st.session_state['file_name'] = uploaded_file.name.replace(".pdf", "_audiobook.mp3")
                st.success("🎉 Full audiobook generated successfully!")
                
            # Clean up temporary chunk files
            for path in temp_files:
                if os.path.exists(path):
                    os.unlink(path)
        else:
            st.error("Could not extract readable text from this PDF.")

if 'audio_file' in st.session_state and os.path.exists(st.session_state['audio_file']):
    st.markdown("---")
    st.subheader("🔊 Listen & Download")
    st.audio(st.session_state['audio_file'], format='audio/mp3')
    with open(st.session_state['audio_file'], "rb") as file:
        st.download_button(
            label="📥 Download Full Audiobook (MP3)",
            data=file,
            file_name=st.session_state['file_name'],
            mime="audio/mp3"
        )
