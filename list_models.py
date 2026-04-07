import google.generativeai as genai

genai.configure(api_key="AIzaSyC0FMVFeFmhyrdjt9gpSdFgGH5U61KDnzU")

print("Listing available models:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)
