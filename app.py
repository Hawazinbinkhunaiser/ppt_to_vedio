import streamlit as st
import tempfile
import os
from pathlib import Path
import zipfile
from io import BytesIO
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
import librosa

def extract_slides_from_pdf(pdf_path, output_dir):
    """Extract slides from PDF as images"""
    doc = fitz.open(pdf_path)
    slide_paths = []
    
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # Convert to image with high resolution
        mat = fitz.Matrix(2, 2)  # 2x zoom for better quality
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        slide_path = os.path.join(output_dir, f"slide_{page_num + 1}.png")
        img.save(slide_path)
        slide_paths.append(slide_path)
    
    doc.close()
    return slide_paths

def get_audio_duration(audio_path):
    """Get duration of audio file in seconds"""
    try:
        duration = librosa.get_duration(path=audio_path)
        return duration
    except:
        return None

def create_video(slide_paths, audio_files, output_path):
    """Create video from slides and audio files"""
    clips = []
    
    for i, slide_path in enumerate(slide_paths):
        slide_num = i + 1
        audio_path = None
        
        # Look for corresponding audio file
        for audio_file in audio_files:
            if f"slide_{slide_num}.mp3" in audio_file or f"slide_{slide_num}.wav" in audio_file:
                audio_path = audio_file
                break
        
        if audio_path and os.path.exists(audio_path):
            # Get audio duration
            audio_duration = get_audio_duration(audio_path)
            if audio_duration:
                # Create image clip with audio duration
                img_clip = ImageClip(slide_path, duration=audio_duration)
                audio_clip = AudioFileClip(audio_path)
                # Combine image and audio
                video_clip = img_clip.set_audio(audio_clip)
                clips.append(video_clip)
            else:
                # If audio can't be read, use 10 seconds silence
                img_clip = ImageClip(slide_path, duration=10)
                clips.append(img_clip)
        else:
            # No audio file found, use 10 seconds silence
            img_clip = ImageClip(slide_path, duration=10)
            clips.append(img_clip)
    
    if clips:
        # Concatenate all clips
        final_video = concatenate_videoclips(clips, method="compose")
        final_video.write_videofile(output_path, fps=1, codec='libx264')
        final_video.close()
        
        # Clean up clips
        for clip in clips:
            clip.close()
    
    return len(clips)

def main():
    st.set_page_config(
        page_title="PDF Slides to Video Converter",
        page_icon="🎥",
        layout="wide"
    )
    
    st.title("🎥 PDF Slides to Video Converter")
    st.markdown("Convert your PDF presentation slides with audio narration into a video!")
    
    # Instructions
    with st.expander("📋 Instructions"):
        st.markdown("""
        1. **Upload your PDF file** containing the presentation slides
        2. **Upload audio files** named as `slide_1.mp3`, `slide_2.mp3`, etc.
           - Supported formats: MP3, WAV
           - Audio files should correspond to slide numbers
        3. **Generate video** - slides without audio will display for 10 seconds
        4. **Download** your generated video
        
        **Note**: Make sure your audio files are named correctly (e.g., slide_1.mp3 for the first slide)
        """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📄 Upload PDF")
        pdf_file = st.file_uploader(
            "Choose PDF file",
            type=['pdf'],
            help="Upload your presentation PDF file"
        )
    
    with col2:
        st.subheader("🎵 Upload Audio Files")
        audio_files = st.file_uploader(
            "Choose audio files",
            type=['mp3', 'wav'],
            accept_multiple_files=True,
            help="Upload audio files named as slide_1.mp3, slide_2.mp3, etc."
        )
    
    if pdf_file:
        st.success(f"PDF uploaded: {pdf_file.name}")
        
        if audio_files:
            st.success(f"Audio files uploaded: {len(audio_files)} files")
            
            # Show uploaded audio files
            with st.expander("📁 Uploaded Audio Files"):
                for audio_file in audio_files:
                    st.write(f"• {audio_file.name}")
        
        if st.button("🎬 Generate Video", type="primary"):
            try:
                with st.spinner("Processing slides and generating video..."):
                    # Create temporary directory
                    with tempfile.TemporaryDirectory() as temp_dir:
                        # Save PDF
                        pdf_path = os.path.join(temp_dir, "presentation.pdf")
                        with open(pdf_path, "wb") as f:
                            f.write(pdf_file.getbuffer())
                        
                        # Extract slides
                        st.info("📄 Extracting slides from PDF...")
                        slide_paths = extract_slides_from_pdf(pdf_path, temp_dir)
                        st.success(f"Extracted {len(slide_paths)} slides")
                        
                        # Save audio files
                        audio_file_paths = []
                        if audio_files:
                            st.info("🎵 Processing audio files...")
                            for audio_file in audio_files:
                                audio_path = os.path.join(temp_dir, audio_file.name)
                                with open(audio_path, "wb") as f:
                                    f.write(audio_file.getbuffer())
                                audio_file_paths.append(audio_path)
                        
                        # Create video
                        st.info("🎬 Creating video...")
                        output_video_path = os.path.join(temp_dir, "presentation_video.mp4")
                        num_clips = create_video(slide_paths, audio_file_paths, output_video_path)
                        
                        if os.path.exists(output_video_path):
                            st.success(f"✅ Video created successfully with {num_clips} slides!")
                            
                            # Provide download button
                            with open(output_video_path, "rb") as video_file:
                                st.download_button(
                                    label="📥 Download Video",
                                    data=video_file.read(),
                                    file_name="presentation_video.mp4",
                                    mime="video/mp4"
                                )
                            
                            # Show video preview
                            st.subheader("🎥 Video Preview")
                            st.video(output_video_path)
                        else:
                            st.error("❌ Failed to create video. Please check your files and try again.")
            
            except Exception as e:
                st.error(f"❌ An error occurred: {str(e)}")
                st.error("Please make sure your PDF and audio files are valid.")
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
        Built with Streamlit • Convert PDF slides to video with audio narration
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
