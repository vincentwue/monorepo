from moviepy.editor import VideoFileClip, vfx
import os

# === Einstellungen ===
input_path = r"C:\Users\vince\Desktop\P1060448.MP4"
output_path = os.path.splitext(input_path)[0] + "_zoom.mp4"

# Wie stark gezoomt werden soll (1.0 = kein Zoom, z. B. 1.2 = 20% nher)
zoom_factor = 1.2

# Wie lange der Zoom dauern soll (in Sekunden)
zoom_duration = 3

# === Video laden ===
clip = VideoFileClip(input_path)

# Mittelpunkt definieren (x, y in 01 Koordinaten)
center_x, center_y = 0.5, 0.5  # Mitte

# Zoom-Animation (progressiver Zoom)
def zoom_in(get_frame, t):
    progress = min(t / zoom_duration, 1)
    scale = 1 + (zoom_factor - 1) * progress
    frame_clip = clip.fx(
        vfx.crop,
        x_center=center_x * clip.w,
        y_center=center_y * clip.h,
        width=clip.w / scale,
        height=clip.h / scale,
    ).resize((clip.w, clip.h))
    return frame_clip.get_frame(t)

# neuen Clip mit Zoom-Effekt erzeugen
zoom_clip = clip.fl(zoom_in, apply_to=['mask'])

# === Export ===
zoom_clip.write_videofile(output_path, codec='libx264', audio_codec='aac')

print("[OK] Fertig:", output_path)
