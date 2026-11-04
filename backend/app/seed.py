"""Catalog seed data.

Pipe dimensions are ASME B36.10 values for the common sizes/schedules we
actually see on RFQs. Walls for STD match SCH 40 up to NPS 10 and XS matches
SCH 80 up to NPS 8, per the standard weight designations.
"""
from sqlmodel import Session, select

from .db import engine
from .models import MaterialGrade, PipeSchedule

MATERIAL_GRADES = [
    # grade_id, category, is_exotic
    ("ASTM A106 GRADE B", "CARBON STEEL", False),
    ("ASTM A53 GRADE B", "CARBON STEEL", False),
    ("ASTM A105", "CARBON STEEL", False),
    ("ASTM A234 WPB", "CARBON STEEL", False),
    ("ASTM A350 LF2", "CARBON STEEL", False),
    ("ASTM A36", "CARBON STEEL", False),
    ("ASTM A516 GRADE 70", "CARBON STEEL", False),
    ("API 5L GRADE B", "CARBON STEEL", False),
    ("ASTM A312 TP304", "STAINLESS", False),
    ("ASTM A312 TP316", "STAINLESS", False),
    ("ASTM A312 TP316L", "STAINLESS", False),
    ("STAINLESS 304", "STAINLESS", False),
    ("STAINLESS 316", "STAINLESS", False),
    ("STAINLESS 316L", "STAINLESS", False),
    ("MONEL 400", "NICKEL ALLOY", True),
    ("INCONEL 600", "NICKEL ALLOY", True),
    ("INCONEL 625", "NICKEL ALLOY", True),
    ("HASTELLOY C276", "NICKEL ALLOY", True),
    ("DUPLEX 2205", "DUPLEX STAINLESS", True),
    ("SUPER DUPLEX 2507", "DUPLEX STAINLESS", True),
    ("TITANIUM GRADE 2", "TITANIUM", True),
]

# (nominal size, schedule, OD in, wall in)
_PIPE_ROWS = [
    ('1/2"', "SCH 40", 0.840, 0.109), ('1/2"', "STD", 0.840, 0.109),
    ('1/2"', "SCH 80", 0.840, 0.147), ('1/2"', "XS", 0.840, 0.147),
    ('1/2"', "SCH 160", 0.840, 0.187),
    ('3/4"', "SCH 40", 1.050, 0.113), ('3/4"', "STD", 1.050, 0.113),
    ('3/4"', "SCH 80", 1.050, 0.154), ('3/4"', "XS", 1.050, 0.154),
    ('3/4"', "SCH 160", 1.050, 0.218),
    ('1"', "SCH 40", 1.315, 0.133), ('1"', "STD", 1.315, 0.133),
    ('1"', "SCH 80", 1.315, 0.179), ('1"', "XS", 1.315, 0.179),
    ('1"', "SCH 160", 1.315, 0.250),
    ('1-1/4"', "SCH 40", 1.660, 0.140), ('1-1/4"', "STD", 1.660, 0.140),
    ('1-1/4"', "SCH 80", 1.660, 0.191), ('1-1/4"', "XS", 1.660, 0.191),
    ('1-1/4"', "SCH 160", 1.660, 0.250),
    ('1-1/2"', "SCH 40", 1.900, 0.145), ('1-1/2"', "STD", 1.900, 0.145),
    ('1-1/2"', "SCH 80", 1.900, 0.200), ('1-1/2"', "XS", 1.900, 0.200),
    ('1-1/2"', "SCH 160", 1.900, 0.281),
    ('2"', "SCH 40", 2.375, 0.154), ('2"', "STD", 2.375, 0.154),
    ('2"', "SCH 80", 2.375, 0.218), ('2"', "XS", 2.375, 0.218),
    ('2"', "SCH 160", 2.375, 0.343),
    ('2-1/2"', "SCH 40", 2.875, 0.203), ('2-1/2"', "STD", 2.875, 0.203),
    ('2-1/2"', "SCH 80", 2.875, 0.276), ('2-1/2"', "XS", 2.875, 0.276),
    ('2-1/2"', "SCH 160", 2.875, 0.375),
    ('3"', "SCH 40", 3.500, 0.216), ('3"', "STD", 3.500, 0.216),
    ('3"', "SCH 80", 3.500, 0.300), ('3"', "XS", 3.500, 0.300),
    ('3"', "SCH 160", 3.500, 0.438),
    ('4"', "SCH 40", 4.500, 0.237), ('4"', "STD", 4.500, 0.237),
    ('4"', "SCH 80", 4.500, 0.337), ('4"', "XS", 4.500, 0.337),
    ('4"', "SCH 160", 4.500, 0.531),
    ('6"', "SCH 40", 6.625, 0.280), ('6"', "STD", 6.625, 0.280),
    ('6"', "SCH 80", 6.625, 0.432), ('6"', "XS", 6.625, 0.432),
    ('6"', "SCH 160", 6.625, 0.718),
    ('8"', "SCH 40", 8.625, 0.322), ('8"', "STD", 8.625, 0.322),
    ('8"', "SCH 80", 8.625, 0.500), ('8"', "XS", 8.625, 0.500),
    ('8"', "SCH 160", 8.625, 0.906),
    ('10"', "SCH 40", 10.750, 0.365), ('10"', "STD", 10.750, 0.365),
    ('10"', "SCH 80", 10.750, 0.593),
    ('10"', "SCH 160", 10.750, 1.125),
    ('12"', "STD", 12.750, 0.375),
    ('12"', "SCH 40", 12.750, 0.406),
    ('12"', "XS", 12.750, 0.500),
    ('12"', "SCH 80", 12.750, 0.687),
    ('12"', "SCH 160", 12.750, 1.312),
    ('16"', "STD", 16.000, 0.375),
    ('16"', "SCH 40", 16.000, 0.500), ('16"', "XS", 16.000, 0.500),
    ('16"', "SCH 80", 16.000, 0.843),
    ('24"', "STD", 24.000, 0.375),
    ('24"', "SCH 40", 24.000, 0.687),
    ('24"', "SCH 80", 24.000, 1.218),
]


def seed_catalog(session: Session) -> None:
    if session.exec(select(MaterialGrade)).first() is None:
        for grade_id, category, is_exotic in MATERIAL_GRADES:
            session.add(MaterialGrade(grade_id=grade_id, category=category, is_exotic=is_exotic))
    if session.exec(select(PipeSchedule)).first() is None:
        for size, sched, od, wall in _PIPE_ROWS:
            session.add(PipeSchedule(
                nominal_pipe_size=size, schedule_name=sched,
                outer_diameter_in=od, wall_thickness_in=wall,
            ))
    session.commit()


if __name__ == "__main__":
    from .db import init_db

    init_db()
    with Session(engine) as s:
        seed_catalog(s)
    print("catalog seeded")
