
import os
import subprocess
import sys
import uuid
import json
import traceback
from datetime import datetime
from database import BOOKS_DIR

def file_log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    with open("pipeline.log", "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [MARKER] {msg}\n")
        f.flush()

def run_marker_on_pdf(pdf_path, output_dir=None):
    """
    Runs Marker on a PDF using the portable Python 3.12 environment with streaming logs.
    """
    if not output_dir:
        output_dir = os.path.join(BOOKS_DIR, f"marker_{uuid.uuid4().hex}")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Path to the marker_single executable in the portable env
    marker_exe = os.path.join(os.getcwd(), "tools", "python312", "Scripts", "marker_single.exe")
    
    if not os.path.exists(marker_exe):
        file_log("ERROR: Marker executable not found at " + marker_exe)
        return None

    file_log(f"Starting Marker extraction for {pdf_path}")
    
    try:
        cmd = [
            marker_exe,
            pdf_path,
            "--output_dir", output_dir
        ]
        
        file_log(f"Executing: {' '.join(cmd)}")
        
        # Use Popen to stream output to the log
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding='utf-8',
            errors='replace'
        )
        
        # Read output line by line
        for line in process.stdout:
            file_log(f"OUTPUT: {line.strip()}")
            
        process.wait()
        
        if process.returncode != 0:
            file_log(f"Marker failed with exit code {process.returncode}")
            return None
            
        file_log("Marker execution successful.")
        
        # Look for the .md file recursively
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                if file.endswith(".md"):
                    md_path = os.path.join(root, file)
                    file_log(f"Markdown found at: {md_path}")
                    return md_path
        
        file_log("ERROR: Marker finished but no .md file was found.")
        return None
        
    except Exception as e:
        file_log(f"ERROR in Marker Service: {str(e)}")
        traceback.print_exc()
        return None

def extract_high_fidelity_markdown(pdf_path):
    """
    The high-level entry point for the UI.
    """
    md_path = run_marker_on_pdf(pdf_path)
    if md_path and os.path.exists(md_path):
        with open(md_path, "r", encoding="utf-8") as f:
            return f.read()
    return None
