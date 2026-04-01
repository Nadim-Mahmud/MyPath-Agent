DECLARATION = {
    "name": "get_obstacles",
    "description": "Retrieve known accessibility obstacles near a given location.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "lat":    {"type": "NUMBER", "description": "Latitude to search near"},
            "lon":    {"type": "NUMBER", "description": "Longitude to search near"},
            "radius": {"type": "NUMBER", "description": "Search radius in metres (default 500)"},
        },
        "required": ["lat", "lon"],
    },
}


def execute(args: dict) -> dict:
    # Storage not yet implemented — stub response
    return {
        "obstacles": [],
        "message": "Obstacle database not yet populated. No known obstacles in this area.",
    }
