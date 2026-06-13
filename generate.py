import replicate
import os
from dotenv import load_dotenv
import time

load_dotenv()

def generate_video(prompt):
    print("Generating video...")
    
    prediction = replicate.predictions.create(
        model="minimax/video-01",
        input={
            "prompt": prompt,
            "prompt_optimizer": True
        }
    )
    
    print("Waiting for video... this takes 1-2 mins")
    
    while prediction.status not in ["succeeded", "failed", "canceled"]:
        time.sleep(5)
        prediction.reload()
        print("Status: " + prediction.status)
    
    if prediction.status == "succeeded":
        print("Done! Video URL: ")
        print(prediction.output)
    else:
        print("Failed: " + str(prediction.error))

generate_video("A beautiful sunset over Nairobi city skyline, cinematic, 4k")