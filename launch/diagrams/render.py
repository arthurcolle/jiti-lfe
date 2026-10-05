#!/usr/bin/env python3
"""Render the article's editable SVG diagrams and matching high-DPI PNGs.

Run from the repository with: devenv shell -- python3 launch/diagrams/render.py
The drawings use the same primitives for SVG and PNG; no image model is used.
"""

from __future__ import annotations

import glob
import html
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "launch/diagrams"
EXPORTS = ROOT / "artifacts/launch/diagrams"
W, SCALE = 680, 2
BG = "#FAFAF7"
PANEL = "#FFFFFF"
INK = "#182B2B"
MUTED = "#4C6060"
LINE = "#C9D5D1"
ACCENT = "#007E70"
TINT = "#E5F3EF"


def font_file(mono=False, bold=False):
    name = ("DejaVuSansMono" if mono else "DejaVuSans") + ("-Bold" if bold else "") + ".ttf"
    paths = glob.glob(f"/nix/store/*dejavu*/share/fonts/truetype/{name}")
    paths += glob.glob(f"/usr/share/fonts/truetype/dejavu/{name}")
    if not paths:
        raise RuntimeError(f"Missing font: {name}")
    return paths[0]


class Diagram:
    def __init__(self, name, title, desc, height):
        self.name, self.title, self.desc, self.height = name, title, desc, height
        self.im = Image.new("RGB", (W * SCALE, height * SCALE), BG)
        self.draw = ImageDraw.Draw(self.im)
        self.fonts = {}
        self.svg = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" viewBox="0 0 {W} {height}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{html.escape(title)}</title>',
            f'<desc id="desc">{html.escape(desc)}</desc>',
            f'<rect width="{W}" height="{height}" fill="{BG}"/>',
        ]

    def rect(self, x, y, w, h, fill=PANEL, stroke=LINE, radius=15, width=1.5):
        coords = tuple(round(v * SCALE) for v in (x, y, x+w, y+h))
        self.draw.rounded_rectangle(coords, radius=radius*SCALE, fill=fill,
                                    outline=stroke, width=round(width*SCALE))
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')

    def text(self, x, y, value, size=28, color=INK, mono=False, bold=False, align="start"):
        key = (size, mono, bold)
        if key not in self.fonts:
            self.fonts[key] = ImageFont.truetype(font_file(mono, bold), size * SCALE)
        font = self.fonts[key]
        measured = self.draw.textlength(value, font=font) / SCALE
        left = x - measured/2 if align == "middle" else x
        if left < 0 or left + measured > W:
            raise ValueError(f"Text extends past canvas: {value}")
        self.draw.text((x*SCALE, y*SCALE), value, font=font, fill=color,
                       anchor="ms" if align == "middle" else "ls")
        family = "DejaVu Sans Mono" if mono else "DejaVu Sans"
        weight = "bold" if bold else "normal"
        self.svg.append(f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" text-anchor="{align}" fill="{color}">{html.escape(value)}</text>')

    def line(self, points, color=ACCENT, width=2.5, arrow=False, dashed=False):
        scaled = [(round(x*SCALE), round(y*SCALE)) for x,y in points]
        if dashed:
            # All dashed paths in these drawings are straight vertical lines.
            (x,y1), (_,y2) = scaled
            for y in range(y1, y2, 14*SCALE):
                self.draw.line([(x,y), (x,min(y+7*SCALE,y2))], fill=color, width=round(width*SCALE))
        else:
            self.draw.line(scaled, fill=color, width=round(width*SCALE), joint="curve")
        dash = ' stroke-dasharray="7 7"' if dashed else ""
        self.svg.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"{dash}/>')
        if arrow:
            x,y = points[-1]
            px,py = points[-2]
            if y>py:
                tri=[(x-6,y-10),(x+6,y-10),(x,y)]
            elif y<py:
                tri=[(x-6,y+10),(x+6,y+10),(x,y)]
            elif x>px:
                tri=[(x-10,y-6),(x-10,y+6),(x,y)]
            else:
                tri=[(x+10,y-6),(x+10,y+6),(x,y)]
            self.draw.polygon([(a*SCALE,b*SCALE) for a,b in tri], fill=color)
            self.svg.append(f'<polygon points="{" ".join(f"{a},{b}" for a,b in tri)}" fill="{color}"/>')

    def header(self, number, heading, subheading):
        self.text(40, 49, f"{number:02d}  /  A LIVING LISP APPLICATION", 20, ACCENT, bold=True)
        self.text(40, 100, heading, 34, bold=True)
        self.text(40, 140, subheading, 24, MUTED)

    def save(self):
        SOURCES.mkdir(parents=True, exist_ok=True)
        EXPORTS.mkdir(parents=True, exist_ok=True)
        (SOURCES / f"{self.name}.svg").write_text("\n".join(self.svg+["</svg>"]) + "\n")
        self.im.save(EXPORTS/f"{self.name}.png", optimize=True)
        self.im.resize((375, round(self.height*375/W)), Image.Resampling.LANCZOS).save(EXPORTS/f"{self.name}-mobile.png")
        return {"id": self.name, "svg": f"launch/diagrams/{self.name}.svg",
                "png": f"artifacts/launch/diagrams/{self.name}.png",
                "width": W*SCALE, "height": self.height*SCALE,
                "alt": self.desc}


def growth():
    desc = "Four requests grow one running Lisp application. It starts with no expense functions. Record an expense adds add-expense; total my spending adds total-expenses; group by category adds spending-by-category; make a budget report adds budget-report. Each stage keeps the earlier functions."
    d = Diagram("01-growing-application", "An application grows by conversation", desc, 1170)
    d.header(1, "Ask. Add. Keep building.", "Four requests, one running application.")
    d.rect(40,176,600,86,fill=TINT,stroke=TINT)
    d.text(64,212,"START: NO EXPENSE FUNCTIONS",21,ACCENT,bold=True)
    d.text(64,245,"The runtime and an empty ledger exist.",24)
    stages = [
        (298,112,"Record an expense",["add-expense"]),
        (446,146,"Total my spending",["add-expense","total-expenses"]),
        (628,180,"Group by category",["add-expense","total-expenses","spending-by-category"]),
        (844,214,"Make a budget report",["add-expense","total-expenses","spending-by-category","budget-report"]),
    ]
    prior = 262
    for i,(y,h,request,functions) in enumerate(stages,1):
        d.line([(340,prior+8),(340,y-8)],arrow=True)
        d.rect(40,y,600,h)
        d.text(64,y+39,f"{i}.  {request}",28,bold=True)
        for j,name in enumerate(functions):
            new = j == len(functions)-1
            d.text(80,y+79+j*34,("+ " if new else "  ")+name,26,
                   ACCENT if new else MUTED,mono=True,bold=new)
        prior = y+h
    d.text(40,1111,"Earlier capabilities remain available.",26,bold=True)
    d.text(40,1148,"Request wording is condensed from the live run.",22,MUTED)
    out=d.save()
    out["caption"]="The application starts with an empty expense ledger and no expense functions. Four chat stages add real Lisp definitions to the same running application; each new capability joins the existing catalogue."
    return out


def composition():
    desc = "One shared ledger contains coffee at $4.50, groceries at $32.00 and transport at $18.00. Both total-expenses and spending-by-category read that ledger. Their results feed budget-report with a $60 budget, returning $54.50 spent, $5.50 remaining and a category breakdown. Values are stored as integer cents."
    d=Diagram("02-function-composition","New functions reuse earlier ones",desc,1055)
    d.header(2,"New capability. Same pieces.","Ordinary Lisp function composition.")
    d.rect(40,177,600,180,fill=TINT,stroke=TINT)
    d.text(64,217,"ONE SHARED LEDGER",22,ACCENT,bold=True)
    for i,(category,amount) in enumerate([("Coffee","$4.50"),("Groceries","$32.00"),("Transport","$18.00")]):
        d.text(64,258+i*35,category,26)
        d.text(478,258+i*35,amount,26,mono=True)
    # Two reads branch from the same ledger. The nodes are stacked for mobile.
    d.line([(88,357),(88,616)],width=2.5)
    d.line([(88,468),(140,468)],arrow=True)
    d.line([(88,616),(140,616)],arrow=True)
    d.rect(140,410,500,116)
    d.text(164,452,"total-expenses",28,ACCENT,mono=True,bold=True)
    d.text(164,494,"Returns 5450 cents",26)
    d.rect(140,558,500,116)
    d.text(164,600,"spending-by-category",25,ACCENT,mono=True,bold=True)
    d.text(164,642,"Returns the category totals",25)
    # A second trunk collects outputs; it is visually separate from ledger reads.
    d.line([(640,468),(659,468),(659,727),(340,727),(340,762)],arrow=True)
    d.line([(640,616),(659,616)])
    d.text(140,707,"Both results feed the report",22,MUTED)
    d.rect(40,770,600,220,fill=TINT,stroke=ACCENT)
    d.text(64,813,"(budget-report 6000)",28,ACCENT,mono=True,bold=True)
    d.text(64,857,"Budget",25,MUTED)
    d.text(424,857,"$60.00",29,bold=True)
    d.text(64,900,"Spent",25,MUTED)
    d.text(424,900,"$54.50",29,bold=True)
    d.text(64,943,"Remaining",25,MUTED)
    d.text(424,943,"$5.50",29,ACCENT,bold=True)
    d.text(40,1030,"The report also includes the category breakdown.",22,MUTED)
    out=d.save()
    out["caption"]="The generated budget-report calls total-expenses and spending-by-category. Both read the existing ledger. The code stores integer cents; the diagram formats those amounts as dollars."
    return out


def repair():
    desc = "Scripted repair demonstration. The worker enters render-budget-report version 1, then pauses when its category helper fails on transport. The original frame and retry-category restart remain live. The controller requests new helper and report definitions; the same worker evaluates the repairs while the original frame remains active. The controller asks to resume retry-category. The original call returns v1-active-frame with entry count 1. Only the next call enters v2-new-frame and increments the count to 2. The repair and original evaluation share a transaction."
    d=Diagram("03-paused-call-repair","Repair without replaying the report",desc,1440)
    d.header(3,"Repair the paused call.","Scripted demonstration of a live restart.")
    cards=[
        (178,138,"WORKER · ENTER ORIGINAL REPORT",["render-budget-report v1","Entry count becomes 1."],False),
        (354,152,"WORKER · PAUSED ON A CONDITION",["Helper fails on :transport.","Original frame + restart stay live."],True),
        (544,132,"CONTROLLER → WORKER",["Define the repaired helper","and a replacement report v2."],False),
        (714,132,"WORKER · STILL IN THE SAME PAUSE",["Evaluate both new definitions.","The original v1 frame remains."],True),
        (884,104,"CONTROLLER → WORKER",["Resume retry-category."],False),
        (1026,136,"WORKER · ORIGINAL CALL RETURNS",["v1-active-frame","Entry count: 1"],True),
        (1228,124,"WORKER · NEXT CALL",["v2-new-frame","Entry count: 2"],False),
    ]
    previous=None
    for y,h,role,lines,accent in cards:
        if previous:
            d.line([(340,previous+8),(340,y-8)],arrow=True,dashed=y==1228)
        d.rect(40,y,600,h,fill=TINT if accent else PANEL,stroke=ACCENT if accent else LINE)
        d.text(64,y+36,role,20,ACCENT,bold=True)
        for j,line in enumerate(lines):
            mono=line.startswith(("render-","v1-","v2-"))
            d.text(64,y+78+j*35,line,25 if mono else 26,mono=mono,bold=mono)
        previous=y+h
    d.text(40,1390,"Original evaluation + repairs = one transaction",22,MUTED)
    d.text(40,1426,"An active frame keeps its original body.",22,MUTED)
    out=d.save()
    out["caption"]="In the scripted repair, the worker retains the original report frame and its active restart while accepting repair actions from the controller. Retrying the helper completes that original call; the replacement report body is used by the next call."
    return out


def persistence():
    desc = "Accepted managed function definitions and data are saved as revisions. A fresh process loads an accepted revision and can call those functions with their saved data; live stacks are not saved. The rollback example preserves revisions 1, 2 and 3, then publishes revision 4 containing the managed state from revision 1. Revision 4 follows revision 3 in history, so intermediate accepted revisions remain available. Revision numbers shown are illustrative."
    d=Diagram("04-recovery-and-rollback","Code and data survive; history stays",desc,1242)
    d.header(4,"Keep the state. Keep history.","Managed recovery and explicit rollback.")
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
    d.text(64,574,"Load the revision. Call the report.",25)
    d.text(64,611,"$54.50 spent · $5.50 remaining",27,bold=True)
    d.text(40,683,"Live stacks are not persisted.",25,MUTED)
    d.line([(40,719),(640,719)],LINE,width=1.5)
    d.text(40,770,"ROLLBACK APPENDS A REVISION",22,ACCENT,bold=True)
    d.text(40,811,"Restore earlier state; retain every revision.",24)
    # Single vertical history avoids the common misleading backward CURRENT arrow.
    steps=[(851,"R1","Earlier accepted state",False),
           (931,"R2","Later accepted state",False),
           (1011,"R3","Current before rollback",False),
           (1091,"R4","Restored state from R1",True)]
    for i,(y,rev,label,accent) in enumerate(steps):
        if i:
            d.line([(82,y-13),(82,y-4)],arrow=True)
        d.rect(40,y,600,65,fill=TINT if accent else PANEL,stroke=ACCENT if accent else LINE,radius=12)
        d.text(62,y+42,rev,25,ACCENT,bold=True,mono=True)
        d.text(145,y+42,label,25,bold=accent)
    d.text(40,1198,"R4 follows R3. R1, R2 and R3 remain in history.",22,MUTED)
    d.text(40,1230,"Revision numbers here are illustrative.",20,MUTED)
    out=d.save()
    out["caption"]="Recovery restores accepted managed code and data into a fresh process, not a suspended stack. A rollback publishes the earlier state as a new revision after the current one, preserving all intervening accepted history."
    return out


def main():
    records=[growth(),composition(),repair(),persistence()]
    (SOURCES/"manifest.json").write_text(json.dumps({"schema_version":1,"diagrams":records},indent=2)+"\n")
    thumbs=[]
    for rec in records:
        im=Image.open(ROOT/rec["png"])
        im.thumbnail((340,740),Image.Resampling.LANCZOS)
        thumbs.append(im)
    sheet=Image.new("RGB",(720, max(im.height for im in thumbs[:2])+max(im.height for im in thumbs[2:])+60),"#E5EAE7")
    y=20
    for row in (thumbs[:2],thumbs[2:]):
        for i,im in enumerate(row): sheet.paste(im,(20+i*350,y))
        y+=max(im.height for im in row)+20
    sheet.save(EXPORTS/"contact-sheet.png")
    print(json.dumps({"diagrams":len(records),"manifest":str(SOURCES/"manifest.json"),"exports":str(EXPORTS)},indent=2))


if __name__=="__main__":
    main()
