PLAN_CONFIG = {
    "ideas": {
        "free": {
            "max_ideas": 10,
            "ai_assist": False,
        },
        "pro": {
            "max_ideas": 1000,
            "ai_assist": True,
        },
        "team": {
            "max_ideas": 5000,
            "ai_assist": True,
            "collaboration": True,
        },
    },

    "music_video": {
        "free": {
            "max_video_minutes_per_month": 60,
        },
        "pro": {
            "max_video_minutes_per_month": 1000,
            "4k_export": True,
        },
        "enterprise": {
            "max_video_minutes_per_month": 10000,
            "4k_export": True,
            "priority_rendering": True,
        },
    },
}
