from dotenv import load_dotenv
import os
import sys
import webbrowser
import logging
import datetime
import subprocess
import random
import requests
import json
import psutil
import wikipedia
from urllib.parse import urlencode
from bs4 import BeautifulSoup
import time
import re
import threading
import schedule




try:
    import speech_recognition as sr
    import pyttsx3
except ImportError as e:
    print(f"Missing dependency: {e}. Please install required packages.")
    sys.exit(1)



# === Configuration ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
engine = pyttsx3.init()
voices = engine.getProperty('voices')

# Use Microsoft David (male voice) if available
for voice in voices:
    if "David" in voice.name or "Mark" in voice.name:
        engine.setProperty('voice', voice.id)
        break

engine.setProperty('rate', 180)   # Speed (adjust as needed)
engine.setProperty('volume', 1.0) # Max volume

silent_mode = False
voice_only_mode = False
stay_awake = False
awake_until = None
notifications_enabled = False
last_weather = None
last_weather_time = 0
current_tts_lang = "en"  # Default: English

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("OPENROUTER_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")


BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "tngtech/deepseek-r1t2-chimera:free"
NAME_FILE = "skai_user.txt"

# === Notification Functions ===
def proactive_weather_update():
    if notifications_enabled:
        report = get_weather()
        speak(f"Good morning! Here’s your daily weather update: {report}")

def proactive_battery_alert():
    if notifications_enabled:
        battery = psutil.sensors_battery()
        if battery and battery.percent < 20 and not battery.power_plugged:
            speak(f"Alert! Your battery is at {battery.percent} percent. Please plug in your charger.")

def proactive_news_update():
    if notifications_enabled:
        india_headlines, _ = get_india_news()
        global_headlines, _ = get_global_news()

        if india_headlines:
            speak("Here are the top 3 news updates from India:")
            for h in india_headlines[:3]:
                speak(h)

        if global_headlines:
            speak("And here are the top 3 global headlines:")
            for h in global_headlines[:3]:
                speak(h)

# === Background Scheduler ===
def start_notifications():
    schedule.every().day.at("08:00").do(proactive_weather_update)
    schedule.every(5).minutes.do(proactive_battery_alert)
    schedule.every(3).hours.do(proactive_news_update)

    def run_schedule():
        while True:
            schedule.run_pending()
            time.sleep(30)

    threading.Thread(target=run_schedule, daemon=True).start()

# === Notification Toggle ===
def handle_notification_toggle(command):
    global notifications_enabled
    if "enable notifications" in command:
        notifications_enabled = True
        speak("Proactive notifications enabled.")
        return True
    elif "disable notifications" in command:
        notifications_enabled = False
        speak("Proactive notifications disabled.")
        return True
    return False

# === Voice Functions ===
def speak(text):
    """Speak with a deep, professional male voice."""
    if not silent_mode:
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"Voice error: {e}")
    if not voice_only_mode:
        print(f"SKAI 🗣️: {text}")



def listen():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("\n🎤 Listening...")
        # Faster detection (stop after 5 seconds max per phrase)
        audio = r.listen(source, phrase_time_limit=5)
        try:
            query = r.recognize_google(audio)
            if not voice_only_mode:
                print(f"You 🗣️: {query}")
            return query.lower()
        except:
            return ""


# === AI Query ===
def ask_deepseek(prompt):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are SKAI, a professional AI assistant. Always respond in a formal, polite, and concise manner, avoiding casual or conversational phrases."},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        response = requests.post(BASE_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except:
        return "Apologies, I encountered an issue while processing your request."


# === Helpers ===
def open_url(url, app_name=None):
    if app_name and sys.platform == "win32":
        try:
            subprocess.Popen(["start", app_name], shell=True)
            return
        except:
            pass
    webbrowser.open(url)

def get_system_stats():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    battery = psutil.sensors_battery()

    if battery:
        battery_status = f"{battery.percent}%"
        if battery.power_plugged:
            battery_status += ", charging"
    else:
        battery_status = "Battery status unavailable"

    return (
        f"Your CPU is currently at {cpu} percent, "
        f"RAM usage is {ram} percent, "
        f"and the disk is {disk} percent full. "
        f"The battery is at {battery_status}."
    )

def get_india_news():
    try:
        url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.content, "xml")
        items = soup.find_all("item")[:5]
        headlines = []
        links = []
        for i, item in enumerate(items):
            title = item.title.text if item.title else "No title"
            link = item.link.text if item.link else ""
            headlines.append(f"{i+1}. {title}")
            links.append(link)
        return headlines, links
    except Exception as e:
        print(f"DEBUG: India News Error: {e}")
        return [], []

