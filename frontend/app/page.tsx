"use client";

import { useState, useRef, useEffect } from "react";

// ---------- Types שמגיעים מה-backend (agent.py) ----------
type AgentEvent =
  | { type: "start"; message: string; region: string }
  | { type: "text"; text: string }
  | { type: "tool_call"; id: string; name: string; input: any }
  | { type: "tool_result"; id: string; name: string; result: any }
  | { type: "final"; answer: string; optimization: Optimization | null }
  | { type: "error"; message: string }
  | { type: "done" };

type Optimization = {
  feasible: boolean;
  infeasibility_reason?: string | null;
  total_cost: number;
  items_cost: number;
  delivery_cost: number;
  baskets: Record<string, BasketLine[]>;
  store_totals: Record<string, number>;
  unfulfilled: string[];
};

type BasketLine = {
  product: string;
  quantity: number;
  unit: string;
  unit_price: number;
  line_total: number;
};

// תיאור ידידותי של כל כלי, להצגה ב-UI
const TOOL_LABELS: Record<string, string> = {
  parse_shopping_list: "מפרסר רשימת קניות",
  search_product: "מחפש",
  get_delivery_info: "בודק משלוח",
  optimize_basket: "מחשב פיצול אופטימלי",
};

const REGIONS: Array<{ value: string; label: string }> = [
  { value: "tel_aviv", label: "תל אביב" },
  { value: "haifa", label: "חיפה" },
  { value: "jerusalem", label: "ירושלים" },
  { value: "beer_sheva", label: "באר שבע" },
];

