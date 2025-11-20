// apps/ableton_video_sync/src/lib/types.ts

export type AlignSegmentResult = {
  source_video: string; // original video file
  segment_index: number; // segment number (1-based)
  recording_id: string | null; // matched Ableton recording ID
  recording_start_sound: string | null;
  recording_end_sound: string | null;
  track_names: string[]; // voice, guitar, etc.

  trim_start: number; // trim start in the video source
  pad_start: number; // applied black padding before
  pad_end: number; // applied black padding after
  used_duration: number; // total audio duration used

  segment_start_s: number; // detected segment start from postprocess
  segment_end_s: number | null; // detected segment end
  segment_duration_s: number | null;

  output_path: string; // aligned output .mp4 file

  flags: {
    missing_end: boolean;
    too_short: boolean;
    confidence: number; // primary cue confidence
    usable: boolean; // good enough to use in auto-video-gen
  };
};

export type AlignFootageResult = {
  project_path: string;
  audio_path: string;
  audio_duration: number;
  output_dir: string;
  segments_aligned: number;
  results: AlignSegmentResult[];
  debug: any[];
};