def get_global_news():
    url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={NEWS_API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        if data.get("status") != "ok":
            return [], []
        articles = data.get("articles", [])[:5]
        headlines = [f"{i+1}. {a['title']}" for i, a in enumerate(articles)]
        links = [a['url'] for a in articles]
        return headlines, links
    except:
        return [], []

def play_youtube_video(query):
    search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    try:
        response = requests.get(search_url).text
        video_ids = re.findall(r"watch\?v=(\S{11})", response)
        if video_ids:
            video_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
            webbrowser.open(video_url)
            return video_url
        return None
    except Exception:
        return None

def get_weather():
    global last_weather, last_weather_time
    # Use cached weather if checked within last 10 minutes
    if time.time() - last_weather_time < 600 and last_weather:
        return last_weather
    try:
        ip_info = requests.get("http://ip-api.com/json/").json()
        city = ip_info.get("city", "your location")
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
        data = requests.get(url).json()
        if data.get("cod") != 200:
            return "I couldn't fetch the weather for your location right now."
        temp = data["main"]["temp"]
        desc = data["weather"][0]["description"]
        last_weather = f"Based on your location, the weather in {city} is {temp}°C with {desc}."
        last_weather_time = time.time()
        return last_weather
    except:
        return "I couldn't check the weather right now."

# === Wake Word ===
def wait_for_wake_word():
    global awake_until, stay_awake
    while True:
        heard = listen()
        if "hey sky" in heard or "ok sky" in heard or "power up sky" in heard or "wake up sky" in heard or "sky online" in heard:
            awake_until = time.time() + 600
            stay_awake = False
            speak("I'm awake and listening for the next 10 minutes.")
            return
        elif "sky awake" in heard or "sky stay" in heard:
            stay_awake = True
            awake_until = None
            speak("Staying awake until you tell me to sleep.")
            return

# === Greeting ===
def greet_user():
    if os.path.exists(NAME_FILE):
        with open(NAME_FILE, "r") as f:
            name = f.read().strip()
    else:
        speak("Hello! I don’t know your name yet. What should I call you?")
        name = listen().title()
        with open(NAME_FILE, "w") as f:
            f.write(name)
    hour = datetime.datetime.now().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    speak(f"{greeting}, {name}! How can I help you today?")




# === Web Integrations ===

def google_search(query):
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    webbrowser.open(url)
    return f"I have searched Google for {query}. The results are now open in your browser."

def wikipedia_summary(topic):
    try:
        summary = wikipedia.summary(topic, sentences=3)
        return f"According to Wikipedia, {summary}"
    except:
        return f"Sorry, I could not find any information about {topic} on Wikipedia."

def get_live_cricket_scores():
    try:
        url = "https://www.cricbuzz.com/cricket-match/live-scores"
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, "html.parser")
        match = soup.find("div", class_="cb-mtch-lst")
        if match:
            return f"Live Cricket Update: {match.get_text(strip=True)}"
        return "No live matches found at the moment."
    except:
        return "I could not fetch live cricket scores right now."

def get_trending_movies():
    try:
        url = "https://www.imdb.com/chart/moviemeter/"
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, "html.parser")
        movies = [m.get_text(strip=True) for m in soup.select(".ipc-title-link-wrapper")[:5]]
        return "Here are the current top trending movies: " + ", ".join(movies)
    except:
        return "I could not fetch trending movies right now."

def get_trending_songs():
    try:
        url = "https://www.billboard.com/charts/hot-100/"
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, "html.parser")
        songs = [s.get_text(strip=True) for s in soup.select("li ul li h3")[:5]]
        return "Here are the current top trending songs: " + ", ".join(songs)
    except:
        return "I could not fetch trending songs right now."


