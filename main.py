import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent import run_agent

app = FastAPI(title="Browser Agent API")

# CORS — Vercel domain'ini ekle
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        os.getenv("FRONTEND_URL", "*")  # Vercel URL'ini .env'e ekle
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskRequest(BaseModel):
    task: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/agent/run")
async def run(req: TaskRequest):
    result = await run_agent(req.task)
    return result


# Adımları canlı aktar
@app.websocket("/agent/stream")
async def stream(ws: WebSocket):
    await ws.accept()
    try:
        data = await ws.receive_json()
        task = data.get("task")

        if not task:
            await ws.send_json({"type": "error", "message": "Görev boş olamaz"})
            await ws.close()
            return

        async def on_step(step):
            await ws.send_json(step)

        result = await run_agent(task, on_step=on_step)
        await ws.send_json({"type": "done", "result": result["result"]})

    except WebSocketDisconnect:
        print("Client bağlantıyı kesti")
    finally:
        await ws.close()