import ollama


response = ollama.chat(
    model="qwen3:1.7b",
    messages=[
        {
            "role": "user",
            "content": "Explain what a GitHub issue is in exactly two sentences."
        }
    ]
)

print(response["message"]["content"])