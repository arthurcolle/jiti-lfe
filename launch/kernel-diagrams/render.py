#!/usr/bin/env python3
"""Render generic kernel figures using the established article drawing primitives.

Run: devenv shell -- python3 launch/kernel-diagrams/render.py
The SVG sources and PNG exports are produced from the same drawing commands.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "launch/kernel-diagrams"
EXPORTS = ROOT / "artifacts/launch/kernel-diagrams"
spec = importlib.util.spec_from_file_location("article_diagrams", ROOT / "launch/diagrams/render.py")
base = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(base)
base.SOURCES, base.EXPORTS = SOURCES, EXPORTS
ACCENT, TINT, PANEL, LINE, MUTED = base.ACCENT, base.TINT, base.PANEL, base.LINE, base.MUTED


class Diagram(base.Diagram):
    def save(self, key, caption):
        record = super().save()
        record.update(key=key, svg=f"launch/kernel-diagrams/{self.name}.svg",
                      png=f"artifacts/launch/kernel-diagrams/{self.name}.png",
                      mobile_png=f"artifacts/launch/kernel-diagrams/{self.name}-mobile.png",
                      caption=caption)
        return record


def conversation():
    desc = (
        "A request to add a capability goes to an external language model with instructions, "
        "registered tool descriptions and observed application state. The model requests a tool "
        "call. The controller validates and routes it to the persistent worker, which evaluates "
        "Lisp in the running application. Actual values, checks or a live pause return through "
        "the controller to inform the next model step. Accepted definitions and managed data "
        "remain available for later requests. Ordinary Lisp function calls do not require inference."
    )
    d = Diagram("01-conversation-and-lisp", "Conversation changes the running application", desc, 1280)
    d.header(1, "Chat becomes running code.", "The model proposes. The Lisp image executes.")
    d.rect(40,178,600,104,fill=TINT,stroke=TINT)
    d.text(64,216,"YOU · ASK FOR A CAPABILITY",21,ACCENT,bold=True)
    d.text(64,255,'“Add a function that does this.”',27)
    d.line([(340,290),(340,320)],arrow=True)
    d.rect(40,328,600,158)
    d.text(64,367,"MODEL SERVICE · OUTSIDE LISP",21,ACCENT,bold=True)
    d.text(64,409,"Instructions + registered tools",26)
    d.text(64,449,"Observed state + conversation",26)
    d.text(40,523,"Requests a registered tool call",23,MUTED)
    d.line([(340,535),(340,557)],arrow=True)
    d.rect(40,565,600,106)
    d.text(64,604,"CONTROLLER",21,ACCENT,bold=True)
    d.text(64,644,"Validate arguments. Route the action.",25)
    d.line([(340,679),(340,709)],arrow=True)
    d.rect(40,717,600,167,fill=TINT,stroke=ACCENT)
    d.text(64,756,"PERSISTENT LISP WORKER",21,ACCENT,bold=True)
    d.text(64,797,"Inspect, define, call or repair functions.",25)
    d.text(64,839,"Use the application's existing state.",25)
    d.line([(340,892),(340,921)],arrow=True)
    d.rect(40,929,600,117)
    d.text(64,968,"ACTUAL RESULTS → CONTROLLER",20,ACCENT,bold=True)
    d.text(64,1010,"Values, checks or a live pause",26)
    d.line([(640,986),(659,986),(659,406),(641,406)],arrow=True)
    d.text(40,1094,"Results guide the next model step.",26,bold=True)
    d.text(40,1140,"Accepted code + data stay in the application.",24)
    d.text(40,1182,"The next request builds on what exists.",24)
    d.line([(40,1210),(640,1210)],LINE,width=1.5)
    d.text(40,1251,"Ordinary Lisp calls do not require inference.",24,MUTED)
    return d.save("conversation", "The language model uses registered tools to inspect and change a running Lisp application. Actual worker results inform its next step; accepted functions and managed data remain available for later requests. Once defined, functions execute as ordinary Lisp.")


def kernel():
    desc = (
        "The controller validates tool arguments and sends actions one at a time to a persistent "
        "worker, receiving observations and results in return. The worker owns evaluation, "
        "the live stack and active restarts. Inside that worker, the world adapter provides "
        "managed code and data, the function catalogue, checkpoint and restore, and durable "
        "export and import. Caller-supplied safety checks and goals are assessed at safe points. "
        "Safety determines whether a candidate may be kept; goals determine completion. "
        "Accepted managed changes publish durable revisions. The reference adapter covers "
        "named functions and readable table data."
    )
    d = Diagram("02-kernel-ownership", "The kernel keeps execution and acceptance coherent", desc, 1410)
    d.header(2, "One worker owns the world.", "A small protocol around a live Lisp application.")
    d.rect(40,178,600,117)
    d.text(64,219,"CONTROLLER",22,ACCENT,bold=True)
    d.text(64,260,"Validate arguments. Route actions serially.",24)
    d.line([(248,303),(248,400)],arrow=True)
    d.line([(437,400),(437,303)],arrow=True)
    d.text(62,356,"Actions",23,MUTED)
    d.text(458,356,"Results",23,MUTED)
    d.rect(40,408,600,753,fill=TINT,stroke=ACCENT)
    d.text(64,451,"PERSISTENT WORKER",23,ACCENT,bold=True)
    d.text(64,488,"Owns live application operations",25)
    d.rect(64,522,552,135)
    d.text(86,561,"LISP EVALUATION",21,ACCENT,bold=True)
    d.text(86,601,"Running code + live call stack",25)
    d.text(86,636,"Active restarts stay on this thread.",24)
    d.rect(64,683,552,177)
    d.text(86,722,"WORLD ADAPTER",21,ACCENT,bold=True)
    d.text(86,762,"Managed code, data and catalogue",25)
    d.text(86,800,"Checkpoint / restore",25)
    d.text(86,838,"Durable export / import",25)
    d.rect(64,886,552,236)
    d.text(86,925,"CALLER CHECKS · AT SAFE POINTS",20,ACCENT,bold=True)
    d.text(86,970,"Safety",26,bold=True)
    d.text(86,1006,"May this candidate be kept?",25)
    d.text(86,1048,"Goals",26,bold=True)
    d.text(86,1084,"Is the requested work complete?",25)
    d.line([(590,1169),(590,1232)],arrow=True)
    d.text(64,1205,"Accepted managed changes",23,MUTED)
    d.rect(40,1240,600,103)
    d.text(64,1280,"DURABLE REVISION STORE",21,ACCENT,bold=True)
    d.text(64,1318,"Accepted code + data, with history",25)
    d.text(40,1387,"The adapter defines what can be restored.",24,MUTED)
    return d.save("composition", "The controller routes actions; the persistent worker owns evaluation and live restarts. Its world adapter defines the managed resources, catalogue and recovery hooks. Caller safety checks govern acceptance while goals describe completion. Accepted managed changes become durable revisions.")


def repair():
    desc = (
        "Generic labels describe the scripted live repair demonstration. A worker enters "
        "application function version 1 and increments its entry count to 1. A helper fails; "
        "the original frame and restart remain live. The controller requests repaired helper "
        "and replacement function definitions. The same worker evaluates both while paused. "
        "The controller then requests the live restart. The original version 1 frame completes "
        "with entry count 1; the next invocation enters version 2 and increments the count to 2. "
        "Original evaluation and repairs share one transaction."
    )
    d = Diagram("03-paused-function-repair", "Repair a helper while its caller is paused", desc, 1450)
    d.header(3, "Keep the call. Repair the code.", "A live restart, illustrated by the scripted demo.")
    cards=[
        (178,138,"WORKER · ENTER FUNCTION v1",["Original call begins.","Entry count becomes 1."],False),
        (354,152,"WORKER · PAUSED ON A CONDITION",["A helper fails.","Original frame + restart stay live."],True),
        (544,132,"CONTROLLER → WORKER",["Define the repaired helper","and replacement function v2."],False),
        (714,132,"WORKER · STILL IN THE SAME PAUSE",["Evaluate both new definitions.","The original v1 frame remains."],True),
        (884,104,"CONTROLLER → WORKER",["Invoke the live restart."],False),
        (1026,136,"WORKER · ORIGINAL CALL COMPLETES",["v1-active-frame","Entry count: 1"],True),
        (1228,124,"WORKER · NEXT INVOCATION",["v2-new-frame","Entry count: 2"],False),
    ]
    previous=None
    for y,h,role,lines,accent in cards:
        if previous:
            d.line([(340,previous+8),(340,y-8)],arrow=True,dashed=y==1228)
        d.rect(40,y,600,h,fill=TINT if accent else PANEL,stroke=ACCENT if accent else LINE)
        d.text(64,y+36,role,20,ACCENT,bold=True)
        for j,line in enumerate(lines):
            mono=line.startswith(("v1-","v2-"))
            d.text(64,y+78+j*35,line,25 if mono else 26,mono=mono,bold=mono)
        previous=y+h
    d.text(40,1392,"Original evaluation + repairs = one transaction",22,MUTED)
    d.text(40,1429,"An active frame keeps its original body.",23,MUTED)
    return d.save("repair", "The scripted capture demonstrates this protocol; function labels are generalized here. The worker evaluates repairs while retaining the original call and its live restart. Retrying the repaired helper completes the original frame. The replacement top-level function body is used by the next invocation.")


def persistence():
    desc = (
        "Accepted managed function definitions and data are saved as durable revisions. "
        "A fresh process imports the accepted revision; recovered functions are callable with "
        "their saved data. Live call stacks and chat memory are not part of this recovery. "
        "The rollback example preserves revisions 1, 2 and 3, then publishes revision 4 "
        "containing the managed state from revision 1. Revision 4 follows revision 3 in "
        "history, preserving intervening accepted states. Revision numbers are illustrative."
    )
    d = Diagram("04-recovery-and-history", "Accepted code and data survive the process", desc, 1264)
    d.header(4, "Keep the state. Keep history.", "Managed recovery and explicit rollback.")
    d.rect(40,178,600,112)
    d.text(64,219,"ACCEPTED APPLICATION STATE",21,ACCENT,bold=True)
    d.text(64,261,"Function definitions + managed data",25)
    d.line([(340,298),(340,329)],arrow=True)
    d.rect(40,337,600,105,fill=TINT,stroke=ACCENT)
    d.text(64,378,"SAVED REVISION",21,ACCENT,bold=True)
    d.text(64,419,"Durable code and data",27)
    d.line([(340,450),(340,482)],arrow=True)
    d.rect(40,490,600,150)
    d.text(64,532,"FRESH PROCESS",21,ACCENT,bold=True)
    d.text(64,574,"Load the accepted revision.",26)
    d.text(64,611,"Call the recovered functions.",27,bold=True)
    d.text(40,681,"Live stacks are not persisted.",25,MUTED)
    d.text(40,717,"Chat memory is separate from application state.",22,MUTED)
    d.line([(40,747),(640,747)],LINE,width=1.5)
    d.text(40,790,"ROLLBACK APPENDS A REVISION",22,ACCENT,bold=True)
    d.text(40,831,"Restore earlier state; retain every revision.",24)
    steps=[(871,"R1","Earlier accepted state",False),
           (951,"R2","Later accepted state",False),
           (1031,"R3","Current before rollback",False),
           (1111,"R4","Restored state from R1",True)]
    for i,(y,rev,label,accent) in enumerate(steps):
        if i:
            d.line([(82,y-13),(82,y-4)],arrow=True)
        d.rect(40,y,600,65,fill=TINT if accent else PANEL,stroke=ACCENT if accent else LINE,radius=12)
        d.text(62,y+42,rev,25,ACCENT,bold=True,mono=True)
        d.text(145,y+42,label,25,bold=accent)
    d.text(40,1220,"R4 follows R3. R1, R2 and R3 remain in history.",22,MUTED)
    d.text(40,1252,"Revision numbers here are illustrative.",20,MUTED)
    return d.save("persistence", "Recovery imports accepted managed code and data into a fresh process; it does not resume an old stack or restore model conversation memory. Explicit rollback publishes an earlier managed state as a new revision, preserving intervening history.")


def main():
    records=[conversation(),kernel(),repair(),persistence()]
    (SOURCES/"manifest.json").write_text(json.dumps({"schema_version":1,"diagrams":records},indent=2)+"\n")
    thumbs=[]
    for rec in records:
        im=Image.open(ROOT/rec["png"])
        im.thumbnail((340,740),Image.Resampling.LANCZOS)
        thumbs.append(im)
    sheet=Image.new("RGB",(720,max(im.height for im in thumbs[:2])+max(im.height for im in thumbs[2:])+60),"#E5EAE7")
    y=20
    for row in (thumbs[:2],thumbs[2:]):
        for i,im in enumerate(row):
            sheet.paste(im,(20+i*350,y))
        y+=max(im.height for im in row)+20
    sheet.save(EXPORTS/"contact-sheet.png")
    print(json.dumps({"diagrams":len(records),"manifest":str(SOURCES/"manifest.json"),"exports":str(EXPORTS)},indent=2))


if __name__ == "__main__":
    main()
