from pathlib import Path, PurePosixPath

from icewine_prediction.config import PROJECT_ROOT


def resolve_artifact_path(value: str, project_root: Path = PROJECT_ROOT) -> Path:
    normalized = value.replace("\\", "/")
    relative = PurePosixPath(normalized)
    if (
        not normalized
        or relative.is_absolute()
        or normalized.startswith("//")
        or ":" in relative.parts[0]
        or ".." in relative.parts
    ):
        raise ValueError(f"artifact path must stay inside the project: {value}")

    root = project_root.resolve()
    resolved = (root / Path(*relative.parts)).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"artifact path must stay inside the project: {value}")
    return resolved
