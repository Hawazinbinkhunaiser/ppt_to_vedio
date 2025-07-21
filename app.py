import streamlit as st
import tempfile
import os
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
from pydub import AudioSegment
import zipfile
from io import BytesIO
import base64
import json

# Set page config
st.set_page_config(
    page_title="PDF Slides to Video Converter",
    page_icon="🎥",
    layout="wide"
)

def extract_slides_from_pdf(pdf_path, output_dir):
    """Extract slides from PDF as images"""
    doc = fitz.open(pdf_path)
    slide_paths = []
    
    progress_bar = st.progress(0)
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # Convert to image with high resolution
        mat = fitz.Matrix(2, 2)  # 2x zoom for better quality
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        slide_path = os.path.join(output_dir, f"slide_{page_num + 1}.png")
        img.save(slide_path, quality=95)
        slide_paths.append(slide_path)
        
        # Update progress
        progress_bar.progress((page_num + 1) / len(doc))
    
    doc.close()
    return slide_paths

def get_audio_duration(audio_path):
    """Get duration of audio file in seconds using pydub"""
    try:
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0  # Convert milliseconds to seconds
    except Exception as e:
        return None

def create_html_slideshow(slide_paths, audio_files, output_path, temp_dir):
    """Create an HTML slideshow that can be viewed in browser"""
    
    # Prepare slide data
    slides_data = []
    total_duration = 0
    
    for i, slide_path in enumerate(slide_paths):
        slide_num = i + 1
        audio_path = None
        duration = 10  # default duration in seconds
        
        # Look for corresponding audio file
        for audio_file in audio_files:
            audio_name = os.path.basename(audio_file)
            if f"slide_{slide_num}.mp3" in audio_name or f"slide_{slide_num}.wav" in audio_name:
                audio_path = audio_file
                break
        
        # Get audio duration if available
        if audio_path and os.path.exists(audio_path):
            audio_duration = get_audio_duration(audio_path)
            if audio_duration:
                duration = audio_duration
        
        # Convert image to base64
        with open(slide_path, 'rb') as img_file:
            img_data = base64.b64encode(img_file.read()).decode()
        
        # Convert audio to base64 if available
        audio_data = None
        if audio_path and os.path.exists(audio_path):
            try:
                with open(audio_path, 'rb') as audio_file:
                    audio_data = base64.b64encode(audio_file.read()).decode()
                    # Detect audio format
                    audio_format = 'mp3' if audio_path.lower().endswith('.mp3') else 'wav'
            except:
                audio_data = None
        
        slides_data.append({
            'slide_num': slide_num,
            'image_data': img_data,
            'audio_data': audio_data,
            'audio_format': audio_format if audio_data else None,
            'duration': duration * 1000,  # Convert to milliseconds for JavaScript
            'start_time': total_duration * 1000
        })
        
        total_duration += duration
    
    # Create HTML slideshow
    html_content = create_slideshow_html(slides_data, total_duration)
    
    # Save HTML file
    html_path = os.path.join(temp_dir, "slideshow.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Also create a downloadable package
    package_path = create_downloadable_package(slides_data, temp_dir)
    
    return html_path, package_path, len(slides_data)

def create_slideshow_html(slides_data, total_duration):
    """Create HTML content for the slideshow"""
    
    html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Slideshow</title>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            font-family: Arial, sans-serif;
            background: #000;
            color: white;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
        }}
        
        .slideshow-container {{
            position: relative;
            max-width: 90vw;
            max-height: 80vh;
            margin: auto;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        }}
        
        .slide {{
            display: none;
            width: 100%;
            height: auto;
        }}
        
        .slide.active {{
            display: block;
        }}
        
        .slide img {{
            width: 100%;
            height: auto;
            display: block;
        }}
        
        .controls {{
            margin: 20px 0;
            text-align: center;
        }}
        
        .controls button {{
            background: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            margin: 0 5px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
        }}
        
        .controls button:hover {{
            background: #0056b3;
        }}
        
        .controls button:disabled {{
            background: #6c757d;
            cursor: not-allowed;
        }}
        
        .progress-bar {{
            width: 80%;
            height: 6px;
            background: #ddd;
            border-radius: 3px;
            margin: 10px 0;
            overflow: hidden;
        }}
        
        .progress {{
            height: 100%;
            background: #007bff;
            width: 0%;
            transition: width 0.1s ease;
        }}
        
        .slide-info {{
            margin: 10px 0;
            font-size: 18px;
        }}
        
        .duration-info {{
            margin: 5px 0;
            font-size: 14px;
            color: #ccc;
        }}
    </style>
