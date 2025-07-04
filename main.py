from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import subprocess
import yt_dlp
import os
import random
import json
import shutil
import time

# Create necessary directories
os.makedirs("temp", exist_ok=True)
os.makedirs("shorts", exist_ok=True)
os.makedirs("static", exist_ok=True)

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Mount static files directory to serve the frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

# Root endpoint to serve the frontend
@app.get("/")
def read_root():
    return FileResponse("static/index.html")

class VideoRequest(BaseModel):
    video_url: str
    quality: str = "720p"
    num_clips: int = 3
    clip_duration: int = 30
    extraction_method: str = "smart"  # 'smart', 'speech', 'scene', 'random'
    advanced_options: Optional[dict] = None

class ShortsResponse(BaseModel):
    message: str
    files: List[str]
    details: Optional[dict] = None

def download_video(video_url: str, quality: str) -> dict:
    """Download a YouTube video with the specified quality"""
    # Generate a unique filename based on timestamp
    filename = f"temp/video_{int(time.time())}"
    
    # Extract numeric part from quality string (e.g., "720p" -> 720)
    quality_value = int(quality.rstrip("p"))
    
    ydl_opts = {
        'format': f'bestvideo[height<={quality_value}]+bestaudio/best',
        'outtmpl': f'{filename}.%(ext)s',
        'quiet': False,  # Show download progress
        'no_warnings': False
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filepath = ydl.prepare_filename(info)
            
            # Return both the filepath and video info for additional details
            return {
                "filepath": filepath,
                "info": {
                    "title": info.get('title'),
                    "duration": info.get('duration'),
                    "uploader": info.get('uploader')
                }
            }
    except Exception as e:
        print(f"Error downloading video: {str(e)}")
        raise Exception(f"Failed to download video: {str(e)}")

def extract_shorts(input_video: str, num_clips: int = 3, clip_duration: int = 30, 
                  method: str = "smart", speech_confidence: float = 0.6, 
                  scene_threshold: float = 0.3) -> tuple:
    """Extract multiple short clips from an input video based on content relevance"""
    output_files = []
    stats = {
        "speech_segments": 0,
        "scene_changes": 0,
        "speech_used": 0,
        "scene_used": 0,
        "random_used": 0
    }
    
    # Get video duration using ffprobe
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration", 
            "-of", "json", input_video
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        video_info = json.loads(result.stdout)
        total_duration = float(video_info['format']['duration'])
    except Exception as e:
        print(f"Error getting video duration: {str(e)}")
        total_duration = 600  # Default to 10 minutes if duration detection fails
    
    speech_segments = []
    scene_list = []
    
    # Step 1: Extract audio for speech recognition if using speech or smart methods
    if method in ["smart", "speech"]:
        audio_file = f"temp/audio_{os.path.basename(input_video)}.wav"
        try:
            extract_audio_cmd = [
                "ffmpeg", "-i", input_video, 
                "-q:a", "0", "-map", "a", audio_file, "-y"
            ]
            subprocess.run(extract_audio_cmd, check=True, capture_output=True)
            
            # Step 2: Speech recognition if audio extraction succeeded
            if os.path.exists(audio_file):
                try:
                    # Note: This requires whisper to be installed
                    # pip install openai-whisper
                    import whisper
                    
                    # Load a small model for efficiency
                    model = whisper.load_model("tiny")
                    result = model.transcribe(audio_file, word_timestamps=True)
                    
                    # Find segments with high confidence speech
                    for segment in result["segments"]:
                        if segment["confidence"] > speech_confidence:
                            # Make sure the segment is not too close to the beginning or end
                            start_time = max(5, segment["start"])
                            if start_time < total_duration - clip_duration - 5:
                                speech_segments.append({
                                    "start": start_time,
                                    "text": segment["text"],
                                    "confidence": segment["confidence"]
                                })
                    
                    stats["speech_segments"] = len(speech_segments)
                    
                    # Clean up
                    os.remove(audio_file)
                except Exception as e:
                    print(f"Error during speech recognition: {str(e)}")
        except subprocess.CalledProcessError as e:
            print(f"Error extracting audio: {str(e)}")
    
    # Step 3: Scene detection if using scene or smart methods
    if method in ["smart", "scene"]:
        try:
            # Create a temporary file to store scene changes
            scene_file = f"temp/scenes_{os.path.basename(input_video)}.csv"
            
            scene_cmd = [
                "ffmpeg", "-i", input_video,
                "-filter:v", f"select='gt(scene,{scene_threshold})',showinfo",
                "-f", "null", "-"
            ]
            
            # Run the scene detection and capture the output
            scene_result = subprocess.run(scene_cmd, capture_output=True, text=True)
            
            # Parse scene changes from ffmpeg output
            for line in scene_result.stderr.split('\n'):
                if "pts_time:" in line:
                    try:
                        time_str = line.split("pts_time:")[1].split()[0]
                        scene_time = float(time_str)
                        if scene_time > 5 and scene_time < total_duration - clip_duration:
                            scene_list.append(scene_time)
                    except Exception:
                        continue
                        
            stats["scene_changes"] = len(scene_list)
        except Exception as e:
            print(f"Error during scene detection: {str(e)}")
    
    # Step 4: Choose the best segments based on combined scene and speech data
    segments_to_use = []
    
    # If using speech or smart methods and speech data is available
    if method in ["smart", "speech"] and speech_segments:
        # Sort by confidence
        speech_segments.sort(key=lambda x: x["confidence"], reverse=True)
        
        # Take top segments up to the number of clips
        top_speech = speech_segments[:min(len(speech_segments), num_clips)]
        segments_to_use.extend([s["start"] for s in top_speech])
        stats["speech_used"] = len(segments_to_use)
    
    # If using scene or smart methods and scene data is available, and we need more segments
    if method in ["smart", "scene"] and scene_list and len(segments_to_use) < num_clips:
        remaining_slots = num_clips - len(segments_to_use)
        
        # Use scene changes that aren't too close to existing segments
        for scene_time in scene_list:
            # Check if this scene is not too close to any existing segment
            if all(abs(scene_time - s) > clip_duration for s in segments_to_use):
                segments_to_use.append(scene_time)
                stats["scene_used"] += 1
                
                if len(segments_to_use) >= num_clips:
                    break
    
    # If we still don't have enough segments, add random timestamps as a fallback
    if len(segments_to_use) < num_clips:
        remaining_slots = num_clips - len(segments_to_use)
        potential_start_times = []
        
        # Generate potential timestamps (excluding the beginning and end)
        safe_duration = total_duration - clip_duration - 10
        if safe_duration > 10:
            for _ in range(remaining_slots * 3):  # Generate 3x more options than needed
                random_time = random.uniform(5, safe_duration)
                # Ensure it's not too close to existing segments
                if all(abs(random_time - s) > clip_duration for s in segments_to_use):
                    potential_start_times.append(random_time)
        
        # Add random segments if available
        if potential_start_times:
            random_segments = random.sample(
                potential_start_times, 
                min(remaining_slots, len(potential_start_times))
            )
            segments_to_use.extend(random_segments)
            stats["random_used"] = len(random_segments)
    
    # Sort segments chronologically
    segments_to_use.sort()
    
    # Step 5: Generate short clips from the selected segments
    for i, start_time in enumerate(segments_to_use):
        output_file = f"shorts/short_{int(time.time())}_{i+1}.mp4"
        
        try:
            # Generate vertical shorts with 9:16 aspect ratio and proper formatting
            # This will extract a clip and then convert it to vertical format
            crop_cmd = [
                "ffmpeg", "-ss", str(start_time), "-t", str(clip_duration),
                "-i", input_video,
                "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-c:v", "libx264", "-c:a", "aac", "-b:a", "128k",
                output_file, "-y"
            ]
            
            subprocess.run(crop_cmd, check=True, capture_output=True)
            if os.path.exists(output_file):
                output_files.append(output_file)
        except Exception as e:
            print(f"Error generating short {i+1}: {str(e)}")
    
    return output_files, stats

@app.post("/process-video", response_model=ShortsResponse)
async def process_video(request: VideoRequest):
    try:
        # Extract options from request
        advanced_options = request.advanced_options or {}
        speech_confidence = advanced_options.get("speech_confidence", 0.6)
        scene_threshold = advanced_options.get("scene_threshold", 0.3)
        
        # Step 1: Download the video
        download_result = download_video(request.video_url, request.quality)
        video_path = download_result["filepath"]
        video_info = download_result["info"]
        
        # Step 2: Extract shorts based on the specified method
        shorts_files, extraction_stats = extract_shorts(
            video_path,
            num_clips=request.num_clips,
            clip_duration=request.clip_duration,
            method=request.extraction_method,
            speech_confidence=speech_confidence,
            scene_threshold=scene_threshold
        )
        
        # Step 3: Prepare response with details
        response_details = {
            "video_info": video_info,
            "extraction_method": request.extraction_method,
            "extraction_stats": extraction_stats
        }
        
        response_message = f"Successfully created {len(shorts_files)} shorts from your video"
        
        # Clean up temporary files
        if os.path.exists(video_path):
            os.remove(video_path)
        
        return ShortsResponse(
            message=response_message,
            files=shorts_files,
            details=response_details
        )
    except Exception as e:
        # Log the error
        error_msg = str(e)
        print(f"Error processing video: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/download")
async def download_file(file: str = Query(...)):
    # Security check to prevent directory traversal
    if ".." in file or file.startswith("/"):
        raise HTTPException(status_code=403, detail="Access forbidden")
    
    if not os.path.exists(file):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(path=file, filename=os.path.basename(file))

@app.get("/cleanup", response_model=dict)
async def cleanup_files():
    """Cleanup temporary and shorts files older than 24 hours"""
    try:
        # Get current time
        current_time = time.time()
        cleanup_count = 0
        
        # Clean temp directory
        for file in os.listdir("temp"):
            file_path = os.path.join("temp", file)
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > 86400:  # 24 hours in seconds
                    os.remove(file_path)
                    cleanup_count += 1
        
        # Clean shorts directory
        for file in os.listdir("shorts"):
            file_path = os.path.join("shorts", file)
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > 86400:  # 24 hours in seconds
                    os.remove(file_path)
                    cleanup_count += 1
        
        return {"message": f"Cleanup completed. Removed {cleanup_count} old files."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # Automatically copy index.html to static directory if it doesn't exist
    if not os.path.exists("static/index.html"):
        if os.path.exists("index.html"):
            shutil.copy("index.html", "static/index.html")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)