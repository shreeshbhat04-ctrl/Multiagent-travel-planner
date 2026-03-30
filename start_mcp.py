import os
import subprocess
from dotenv import load_dotenv

# Load variables from .env into the current operating system environment
load_dotenv()

# Verify required env vars
required_vars = ["GOOGLE_CLOUD_PROJECT"]
optional_vars = ["GOOGLE_MAPS_API_KEY", "OPENWEATHERMAP_API_KEY"]

for var in required_vars:
    if not os.getenv(var):
        print(f"❌ ERROR: {var} is not set. Did you copy .env.example to .env and fill it out?")
        exit(1)

for var in optional_vars:
    val = os.getenv(var, "")
    if not val or val.startswith("your-"):
        print(f"⚠️  WARNING: {var} is not configured. Some tools may not work.")

print(f"✅ Starting MCP Toolbox Server for project: {os.getenv('GOOGLE_CLOUD_PROJECT')}")
maps_key = os.getenv('GOOGLE_MAPS_API_KEY', '')
weather_key = os.getenv('OPENWEATHERMAP_API_KEY', '')
print(f"   Maps API: {'✅' if maps_key and not maps_key.startswith('your-') else '⚠️  Not configured'}")
print(f"   Weather API: {'✅' if weather_key and not weather_key.startswith('your') else '⚠️  Not configured'}")

# Run the toolbox executable with the loaded environment variables
try:
    executable = "toolbox.exe" if os.name == "nt" else "./toolbox"

    subprocess.run([
        executable,
        "--config=mcp_server/tools.yaml",
        "--port=5000"
    ], env=os.environ, check=True)
except FileNotFoundError:
    print(f"❌ ERROR: Could not find '{executable}'. Download from:")
    print("   https://github.com/googleapis/genai-toolbox/releases")
except KeyboardInterrupt:
    print("\nShutting down MCP server.")
