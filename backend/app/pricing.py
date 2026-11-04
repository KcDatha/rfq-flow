"""Starter price book for one-click quotes.

These are placeholder ballpark prices so the quote flow works end to end.
In production this is where the ERP/distributor price file plugs in.
"""

# Base unit price (EA) by category at the smallest common size.
_BASE_BY_CATEGORY = {
    "Pipe": 18.0,      # per length (LGT) at small sizes
    "Fitting": 12.0,
    "Flange": 28.0,
    "Valve": 145.0,
    "Stud Bolt": 9.0,
    "Gasket": 6.0,
    "Tube": 14.0,
}

_MATERIAL_MULTIPLIER = {
    "CARBON STEEL": 1.0,
    "STAINLESS": 2.4,
    "DUPLEX STAINLESS": 3.8,
    "NICKEL ALLOY": 6.5,
    "TITANIUM": 7.5,
}

_SIZE_NUM = {
    '1/2"': 0.5, '3/4"': 0.75, '1"': 1.0, '1-1/4"': 1.25, '1-1/2"': 1.5,
    '2"': 2.0, '2-1/2"': 2.5, '3"': 3.0, '4"': 4.0, '6"': 6.0, '8"': 8.0,
    '10"': 10.0, '12"': 12.0, '16"': 16.0, '24"': 24.0,
}


def estimate_unit_price(product_category: str | None, size: str | None,
                        material_category: str | None) -> float:
    base = _BASE_BY_CATEGORY.get(product_category or "", 20.0)
    size_factor = 0.6 + 0.4 * _SIZE_NUM.get(size or "", 2.0)
    material_factor = _MATERIAL_MULTIPLIER.get(material_category or "", 1.0)
    return round(base * size_factor * material_factor, 2)
