from m22.music22_settings_dir.music22_video_generator_settings import Music22VideoGeneratorSettings

if __name__ == "__main__":
    settings = Music22VideoGeneratorSettings(
        root=r"d:\music_video_generation",
        project_name="todo_song",
        bpm=96,
        debug=True,
        debug_downscale_factor=4,
        base_width=1920,
        base_height=1080,
        base_fps=30,
        fps_downscale_factor=4,
    )
    # optional: settings.mode.set_value("markov"); settings.markov_json.set_value('{"__start__": {"CamA":0.6,"CamB":0.4}}')
    path = settings.generate_video()