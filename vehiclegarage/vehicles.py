"""The 36 stock vehicle slots in kartParam.bin order."""

from dataclasses import dataclass

WEIGHT_CLASSES = ("Light", "Medium", "Heavy")


@dataclass(frozen=True)
class StockVehicle:
    slot: int
    name: str
    kind: str  # "Kart" or "Bike"
    weight_class: int  # 0 light, 1 medium, 2 heavy

    @property
    def weight_label(self) -> str:
        return WEIGHT_CLASSES[self.weight_class]


_NAMES = (
    "Standard Kart S", "Standard Kart M", "Standard Kart L",
    "Booster Seat", "Classic Dragster", "Offroader",
    "Mini Beast", "Wild Wing", "Flame Flyer",
    "Cheep Charger", "Super Blooper", "Piranha Prowler",
    "Tiny Titan", "Daytripper", "Jetsetter",
    "Blue Falcon", "Sprinter", "Honeycoupe",
    "Standard Bike S", "Standard Bike M", "Standard Bike L",
    "Bullet Bike", "Mach Bike", "Flame Runner",
    "Bit Bike", "Sugarscoot", "Wario Bike",
    "Quacker", "Zip Zip", "Shooting Star",
    "Magikruiser", "Sneakster", "Spear",
    "Jet Bubble", "Dolphin Dasher", "Phantom",
)

VEHICLES: tuple[StockVehicle, ...] = tuple(
    StockVehicle(i, name, "Kart" if i < 18 else "Bike", i % 3) for i, name in enumerate(_NAMES)
)
