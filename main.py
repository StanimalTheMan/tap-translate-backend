import io
import json
from openai import OpenAI
import os
from bs4 import BeautifulSoup
from fastapi import Body, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import translate_v2 as translate
import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from gtts import gTTS
from dotenv import load_dotenv
from korean_romanizer.romanizer import Romanizer

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

# explain word using OPEN AI
open_ai_client = OpenAI(api_key=os.getenv("OPEN_AI_API_KEY"))

def truncate_at_sentence_end(text):
    last_period = text.rfind(".")
    if last_period != -1:
        return text[:last_period + 1]
    return text

def explain_word(word, context):
    response = open_ai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that explains words in the context of song lyrics."},
            {"role": "user", "content": f"Explain the word  '{word}' in the context of this song lyric: '{context}'.  Provide a definition, translation (if applicable), and cultural context."},
        ],
        max_tokens=200,
    )
    return truncate_at_sentence_end(response.choices[0].message.content)

@app.post("/analyze_song_comprehensive")
async def analyze_song_comprehensive(
    song_title: str = Body(...),
    artist: str = Body(...),
    lyrics: str = Body(...)
):
    """
    Returns: {
        "cultural_analysis": {roots, metaphors, impact},
        "slang_terms": [{
            "term": str,
            "meaning": str,
            "origin": str,
            "example": str
        }]
    }
    """
    prompt = f"""
    Analyze the song '{song_title}' by {artist} with these lyrics:
    ---
    {lyrics}
    ---

    Perform TWO TASKS:

    A) CULTURAL ANALYSIS (JSON):
    1. roots: Region/era/genre influences (15 words max)
    2. metaphors: Key symbolic language (20 words max)
    3. impact: Cultural significance (15 words max)

    B) SLANG DETECTION (JSON list):
    - Identify 3-5 most important slang/idiomatic phrases
    - For each provide:
        1. term: The slang phrase
        2. meaning: Literal vs. contextual meaning
        3. origin: Cultural/linguistic roots
        4. example: Usage example from lyrics

    Return valid JSON ONLY with this structure:
    {{
        "cultural_analysis": {{"roots": "", "metaphors": "", "impact": ""}},
        "slang_terms": [{{"term": "", "meaning": "", "origin": "", "example": ""}}]
    }}
    """

    response = open_ai_client.chat.completions.create(
        model="gpt-4-turbo-preview",  # Better JSON handling
        messages=[
            {"role": "system", "content": "You are a music linguist specializing in cultural analysis."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5,
        max_tokens=400,
        response_format={"type": "json_object"}
    )

    try:
        return json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        return {"error": "Analysis failed - invalid response format"}

@app.post("/explain_word")
def explain_word_endpoint(word: str = Body(...), context: str = Body(...)):
    explanation = explain_word(word, context)
    return {"explanation": explanation}


@app.post("/translate")
def translate(
    text: str = Body(..., embed=True),  # Extract 'text' from the request body
    target_lang: str = Body("en")       # Extract 'target_lang' from the request body (default: "en")
):
    result = translate_client.translate(text, target_language=target_lang)
    return {"translation": result["translatedText"]}

@app.post("/romanize")
def romanize(
    text: str = Body(..., embed=True),  # Extract 'text' from the request body
     # Extract 'target_lang' from the request body (default: "en")
):
    romanizer = Romanizer(text)
    return {"romanization": romanizer.romanize()}

@app.get("/songs")
def get_songs(query: str, artist: str):
    """Fetch songs by exact title and artist"""
    # Use 'track:' and 'artist:' filters to search for an exact song title and artist
    results = sp.search(q=f'track:"{query}" artist:"{artist}"', limit=1, type="track")

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
