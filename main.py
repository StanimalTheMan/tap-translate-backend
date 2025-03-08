import io
import os
from bs4 import BeautifulSoup
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import translate_v2 as translate
import requests
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

# Genius API setup
GENIUS_API_TOKEN = os.getenv("GENIUS_API_TOKEN")

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
))

# Load Google Cloud credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./service-account.json"

# Initalize translation client
translate_client = translate.Client()

def get_lyrics(song_name: str, artist_name: str):
    """Fetch lyrics from Genius API by scraping the lyrics page"""
    headers = {"Authorization": f"Bearer {GENIUS_API_TOKEN}"}
    search_url = "https://api.genius.com/search"

    params = {"q": f"{song_name} {artist_name}"}
    response = requests.get(search_url, headers=headers, params=params)

    if response.status_code != 200:
        return "Error: Failed to search Genius API"
    
    hits = response.json().get("response", {}).get("hits", [])
    if not hits:
        return "Lyrics not found"
    
    # Step 2: Get song URL
    song_url = hits[0]["result"]["url"]

    # Step 3: Scrape lyrics from the song page
    page = requests.get(song_url)
    soup = BeautifulSoup(page.text, "html.parser")

    lyrics_container = soup.find_all("div", {"data-lyrics-container": "true"})
    lyrics = "\n".join([div.get_text("\n") for div in lyrics_container])
    print(lyrics)
    return lyrics


@app.get("/translate")
def translate(text: str, target_lang: str = "en"):
    result = translate_client.translate(text, target_language=target_lang)
    return {"translation": result["translatedText"]}

@app.get("/songs")
def get_songs(query: str):
    """Fetch songs related to the given word"""
    results = sp.search(q=query, limit=1, type="track")

    songs = []
    for track in results["tracks"]["items"]:
        name = track["name"]
        artist = track["artists"][0]["name"]
        url = track["external_urls"]["spotify"]
        lyrics = get_lyrics(name, artist)

        songs.append({"name": name, "artist": artist, "url": url, "lyrics": lyrics})

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
