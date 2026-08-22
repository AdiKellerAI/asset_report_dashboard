from app.models import ExpenseType, Property

PROPERTIES = ["Brunswick", "Colburn"]

# (code, label, is_income, is_operating)
EXPENSE_TYPES = [
    ("rent_income", "Rent Income", True, True),
    ("management_fee", "Management Fee", False, True),
    ("tenant_placement_fee", "Tenant Placement Fee", False, True),
    ("maintenance_repair", "Maintenance / Repair", False, True),
    ("property_tax", "Property Tax", False, True),
    ("annual_state_fee", "Annual State Fee", False, True),
    ("legal_professional_fee", "Legal / Professional Fee", False, True),
    ("water_bill", "Water Bill", False, True),
    ("sewer_bill", "Sewer Bill", False, True),
    ("insurance", "Insurance", False, True),
    ("tax_prep_fee", "Tax Prep Fee", False, True),
    ("other_expense", "Other Expense", False, True),
    # Non-operating cash movements - kept as their own transaction rows (audit
    # trail) but excluded from gross_income/total_operating_expense/noi. See
    # docs/PROJECT_STATUS.md's "other_expense category" finding.
    ("internal_transfer", "Internal Transfer (Between Properties)", False, False),
    ("security_deposit_transfer", "Security Deposit Transfer", False, False),
    ("owner_distribution", "Owner Distribution / Contribution", False, False),
]


def seed(session):
    existing_nicknames = {p.nickname for p in session.query(Property).all()}
    for nickname in PROPERTIES:
        if nickname not in existing_nicknames:
            session.add(Property(nickname=nickname))

    existing_codes = {e.code for e in session.query(ExpenseType).all()}
    for code, label, is_income, is_operating in EXPENSE_TYPES:
        if code not in existing_codes:
            session.add(ExpenseType(code=code, label=label, is_income=is_income, is_operating=is_operating))

    session.commit()