</head>
<body>
    <h1>🎥 PDF Slideshow Presentation</h1>
    
    <div class="slideshow-container">
        <div id="slides">
            <!-- Slides will be inserted here -->
        </div>
    </div>
    
    <div class="slide-info">
        <span id="slide-counter">Slide 1 of {len(slides_data)}</span>
    </div>
    
    <div class="progress-bar">
        <div class="progress" id="progress"></div>
    </div>
    
    <div class="duration-info">
        <span id="time-info">00:00 / {int(total_duration//60):02d}:{int(total_duration%60):02d}</span>
    </div>
    
    <div class="controls">
        <button onclick="previousSlide()">⏮ Previous</button>
        <button id="playBtn" onclick="togglePlay()">▶ Play</button>
        <button onclick="nextSlide()">Next ⏭</button>
        <button onclick="resetSlideshow()">🔄 Reset</button>
    </div>
    
    <script>
        const slidesData = {json.dumps(slides_data)};
        let currentSlide = 0;
        let isPlaying = false;
        let startTime = 0;
        let currentAudio = null;
        let animationId = null;
        
        // Initialize slides
        function initSlides() {{
            const slidesContainer = document.getElementById('slides');
            slidesData.forEach((slide, index) => {{
                const slideDiv = document.createElement('div');
                slideDiv.className = index === 0 ? 'slide active' : 'slide';
                slideDiv.innerHTML = `<img src="data:image/png;base64,${{slide.image_data}}" alt="Slide ${{slide.slide_num}}">`;
                slidesContainer.appendChild(slideDiv);
            }});
        }}
        
        function showSlide(n) {{
            const slides = document.querySelectorAll('.slide');
            currentSlide = (n + slides.length) % slides.length;
            
            slides.forEach(slide => slide.classList.remove('active'));
            slides[currentSlide].classList.add('active');
            
            document.getElementById('slide-counter').textContent = `Slide ${{currentSlide + 1}} of ${{slides.length}}`;
            
            if (isPlaying) {{
                playSlideAudio();
            }}
        }}
        
        function nextSlide() {{
            if (currentSlide < slidesData.length - 1) {{
                showSlide(currentSlide + 1);
            }} else if (isPlaying) {{
                // End of slideshow
                stopSlideshow();
            }}
        }}
        
        function previousSlide() {{
            showSlide(currentSlide - 1);
        }}
        
        function playSlideAudio() {{
            if (currentAudio) {{
                currentAudio.pause();
                currentAudio = null;
            }}
            
            const slide = slidesData[currentSlide];
            if (slide.audio_data) {{
                const audioSrc = `data:audio/${{slide.audio_format}};base64,${{slide.audio_data}}`;
                currentAudio = new Audio(audioSrc);
                currentAudio.play().catch(e => console.log('Audio play failed:', e));
                
                currentAudio.onended = () => {{
                    if (isPlaying) {{
                        setTimeout(() => {{
                            nextSlide();
                        }}, 100);
                    }}
                }};
            }} else {{
                // No audio, wait for slide duration
                setTimeout(() => {{
                    if (isPlaying) {{
                        nextSlide();
                    }}
                }}, slide.duration);
            }}
        }}
        
        function togglePlay() {{
            const playBtn = document.getElementById('playBtn');
            if (isPlaying) {{
                stopSlideshow();
            }} else {{
                startSlideshow();
            }}
        }}
        
        function startSlideshow() {{
            isPlaying = true;
            startTime = Date.now();
            document.getElementById('playBtn').innerHTML = '⏸ Pause';
            playSlideAudio();
            updateProgress();
        }}
        
        function stopSlideshow() {{
            isPlaying = false;
            document.getElementById('playBtn').innerHTML = '▶ Play';
            if (currentAudio) {{
                currentAudio.pause();
            }}
            if (animationId) {{
                cancelAnimationFrame(animationId);
            }}
        }}
        
        function resetSlideshow() {{
            stopSlideshow();
            currentSlide = 0;
            showSlide(0);
            document.getElementById('progress').style.width = '0%';
            document.getElementById('time-info').textContent = '00:00 / {int(total_duration//60):02d}:{int(total_duration%60):02d}';
        }}
        
        function updateProgress() {{
            if (!isPlaying) return;
            
            const elapsed = (Date.now() - startTime) / 1000;
            const progress = Math.min(elapsed / {total_duration} * 100, 100);
            document.getElementById('progress').style.width = progress + '%';
            
            const minutes = Math.floor(elapsed / 60);
            const seconds = Math.floor(elapsed % 60);
            document.getElementById('time-info').textContent = 
                `${{minutes.toString().padStart(2, '0')}}:${{seconds.toString().padStart(2, '0')}} / {int(total_duration//60):02d}:{int(total_duration%60):02d}`;
            
            if (progress < 100) {{
                animationId = requestAnimationFrame(updateProgress);
            }}
        }}
        
        // Keyboard controls
        document.addEventListener('keydown', function(e) {{
            switch(e.key) {{
                case 'ArrowLeft':
                    previousSlide();
                    break;
                case 'ArrowRight':
                case ' ':
                    e.preventDefault();
                    if (e.key === ' ') {{
                        togglePlay();
                    }} else {{
                        nextSlide();
                    }}
                    break;
                case 'Home':
                    resetSlideshow();
                    break;
            }}
        }});
        
        // Initialize
        initSlides();
    </script>
</body>
</html>
"""
    
    return html_template

def create_downloadable_package(slides_data, temp_dir):
    """Create a downloadable ZIP package with all slides and a viewer"""
    package_path = os.path.join(temp_dir, "slideshow_package.zip")
    
    with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add HTML viewer
        html_content = create_slideshow_html(slides_data, sum(slide['duration'] for slide in slides_data) / 1000)
        zipf.writestr("slideshow.html", html_content)
        
        # Add README
        readme_content = """
# PDF Slideshow Package

This package contains:
- slideshow.html: Interactive HTML presentation viewer
- All slide images and audio files

## How to use:
1. Extract all files to a folder
2. Open slideshow.html in any web browser
3. Use the play button to start automatic playback
4. Use arrow keys or buttons to navigate manually

## Controls:
- Play/Pause: Space bar or Play button
- Next slide: Right arrow or Next button  
- Previous slide: Left arrow or Previous button
- Reset: Home key or Reset button

Enjoy your presentation!
"""
        zipf.writestr("README.txt", readme_content)
    
    return package_path

def main():
    st.title("🎥 PDF Slides to Video Converter")
    st.markdown("Convert your PDF presentation slides with audio narration into an interactive slideshow!")
    
    # Instructions
    with st.expander("📋 Instructions"):
        st.markdown("""
        1. **Upload your PDF file** containing the presentation slides
        2. **Upload audio files** named as `slide_1.mp3`, `slide_2.mp3`, etc.
           - Supported formats: MP3, WAV
           - Audio files should correspond to slide numbers
        3. **Generate slideshow** - slides without audio will display for 10 seconds
        4. **View and download** your interactive slideshow
        
        **Note**: This creates an HTML slideshow that can be viewed in any browser, with or without audio.
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
        
        if st.button("🎬 Generate Interactive Slideshow", type="primary"):
            try:
                with st.spinner("Processing slides and creating slideshow..."):
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
                        
                        # Create slideshow
                        st.info("🎬 Creating interactive slideshow...")
                        html_path, package_path, num_slides = create_html_slideshow(
                            slide_paths, audio_file_paths, None, temp_dir
                        )
                        
                        if os.path.exists(html_path) and num_slides > 0:
                            st.success(f"✅ Interactive slideshow created with {num_slides} slides!")
                            
                            # Provide download buttons
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                # Download HTML file
                                with open(html_path, "rb") as f:
                                    st.download_button(
                                        label="📥 Download HTML Slideshow",
                                        data=f.read(),
                                        file_name="slideshow.html",
                                        mime="text/html"
                                    )
                            
                            with col2:
                                # Download complete package
                                if os.path.exists(package_path):
                                    with open(package_path, "rb") as f:
                                        st.download_button(
                                            label="📦 Download Complete Package",
                                            data=f.read(),
                                            file_name="slideshow_package.zip",
                                            mime="application/zip"
                                        )
                            
                            # Show preview
                            st.subheader("🎥 Slideshow Preview")
                            try:
                                with open(html_path, 'r', encoding='utf-8') as f:
                                    html_content = f.read()
                                st.components.v1.html(html_content, height=600, scrolling=True)
                            except:
                                st.info("Slideshow created successfully! Download the HTML file to view it in your browser.")
                        else:
                            st.error("❌ Failed to create slideshow. Please check your files and try again.")
            
            except Exception as e:
                st.error(f"❌ An error occurred: {str(e)}")
                st.error("Please make sure your PDF and audio files are valid.")
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
        Built with Streamlit • Convert PDF slides to interactive slideshow with audio
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
    
