import subprocess
import sys
import typer
from typing import Optional
import concurrent.futures
import uuid
import os
app = typer.Typer()

def test_stream(url):
    try:
        # Use ffprobe to check if the stream is valid
        command = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "stream=codec_type",
            "-of", "default=noprint_wrappers=1:nokey=1",
            "-i", url
        ]
        
        # Run with a timeout of 10 seconds
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout.strip():
            return True, result.stdout.strip()
        else:
            return False, result.stderr
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)

import os
try:
    from PIL import Image, ImageFilter, ImageStat
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

def has_text_in_center(image_path):
    """
    Detect if there's text-like content in the center of the image.
    Text typically has high contrast edges. Error screens usually show text in the center.
    Returns True if text is detected (bad stream), False otherwise (good stream).
    
    Note: We exclude the bottom 25% to avoid false positives from subtitles.
    """
    try:
        img = Image.open(image_path).convert('L')  # Convert to grayscale
        width, height = img.size
        
        # Crop to center region, excluding bottom 25% (where subtitles appear)
        # This focuses on the middle 50% width and middle 50% height (but not the bottom)
        left = width // 4
        top = height // 4
        right = 3 * width // 4
        bottom = int(height * 0.65)  # Stop at 65% height to exclude subtitle area
        center = img.crop((left, top, right, bottom))
        
        # Apply edge detection
        edges = center.filter(ImageFilter.FIND_EDGES)
        
        # Calculate statistics
        stat = ImageStat.Stat(edges)
        mean_edge = stat.mean[0]
        
        # If there's a lot of edge content in the center, it's likely text
        # Text on error screens typically has mean edge value > 12
        # Video content typically has lower edge density in center (< 10)
        text_detected = mean_edge > 10
        
        img.close()
        return text_detected, mean_edge
        
    except Exception as e:
        return False, 0

