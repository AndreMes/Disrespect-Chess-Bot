from __future__ import annotations

import argparse
from html import escape
from pathlib import Path

import chess.pgn


def render_history_dashboard(directory: Path) -> Path:
    """Generate a local, dependency-free index for saved games and reports."""
    rows: list[str] = []
    for pgn_path in sorted(directory.glob("*.pgn"), key=lambda path: path.stat().st_mtime, reverse=True):
        with pgn_path.open(encoding="utf-8") as file:
            game = chess.pgn.read_game(file)
        if game is None:
            continue
        stem = pgn_path.stem
        report_path = directory / f"{stem}.report.md"
        json_path = directory / f"{stem}.json"
        report_link = f'<a href="{escape(report_path.name)}">relatório</a>' if report_path.exists() else "—"
        json_link = f'<a href="{escape(json_path.name)}">JSON</a>' if json_path.exists() else "—"
        rows.append(
            "<tr>"
            f"<td>{escape(stem)}</td>"
            f"<td>{escape(game.headers.get('White', '?'))}</td>"
            f"<td>{escape(game.headers.get('Black', '?'))}</td>"
            f"<td>{escape(game.headers.get('Result', '*'))}</td>"
            f"<td><a href=\"{escape(pgn_path.name)}\">PGN</a> · {report_link} · {json_link}</td>"
            "</tr>"
        )
    body = "\n".join(rows) or "<tr><td colspan=\"5\">Ainda não há partidas registradas.</td></tr>"
    page = f"""<!doctype html>
<html lang=\"pt-BR\"><head><meta charset=\"utf-8\"><title>Disrespect Bot — Histórico</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccc;padding:.55rem;text-align:left}}th{{background:#222;color:#fff}}tr:nth-child(even){{background:#f6f6f6}}</style>
</head><body><h1>Disrespect Bot — Histórico</h1><table><thead><tr><th>Partida</th><th>Brancas</th><th>Pretas</th><th>Resultado</th><th>Arquivos</th></tr></thead><tbody>
{body}
</tbody></table></body></html>"""
    dashboard_path = directory / "index.html"
    dashboard_path.write_text(page, encoding="utf-8")
    return dashboard_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera o painel local do histórico do Disrespect Bot.")
    parser.add_argument("--logs", default="logs")
    args = parser.parse_args()
    path = render_history_dashboard(Path(args.logs))
    print(path)


if __name__ == "__main__":
    main()
