from pathlib import Path

from ldf.models.powercore.win_exe import WinExe


class OnAirDesigner(WinExe):
    exe = "./OnAirDesigner.exe"
    cwd = "C:\\Program Files (x86)\\OnAirDesigner"

    def convert_config(self, path: Path | str, unit: str | None = None):
        """convers .db3 to .cfg and returns path of resulting config file"""
        args: list[str] = []

        if isinstance(path, str):
            path = Path(path)

        if unit is not None:
            args.extend(("--unit", unit))
        args.append("--createConfig")
        args.append(path.as_posix().replace("/", "\\"))

        self._run(*args)

        if unit is None:
            unit = "unit"

        return path.parent / unit / f"{path.name[:-len(path.suffix)]}.cfg"
