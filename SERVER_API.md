# SKY Yoga AI Coach - Server API Documentation

## Overview

`server.py` is a production-ready REST API server that provides the same functionality as `main.py` but through HTTP endpoints. It displays a 50/50 split between the user's live camera feed and the reference exercise video, with real-time AI-powered form analysis and coaching.

## Features

✅ **Live Video Streaming** - MJPEG stream of 50/50 split (user + reference feeds)
✅ **REST API** - Full control via HTTP endpoints
✅ **Pause/Resume Control** - API endpoints to pause and resume exercises
✅ **Real-time Status** - Current exercise state, rep counting, form analysis
✅ **Web Dashboard** - Beautiful HTML dashboard for monitoring and control
✅ **Exercise Tracking** - Automatic exercise detection and coaching
✅ **Rep Counting** - Real-time rep counting with target tracking
✅ **Form Analysis** - AI-powered pose detection and feedback

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure you have:
   - Webcam connected
   - `pose_landmarker_heavy.task` model file in project root
   - Internet connection for reference video streaming

## Running the Server

```bash
python server.py
```

The server will start on `http://localhost:8000`

### Optional Environment Variables

```bash
# Use custom video source (local file or URL)
set SKY_VIDEO=path/to/video.mp4

# Enable video caching for faster startup
set SKY_CACHE_DIR=./cache

# Run with specific host/port (via uvicorn)
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

## Web Dashboard

Access the interactive dashboard at: **http://localhost:8000**

### Dashboard Features

- **Live Video Stream** - Real-time 50/50 split view
- **Exercise Status** - Current state, rep count, form feedback
- **Control Buttons**
  - ⏸ **Pause** - Freezes both video and exercise tracking
  - ▶ **Resume** - Resumes video and exercise
  - ↻ **Reset** - Resets rep counter for current exercise
- **Coach Messages** - Real-time feedback from the AI coach
- **Auto-updating Status** - Refreshes every 500ms

## API Endpoints

### Core Endpoints

#### `GET /`
Returns the HTML dashboard interface.

**Response:** HTML page

---

#### `GET /video/stream`
Streams live video as MJPEG format (compatible with `<img>` tags).

**Response:** MJPEG stream

```html
<img src="http://localhost:8000/video/stream" />
```

---

#### `GET /api/status`
Returns current exercise session state.

**Response:**
```json
{
  "paused": false,
  "active_exercise": "hand",
  "rep_count": 5,
  "target_reps": 10,
  "coach_state": "ACTIVE",
  "watch_msg": "Watch carefully",
  "correct": true,
  "message": "Form is correct!",
  "hold_remaining": 0.0,
  "video_pos": 120.5
}
```

**Fields:**
- `paused` (bool) - Whether exercise is paused
- `active_exercise` (str) - Current exercise key or null
- `rep_count` (int) - Completed repetitions
- `target_reps` (int) - Target repetitions for current phase
- `coach_state` (str) - One of: WATCH, PREPARE, ACTIVE, ZOOM, HOLD
- `watch_msg` (str) - Message for WATCH phase
- `correct` (bool) - Whether current form is correct
- `message` (str) - Real-time coach feedback
- `hold_remaining` (float) - Seconds remaining in HOLD phase
- `video_pos` (float) - Video position in seconds

---

#### `POST /api/pause`
Pauses the exercise and video.

**Response:**
```json
{
  "success": true,
  "message": "Exercise paused",
  "paused": true
}
```

---

#### `POST /api/resume`
Resumes the exercise and video.

**Response:**
```json
{
  "success": true,
  "message": "Exercise resumed",
  "paused": false
}
```

---

#### `POST /api/reset`
Resets the current exercise (clears rep count).

**Response:**
```json
{
  "success": true,
  "message": "Exercise reset",
  "rep_count": 0
}
```

---

#### `GET /api/health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "SKY Yoga AI Coach API",
  "version": "1.0.0"
}
```

---

### FastAPI Documentation

Access interactive API documentation:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Architecture

### Main Components

1. **FastAPI Application** (`app`)
   - REST API server
   - Web dashboard
   - Video streaming endpoints

2. **SessionState Class**
   - Thread-safe state management
   - Shared between main loop and API endpoints
   - Lock-protected for concurrent access

3. **Main Processing Loop** (`main_loop()`)
   - Runs in background thread
   - Processes video frames
   - Performs pose detection
   - Manages exercise coaching
   - Updates SessionState

4. **Video Stream Generator** (`generate_video_stream()`)
   - Yields MJPEG frames
   - Reads from SessionState
   - Encodes frames as JPEG

### Threading Model

```
startup event
    ↓
launch main_loop() in daemon thread
    ↓
main_loop processes frames continuously
    ↓
API endpoints read/modify session state (thread-safe)
    ↓
