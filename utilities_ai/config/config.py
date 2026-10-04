import configparser
from pathlib import Path

config = configparser.ConfigParser()

config.read(Path(__file__).parent / "config.ini")

MONGODB_MAX_POOLS = int(config["MONGODB"]["MAX_POOLS"])
