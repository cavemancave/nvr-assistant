import os
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

def on_connect(client, userdata, flags, rc, properties=None):
    print("Connected to MQTT broker")

def send_test_image(client, image_path):
    topic_img = "nvr/notification/image"
    topic_trigger = "nvr/notification/trigger"
    try:
        # Read image file
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        # Publish to MQTT topic
        print(f"Sending image from {image_path} to topic {topic_img}")
        print(f"Image size: {len(image_bytes)} bytes")
        
        client.publish(topic_img, image_bytes)
        print(f"Published image to {topic_img}")
        client.publish(topic_trigger, "yes")
        print(f"Published yes to {topic_trigger}")
        
    except Exception as e:
        print(f"Error sending image: {e}")

def mqtt_init():
    client = mqtt.Client(protocol=mqtt.MQTTv5)
    client.on_connect = on_connect
    mqtt_host = os.getenv("MQTT_HOST", "localhost")
    mqtt_port = int(os.getenv("MQTT_PORT", 1883))
    mqtt_user = os.getenv("MQTT_USER")
    mqtt_pass = os.getenv("MQTT_PASS")
    
    if mqtt_user and mqtt_pass:
        client.username_pw_set(mqtt_user, mqtt_pass)
    
    try:
        client.connect(mqtt_host, mqtt_port, 60)
        client.loop_start()
        return client
    except Exception as e:
        print(f"Error connecting to MQTT broker: {e}")
        return None

def mqtt_deinit(client):
    if client:
        client.loop_stop()
        client.disconnect()
        print("Disconnected from MQTT broker")
    else:
        print("No MQTT client to disconnect")
        
def main():
    client = mqtt_init()
    send_test_image(client, "test.jpg")
    mqtt_deinit(client)

if __name__ == "__main__":
    main()