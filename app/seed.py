from app.models import ExpenseType, Property

PROPERTIES = ["Brunswick", "Colburn"]

EXPENSE_TYPES = [
    ("rent_income", "Rent Income", True),
    ("management_fee", "Management Fee", False),
    ("tenant_placement_fee", "Tenant Placement Fee", False),
    ("maintenance_repair", "Maintenance / Repair", False),
    ("property_tax", "Property Tax", False),
    ("annual_state_fee", "Annual State Fee", False),
    ("legal_professional_fee", "Legal / Professional Fee", False),
    ("water_bill", "Water Bill", False),
    ("sewer_bill", "Sewer Bill", False),
    ("insurance", "Insurance", False),
    ("tax_prep_fee", "Tax Prep Fee", False),
    ("other_expense", "Other Expense", False),
]


def seed(session):
    existing_nicknames = {p.nickname for p in session.query(Property).all()}
    for nickname in PROPERTIES:
        if nickname not in existing_nicknames:
            session.add(Property(nickname=nickname))

    existing_codes = {e.code for e in session.query(ExpenseType).all()}
    for code, label, is_income in EXPENSE_TYPES:
        if code not in existing_codes:
            session.add(ExpenseType(code=code, label=label, is_income=is_income))

    session.commit()
