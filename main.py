import threading
import time
import os
import base64
from io import BytesIO
from dotenv import load_dotenv
import requests
import cv2
from openai import OpenAI
import datetime
import ha_notify

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

mqtt_client = ha_notify.mqtt_init()
last_notification_time = None

def genmini_image_understanding(image, prompt="What is in this image?"):
    debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
    if debug_mode:
        print(f"Debug mode is ON. Prompt: {prompt}")
        return "yes"
    base64_image = base64.b64encode(cv2.imencode('.jpg', image)[1]).decode('utf-8')
    response = client.chat.completions.create(
    model="gemini-2.0-flash",
    messages=[
        {
        "role": "user",
        "content": [
            {
            "type": "text",
            "text": f"{prompt}",
            },
            {
            "type": "image_url",
            "image_url": {
                "url":  f"data:image/jpeg;base64,{base64_image}"
            },
            },
        ],
        }
    ],
    )
    answer = response.choices[0].message.content
    print(f"Gemini answer: {answer}")
    return answer
    

def send_mqtt_notification(image_path):

        print("Sending MQTT notification...")
        ha_notify.send_test_image(mqtt_client, image_path)
        
    
def fall_detection_thread(image):
    global last_notification_time
    current_time = datetime.datetime.now()
    if last_notification_time and (current_time - last_notification_time).total_seconds() < 60:
        print("Already notified within the last minute, skipping fall detection.")
        return
    # Ensure log directory exists
    log_dir = "log"
    os.makedirs(log_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    img_path = os.path.join(log_dir, f"{timestamp}.jpg")
    txt_path = os.path.join(log_dir, f"{timestamp}.txt")

    # Save image
    cv2.imwrite(img_path, image)

    prompt_fall_detection = "Please help me analyze whether there is someone falling in this screenshot. If there is a possibility, I will send a prompt to others to confirm."
    
    answer = genmini_image_understanding(image, f"As an NVR assistant, I will send you a screenshot of the movement in the surveillance. {prompt_fall_detection} Just answer yes or no.")
    is_fall = "yes" in answer.lower()

    # Save answer
    with open(txt_path, "w") as f:
        f.write(answer)

    if is_fall:
        print("ALERT: Person fall detected!")
        last_notification_time = current_time
        send_mqtt_notification(img_path)

def main():
    from ultralytics import YOLO
    import cv2

    # Load pre-trained YOLOv8 model (automatically downloads)
    model = YOLO("yolov8n.pt")  # you can use yolov8n/s/m/l/x

    # Open a video file or camera stream
    cap = cv2.VideoCapture("rtsp://localhost:9554/live")  # or 0 for webcam
    #cap = cv2.VideoCapture("/home/taishan/code/mediamtx/out/live.mp4")
    if not cap.isOpened():
        print("Error: Could not open video stream.")
        return
    
    last_check_time = 0
    fall_thread = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Run YOLOv8 inference on the frame
        results = model(frame)

        person_detected = False
        for result in results:
            boxes = result.boxes
            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                if cls_id == 0:  # Class 0 = 'person' in COCO
                    person_detected = True
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"Person {conf:.2f}", (x1, y1 - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        # Every 3 seconds, if person detected, start fall detection thread
        current_time = time.time()
        if person_detected and (current_time - last_check_time > 3):
            last_check_time = current_time
            # Send a copy of the frame to the thread
            img_copy = frame.copy()
            fall_thread = threading.Thread(target=fall_detection_thread, args=(img_copy,))
            fall_thread.daemon = True
            fall_thread.start()

        cv2.imshow("Human Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    ha_notify.mqtt_deinit(mqtt_client)

if __name__ == "__main__":
    main()
