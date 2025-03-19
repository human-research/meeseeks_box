import os


def load_api_config():
    """Load API configuration from ~/.meeseeks_box/llm file."""
    config = {
        "API_KEY": None,
        "OPENAI_API_ENDPOINT": None
    }
    
    config_path = os.path.expanduser("~/.meeseeks_box/llm")
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip("'\"")
                        if key in config:
                            config[key] = value
        except Exception as e:
            print(f"Warning: Failed to load config file: {e}")
    else:
        print(f"Warning: Config file not found at {config_path}")
    
    # Check if environment variables can override
    if os.environ.get("API_KEY"):
        config["API_KEY"] = os.environ.get("API_KEY")
    if os.environ.get("OPENAI_API_ENDPOINT"):
        config["OPENAI_API_ENDPOINT"] = os.environ.get("OPENAI_API_ENDPOINT")
    
    # Validate config
    if not config["API_KEY"]:
        print("Warning: API_KEY not found in config or environment")
    if not config["OPENAI_API_ENDPOINT"]:
        print("Warning: OPENAI_API_ENDPOINT not found in config or environment")
    
    return config