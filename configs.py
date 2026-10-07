import os 
from dotenv import load_dotenv

load_dotenv()

MODEL_ID = os.getenv("MODEL_ID")
BASE_URL = os.getenv("BASE_URL")
API_KEY = os.getenv("API_KEY")