"""Writes site/rift-manual.pdf and site/rift-quick.pdf from the generated pages (their Download PDF buttons;
owner, 2026-11-25), with headless Chrome through Playwright: the pages as on screen, backgrounds kept.

    python3 scripts/gen_rift_pdfs.py [--chrome /usr/bin/google-chrome]
"""
from __future__ import annotations

import argparse
import asyncio
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


async def _pdf(chrome: str) -> None:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=chrome, args=["--no-sandbox"])
        for name in ("rift-manual", "rift-quick"):
            pg = await b.new_page(viewport={"width": 1200, "height": 900})
            await pg.goto((SITE / f"{name}.html").as_uri(), wait_until="networkidle")
            await pg.emulate_media(media="screen")
            await pg.add_style_tag(content=".pdfbtn{display:none!important}nav{position:static!important}")
            await pg.pdf(path=str(SITE / f"{name}.pdf"), format="A4", print_background=True,
                         margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})   # (the dark background to the paper's edge)
            print(f"wrote site/{name}.pdf")
        await b.close()


def main(argv=None) -> int:
    a = argparse.ArgumentParser()
    a.add_argument("--chrome", default="/usr/bin/google-chrome")
    asyncio.run(_pdf(a.parse_args(argv).chrome))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
