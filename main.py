import io
import os
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from gtts import gTTS
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# CORS setup to allow Next.js to access the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get Spotify API credentials from environment variables
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
))

@app.get("/translate")
def translate_word():
    """Mock translation (Replace with real API later)"""
    translations = {"사랑": "Love", "음악": "Music", "행복": "Happiness"}
    return {"translation": translations.get("사랑", "Unknown")}

@app.get("/songs")
def get_songs():
    """Fetch songs related to the given word"""
    results = sp.search(q="gaho", limit=5, type="track")
    print(results)
    songs = [
        {"name": track["name"], "artist": track["artists"][0]["name"], "url": track["external_urls"]["spotify"]}
        for track in results["tracks"]["items"]
    ]
    return {"songs": songs}

@app.get("/tts")
def text_to_speech():
    """Generate speech and return it as an audio stream"""
    tts = gTTS(text="사랑", lang="ko")
    
    # Save audio to a BytesIO buffer instead of a file
    audio_buffer = io.BytesIO()
    tts.write_to_fp(audio_buffer)
    audio_buffer.seek(0)

    return Response(content=audio_buffer.read(), media_type="audio/mpeg")
