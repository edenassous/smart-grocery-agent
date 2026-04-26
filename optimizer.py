"""
ILP solver לפיצול סל אופטימלי בין חנויות.
תומך ב-soft constraints: אם פריט לא ניתן לקנייה (בגלל סף הזמנה),
הוא יסומן כ-unfulfilled במקום להפיל את כל הפתרון.
"""
from dataclasses import dataclass, field
import pulp


@dataclass
class BasketItem:
    product_name: str
    quantity: float
    unit: str


@dataclass
class PriceOption:
    store_id: str
    price_per_unit: float


@dataclass
class StoreInfo:
    store_id: str
    store_name: str
    delivery_fee: float
    min_order: float


@dataclass
class OptimizationResult:
    total_cost: float
    items_cost: float
    delivery_cost: float
    baskets: dict[str, list[dict]]
    store_totals: dict[str, float]
    unfulfilled: list[str]
    feasible: bool = True
    infeasibility_reason: str | None = None


# קנס לפריט שלא הוקצה. גבוה מספיק כדי שתמיד עדיף לקנות אם אפשר.
SKIP_PENALTY = 10000.0


def optimize(
    basket: list[BasketItem],
    prices: dict[str, list[PriceOption]],
    stores: dict[str, StoreInfo],
) -> OptimizationResult:
    # --- פריטים שאין להם בכלל מחיר ---
    unfulfilled = [item.product_name for item in basket if not prices.get(item.product_name)]
    basket = [item for item in basket if prices.get(item.product_name)]

    if not basket:
        return OptimizationResult(0, 0, 0, {}, {}, unfulfilled)

    prob = pulp.LpProblem("basket_split", pulp.LpMinimize)

    # --- משתנים ---
    x = {}
    for i, item in enumerate(basket):
        for opt in prices[item.product_name]:
            x[(i, opt.store_id)] = pulp.LpVariable(
                f"x_{i}_{opt.store_id}", cat=pulp.LpBinary
            )
    y = {s: pulp.LpVariable(f"y_{s}", cat=pulp.LpBinary) for s in stores}
    skip = {i: pulp.LpVariable(f"skip_{i}", cat=pulp.LpBinary) for i in range(len(basket))}

    # --- מטרה: מינימום של מחירים + משלוח + קנס על skip ---
    items_cost = pulp.lpSum(
        opt.price_per_unit * basket[i].quantity * x[(i, opt.store_id)]
        for i, item in enumerate(basket)
        for opt in prices[item.product_name]
    )
    delivery_cost = pulp.lpSum(stores[s].delivery_fee * y[s] for s in stores)
    skip_cost = pulp.lpSum(SKIP_PENALTY * skip[i] for i in range(len(basket)))
    prob += items_cost + delivery_cost + skip_cost

    # --- אילוץ 1: כל פריט - או שנקנה פעם אחת, או שדולגנו עליו ---
    for i, item in enumerate(basket):
        prob += (
            pulp.lpSum(x[(i, opt.store_id)] for opt in prices[item.product_name])
            + skip[i] == 1,
            f"buy_or_skip_{i}",
        )

    # --- אילוץ 2: אם קונים מחנות, y=1 ---
    for (i, s), var in x.items():
        prob += var <= y[s], f"activate_{i}_{s}"

    # --- אילוץ 3: סף הזמנה מינימלי (רק אם החנות פעילה) ---
    for s, info in stores.items():
        store_subtotal = pulp.lpSum(
            opt.price_per_unit * basket[i].quantity * x[(i, opt.store_id)]
            for i, item in enumerate(basket)
            for opt in prices[item.product_name]
            if opt.store_id == s
        )
        prob += store_subtotal >= info.min_order * y[s], f"min_order_{s}"

    # --- פתרון ---
    solver = pulp.PULP_CBC_CMD(msg=False)
    status = prob.solve(solver)

    if status != pulp.LpStatusOptimal:
        return OptimizationResult(
            total_cost=0, items_cost=0, delivery_cost=0,
            baskets={}, store_totals={}, unfulfilled=unfulfilled,
            feasible=False,
            infeasibility_reason=f"Solver: {pulp.LpStatus[status]}",
        )

    # --- בניית התוצאה ---
    baskets: dict[str, list[dict]] = {}
    store_totals: dict[str, float] = {}
    items_total = 0.0

    for i, item in enumerate(basket):
        if pulp.value(skip[i]) > 0.5:
            unfulfilled.append(item.product_name)
            continue
        for opt in prices[item.product_name]:
            if pulp.value(x[(i, opt.store_id)]) > 0.5:
                line_total = round(opt.price_per_unit * item.quantity, 2)
                baskets.setdefault(opt.store_id, []).append({
                    "product": item.product_name,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "unit_price": opt.price_per_unit,
                    "line_total": line_total,
                })
                store_totals[opt.store_id] = round(
                    store_totals.get(opt.store_id, 0) + line_total, 2
                )
                items_total += line_total
                break

    delivery_total = sum(stores[s].delivery_fee for s in baskets.keys())

    return OptimizationResult(
        total_cost=round(items_total + delivery_total, 2),
        items_cost=round(items_total, 2),
        delivery_cost=round(delivery_total, 2),
        baskets=baskets,
        store_totals=store_totals,
        unfulfilled=unfulfilled,
    )
