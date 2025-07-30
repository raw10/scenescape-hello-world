# SceneScape Hello World

A simple, practical example showing how to connect to SceneScape and count people in real-time. This sample demonstrates both REST API and MQTT protocols working together, and shows two deployment methods: native Python and Docker.

**This is designed as a starting point** - fork this project and modify `hello_world.py` directly for your specific needs!

## What This Does

**`hello_world.py`** - A complete working example that:

- Uses **REST API** to get scene configuration and validate connectivity
- Uses **MQTT** to receive live object tracking data in real-time
- Counts people across all scenes by processing live events
- Displays live updates and tracks peak occupancy statistics
- Demonstrates both **native Python** and **Docker** deployment methods

**All SceneScape integration code is included directly in `hello_world.py`** - no separate libraries or SDKs to maintain!

## Key Features

- **Self-Contained**: Everything you need is in one file you can easily understand
- **Real Working Example**: Counts people across scenes - intuitive and practical
- **No Abstractions**: All REST and MQTT code directly visible and modifiable
- **Heavily Commented**: Explains WHY things are done, not just what
- **Fork-Friendly**: Designed to be copied and customized for your needs
- **Zero Maintenance**: No SDK to maintain - you own your modifications
- **Docker Ready**: Works in both native Python and Docker environments

**Just one main file** - `hello_world.py` contains all the SceneScape integration code you need!

## Project Structure

```text
├── hello_world.py          # Main application (self-contained)
├── requirements.txt        # Python dependencies
├── .env.example           # Environment template for users
├── Dockerfile             # Docker image
├── docker-compose.yml     # Docker deployment
├── README.md              # This documentation
└── secrets/               # Authentication files
    ├── controller.auth.example
    └── controller.auth     # Your MQTT credentials (create this)
```

## Quick Start

### Prerequisites

- Python 3.7+ with pip
- Docker and Docker Compose (for Docker mode)
- Access to SceneScape server (REST API and MQTT broker)

### 1. Clone and Setup

```bash
git clone <this-repo>
cd scenescape-hello-world
```

**For native Python only:**

```bash
# Install Python dependencies
pip install -r requirements.txt
```

**Note:** Docker users can skip the pip install step since dependencies are installed automatically in the container.

### 2. Configure Your SceneScape Connection

Copy the environment template and edit with your server details:

```bash
# Copy environment template
cp .env.example .env.local
```

Edit `.env.local` with your server details:

```bash
# SceneScape Server Configuration
SCENESCAPE_REST_URL=https://your-scenescape-host/api/v1
SCENESCAPE_API_TOKEN=your_api_token_here

# MQTT Broker Configuration  
SCENESCAPE_MQTT_HOST=your-scenescape-host
SCENESCAPE_MQTT_PORT=1883

# SSL/TLS Configuration (usually false for development)
SCENESCAPE_VERIFY_SSL=false

# Authentication file path (contains MQTT credentials)
SCENESCAPE_AUTH_FILE=secrets/controller.auth
```

Edit `secrets/controller.auth` with your MQTT credentials:

```json
{"user": "scenectrl", "password": "your_mqtt_password_here"}
```

### 3. Choose Your Deployment Method

#### Option A: Native Python

```bash
# Load environment variables and run
source .env.local
python hello_world.py
```

#### Option B: Docker (Recommended)

```bash
# Environment is automatically loaded from .env.local
docker compose up --build
```

You should see:

- Connection status for REST API and MQTT
- Live people counts updating in real-time
- Peak occupancy statistics when you stop (Ctrl+C)

## Environment Variable Reference

