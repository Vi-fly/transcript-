import streamlit as st
from youtube_utils import extract_video_id, get_video_info, get_youtube_transcript
from transcription import TranscriptionService
from translator import TranslationService
import time

def initialize_services():
    """Initialize services with proper error handling"""
    try:
        translation_service = TranslationService()
        transcription_service = TranscriptionService()
        return transcription_service, translation_service
    except Exception as e:
        st.error(f"Error initializing services: {str(e)}")
        return None, None

def check_url(url):
    """Basic URL validation"""
    return url.startswith(('https://youtube.com/', 'https://www.youtube.com/', 
                          'https://youtu.be/', 'https://www.youtu.be/'))

def main():
    st.set_page_config(
        page_title="YouTube Transcription & Translation",
        page_icon="🎥",
        layout="wide"
    )
    
    st.title("YouTube Video Transcription & Translation")
    
    # Initialize services
    transcription_service, translation_service = initialize_services()
    
    if translation_service is None or transcription_service is None:
        st.error("Failed to initialize required services. Please refresh the page.")
        return
    
    # Sidebar information
    with st.sidebar:
        st.header("About")
        st.write("""
        This app allows you to:
        1. Generate transcripts from YouTube videos
        2. Translate the transcript into multiple languages
        3. Handle videos with or without captions
        """)
        st.divider()
        st.write("Note: The app will first try to use YouTube captions for instant results. If none are available, it will use AI transcription.")
    
    # Main content
    youtube_url = st.text_input(
        "Enter YouTube Video URL:",
        placeholder="https://youtube.com/watch?v=...",
        key="url_input"
    )
    
    if youtube_url:
        if not check_url(youtube_url):
            st.error("Please enter a valid YouTube URL")
            return
            
        try:
            with st.spinner("Fetching video information..."):
                # Get video ID first
                video_id = extract_video_id(youtube_url)
                video_info = get_video_info(youtube_url)
            
            # Display video information
            col1, col2 = st.columns([1, 2])
            with col1:
                if video_info['thumbnail_url']:
                    st.image(video_info['thumbnail_url'], width=None)
            with col2:
                st.subheader(video_info['title'])
                st.write(f"Author: {video_info['author']}")
                duration_min = video_info['length'] // 60
                duration_sec = video_info['length'] % 60
                st.write(f"Duration: {duration_min}m {duration_sec}s")
            
            # Process button
            if st.button("Generate Transcript"):
                transcript = None
                
                # First try YouTube captions
                with st.spinner("Fetching YouTube captions..."):
                    transcript = get_youtube_transcript(video_id)
                
                if transcript:
                    st.success("✅ Successfully retrieved YouTube captions!")
                    st.session_state['transcript'] = transcript
                else:
                    # If no captions available, use Whisper
                    st.warning("⚠️ No YouTube captions available. Using AI transcription (this may take several minutes)...")
                    
                    try:
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # Update status for download
                        status_text.write("⬇️ Downloading video audio...")
                        progress_bar.progress(25)
                        
                        # Process with Whisper
                        transcript = transcription_service.process_video(youtube_url)
                        
                        if transcript and transcript.strip():
                            progress_bar.progress(100)
                            st.success("✅ Successfully generated transcript using AI!")
                            st.session_state['transcript'] = transcript
                        else:
                            st.error("❌ Failed to generate transcript: No text was produced")
                            return
                            
                        # Clean up progress indicators
                        progress_bar.empty()
                        status_text.empty()
                        
                    except Exception as e:
                        st.error(f"❌ Error during AI transcription: {str(e)}")
                        return
                        
            # Translation options
            if 'transcript' in st.session_state and st.session_state['transcript']:
                st.subheader("Original Transcript")
                with st.expander("Show/Hide Transcript", expanded=True):
                    st.write(st.session_state['transcript'])
                
                # Language selection
                supported_languages = translation_service.get_supported_languages()
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    target_lang = st.selectbox(
                        "Select language for translation:",
                        options=list(supported_languages.keys()),
                        format_func=lambda x: supported_languages[x]
                    )
                
                with col2:
                    st.write("")  # For alignment
                    st.write("")  # For alignment
                    if st.button("Translate"):
                        # Validate transcript before translation
                        if not st.session_state['transcript'] or not st.session_state['transcript'].strip():
                            st.error("No valid transcript to translate")
                            return
                            
                        with st.spinner("Translating..."):
                            try:
                                translated_text = translation_service.translate_text(
                                    st.session_state['transcript'],
                                    target_lang
                                )
                                
                                if translated_text and translated_text.strip():
                                    st.subheader(f"Translated Text ({supported_languages[target_lang]})")
                                    with st.expander("Show/Hide Translation", expanded=True):
                                        st.write(translated_text)
                                else:
                                    st.error("Translation produced no result")
                            except Exception as e:
                                st.error(f"Translation error: {str(e)}")
                
        except Exception as e:
            st.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main()