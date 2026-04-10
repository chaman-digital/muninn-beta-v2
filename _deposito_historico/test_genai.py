import os
import json
from google import genai
from google.genai import types
from PIL import Image

try:
    filepath = "2023/PAGOS PENSIÓN/PHOTO-2023-08-04-16-47-50.jpg"
    if not os.path.exists(filepath):
        import glob
        matches = glob.glob(f"**/*PHOTO-2023-08-04-16-47-50*", recursive=True)
        if matches:
            filepath = matches[0]

    api_key = "AIzaSy_fake_key_just_to_init_client"
    client = genai.Client(api_key=api_key)
    
    # We will trigger the API call, it will fail with 400 API_KEY_INVALID,
    # but we want to see if it throws UnicodeEncodeError BEFORE hitting the network!
    pil_img = Image.open(filepath)
    if hasattr(pil_img, 'filename'):
        pil_img.filename = "evidencia_limpia.jpg"
        
    print("Testing with replaced pil_img.filename")
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[pil_img, "Test prompt"]
        )
    except Exception as api_err:
        print("API Error (as expected if invalid key, but NOT UnicodeEncodeError):", type(api_err).__name__, api_err)
        
    print("\n\nTesting with ORIGINAL pil_img.filename")
    pil_img_orig = Image.open(filepath)
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[pil_img_orig, "Test prompt"]
        )
    except Exception as e:
        print("ORIGINAL MSG:", type(e).__name__, e)
        
    print("\n\nTesting with string filepath directly")
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[filepath, "Test prompt"]
        )
    except Exception as e:
        print("FILEPATH MSG:", type(e).__name__, e)

except Exception as e:
    import traceback
    traceback.print_exc()