def capture_frame(url, timestamp, output_file, timeout=30):
    if os.path.exists(output_file):
        try:
            os.remove(output_file)
        except:
            pass
            
    command = [
        "ffmpeg",
        "-y",
        "-ss", str(timestamp),
        "-i", url,
        "-vframes", "1",
        "-q:v", "2",
        output_file
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            return True, "Success"
        else:
            # Check if it's an audio-only stream
            stderr = result.stderr.lower()
            if "does not contain any stream" in stderr or "unspecified size" in stderr:
                return False, "Audio-only stream (no video)"
            elif "invalid argument" in stderr:
                return False, "No valid video stream"
            else:
                return False, "Frame capture failed"
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, f"Error: {str(e)}"

def verify_stream_with_frame_capture(url, keep_frame=False, timeout=30, output_dir="."):
    """
    Verify stream by capturing a frame at 20s and checking for text in the center.
    Text in the center usually indicates an error screen (bad stream).
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # Create safe filename
    safe_name = "".join([c if c.isalnum() else "_" for c in url.split("://")[-1]])[:50]
    if keep_frame:
        output_file = os.path.join(output_dir, f"capture_{safe_name}.jpg")
    else:
        output_file = os.path.join(output_dir, f"temp_capture_{uuid.uuid4().hex}.jpg")
    
    # Capture frame at 20s
    success, error_msg = capture_frame(url, 20, output_file, timeout)
    if not success:
        return False, f"Could not capture frame: {error_msg}"

    # Check for text if Pillow is available
    if PILLOW_AVAILABLE:
        try:
            has_text, edge_score = has_text_in_center(output_file)
            
            if not keep_frame and os.path.exists(output_file):
                os.remove(output_file)
            
            if has_text:
                return False, f"Text detected in center (likely error screen, edge score: {edge_score:.1f})"
            else:
                return True, f"No text detected (video content, edge score: {edge_score:.1f})"
                
        except Exception as e:
            if not keep_frame and os.path.exists(output_file):
                os.remove(output_file)
            return True, f"Frame captured but text detection failed: {e}"
    else:
        if not keep_frame and os.path.exists(output_file):
            os.remove(output_file)
        return True, "Frame captured (Pillow not installed, skipping text detection)"

def check_single_url(item, thorough, keep_frames, output_dir):
    name = item["name"]
    stream_url = item["url"]
    original_lines = item["original_lines"]
    
    log_messages = []
    
    is_working, details = test_stream(stream_url)
    result_lines = []
    
    if is_working:
        if thorough:
            log_messages.append(f"  ✅ Basic check passed. Verifying frame capture (20s vs 30s)...")
            is_verified, verify_details = verify_stream_with_frame_capture(stream_url, keep_frame=keep_frames, output_dir=output_dir)
            if is_verified:
                log_messages.append(f"  ✅ Verified! {verify_details}")
                result_lines = original_lines
            else:
                log_messages.append(f"  ❌ Verification Failed: {verify_details}")
        else:
            log_messages.append(f"  ✅ Working! Streams: {details.replace(chr(10), ', ')}")
            result_lines = original_lines
    else:
        log_messages.append(f"  ❌ Failed. Reason: {details}")
        
    return item, result_lines, "\n".join(log_messages)

@app.command()
def main(
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Path to a file containing URLs to test."),
    url: Optional[str] = typer.Option(None, "--url", "-u", help="A single URL to test."),
    thorough: bool = typer.Option(False, "--thorough", "-t", help="Perform 2nd level validation by capturing video frames (slower)."),
    keep_frames: bool = typer.Option(False, "--keep-frames", "-k", help="Keep the captured video frames (only works with --thorough)."),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of parallel workers. Default is 1."),
    output_dir: str = typer.Option("captured_images", "--output-dir", "-o", help="Directory to save captured images. Defaults to 'captured_images'.")
):
    """
    Test IPTV URLs for validity using ffprobe.
    If --file is provided, the file will be overwritten with only the working links.
    """
    if not PILLOW_AVAILABLE and thorough:
        print("Warning: Pillow not installed. Frozen stream detection will be disabled.")

    if not file and not url:
        print("Error: Please provide either --file or --url.")
        raise typer.Exit(code=1)

    urls_to_test = []
    
    if url:
        urls_to_test.append({"name": "Single URL", "url": url, "original_lines": [url]})

    if file:
        try:
            with open(file, "r") as f:
                lines = f.readlines()
                
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if not line:
                    i += 1
                    continue
                
                # Handle M3U format: #EXTINF line followed by URL line
                if line.startswith("#EXTINF"):
                    extinf_line = lines[i].rstrip() # Keep original line content but remove trailing newline
                    i += 1
                    if i < len(lines):
                        url_line = lines[i].strip()
                        if url_line and not url_line.startswith("#"):
                            # Extract name from EXTINF if possible, otherwise use "M3U Channel"
                            # Format: #EXTINF:-1 tvg-name="Name" ... ,Channel Name
                            channel_name = "M3U Channel"
                            if "," in extinf_line:
                                channel_name = extinf_line.split(",")[-1].strip()
                            
                            urls_to_test.append({
                                "name": channel_name, 
                                "url": url_line, 
                                "original_lines": [extinf_line, url_line]
                            })
                        else:
                            # Orphaned EXTINF or comment, skip or handle as needed. 
                            pass
                    i += 1
                    continue

                # Handle "Channel,URL" format
                if "," in line and not line.startswith("#"):
                    parts = line.split(",", 1)
                    channel_name = parts[0].strip()
                    stream_url = parts[1].strip()
                    urls_to_test.append({
                        "name": channel_name, 
                        "url": stream_url, 
                        "original_lines": [line]
                    })
                    i += 1
                    continue
                
                # Assume it's just a URL if it looks like one
                if line.startswith("http") or line.startswith("rtmp") or line.startswith("rtsp"):
                     urls_to_test.append({
                        "name": "Unknown Channel", 
                        "url": line, 
                        "original_lines": [line]
                    })
                     i += 1
                     continue
                
                # Skip other lines (comments, etc)
                i += 1

        except FileNotFoundError:
            print(f"Error: File '{file}' not found.")
            raise typer.Exit(code=1)

    print(f"Testing {len(urls_to_test)} URLs{' (Thorough Mode)' if thorough else ''} with {workers} workers...\n")

    working_links = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        # Submit all tasks while preserving order in a list of futures
        futures = [executor.submit(check_single_url, item, thorough, keep_frames, output_dir) for item in urls_to_test]
        
        # Use as_completed to print progress as it happens
        completed_count = 0
        for future in concurrent.futures.as_completed(futures):
            completed_count += 1
            item, res_lines, log_msg = future.result()
            print(f"[{completed_count}/{len(urls_to_test)}] Checked {item['name']}: {item['url']}")
            print(log_msg)
            print("-" * 40)
            
        # Collect results in ORIGINAL order
        for future in futures:
             item, res_lines, log_msg = future.result()
             if res_lines:
                 working_links.extend(res_lines)

    # If a file was provided, overwrite it with working links
    if file:
        print(f"\nUpdating {file}...")
        print(f"Original count: {len(urls_to_test)}")
        print(f"Working count:  {len(working_links) // 2 if any(l.startswith('#EXTINF') for l in working_links) else len(working_links)}") # Approx count
        
        try:
            with open(file, "w") as f:
                # Re-read first line to check for header
                with open(file, "r") as original_f:
                    first_line = original_f.readline()
                    if first_line.startswith("#EXTM3U"):
                        f.write(first_line)
                
                for line in working_links:
                    f.write(line + "\n")
            print(f"✅ File overwritten with working links.")
        except Exception as e:
            print(f"❌ Error writing to file: {e}")

if __name__ == "__main__":
    app()
