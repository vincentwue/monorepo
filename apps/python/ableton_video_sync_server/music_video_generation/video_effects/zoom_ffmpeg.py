import subprocess
import os
import shlex

def zoom_video(input_path: str, zoom_factor: float = 1.2, duration: float = 3.0, fps: int = 30):
    """
    Schneller Zoom-in-Effekt mit FFmpeg.
    """
    base, ext = os.path.splitext(input_path)
    output_path = f"{base}_zoom{ext}"

    # FFmpeg-Zoom-Expression: auf Basis der Framezahl, nicht Zeit
    zoom_expr = f"1+({zoom_factor - 1})*on/{int(duration*fps)}"

    vf = (
        f"zoompan=z='{zoom_expr}':"
        f"x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':"
        f"d={int(duration*fps)},"
        f"fps={fps},scale=iw:ih"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-c:a", "copy",
        output_path,
    ]

    print("[START] Starte FFmpeg...")
    print(" ".join(shlex.quote(c) for c in cmd))
    subprocess.run(cmd, check=True)
    print(f"[OK] Fertig: {output_path}")
    return output_path


if __name__ == "__main__":
    zoom_video(r"C:\Users\vince\Desktop\P1060448.MP4", zoom_factor=1.2, duration=3)
