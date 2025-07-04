# 🎬 Smart YouTube Shorts Generator 

This project is a **YouTube Shorts generator** developed using **FastAPI**. It allows users to input a YouTube video URL and generates **vertical short clips** using a combination of **speech recognition**, **scene detection**, and **visual/text cues**.

Whether it's dialogue-based content or dynamic visual scenes — this tool extracts meaningful highlights in **Shorts format (9:16)**.

---

## 🧠 How It Works

- 📥 **Downloads** a YouTube video using `yt-dlp`
- 🗣️ **Transcribes speech** using **Whisper (OpenAI)**
- 👁️ **Detects scenes** visually via `ffmpeg`
- 🧠 Combines audio + visual cues to extract key moments
- 🔄 **Crops** and converts clips into **Shorts-friendly** format (vertical 9:16)
- 📤 Exposes APIs to download or clean up generated content

---

## 📸 Demo Screenshots

### 🏠 Home Screen  
![image](https://github.com/user-attachments/assets/9c800e10-5603-4144-9bd9-3ab4d07390af)

### ⚙️ Shorts Generation in Progress  
![demo2](https://github.com/user-attachments/assets/fa282659-28bc-4c2c-a379-2d67f2a73a03)

### 🎬 Output Screen  
![demo3](https://github.com/user-attachments/assets/03eb65e0-4f8b-4f51-b29d-80231fda0ff2)

---

## 🛠️ Tech Stack

- ⚙️ **FastAPI** for backend API
- 🎞️ **yt-dlp** to download YouTube videos
- 🗣️ **Whisper** for speech-to-text
- 🎬 **FFmpeg** for audio/video processing & scene cuts
- 🧪 **Uvicorn** as the ASGI server

---

## ✨ Features

- Supports both **audio-based** (speech/text) and **visual-based** (scene change) extraction
- Option to select:
  - Number of clips
  - Clip duration
  - Extraction method (`audio`, `visual`, or `hybrid`)
- Generates **vertical format (9:16)** shorts ideal for:
  - YouTube Shorts
  - Instagram Reels
  - TikTok
- Lightweight and API-driven for future frontend integration

---

## 🔧 Installation Instructions

1. Clone the Repository

```bash
git clone https://github.com/shyamatyagi/yt-shorts-generator.git
cd yt-shorts-generator
```

2. Create a Virtual Environment and Install Dependencies 

```bash
#macOS/Linux:
python3 -m venv venv
source venv/bin/activate

# Windows:
python -m venv venv
venv\Scripts\activate

#Then install dependencies:
pip install -r requirements.txt

```
3. Run the FastAPI Server
```bash
uvicorn main:app --reload
```

