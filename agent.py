"""
Agent loop - Claude כמתזמר, הכלים עושים את העבודה האמיתית.

שני מצבי הרצה:
  run_agent(...)    → מחזיר מחרוזת סופית (ל-CLI).
  stream_agent(...) → generator שמחזיר events בזמן אמת (ל-SSE).
"""
import json
from typing import Any, Iterator, Literal, TypedDict
import anthropic
from tools import TOOLS, execute_tool

MODEL = "claude-opus-4-7"  # אפשר להחליף ל-claude-sonnet-4-6 כדי לחסוך
MAX_ITERATIONS = 20

SYSTEM_PROMPT = """אתה עוזר חכם למציאת סלי ירקות זולים. התהליך שלך:

1. השתמש ב-parse_shopping_list כדי לפרסר את בקשת המשתמש לרשימת פריטים.
2. לכל פריט ברשימה, קרא ל-search_product עם שם המוצר ואזור המשלוח.
   אפשר לקרוא לכמה search_product במקביל באותה תגובה (כל אחד tool_use נפרד).
3. בנה רשימה של חנויות ייחודיות שהופיעו בתוצאות. לכל אחת, קרא ל-get_delivery_info.
4. קרא ל-optimize_basket עם כל המידע - הוא יחזיר את הפיצול האופטימלי.
   *חשוב*: אל תנסה לחשב בעצמך איזה פיצול זול יותר - תמיד קרא לכלי.
   אם הכלי מחזיר feasible=false, הסבר למשתמש את הסיבה (סל קטן מדי לסף ההזמנה למשל).
5. הצג את התוצאה למשתמש בעברית, באופן ברור:
   - כמה סלים יש (לפי חנות)
   - מה בכל סל עם מחיר
   - סך עלות המוצרים, סך משלוחים, וסה"כ
   - אם יש פריטים שלא נמצאו - תאר אותם
   - תן הסבר קצר למה הפיצול הזה הכי זול.

אל תדלג על שלבים ואל תמציא מחירים. אם כלי החזיר שגיאה - דווח עליה בבירור למשתמש."""


# ---------- Event types ל-SSE streaming ----------

class StartEvent(TypedDict):
    type: Literal["start"]
    message: str
    region: str

class TextEvent(TypedDict):
    type: Literal["text"]
    text: str

class ToolCallEvent(TypedDict):
    type: Literal["tool_call"]
    id: str
    name: str
    input: dict

class ToolResultEvent(TypedDict):
    type: Literal["tool_result"]
    id: str
    name: str
    result: Any

class FinalEvent(TypedDict):
    type: Literal["final"]
    answer: str
    optimization: dict | None  # תוצאת ה-optimizer האחרונה, ל-UI

class ErrorEvent(TypedDict):
    type: Literal["error"]
    message: str

Event = (
    StartEvent | TextEvent | ToolCallEvent
    | ToolResultEvent | FinalEvent | ErrorEvent
)


# ---------- Core streaming loop ----------

def stream_agent(user_message: str, region: str) -> Iterator[Event]:
    """Generator שמחזיר events בזמן אמת תוך כדי ריצת ה-agent."""
    client = anthropic.Anthropic()

    yield {"type": "start", "message": user_message, "region": region}

    messages = [{
        "role": "user",
        "content": f"אזור משלוח: {region}\n\nבקשה: {user_message}",
    }]

    last_optimization: dict | None = None

    for _step in range(MAX_ITERATIONS):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )
        except Exception as e:
            yield {"type": "error", "message": f"Claude API error: {e}"}
            return

        messages.append({"role": "assistant", "content": response.content})

        tool_results_for_next_turn = []
        final_text_parts = []

        for block in response.content:
            if block.type == "text":
                yield {"type": "text", "text": block.text}
                final_text_parts.append(block.text)

            elif block.type == "tool_use":
                yield {
                    "type": "tool_call",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                }
                result = execute_tool(block.name, block.input)
                if block.name == "optimize_basket" and isinstance(result, dict):
                    last_optimization = result

                yield {
                    "type": "tool_result",
                    "id": block.id,
                    "name": block.name,
                    "result": result,
                }
                tool_results_for_next_turn.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })

        if response.stop_reason == "end_turn":
            yield {
                "type": "final",
                "answer": "\n".join(final_text_parts),
                "optimization": last_optimization,
            }
            return

        if response.stop_reason != "tool_use":
            yield {"type": "error", "message": f"stop_reason לא צפוי: {response.stop_reason}"}
            return

        messages.append({"role": "user", "content": tool_results_for_next_turn})

    yield {"type": "error", "message": f"הגעתי ל-{MAX_ITERATIONS} איטרציות - כנראה loop."}


# ---------- Non-streaming wrapper ל-CLI ----------

def run_agent(user_message: str, region: str, verbose: bool = True) -> str:
    final_answer = ""
    for evt in stream_agent(user_message, region):
        if verbose:
            _print_event(evt)
        if evt["type"] == "final":
            final_answer = evt["answer"]
        elif evt["type"] == "error":
            return f"[ERROR] {evt['message']}"
    return final_answer


def _print_event(evt: Event) -> None:
    t = evt["type"]
    if t == "text":
        print(f"  💭 {evt['text'][:120]}")
    elif t == "tool_call":
        print(f"  → {evt['name']}({_short(evt['input'])})")
    elif t == "tool_result":
        print(f"    ← {_short(evt['result'])}")
    elif t == "error":
        print(f"  ❌ {evt['message']}")


def _short(obj: Any, maxlen: int = 120) -> str:
    s = json.dumps(obj, ensure_ascii=False, default=str)
    return s if len(s) <= maxlen else s[:maxlen] + "..."
