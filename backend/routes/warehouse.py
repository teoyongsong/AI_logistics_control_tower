from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

router = APIRouter()

class PickTask(BaseModel):
    item_id: str
    aisle: int
    shelf: int
    demand_score: float = 0.5


class PickingRequest(BaseModel):
    picker_start_aisle: int
    tasks: List[PickTask]


@router.post("/optimize")
def warehouse_picking(request: PickingRequest):
    sorted_tasks = sorted(
        request.tasks,
        key=lambda t: (abs(t.aisle - request.picker_start_aisle), -t.demand_score, t.shelf),
    )
    optimized_sequence = [f"Aisle {t.aisle} / Shelf {t.shelf} / Item {t.item_id}" for t in sorted_tasks]
    high_demand_zones = sorted({f"Aisle {t.aisle}" for t in request.tasks if t.demand_score >= 0.8})

    walk_reduction = min(35, 8 + len(request.tasks) * 2)
    return {
        "optimized_sequence": optimized_sequence,
        "high_demand_zones": high_demand_zones,
        "estimated_walk_reduction_pct": walk_reduction,
        "explainability": {
            "inputs": {
                "picker_start_aisle": request.picker_start_aisle,
                "tasks_count": len(request.tasks),
            },
            "components": {
                "sorting_rule": "closest_aisle_then_high_demand_then_shelf",
                "high_demand_zone_count": len(high_demand_zones),
                "estimated_walk_reduction_pct": walk_reduction,
            },
            "formula": "min(35, 8 + tasks_count*2)",
            "thresholds": {
                "high_demand_cutoff": 0.8,
                "walk_reduction_cap_pct": 35,
            },
        },
    }
