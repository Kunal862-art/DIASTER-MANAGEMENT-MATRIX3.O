import google.generativeai as genai

genai.configure(api_key="AIzaSyBU9wswRSU3DuN0zZAXWjLEPNZM5hw9wlU")

print("Listing available models:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)
