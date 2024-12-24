import subprocess
import time

def main():
    """
    This script spawns an ffmpeg process to capture the window titled:
      'Watermill Coin Feed - Google Chrome'
    at 30 fps, with mouse pointer shown, and streams to:
      rtmp://localhost:1936/live/watermill
    It ensures that the captured dimensions are even numbers to comply with H.264 encoding requirements.
    """
    # Update this to match your EXACT window title (no extra spaces, hyphens, etc.)
    window_title = 'title=Watermill Coin Feed - Google Chrome'

    ffmpeg_command = [
        "ffmpeg",
        "-f", "gdigrab",           # Windows screen capture
        "-framerate", "30",
        "-draw_mouse", "1",
        "-i", window_title,
        # Add a scaling filter that rounds width and height down to the nearest even integer
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-vcodec", "libx264",
        "-preset", "veryfast",
        "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-f", "flv", "rtmp://localhost:1936/live/watermill"
    ]

    print(f"Starting ffmpeg with command: {' '.join(ffmpeg_command)}")
    try:
        proc = subprocess.Popen(ffmpeg_command)

        print("FFmpeg process started. Press Ctrl+C to stop.")
        while True:
            if proc.poll() is not None:
                # ffmpeg ended
                print("FFmpeg process ended.")
                break
            time.sleep(2)

    except KeyboardInterrupt:
        print("\nCtrl+C detected, stopping ffmpeg...")
        if proc:
            proc.terminate()
            proc.wait()  # Wait for the process to terminate
        print("FFmpeg process terminated.")
    except Exception as e:
        print(f"Error running ffmpeg: {e}")
        if proc:
            proc.terminate()
            proc.wait()
        print("FFmpeg process terminated due to an error.")

if __name__ == "__main__":
    main()
