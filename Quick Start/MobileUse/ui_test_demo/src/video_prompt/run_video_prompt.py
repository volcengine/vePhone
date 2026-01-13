from __future__ import annotations

import json

from ..env_utils import load_env_from_root
from .core import _get_project_root, _parse_cli, video_to_prompt_result


def main() -> int:
    load_env_from_root(_get_project_root())
    args, fps, video_kwargs = _parse_cli()
    out = video_to_prompt_result(**video_kwargs, recording_id=args.recording_id, fps=fps)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
