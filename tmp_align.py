from pathlib import Path
from apps.python.ableton_video_sync_server.music_video_generation.postprocessing.align_service import FootageAlignService
svc = FootageAlignService()
print(svc.align(r"D:\music_video_generation\water"))
