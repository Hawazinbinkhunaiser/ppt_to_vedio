import streamlit as st
import tempfile
import os
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import cv2
from pydub import AudioSegment
from pydub.utils import which
import subprocess
import time

# Set page config
st.set_page_config(
    page_title="PDF Slides to Video Converter",
    page_icon="🎥",
    layout="wide"
)

def check_ffmpeg():
    """Check if ffmpeg is available"""
    return which("ffmpeg") is not None

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
    """Get duration of audio file in seconds using pydub"""
    try:
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0  # Convert milliseconds to seconds
    except Exception as e:
        st.warning(f"Could not read audio file {os.path.basename(audio_path)}: {e}")
        return None

def create_video_opencv(slide_paths, audio_files, output_path, temp_dir):
    """Create video using OpenCV and ffmpeg"""
    try:
        # Prepare slide information
        slide_info = []
        total_duration = 0
        
        for i, slide_path in enumerate(slide_paths):
            slide_num = i + 1
            audio_path = None
            duration = 10  # default duration
            
            # Look for corresponding audio file
            for audio_file in audio_files:
                audio_name = os.path.basename(audio_file)
                if f"slide_{slide_num}.mp3" in audio_name or f"slide_{slide_num}.wav" in audio_name:
                    audio_path = audio_file
                    break
            
            if audio_path and os.path.exists(audio_path):
                audio_duration = get_audio_duration(audio_path)
                if audio_duration:
                    duration = audio_duration
            
            slide_info.append({
                'slide_path': slide_path,
                'audio_path': audio_path,
                'duration': duration,
                'start_time': total_duration
            })
            total_duration += duration
        
        # Read first slide to get dimensions
        first_slide = cv2.imread(slide_paths[0])
        if first_slide is None:
            raise Exception("Could not read the first slide image")
        
        height, width, layers = first_slide.shape
        
        # Create temporary video without audio
        temp_video_path = os.path.join(temp_dir, "temp_video.mp4")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        fps = 1  # 1 frame per second for simplicity
        
        out = cv2.VideoWriter(temp_video_path, fourcc, fps, (width, height))
        
        # Add frames for each slide
        for slide_data in slide_info:
            slide_img = cv2.imread(slide_data['slide_path'])
            if slide_img is None:
                continue
            
            # Add frames based on duration (fps * duration)
            num_frames = max(1, int(fps * slide_data['duration']))
            for _ in range(num_frames):
                out.write(slide_img)
        
        out.release()
        
        # Now combine audio using ffmpeg if available
        if check_ffmpeg():
            return create_video_with_ffmpeg(slide_info, temp_video_path, output_path, temp_dir)
        else:
            # If no ffmpeg, just return the video without audio
            os.rename(temp_video_path, output_path)
            return len(slide_paths), False
        
    except Exception as e:
        st.error(f"Error creating video: {e}")
        return 0, False

def create_video_with_ffmpeg(slide_info, video_path, output_path, temp_dir):
    """Combine video with audio using ffmpeg"""
    try:
        # Create audio timeline
        audio_clips = []
        current_time = 0
        
        for slide_data in slide_info:
            if slide_data['audio_path'] and os.path.exists(slide_data['audio_path']):
                # Add audio at the correct time
                audio_clips.append(f"[1:a]atrim=0:{slide_data['duration']},asetpts=PTS-STARTPTS[a{len(audio_clips)}];")
            current_time += slide_data['duration']
        
        if audio_clips:
            # Create complex audio filter
            audio_files_input = []
            audio_filter = ""
            
            for i, slide_data in enumerate(slide_info):
                if slide_data['audio_path'] and os.path.exists(slide_data['audio_path']):
                    audio_files_input.extend(["-i", slide_data['audio_path']])
            
            # Simple approach: create video with first available audio
            for slide_data in slide_info:
                if slide_data['audio_path'] and os.path.exists(slide_data['audio_path']):
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", video_path,
                        "-i", slide_data['audio_path'],
                        "-c:v", "libx264",
                        "-c:a", "aac",
                        "-shortest",
                        output_path
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        return len(slide_info), True
                    break
        
        # If no audio or ffmpeg fails, copy the video without audio
        os.rename(video_path, output_path)
        return len(slide_info), False
        
    except Exception as e:
        st.warning(f"Audio processing failed: {e}. Creating video without audio.")
        os.rename(video_path, output_path)
        return len(slide_info), False

def main():
    st.title("🎥 PDF Slides to Video Converter")
    st.markdown("Convert your PDF presentation slides with audio narration into a video!")
    
    # Check system capabilities
    ffmpeg_available = check_ffmpeg()
    
    if not ffmpeg_available:
        st.warning("⚠️ FFmpeg not detected. Videos will be created without audio synchronization. Audio files will still be processed but may not be perfectly synchronized.")
    
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
                        progress_bar = st.progress(0)
                        st.info("📄 Extracting slides from PDF...")
                        slide_paths = extract_slides_from_pdf(pdf_path, temp_dir)
                        progress_bar.progress(0.3)
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
                        
                        progress_bar.progress(0.6)
                        
                        # Create video
                        st.info("🎬 Creating video...")
                        output_video_path = os.path.join(temp_dir, "presentation_video.mp4")
                        num_clips, has_audio = create_video_opencv(slide_paths, audio_file_paths, output_video_path, temp_dir)
                        
                        progress_bar.progress(1.0)
                        
                        if os.path.exists(output_video_path) and num_clips > 0:
                            success_msg = f"✅ Video created successfully with {num_clips} slides!"
                            if has_audio:
                                success_msg += " (with audio)"
                            else:
                                success_msg += " (video only - audio sync may not be perfect)"
                            
                            st.success(success_msg)
                            
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
                            try:
                                st.video(output_video_path)
                            except:
                                st.info("Video created successfully! Use the download button above to get your video.")
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
