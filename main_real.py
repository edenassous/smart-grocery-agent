"""
CLI חדש שמשתמש בנתונים האמיתיים (real_prices.db).
"""
from dotenv import load_dotenv
load_dotenv()

import sys
import json
import anthropic

import tools_real

MODEL = "claude-opus-4-7"
SYSTEM_PROMPT = """אתה עוזר חכם למציאת סלי קניה זולים, מבוסס מאגר מחירים אמיתי של 3 רשתות בישראל (רמי לוי, שופרסל, ויקטורי).

תהליך:
1. parse_shopping_list - לפרסר את בקשת המשתמש לרשימת פריטים בשמות כלליים.
2. לכל פריט, search_product - יחזיר עד 5 מוצרים תואמים עם מחירים מכל רשת.
3. בחר עבור כל פריט את המוצר המתאים ביותר (לרוב הראשון, אלא אם המשתמש ציין מותג).
4. optimize_basket - עם הברקודים שבחרת + הכמויות. הוא יחזיר את הפיצול הזול ביותר.
5. הצג את התוצאה: כמה סלים, מה בכל אחד, חיסכון מול קניה במקום אחד.

אם search_product לא מחזיר תוצאות לפריט מסוים - דווח על זה ונסה שם דומה (לדוגמה "חלב" במקום "חלב טרי")."""


def run_agent(user_message: str) -> None:
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": user_message}]

    for step in range(15):
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=tools_real.TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        for block in response.content:
            if block.type == "text" and block.text.strip():
                print(f"\n💭 {block.text}\n")

        if response.stop_reason == "end_turn":
            return

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    short = json.dumps(block.input, ensure_ascii=False)[:500]
                    print(f"  → {block.name}({short})")
                    result = tools_real.execute_tool(block.name, block.input)
                    short_r = json.dumps(result, ensure_ascii=False, default=str)[:120]
                    print(f"    ← {short_r}...")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })
            messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("שימוש: python main_real.py 'רשימת קניות'")
        sys.exit(1)
    run_agent(" ".join(sys.argv[1:]))
