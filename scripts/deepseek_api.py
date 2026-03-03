"""
直接使用Transformers运行DeepSeek模型的简单API服务
"""

import os
import sys
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# 模型路径
MODEL_PATH = "D:/code/LLM/model_cache/deepseek-ai/DeepSeek-V2-Lite"

app = FastAPI(title="DeepSeek Local API")

# 全局模型和分词器
model = None
tokenizer = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "deepseek"
    messages: List[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 1024
    stream: bool = False


@app.on_event("startup")
async def load_model():
    global model, tokenizer
    print(f"Loading model from {MODEL_PATH}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH, trust_remote_code=True, device_map="auto", torch_dtype=torch.float16
    )
    print("Model loaded successfully!")


@app.get("/")
async def root():
    return {"message": "DeepSeek Local API is running"}


@app.get("/models")
async def list_models():
    return {
        "data": [
            {
                "id": "deepseek",
                "object": "model",
                "created": 1234567890,
                "owned_by": "local",
            }
        ]
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    # 构建提示
    prompt = ""
    for msg in request.messages:
        if msg.role == "system":
            prompt += f"System: {msg.content}\n"
        elif msg.role == "user":
            prompt += f"User: {msg.content}\n"
        elif msg.role == "assistant":
            prompt += f"Assistant: {msg.content}\n"
    prompt += "Assistant:"

    # 生成
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=request.max_tokens,
            temperature=request.temperature,
            do_sample=request.temperature > 0,
            pad_token_id=tokenizer.eos_token_id,
        )

    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # 提取 Assistant 的回复
    assistant_response = response.split("Assistant:")[-1].strip()

    return {
        "id": "chatcmpl-local",
        "object": "chat.completion",
        "created": 1234567890,
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": assistant_response},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(inputs.input_ids[0]),
            "completion_tokens": len(outputs[0]) - len(inputs.input_ids[0]),
            "total_tokens": len(outputs[0]),
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
