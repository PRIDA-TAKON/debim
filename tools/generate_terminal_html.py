import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console(record=True, width=100)

# Simulate terminal prompt
def prompt(cmd: str):
    p = Text()
    p.append("user@ai-workstation", style="bold green")
    p.append(":", style="white")
    p.append("~/debim", style="bold blue")
    p.append("$ ", style="bold white")
    p.append(cmd, style="bold yellow")
    console.print(p)

console.print()
prompt("debim validate -m examples/openbim_duplex/project.yaml")

# Validation summary
v_table = Table(title="[bold cyan]debim Validation Engine (Deterministic IFC4 Rules)[/bold cyan]", box=None)
v_table.add_column("Category", style="bold white")
v_table.add_column("Rule / Check", style="cyan")
v_table.add_column("Status", justify="right")

v_table.add_row("Grid Consistency", "Cartesian 3D orthogonal coordinate resolution", "[bold green]PASSED[/bold green] (0.01s)")
v_table.add_row("Storey Heights", "Elevation continuity & vertical bounds", "[bold green]PASSED[/bold green] (0.01s)")
v_table.add_row("Dual Representation", "Primitive solids + baked asset links", "[bold green]PASSED[/bold green] (0.02s)")
v_table.add_row("MEP Distribution", "Port connectivity & 3D drop alignment", "[bold green]PASSED[/bold green] (0.03s)")
console.print(Panel(v_table, border_style="green", title="[bold green]Model Integrity: 100% Validated[/bold green]"))

console.print()
prompt("debim qto -m examples/townhouse/project.yaml")

# QTO Table
qto_table = Table(title="Quantitative Take-Off (QTO) Summary", show_header=True, header_style="bold magenta")
qto_table.add_column("Tag", style="cyan")
qto_table.add_column("Class", style="green")
qto_table.add_column("Material", style="yellow")
qto_table.add_column("Concrete Vol (m3)", justify="right", style="white")
qto_table.add_column("Formwork Area (m2)", justify="right", style="white")
qto_table.add_column("Rebar Weight (kg)", justify="right", style="white")

qto_table.add_row("C-A1", "IfcColumn", "CONC_240", "0.140", "2.800", "26.354")
qto_table.add_row("B-A1_B1", "IfcBeam", "CONC_240", "0.320", "4.000", "58.384")
qto_table.add_row("W-A1_A2", "IfcWall", "AAC_75", "1.027", "27.400", "0.000")
qto_table.add_row("D1", "IfcDoor", "WOOD_TEAK", "0.000", "0.000", "0.000")
qto_table.add_row("ST-01", "IfcStair", "CONC_240", "0.850", "6.200", "42.150")

console.print(qto_table)

totals_panel = Panel(
    "[bold white]Total Concrete Volume:[/bold white] 2.337 m3   |   "
    "[bold white]Total Formwork Area:[/bold white] 40.400 m2   |   "
    "[bold white]Total Rebar Weight:[/bold white] 126.888 kg",
    title="[bold cyan]QTO Totals Summary[/bold cyan]",
    border_style="cyan"
)
console.print(totals_panel)

console.print()
prompt("debim cost -m examples/townhouse/project.yaml -p prices.yaml")
console.print("[bold green]✓[/bold green] Cost estimation completed: [bold white]dist/boq.csv[/bold white] (MasterFormat & UniFormat aligned)")
console.print("[bold green]✓[/bold green] Total Estimated Project Cost: [bold yellow]฿ 486,250.00 THB[/bold yellow]")

html_content = console.export_html(inline_styles=True)

# Add sleek mac/dark terminal window decoration
terminal_wrapper = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{
    background-color: #121316;
    margin: 0;
    padding: 24px;
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100vh;
    box-sizing: border-box;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
  }}
  .window {{
    width: 100%;
    max-width: 1100px;
    background-color: #1e1e24;
    border-radius: 10px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.1);
    overflow: hidden;
  }}
  .title-bar {{
    background: #282a36;
    padding: 12px 16px;
    display: flex;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }}
  .buttons {{
    display: flex;
    gap: 8px;
    margin-right: 16px;
  }}
  .dot {{
    width: 12px;
    height: 12px;
    border-radius: 50%;
  }}
  .red {{ background: #ff5f56; }}
  .yellow {{ background: #ffbd2e; }}
  .green {{ background: #27c93f; }}
  .title {{
    color: #a0a0a8;
    font-size: 13px;
    font-weight: 500;
    flex-grow: 1;
    text-align: center;
    padding-right: 60px;
  }}
  .terminal-body {{
    padding: 20px;
    background: #181920;
    overflow: hidden;
  }}
  pre {{
    margin: 0;
    line-height: 1.35;
    font-size: 13.5px;
  }}
</style>
</head>
<body>
  <div class="window">
    <div class="title-bar">
      <div class="buttons">
        <div class="dot red"></div>
        <div class="dot yellow"></div>
        <div class="dot green"></div>
      </div>
      <div class="title">debim — Declarative BIM Compiler & QTO Engine</div>
    </div>
    <div class="terminal-body">
      {html_content}
    </div>
  </div>
</body>
</html>
"""

with open("docs/assets/terminal.html", "w", encoding="utf-8") as f:
    f.write(terminal_wrapper)

print("Saved docs/assets/terminal.html successfully.")
