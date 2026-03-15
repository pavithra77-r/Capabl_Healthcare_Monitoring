# utils package

# Load .env automatically when running locally.
# In production (e.g., Docker), environment variables are expected to be set via the container runtime.
try:
    from dotenv import load_dotenv

    load_dotenv()  # loads .env if present
except ImportError:
    # dotenv is optional if environment variables are set externally.
    pass