All configuration is done through environment variables in your `.env.local` file:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SCENESCAPE_REST_URL` | SceneScape REST API base URL | - | Yes |
| `SCENESCAPE_API_TOKEN` | API authentication token | - | Yes |
| `SCENESCAPE_VERIFY_SSL` | Verify SSL certificates | `false` | No |
| `SCENESCAPE_MQTT_HOST` | MQTT broker hostname | - | Yes |
| `SCENESCAPE_MQTT_PORT` | MQTT broker port | `1883` | No |
| `SCENESCAPE_AUTH_FILE` | Path to controller.auth file | `secrets/controller.auth` | Yes |

## How It Works

This hello world application demonstrates how REST API and MQTT protocols work together for SceneScape integration:

### REST API (Configuration & Setup)

- Gets scene information and validates connectivity at startup
- Used for one-time configuration queries and authentication testing

### MQTT (Live Data Stream)

- Receives real-time object tracking events from all scenes
- Processes live data to count people and track occupancy

### Deployment Methods

- **Native Python**: Run directly with Python after sourcing environment variables
- **Docker**: Containerized deployment with automatic environment loading

### REST API Integration Details (in `hello_world.py`)

- **Token Authentication**: Uses Bearer token format for authentication
- **SSL Verification Disabled**: Handles self-signed certificates (`verify=False`)
- **JSON Content-Type**: Proper headers for API communication
- **Base Path**: Uses `/api/v1` as the base path for all endpoints

```python
# Working REST setup
session.headers.update({
    'Authorization': f'Token {api_token}',
    'Content-Type': 'application/json'
})
response = session.get(url, verify=False)
```

### MQTT Integration Details (in `hello_world.py`)

- **TLS Enabled**: Uses TLS encryption for secure communication
- **Certificate Verification Disabled**: Works with self-signed certificates (`cert_reqs=ssl.CERT_NONE`)
- **Insecure TLS**: Bypasses hostname verification (`tls_insecure_set(True)`)
- **Username/Password Auth**: Uses credentials from controller.auth file
- **Correct Topic Pattern**: Uses `scenescape/regulated/scene/+` for live object tracking data

```python
# Working MQTT setup
client.tls_set(cert_reqs=ssl.CERT_NONE)
client.tls_insecure_set(True)
client.username_pw_set(username, password)
```

### People Counter Logic (`hello_world.py`)

1. **Initialize REST client** - Get scene information and validate connection
2. **Initialize MQTT client** - Connect to live data stream
3. **Process messages** - Count objects (people) in real-time per scene
4. **Display results** - Show live counts and summary statistics

## MQTT Topic Patterns

SceneScape uses these MQTT topic patterns for live data:

- `scenescape/regulated/scene/+` - **Primary topic for live object tracking data** (use this!)
- `scenescape/regulated/scene/{scene_id}` - Live data for specific scene

**Example live data payload**:

```json
{
  "timestamp": "2025-07-30T22:23:32.219Z",
  "id": "3bc091c7-e449-46a0-9540-29c499bca18c",
  "name": "Retail",
  "scene_rate": 39.7,
  "rate": {"camera1": 10.0, "camera2": 10.0},
  "objects": [
    {
      "category": "person",
      "type": "person", 
      "confidence": 0.9669200778007507,
      "id": "5772400f-2536-4de2-a82d-b9fa74aaefc4",
      "translation": [5.5494025006814125, 4.615637869482904, 0.0],
      "velocity": [0.3715157479989612, -0.06735682868246627, 0.0],
      "visibility": ["camera2"],
      "first_seen": "2025-07-30T22:23:31.919Z"
    }
  ]
}
```

## Customization

This is designed to be modified! Open `hello_world.py` and customize it for your specific needs:

- **Different Object Types**: Modify the counting logic to track specific object types
- **Data Storage**: Add database storage for historical analysis  
- **Web Dashboard**: Create a simple web interface to view live data
- **Alerts and Notifications**: Add email/Slack notifications for occupancy thresholds
- **Zone-Based Counting**: Use object positions to count people in specific zones

The code is heavily commented to help you understand and modify each part.

## Troubleshooting

### Common Issues

1. **MQTT Connection Refused**
   - Verify broker host/port are correct
   - Check credentials in `secrets/controller.auth`
   - Test with: `timeout 10s python hello_world.py`

2. **REST API Authentication Failed**
   - Verify API token is correct and active
   - Check base URL includes `/api/v1` path
   - Ensure `verify_ssl=false` for self-signed certificates

3. **No MQTT Data Received**
   - Use correct topic pattern: `scenescape/regulated/scene/+`
   - Ensure scenes are active and processing
   - Check MQTT credentials are valid

4. **Certificate/SSL Errors**
   - Use `verify_ssl=false` for REST API with self-signed certificates
   - The application handles TLS configuration automatically

### Testing Connectivity

```bash
# Test the application (should show connection status)
python hello_world.py

# For Docker
docker compose exec hello-world python hello_world.py
```

## Why This Approach?

This project follows a **self-contained sample** philosophy rather than building an SDK:

1. **Educational Value**: You can see exactly how SceneScape integration works
2. **Zero Dependencies**: No external SDK to maintain or debug
3. **Full Customization**: Modify any part of the integration for your needs
4. **No Abstractions**: Direct access to REST and MQTT protocols
5. **Fork-Friendly**: Perfect starting point for your own projects

Instead of learning an SDK, you learn the actual SceneScape protocols!

## License

This template is provided as-is for SceneScape integration projects.