export default function Page() {
  const [message, setMessage] = useState(
    "אני צריך 5 קילו עגבניות, 3 קילו מלפפונים, 2 קילו פלפל אדום, 3 קילו בצל, 5 קילו תפוחי אדמה, 2 חסה, 1.5 קילו ברוקולי"
  );
  const [region, setRegion] = useState("tel_aviv");
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [running, setRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // scroll אוטומטי כשמגיעים events חדשים
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  async function handleSubmit() {
    if (running || !message.trim()) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setEvents([]);
    setRunning(true);

    try {
      const resp = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, region }),
        signal: controller.signal,
      });

      if (!resp.ok || !resp.body) {
        throw new Error(`HTTP ${resp.status}`);
      }

      // קריאת stream ופירוק SSE
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE: כל אירוע מסתיים ב-"\n\n". יכולים להגיע כמה במקטע אחד.
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          const payload = line.slice(5).trim();
          try {
            const evt = JSON.parse(payload) as AgentEvent;
            setEvents((prev) => [...prev, evt]);
          } catch {
            console.warn("לא הצלחתי לפרסר SSE:", payload);
          }
        }
      }
    } catch (e: any) {
      if (e.name !== "AbortError") {
        setEvents((prev) => [...prev, { type: "error", message: e.message }]);
      }
    } finally {
      setRunning(false);
    }
  }

  function handleStop() {
    abortRef.current?.abort();
    setRunning(false);
  }

  // מחלץ את ה-event הסופי אם יש, כדי להציג את הסלים בצורה יפה
  const finalEvent = events.find((e) => e.type === "final") as
    | Extract<AgentEvent, { type: "final" }>
    | undefined;

  return (
    <main className="max-w-4xl mx-auto p-6">
      <header className="mb-6">
        <h1 className="text-3xl font-bold text-stone-800">🥬 סל הירקות הזול</h1>
        <p className="text-stone-600 mt-1">
          סוכן AI שמשווה מחירים בין חנויות, ומחליט אם כדאי לפצל להזמנה אחת או יותר.
        </p>
      </header>

      {/* Form */}
      <section className="bg-white rounded-xl border border-stone-200 p-5 shadow-sm">
        <label className="block text-sm font-medium text-stone-700 mb-2">
          רשימת קניות (טקסט חופשי)
        </label>
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          disabled={running}
          rows={3}
          className="w-full rounded-lg border border-stone-300 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:bg-stone-50"
          placeholder="למשל: 2 קילו עגבניות, חסה, ו-5 פלפלים..."
        />

        <div className="mt-3 flex flex-wrap items-center gap-3">
          <label className="text-sm font-medium text-stone-700">אזור:</label>
          <select
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            disabled={running}
            className="rounded-lg border border-stone-300 p-2 text-sm disabled:bg-stone-50"
          >
            {REGIONS.map((r) => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>

          <div className="flex-1" />

          {running ? (
            <button
              onClick={handleStop}
              className="px-4 py-2 bg-stone-200 hover:bg-stone-300 rounded-lg text-sm font-medium"
            >
              עצור
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={!message.trim()}
              className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-stone-300 text-white rounded-lg text-sm font-medium"
            >
              מצא לי סל זול
            </button>
          )}
        </div>
      </section>

      {/* Progress stream */}
      {events.length > 0 && (
        <section className="mt-6 bg-white rounded-xl border border-stone-200 shadow-sm">
          <div className="px-5 py-3 border-b border-stone-200 text-sm font-medium text-stone-700">
            התקדמות הסוכן
          </div>
          <div
            ref={scrollRef}
            className="progress-scroll max-h-64 overflow-y-auto px-5 py-3 text-sm space-y-1.5"
          >
            {events.map((evt, i) => (
              <EventLine key={i} evt={evt} />
            ))}
            {running && (
              <div className="text-stone-500 italic flex items-center gap-2">
                <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                עובד...
              </div>
            )}
          </div>
        </section>
      )}

      {/* Final result */}
      {finalEvent && finalEvent.optimization && (
        <ResultPanel optimization={finalEvent.optimization} answer={finalEvent.answer} />
      )}
    </main>
  );
}

function EventLine({ evt }: { evt: AgentEvent }) {
  switch (evt.type) {
    case "start":
      return <div className="text-stone-500">▶️ מתחיל חיפוש עבור אזור {evt.region}</div>;

    case "text":
      if (!evt.text.trim()) return null;
      return <div className="text-stone-700">💭 {evt.text}</div>;

    case "tool_call": {
      const label = TOOL_LABELS[evt.name] ?? evt.name;
      const detail = describeToolInput(evt.name, evt.input);
      return (
        <div className="text-stone-700">
          <span className="text-emerald-700">→</span> {label}
          {detail && <span className="text-stone-500"> · {detail}</span>}
        </div>
      );
    }

    case "tool_result":
      return null; // לא נציג את כל ה-JSON ב-UI, זה רעש

    case "error":
      return <div className="text-red-600">❌ {evt.message}</div>;

    case "final":
      return <div className="text-emerald-700 font-medium">✓ סיימתי!</div>;

    case "done":
      return null;
  }
}

function describeToolInput(name: string, input: any): string {
  if (name === "search_product") return `${input.product_name}`;
  if (name === "get_delivery_info") return `${input.store_id}`;
  if (name === "optimize_basket") {
    const n = Array.isArray(input.basket) ? input.basket.length : 0;
    return `${n} פריטים`;
  }
  return "";
}

function ResultPanel({
  optimization,
  answer,
}: {
  optimization: Optimization;
  answer: string;
}) {
  if (!optimization.feasible) {
    return (
      <section className="mt-6 bg-amber-50 border border-amber-200 rounded-xl p-5">
        <div className="font-medium text-amber-900">לא נמצא פתרון</div>
        <p className="text-sm text-amber-800 mt-1">
          {optimization.infeasibility_reason ?? "סיבה לא ידועה"}
        </p>
      </section>
    );
  }

  const basketEntries = Object.entries(optimization.baskets);

  return (
    <section className="mt-6 space-y-4">
      {/* סיכום כללי */}
      <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5">
        <div className="flex items-baseline gap-3">
          <div className="text-3xl font-bold text-emerald-900">
            {optimization.total_cost.toFixed(2)}₪
          </div>
          <div className="text-sm text-emerald-800">
            (מוצרים {optimization.items_cost.toFixed(2)}₪ + משלוח {optimization.delivery_cost.toFixed(2)}₪)
          </div>
        </div>
        <div className="text-sm text-emerald-700 mt-1">
          {basketEntries.length === 1 ? "סל אחד" : `${basketEntries.length} סלים נפרדים`}
        </div>
      </div>

      {/* סלים */}
      <div className="grid md:grid-cols-2 gap-4">
        {basketEntries.map(([storeId, items]) => (
          <div key={storeId} className="bg-white rounded-xl border border-stone-200 p-4 shadow-sm">
            <div className="flex items-baseline justify-between border-b border-stone-100 pb-2 mb-3">
              <div className="font-semibold text-stone-800">{storeId}</div>
              <div className="text-sm text-stone-600">
                {optimization.store_totals[storeId].toFixed(2)}₪
              </div>
            </div>
            <ul className="space-y-1.5 text-sm">
              {items.map((item, i) => (
                <li key={i} className="flex justify-between">
                  <span className="text-stone-700">
                    {item.quantity} {item.unit === "kg" ? "ק״ג" : "יח׳"} {item.product}
                  </span>
                  <span className="text-stone-500 tabular-nums">
                    {item.line_total.toFixed(2)}₪
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* פריטים שלא נמצאו */}
      {optimization.unfulfilled.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm">
          <span className="font-medium text-amber-900">לא נמצאו: </span>
          <span className="text-amber-800">{optimization.unfulfilled.join(", ")}</span>
        </div>
      )}

      {/* הסבר מילולי של ה-agent */}
      {answer && (
        <details className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-sm">
          <summary className="cursor-pointer font-medium text-stone-700">
            ההסבר של הסוכן
          </summary>
          <p className="mt-2 text-stone-700 whitespace-pre-wrap">{answer}</p>
        </details>
      )}
    </section>
  );
}
