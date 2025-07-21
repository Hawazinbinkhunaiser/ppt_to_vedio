import streamlit as st
import tempfile
import os
from pdf2image import convert_from_bytes
from PIL import Image
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

st.set_page_config(page_title="PDF + Audio to Video", layout="centered")
st.title("🎞️ PDF Slides and MP3 to Video Generator")

# Upload inputs
pdf_file = st.file_uploader("Upload your slide deck as a PDF", type=["pdf"])
audio_files = st.file_uploader("Upload MP3 files (Slide_1.mp3, Slide_2.mp3...)", type=["mp3"], accept_multiple_files=True)

if pdf_file and audio_files:
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save audio files and index them by name
        audio_map = {}
        for audio in audio_files:
            path = os.path.join(tmpdir, audio.name)
            with open(path, "wb") as f:
                f.write(audio.getbuffer())
            audio_map[audio.name.lower()] = path

        # Convert PDF pages to images
        st.info("Converting PDF slides to images...")
        slide_images = convert_from_bytes(pdf_file.read(), dpi=200)

        clips = []
        errors = []

        for idx, img in enumerate(slide_images, start=1):
            image_path = os.path.join(tmpdir, f"slide_{idx}.png")
            img.save(image_path, "PNG")

            audio_filename = f"slide_{idx}.mp3"
            audio_path = audio_map.get(audio_filename.lower())

            if audio_path:
                try:
                    audio = AudioFileClip(audio_path)
                    duration = audio.duration

                    clip = (
                        ImageClip(image_path)
                        .set_duration(duration)
                        .set_audio(audio)
                        .resize(height=720)
                    )
                    clips.append(clip)
                except Exception as e:
                    errors.append(f"Slide {idx}: {e}")
            else:
                errors.append(f"Missing audio: {audio_filename}")

        if clips:
            st.info("Rendering final video...")
            final_video = concatenate_videoclips(clips, method="compose")
            video_path = os.path.join(tmpdir, "final_video.mp4")
            final_video.write_videofile(video_path, fps=24, codec="libx264", audio_codec="aac")

            with open(video_path, "rb") as f:
                st.success("✅ Video created successfully!")
                st.download_button("Download Video", f.read(), file_name="slides_audio_video.mp4", mime="video/mp4")
        else:
            st.error("No valid slides or audio found.")

        if errors:
            st.warning("Some issues occurred:")
            for e in errors:
                st.text(f"• {e}")
