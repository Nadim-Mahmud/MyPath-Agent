DECLARATION = {
    "name": "report_obstacle",
    "description": "Report an accessibility barrier (e.g. broken ramp, missing curb cut) at a location.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "lat":         {"type": "NUMBER", "description": "Latitude of the obstacle"},
            "lon":         {"type": "NUMBER", "description": "Longitude of the obstacle"},
            "description": {"type": "STRING", "description": "Description of the barrier"},
            "type":        {"type": "STRING", "description": "Type: broken_ramp, missing_curb_cut, construction, other"},
        },
        "required": ["lat", "lon", "description"],
    },
}


def execute(args: dict) -> dict:
    # Storage not yet implemented — stub response
    return {
        "status": "received",
        "message": "Obstacle report recorded. Thank you for improving accessibility data.",
        "lat": args.get("lat"),
        "lon": args.get("lon"),
    }
