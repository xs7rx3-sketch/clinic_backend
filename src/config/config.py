import configparser
import os

config = configparser.ConfigParser()
config_file = os.path.join(os.path.dirname(__file__), "config.ini")
config.read(config_file)

MAIN_LLM_MODEL_NAME = config["MAIN_LLM"]["MODEL"]
MAIN_LLM_TEMPERATURE = float(config["MAIN_LLM"]["TEMPERATURE"])
MAIN_LLM_BASE_URL = config["MAIN_LLM"]["BASE_URL"] if config["MAIN_LLM"]["BASE_URL"] != "null" else None

SQL_LLM_MODEL_NAME = config["SQL_LLM"]["MODEL"]
SQL_LLM_TEMPERATURE = float(config["SQL_LLM"]["TEMPERATURE"])
SQL_LLM_BASE_URL = config["SQL_LLM"]["BASE_URL"] if config["SQL_LLM"]["BASE_URL"] != "null" else None
