#!/usr/bin/env python3
"""Calculate reconciled scheduling metrics from source and output records."""
import csv, json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DATA,OUT=ROOT/"data",ROOT/"outputs"
def read(p):
    with p.open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def run():
    exams=read(DATA/"exams.csv")
    rooms=read(DATA/"rooms.csv")
    invs=read(DATA/"invigilators.csv")
    assigned=read(OUT/"final_schedule.csv")
    unscheduled=read(OUT/"unscheduled_exams.csv")
    capacity=read(DATA/"room_capacity.csv")
    cap_by_room={x["room_id"]:int(x["capacity"]) for x in capacity}
    room_use=Counter(x["room_id"] for x in assigned)
    inv_use=Counter(x["invigilator_id"] for x in assigned)
    reasons=Counter(x["reason_code"] for x in unscheduled)
    metrics={
        "total_exams":len(exams),"assigned_exams":len(assigned),"unscheduled_exams":len(unscheduled),
        "completion_rate":round(len(assigned)/len(exams),4) if exams else 0,
        "unscheduled_reason_counts":dict(reasons),
        "rooms_used":len(room_use),"rooms_available":len(rooms),
        "room_slot_utilization":round(len(assigned)/(len(rooms)*20),4) if rooms else 0,
        "invigilators_used":len(inv_use),"invigilators_available":len(invs),
        "maximum_room_seat_utilization":round(max((int(a["enrolled_students"])/cap_by_room[a["room_id"]] for a in assigned),default=0),4),
        "assignment_rows_reconcile":len(assigned)+len(unscheduled)==len(exams),
        "unscheduled_reason_coverage":all(bool(x["reason_code"]) for x in unscheduled)
    }
    OUT.mkdir(exist_ok=True)
    (OUT/"metrics.json").write_text(json.dumps(metrics,indent=2),encoding="utf-8")
    print(json.dumps(metrics,indent=2))
if __name__=="__main__":run()
