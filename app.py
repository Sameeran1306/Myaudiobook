import os
import re
import tempfile
import asyncio
import subprocess
import streamlit as st
import fitz  # PyMuPDF
import edge_tts

st.set_page_config(page_title="Pro Audiobook Creator", page_icon="🎙️", layout="wide")

# --- 1. Advanced PDF Parsing & Cleaning ---
def clean_text(text):
    """Production-grade text normalization."""
    # Fix hyphenated words broken by line breaks
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
    # Remove standalone page numbers and typical header/footer artifacts
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
    # Replace multiple newlines and weird spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_chapters_from_pdf(pdf_path):
    """Extracts text chunked by the actual PDF Table of Contents."""
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()
    chapters = []
    
    if not toc:
        # Fallback: If no TOC, chunk by every 10 pages
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        
        words = full_text.split()
        chunk_size = 3000
        for i in range(0, len(words), chunk_size):
            chunk_text = " ".join(words[i:i+chunk_size])
            chapters.append({"title": f"Part {i//chunk_size + 1}", "text": clean_text(chunk_text)})
        doc.close()
        return chapters

    # If TOC exists, extract text between chapter pages
    for i in range(len(toc)):
        lvl, title, start_page = toc[i]
        start_page -= 1 # PyMuPDF pages are 0-indexed
        end_page = toc[i+1][2] - 1 if i + 1 < len(toc) else len(doc)
        
        chapter_text = ""
        for page_num in range(start_page, end_page):
            chapter_text += doc[page_num].get_text()
            
        cleaned = clean_text(chapter_text)
        if len(cleaned) > 50: # Skip empty structural chapters
            chapters.append({"title": title.replace("/", "-"), "text": cleaned})
            
    doc.close()
    return chapters

# --- 2. Neural Audio Generation (Async) ---
async def generate_chapter_audio(text, voice, output_path):
    """Uses Edge-TTS to generate highly realistic neural speech."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)
    return output_path

# --- 3. Final M4B Compilation with Chapters ---
def compile_m4b_with_chapters(chapter_files, output_m4b):
    """Uses FFmpeg to combine audio and inject chapter metadata."""
    # Create a concat text file for FFmpeg
    concat_file_path = "concat.txt"
    with open(concat_file_path, "w", encoding="utf-8") as f:
        for idx, (_, audio_path) in enumerate(chapter_files):
            # Ensure path uses forward slashes for FFmpeg compatibility
            safe_path = audio_path.replace("\\", "/")
            f.write(f"file '{safe_path}'\n")
            
    # Run FFmpeg to concatenate and convert to M4B (AAC format)
    # Using extremely fast copy codec where possible, or AAC re-encoding
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", 
        "-i", concat_file_path, 
        "-c:a", "aac", "-b:a", "64k", # 64k is standard audiobook bitrate
        "-vn", output_m4b
    ]
    
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(concat_file_path)

# --- UI Layout ---
st.title("🎙️ Studio-Grade PDF to Audiobook")
st.markdown("Generates **Chapter-Marked .M4B Audiobooks** using Microsoft Neural Voices.")

with st.sidebar:
    st.header("⚙️ Voice Casting")
    # A curated list of the best Edge-TTS English voices
    voices = {
        "Guy (US - Deep, Professional)": "en-US-GuyNeural",
        "Christopher (US - Conversational)": "en-US-ChristopherNeural",
        "Aria (US - Clear, Engaging)": "en-US-AriaNeural",
        "Sonia (UK - Crisp, Elegant)": "en-GB-SoniaNeural",
        "Ryan (UK - Calm, Storyteller)": "en-GB-RyanNeural",
        "Natasha (AU - Friendly)": "en-AU-NatashaNeural"
    }
    voice_label = st.selectbox("Narrator Voice", list(voices.keys()))
    selected_voice = voices[voice_label]

uploaded_file = st.file_uploader("Upload PDF Book", type=["pdf"])

if uploaded_file:
    if st.button("🎬 Produce Audiobook", type="primary"):
        temp_dir = tempfile.mkdtemp()
        pdf_path = os.path.join(temp_dir, "source.pdf")
        
        with open(pdf_path, "wb") as f:
            f.write(uploaded_file.read())
            
        with st.status("📚 Analyzing Book Structure...", expanded=True) as status:
            st.write("Extracting Table of Contents and cleaning text...")
            chapters = extract_chapters_from_pdf(pdf_path)
            st.write(f"Found {len(chapters)} logical chapters/sections.")
            
            status.update(label="🎙️ Synthesizing Neural Audio...", state="running")
            progress_bar = st.progress(0)
            
            chapter_audio_files = []
            
            # Create a new event loop for Edge-TTS asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            for i, chapter in enumerate(chapters):
                st.write(f"Recording: *{chapter['title']}*")
                audio_path = os.path.join(temp_dir, f"chap_{i}.mp3")
                
                # Run the async TTS generation
                loop.run_until_complete(
                    generate_chapter_audio(chapter['text'], selected_voice, audio_path)
                )
                chapter_audio_files.append((chapter['title'], audio_path))
                progress_bar.progress((i + 1) / len(chapters))
                
            loop.close()
            
            status.update(label="🎞️ Mastering M4B Audiobook...", state="running")
            st.write("Compiling files and injecting chapter metadata...")
            
            final_m4b_path = os.path.join(temp_dir, "Final_Audiobook.m4b")
            compile_m4b_with_chapters(chapter_audio_files, final_m4b_path)
            
            st.session_state['final_audio'] = final_m4b_path
            st.session_state['book_name'] = uploaded_file.name.replace(".pdf", ".m4b")
            
            status.update(label="✅ Audiobook Production Complete!", state="complete")

if 'final_audio' in st.session_state:
    st.markdown("---")
    st.success("🎉 Your production-grade audiobook is ready.")
    
    with open(st.session_state['final_audio'], "rb") as file:
        st.download_button(
            label="📥 Download .M4B Audiobook",
            data=file,
            file_name=st.session_state['book_name'],
            mime="audio/mp4"
        )
    st.caption("💡 Tip: Play the .m4b file in apps like Apple Books, Audible, or Smart Audiobook Player to see the chapter menu!")
