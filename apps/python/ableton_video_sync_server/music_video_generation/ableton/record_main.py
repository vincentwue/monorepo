from music_video_generation.ableton.recording_runtime import start_recording_runtime
from packages.python.live_rpyc.live_client import LiveClient


def main():
    start_recording_runtime()
    client = LiveClient.get_instance()
    client.run_forever()


if __name__ == "__main__":
    main()

