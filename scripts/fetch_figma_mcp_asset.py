#!/usr/bin/env python3
"""Download a Figma Desktop MCP ``localhost`` asset URL into the repo.

While the DoEG file is open in Figma Desktop, run ``get_design_context`` in
Cursor for the target node; paste the ``http://127.0.0.1:3845/assets/….png``
URL from the generated snippet, then:

  python3 scripts/fetch_figma_mcp_asset.py \\
      'http://127.0.0.1:3845/assets/<hash>.png' \\
      moderator/ui/assets/novice_piano_sheets.png
"""
from __future__ import annotations

import sys
import urllib.request


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__.strip())
        return 2
    url, out_path = sys.argv[1], sys.argv[2]
    with urllib.request.urlopen(url) as resp, open(out_path, "wb") as out:
        out.write(resp.read())
    print("wrote", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
