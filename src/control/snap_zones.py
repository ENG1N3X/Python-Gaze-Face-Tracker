class SnapZoneRegistry:
    """Snap cursor to registered rectangular zones in logical screen points."""

    def __init__(self, zones: list[dict]) -> None:
        self._zones = zones

    @classmethod
    def from_config(cls, config: dict) -> "SnapZoneRegistry":
        return cls(config.get("snap_zones", []))

    def snap(self, x: float, y: float) -> tuple[float, float] | None:
        for z in self._zones:
            if abs(x - z["cx"]) <= z["hw"] and abs(y - z["cy"]) <= z["hh"]:
                return (float(z["cx"]), float(z["cy"]))
        return None