video stream pulls frames from session state
    ↓
shutdown event → sets _should_stop flag
```

## Exercise Timeline

The server follows the same exercise timeline as `main.py`:

```python
EXERCISE_TIMELINE = [
    {"key": "hand",        "start": 14},      # Hand exercises
    {"key": "leg",         "start": 661},     # Leg exercises
    {"key": "neuro",       "start": 1331},    # Neuro-muscular
    {"key": "eye",         "start": 1835},    # Eye exercises
    {"key": "kapalabhati", "start": 1879},    # Breathing
    {"key": "makarasana",  "start": 2418},    # Shark pose
    {"key": "massage",     "start": 3024},    # Massage
    {"key": "acupressure", "start": 2756},    # Acupressure
    {"key": "relaxation",  "start": 3100},    # Relaxation
]
```

## Coach States

The AI coach uses these states:

| State | Meaning | Color |
|-------|---------|-------|
| **WATCH** | Observing reference video | Yellow |
| **PREPARE** | Getting ready to perform | Cyan |
| **ACTIVE** | Performing exercise, form being evaluated | Green |
| **ZOOM** | Zoomed view instruction | Grey |
| **HOLD** | Hold position, form is being finalized | Orange |

## API Usage Examples

### Python Client Example

```python
import requests
import time

BASE_URL = "http://localhost:8000"

# Get current status
status = requests.get(f"{BASE_URL}/api/status").json()
print(f"Exercise: {status['active_exercise']}")
print(f"Reps: {status['rep_count']} / {status['target_reps']}")

# Pause exercise
requests.post(f"{BASE_URL}/api/pause")

# Wait...
time.sleep(5)

# Resume
requests.post(f"{BASE_URL}/api/resume")

# Reset
requests.post(f"{BASE_URL}/api/reset")
```

### JavaScript Fetch Example

```javascript
// Get status
fetch('http://localhost:8000/api/status')
  .then(r => r.json())
  .then(data => console.log(data));

// Pause
fetch('http://localhost:8000/api/pause', { method: 'POST' });

// Resume
fetch('http://localhost:8000/api/resume', { method: 'POST' });
```

### cURL Example

```bash
# Check health
curl http://localhost:8000/api/health

# Get status
curl http://localhost:8000/api/status

# Pause
curl -X POST http://localhost:8000/api/pause

# Resume
curl -X POST http://localhost:8000/api/resume

# Reset
curl -X POST http://localhost:8000/api/reset
```

## Comparison: main.py vs server.py

| Feature | main.py | server.py |
|---------|---------|-----------|
| Display Mode | OpenCV window | Web browser + MJPEG stream |
| Control Method | Keyboard (SPACE, Q) | HTTP API endpoints |
| Remote Access | ❌ No | ✅ Yes (network accessible) |
| Dashboard | ❌ No | ✅ Yes (HTML UI) |
| Pause Button | ✅ SPACE key | ✅ API endpoint |
| Video Format | Native OpenCV | MJPEG stream |
| Performance | Low latency | Network-dependent latency |
| Portability | Local only | Web accessible |

## Troubleshooting

### "Camera not opened"
- Check that webcam is connected and not in use by another app
- Try: `python -c "import cv2; cap = cv2.VideoCapture(0); print(cap.isOpened())"`

### "Model file not found"
- Ensure `pose_landmarker_heavy.task` exists in project root
- Download from: https://developers.google.com/mediapipe/solutions/vision/pose_landmarker

### "Cannot open video URL"
- Check internet connection
- Verify URL is accessible
- Try setting `SKY_CACHE_DIR` to cache locally

### "Frames not updating"
- Check CPU usage (pose detection is intensive)
- Verify webcam has sufficient light
- Try closing other applications

### CORS Errors in Browser
- Already configured with `CORSMiddleware`
- Should work from any origin
- Check browser console for specific errors

## Performance Optimization

1. **Frame Quality** - Reduce JPEG quality (line ~310):
```python
cv2.imwrite(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])  # Default: 80
```

2. **Processing Speed** - Reduce frame delay:
```python
time.sleep(0.005)  # Process more frames per second
```

3. **Network Bandwidth** - Lower video resolution via camera parameters

## Extending the Server

### Add Custom Endpoints

```python
@app.get("/api/custom")
async def custom_endpoint():
    state = session_state.get_state()
    # Custom logic...
    return JSONResponse(content={"custom": "response"})
```

### Modify Video Stream Processing

Edit `main_loop()` function to add logic before `session_state.set_frame()`.

### Change UI Styling

Edit the HTML in the `dashboard()` function.

## License

Part of SKY Yoga AI Coach project.

## Support

For issues or questions:
1. Check API documentation at http://localhost:8000/docs
2. Review server logs for errors
3. Verify system requirements and environment setup