# === Command Handler ===
def handle_command(command):
    global silent_mode, voice_only_mode
    global stay_awake, awake_until

    if handle_notification_toggle(command):
        return
    
    if "time" in command:
        now = datetime.datetime.now().strftime("%I:%M %p")
        speak(f"The time is {now}.")
        return
    elif "date" in command or "today" in command:
        today = datetime.datetime.now().strftime("%A, %B %d, %Y")
        speak(f"Today is {today}.")
        return
    elif "weather" in command:
        weather_report = get_weather()
        speak(weather_report)
        return
    elif "system status" in command or "cpu" in command or "ram" in command:
        stats = get_system_stats()
        speak(f"Here’s the current system status: {stats}")
        return

    elif "india news" in command:
        headlines, links = get_india_news()
        if not headlines:
            speak("I couldn't fetch the India news right now.")
            return
        speak("Here are the top news headlines from India:")
        for h in headlines:
            speak(h)
        speak("Would you like me to open the first article?")
        if "yes" in listen() or "open" in listen():
            webbrowser.open(links[0])
        return

    elif "global news" in command or "world news" in command:
        headlines, links = get_global_news()
        if not headlines:
            speak("I couldn't fetch the global news right now.")
            return
        speak("Here are the top global headlines:")
        for h in headlines:
            speak(h)
        speak("Would you like me to open the first article?")
        if "yes" in listen() or "open" in listen():
            webbrowser.open(links[0])
        return
    
        # === Web Search and Wikipedia ===
    elif command.startswith("search for "):
        topic = command.replace("search for", "").strip()
        result = google_search(topic)
        speak(result)
        return

    elif command.startswith("wikipedia "):
        topic = command.replace("wikipedia", "").strip()
        summary = wikipedia_summary(topic)
        speak(summary)
        return

    # === Cricket Scores ===
    elif "cricket scores" in command:
        scores = get_live_cricket_scores()
        speak(scores)
        return

    # === Trending Movies & Songs ===
    elif "trending movies" in command:
        movies = get_trending_movies()
        speak(movies)
        return

    elif "trending songs" in command:
        songs = get_trending_songs()
        speak(songs)
        return


    if "play" in command and "youtube" in command:
        video_name = command.replace("play", "").replace("on youtube", "").strip()
        speak(f"Searching YouTube for {video_name}")
        video_url = play_youtube_video(video_name)
        if video_url:
            speak("Playing the top result on YouTube.")
        else:
            speak("I couldn't find any video.")
        return

    if "stay awake" in command or "active mode" in command:
        stay_awake = True
        awake_until = None
        speak("I’ll stay awake and keep listening for your commands until you tell me to sleep.")
        return

    elif "go to sleep" in command or "standby mode" in command:
        stay_awake = False
        awake_until = None
        speak("Going into standby mode. Say 'Hey SKAI' to wake me up again.")
        return

    elif "bye sky" in command or "goodbye" in command:
        speak("Goodbye! Shutting down.")
        sys.exit(0)

    if "music player" in command:
        speak("Opening music player.")
        if sys.platform == "win32":
            os.system("start wmplayer")
    elif "spotify" in command:
        speak("Opening Spotify.")
        open_url("https://open.spotify.com", app_name="spotify" if sys.platform == "win32" else None)
    elif "google" in command:
        speak("Opening Google.")
        open_url("https://www.google.com")
    elif "notepad" in command:
        speak("Opening Notepad.")
        if sys.platform == "win32":
            os.system("start notepad")
    elif "calculator" in command:
        speak("Opening Calculator.")
        if sys.platform == "win32":
            os.system("start calc")
    elif "shutdown" in command:
        speak("Are you sure you want to shut down? Say yes or no.")
        if "yes" in listen():
            os.system("shutdown /s /t 1")
    elif "restart" in command:
        speak("Restart the system? Say yes or no.")
        if "yes" in listen():
            os.system("shutdown /r /t 1")
    elif "lock" in command:
        speak("Locking system.")
        if sys.platform == "win32":
            os.system("rundll32.exe user32.dll,LockWorkStation")
    elif "silent mode" in command:
        silent_mode = True
        speak("Silent mode activated.")
    elif "voice mode" in command:
        silent_mode = False
        speak("Voice mode activated.")
    elif "voice only mode" in command:
        voice_only_mode = True
        speak("Voice-only mode activated.")
    elif "normal mode" in command:
        voice_only_mode = False
        speak("Normal mode restored.")

    elif "tell me a joke" in command:
        speak("Let me find something funny...")
        joke = ask_deepseek("Tell me a short, funny joke (1-6 lines).")
        speak(joke)
        
    # === AI Query ===
    else:
        ai_reply = ask_deepseek(command)
        speak(ai_reply)


    # === Main Loop ===
def main():
    greet_user()
    threading.Thread(target=start_notifications, daemon=True).start()
    while True:
        wait_for_wake_word()
        while True:
            if not stay_awake and awake_until and time.time() > awake_until:
                speak("10 minutes have passed. Going back to sleep.")
                break
            if stay_awake:
                speak("I'm in active mode and listening. What can I do for you?")
            query = listen()
            if query:
                handle_command(query)
            if not stay_awake and not awake_until:
                break

if __name__ == "__main__":
    main()
