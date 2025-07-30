#!/usr/bin/env python3
"""
SceneScape Hello World - People Counter

This is a simple example that demonstrates how to:
1. Connect to SceneScape REST API to get scene information
2. Connect to SceneScape MQTT broker to receive live object tracking data
3. Count people across all scenes in real-time

This is designed as a starting point - fork this project and modify it for your needs!

All SceneScape integration code is included directly in this file - no separate
client libraries to maintain. Just modify this file directly for your use case.
"""

import os
import sys
import json
import time
import ssl
import logging
import requests
from datetime import datetime
from collections import defaultdict
from urllib3.exceptions import InsecureRequestWarning

# Handle different paho-mqtt versions
try:
  import paho.mqtt.client as mqtt
  # Try to use v2 API if available
  try:
    from paho.mqtt.client import CallbackAPIVersion
    MQTT_V2_AVAILABLE = True
  except ImportError:
    MQTT_V2_AVAILABLE = False
except ImportError:
  print("ERROR: paho-mqtt is required. Install with: pip install paho-mqtt")
  sys.exit(1)

# Disable SSL warnings when using verify=False
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Set up logging
logging.basicConfig(
  level=logging.INFO,
  format='%(asctime)s - %(levelname)s - %(message)s',
  datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class PeopleCounter:
  """
  A simple people counter that uses SceneScape to track people across scenes.

  This example shows:
  - How to get scene information via REST API (directly implemented)
  - How to receive live object data via MQTT (directly implemented)
  - How to process and count objects in real-time

  All SceneScape integration code is included directly in this class.
  """

  def __init__(self):
    self.scenes = {}  # Scene info from REST API
    self.people_counts = defaultdict(int)  # Current people count per scene
    self.max_people_counts = defaultdict(int)  # Maximum people seen per scene
    self.max_total_people = 0  # Maximum total people across all scenes
    self.scene_names = {}  # Cache scene names for display
    self.total_people = 0  # Total people across all scenes
    self.last_update = None
    self.last_summary_time = 0  # For periodic summary display
    self.message_count = 0  # Count of MQTT messages received

    # HTTP session for REST API
    self.session = None

    # MQTT client for live data
    self.mqtt_client = None

  def load_configuration(self):
    """Load configuration from environment variables"""
    config = {
      'rest_url': os.getenv('SCENESCAPE_REST_URL'),
      'api_token': os.getenv('SCENESCAPE_API_TOKEN'),
      'verify_ssl': os.getenv('SCENESCAPE_VERIFY_SSL', 'false').lower() == 'true',
      'mqtt_host': os.getenv('SCENESCAPE_MQTT_HOST'),
      'mqtt_port': int(os.getenv('SCENESCAPE_MQTT_PORT', '1883')),
      'auth_file': os.getenv('SCENESCAPE_AUTH_FILE', 'secrets/controller.auth')
    }

    # Validate required configuration
    missing = []
    for key, value in config.items():
      if key in ['rest_url', 'api_token', 'mqtt_host'] and not value:
        missing.append(key.upper())

    if missing:
      logger.error(f"Missing required environment variables: {', '.join(missing)}")
      logger.error("Please set these environment variables or check your .env.local file")
      return None

    return config

  def initialize_rest_client(self, config):
    """Initialize REST API client and fetch scene information"""
    logger.info("Initializing REST API client...")

    # Create HTTP session with authentication
    self.session = requests.Session()
    self.session.headers.update({
      'Authorization': f'Token {config["api_token"]}',
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    })

    base_url = config['rest_url'].rstrip('/')
    verify_ssl = config['verify_ssl']

    # Test connection and get scenes
    try:
      logger.info("Fetching scene information...")

      # Make REST API call to get scenes
      url = f"{base_url}/scenes"
      logger.debug(f"GET {url}")
      response = self.session.get(url, verify=verify_ssl, timeout=30)
      response.raise_for_status()

      scenes_data = response.json()

      if scenes_data and 'results' in scenes_data:
        for scene in scenes_data['results']:
          scene_id = scene['uid']
          scene_name = scene.get('name', f'Scene-{scene_id[:8]}')
          self.scenes[scene_id] = {
            'name': scene_name,
            'uid': scene_id,
            'status': scene.get('status', 'unknown')
          }
          logger.info(f"Found scene: {scene_name} ({scene_id})")

        logger.info(f"Successfully connected to SceneScape REST API - found {len(self.scenes)} scenes")
        return True
      else:
        logger.error("No scenes found or invalid response format")
        return False

    except requests.exceptions.Timeout:
      logger.error(f"Request timeout for {url}")
      return False
    except requests.exceptions.ConnectionError:
      logger.error(f"Connection error for {url}")
      return False
    except requests.exceptions.HTTPError as e:
      logger.error(f"HTTP error {response.status_code} for {url}: {e}")
      return False
    except Exception as e:
      logger.error(f"Failed to connect to REST API: {e}")
      return False

  def load_mqtt_credentials(self, auth_file):
    """Load MQTT credentials from auth file"""
    # Handle Docker vs native paths
    if not os.path.exists(auth_file) and auth_file.startswith('/app/'):
      auth_file = auth_file.replace('/app/', '')

    try:
      with open(auth_file, 'r') as f:
        auth_data = json.load(f)

      username = auth_data.get('user')
      password = auth_data.get('password')

      if not username or not password:
        logger.error("Missing user or password in auth file")
        return None, None

      logger.info(f"Loaded MQTT credentials for user: {username}")
      return username, password

    except FileNotFoundError:
      logger.error(f"Auth file not found: {auth_file}")
      return None, None
    except json.JSONDecodeError:
      logger.error(f"Invalid JSON in auth file: {auth_file}")
      return None, None
    except Exception as e:
      logger.error(f"Error loading auth file: {e}")
      return None, None

  def initialize_mqtt_client(self, config):
    """Initialize MQTT client for live data"""
    logger.info("Initializing MQTT client...")

    # Load MQTT credentials
    username, password = self.load_mqtt_credentials(config['auth_file'])
    if not username or not password:
      return False

    # Create MQTT client with version compatibility
    if MQTT_V2_AVAILABLE:
      self.mqtt_client = mqtt.Client(CallbackAPIVersion.VERSION1)
    else:
      self.mqtt_client = mqtt.Client()

    # Set callbacks
    self.mqtt_client.on_connect = self._on_mqtt_connect
    self.mqtt_client.on_message = self._on_mqtt_message
    self.mqtt_client.on_disconnect = self._on_mqtt_disconnect

    # Configure TLS (SceneScape uses TLS even on port 1883)
    self.mqtt_client.tls_set(cert_reqs=ssl.CERT_NONE)
    self.mqtt_client.tls_insecure_set(True)

    # Set authentication
    self.mqtt_client.username_pw_set(username, password)

    # Connect to broker
    try:
      logger.info(f"Connecting to MQTT broker {config['mqtt_host']}:{config['mqtt_port']}...")
      result = self.mqtt_client.connect(config['mqtt_host'], config['mqtt_port'], 60)

      if result == mqtt.MQTT_ERR_SUCCESS:
        # Start the network loop
        self.mqtt_client.loop_start()

        # Wait a moment for connection to establish
        time.sleep(1)

        if self.mqtt_client.is_connected():
          logger.info("Successfully connected to MQTT broker")

          # Subscribe to scene data
          topic = "scenescape/regulated/scene/+"
          result, mid = self.mqtt_client.subscribe(topic)
          if result == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"Subscribed to topic: {topic}")
            logger.info("Waiting for live object data...")
            return True
          else:
            logger.error(f"Failed to subscribe to {topic}, error code: {result}")
            return False
        else:
          logger.error("Failed to establish MQTT connection")
          return False
      else:
        logger.error(f"MQTT connection failed with code: {result}")
        return False

    except Exception as e:
      logger.error(f"MQTT connection error: {e}")
      return False

  def _on_mqtt_connect(self, client, userdata, flags, rc):
    """Callback for when the MQTT client connects to the broker"""
    if rc == 0:
      logger.debug("MQTT client connected successfully")
    else:
      logger.error(f"MQTT connection failed with code {rc}")

  def _on_mqtt_disconnect(self, client, userdata, rc):
    """Callback for when the MQTT client disconnects from the broker"""
    if rc != 0:
      logger.warning(f"Unexpected MQTT disconnection (code: {rc})")
    else:
      logger.debug("MQTT client disconnected")

  def _on_mqtt_message(self, client, userdata, msg):
    """Callback for when an MQTT message is received"""
    try:
      topic = msg.topic
      payload = msg.payload.decode('utf-8')

      # Parse JSON payload
      try:
        data = json.loads(payload)
      except json.JSONDecodeError:
        logger.warning(f"Non-JSON message on {topic}: {payload[:100]}...")
        return

      # Process the message
      self.handle_mqtt_message(topic, data)

    except Exception as e:
      logger.error(f"Error processing MQTT message: {e}")

  def handle_mqtt_message(self, topic, data):
    """
    Handle incoming MQTT messages with object tracking data

    This is where you would add your custom logic for processing
    SceneScape object tracking data.
    """
    try:
      # Extract scene information - data uses 'id' not 'scene_uid'
      scene_id = data.get('id')
      if not scene_id:
        logger.warning("Message missing scene 'id' field")
        return

      # Cache scene name for display
      scene_name = data.get('name', self.scenes.get(scene_id, {}).get('name', f'Scene-{scene_id[:8]}'))
      self.scene_names[scene_id] = scene_name

      # Count people only
      objects = data.get('objects', [])
      people_in_scene = 0

      for obj in objects:
        # Filter for person objects
        if obj.get('type') == 'person' or obj.get('category') == 'person':
          people_in_scene += 1

      # Update our counts
      self.people_counts[scene_id] = people_in_scene
      self.total_people = sum(self.people_counts.values())

      # Track maximum counts
      if people_in_scene > self.max_people_counts[scene_id]:
        self.max_people_counts[scene_id] = people_in_scene
      if self.total_people > self.max_total_people:
        self.max_total_people = self.total_people

      self.last_update = datetime.now()
      self.message_count += 1

      # Show periodic summary
      current_time = time.time()
      is_docker = os.getenv('DOCKER_CONTAINER') or not sys.stdout.isatty()
      summary_interval = 3.0 if is_docker else 1.0  # Less frequent in Docker

      if current_time - self.last_summary_time >= summary_interval:
        self.show_live_summary()
        self.last_summary_time = current_time

    except Exception as e:
      logger.error(f"Error processing MQTT message: {e}")
      logger.debug(f"Message data: {data}")

  def show_live_summary(self):
    """Show a concise live summary of current people counts"""
    if not self.people_counts:
      return

    # Build summary line
    scene_summaries = []
    for scene_id, count in self.people_counts.items():
      scene_name = self.scene_names.get(scene_id, f'Scene-{scene_id[:8]}')
      scene_summaries.append(f"{scene_name}: {count}")

    summary = " | ".join(scene_summaries)
    timestamp = self.last_update.strftime('%H:%M:%S') if self.last_update else "No data"

    # Check if we're running in Docker or non-interactive environment
    is_docker = os.getenv('DOCKER_CONTAINER') or not sys.stdout.isatty()

    if is_docker:
      # In Docker, print new lines so users can see the updates
      print(f"[{timestamp}] Total: {self.total_people} people ({summary}) - {self.message_count} msgs")
    else:
      # Native terminal, use carriage return for single updating line
      print(f"\r[{timestamp}] Total: {self.total_people} people ({summary}) - {self.message_count} msgs", end='', flush=True)

  def print_status(self):
    """Print peak occupancy summary"""
    print("\n" + "="*60)
    print("SceneScape People Counter - Peak Occupancy Summary")
    print("="*60)

    if self.last_update:
      print(f"Last Update: {self.last_update.strftime('%H:%M:%S')}")
      print(f"Total Messages Processed: {self.message_count:,}")
    else:
      print("Last Update: No data received yet")
      return

    print(f"Maximum Total People Detected: {self.max_total_people}")
    print()

    if self.max_people_counts:
      print("Maximum People Count by Scene:")
      for scene_id, max_count in self.max_people_counts.items():
        scene_name = self.scene_names.get(scene_id, f'Scene-{scene_id[:8]}')
        current_count = self.people_counts.get(scene_id, 0)
        print(f"  {scene_name}: {max_count} people (currently: {current_count})")
    else:
      print("No live data received yet...")

    print("="*60)

  def run(self):
    """Main application loop"""
    logger.info("Starting SceneScape People Counter...")

    # Load configuration
    config = self.load_configuration()
    if not config:
      return False

    # Initialize REST client and get scene info
    if not self.initialize_rest_client(config):
      return False

    # Initialize MQTT client for live data
    if not self.initialize_mqtt_client(config):
      return False

    # Main loop
    try:
      print("\n" + "="*60)
      print("SceneScape People Counter - Live Data")
      print("="*60)
      print("Press Ctrl+C to stop...")
      print()

      # Initialize summary timing
      self.last_summary_time = time.time()

      while True:
        time.sleep(5)  # Check every 5 seconds

        # Print a detailed status every 30 seconds
        if self.message_count > 0 and self.message_count % 150 == 0:  # ~30 sec at typical message rates
          print()  # New line after live summary
          self.print_status()
          print()  # Space before resuming live summary

    except KeyboardInterrupt:
      print()  # New line after live summary
      logger.info("Shutting down people counter...")
      self.print_status()  # Final detailed summary
    except Exception as e:
      logger.error(f"Unexpected error: {e}")
    finally:
      # Cleanup
      if self.mqtt_client:
        try:
          self.mqtt_client.loop_stop()
          self.mqtt_client.disconnect()
        except:
          pass
      logger.info("People counter stopped.")

    return True


def main():
  """Entry point for the hello world application"""

  # Quick environment check
  if not os.getenv('SCENESCAPE_REST_URL'):
    print("Configuration Error!")
    print()
    print("Missing required environment variables. Please ensure you have:")
    print()
    print("1. Copied .env.example to .env.local")
    print("2. Updated .env.local with your SceneScape server details")
    print("3. For native Python: source .env.local")
    print("4. For Docker: docker compose up (automatically loads .env.local)")
    print()
    print("See README.md for detailed setup instructions.")
    return 1

  # Run the people counter
  counter = PeopleCounter()
  success = counter.run()

  return 0 if success else 1


if __name__ == "__main__":
  sys.exit(main())
