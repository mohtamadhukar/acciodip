import yaml

def load_config(config_path='config.yaml'):
    """
    Load YAML configuration.
    """
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)