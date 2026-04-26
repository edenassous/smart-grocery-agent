"""
FastAPI server עם SSE לשידור ה-agent בזמן אמת ל-frontend.

הרצה:
  uvicorn api:app --reload --port 8000

Endpoints:
  GET  /api/health
  POST /api/search  (streaming: text/event-stream)
"""

from dotenv import load_dotenv
load_dotenv()

import json
from typing import Iterator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent import stream_agent

app = FastAPI(title="Veggie Basket Agent API")

# ל-Dev: מאפשר לכל localhost. לפרודקשן - הגבל לדומיין של ה-frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    region: str = Field(..., pattern="^(tel_aviv|haifa|jerusalem|beer_sheva)$")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/search")
def search(req: SearchRequest) -> StreamingResponse:
    """
    מזרים את הריצה של ה-agent כ-SSE. כל event הוא JSON על שורה.
    פורמט SSE: "data: <json>\\n\\n"

    סוגי events:
      start        - התחלת ריצה
      text         - טקסט מה-LLM (הסבר מה הוא הולך לעשות)
      tool_call    - קריאה לכלי + input
      tool_result  - תוצאת הכלי
      final        - תשובה סופית + optimization עבור UI
      error        - שגיאה
      done         - אירוע סוף שרירותי לסגירה נקייה
    """
    def event_stream() -> Iterator[str]:
        try:
            for evt in stream_agent(req.message, req.region):
                yield _sse(evt)
        except Exception as e:
            yield _sse({"type": "error", "message": f"{type(e).__name__}: {e}"})
        finally:
            yield _sse({"type": "done"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # מונע buffering של nginx
            "Connection": "keep-alive",
        },
    )


def _sse(data: dict) -> str:
    """עוטף dict בפורמט SSE."""
    return f"data: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
