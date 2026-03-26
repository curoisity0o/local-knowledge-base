{
"$schema": "https://opencode.ai/config.json",
"provider": {
"volcengine": {
"npm": "@ai-sdk/openai-compatible",
"name": "volcengine",
"options": {
"baseURL": "https://ark.cn-beijing.volces.com/api/coding/v3",
"apiKey": "007a0acf-77a8-43b3-a0ef-b111b21f3d10"
},
"models": {
"ark-code-latest": {
"name": "ark-code-latest"
},
"kimi-k2.5": {
"name": "kimi-k2.5",
"modalities": {
"input": ["text", "image"],
"output": ["text"]
},
"options": {
"thinking": {
"type": "enabled"
}
}
}
}
}
}
}