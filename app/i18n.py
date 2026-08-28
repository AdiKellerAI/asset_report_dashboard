"""Minimal site-wide translation: the currency toggle now also flips the
whole UI to Hebrew + RTL (persisted via a `lang` cookie, read once per
request in a before_request hook - see app/__init__.py). Every visible
English string is a key here; translate() falls back to the original text
for anything not yet covered, so a missing entry degrades gracefully
instead of raising.

Property nicknames (Brunswick, Colburn) and expense_type codes are
deliberately not run through this - only user-facing labels are.
"""

TRANSLATIONS = {
    # Chrome / nav
    "Asset Report Dashboard": "לוח נכסים",
    "Home": "בית",
    "Log out": "התנתקות",
    "Trends": "מגמות",
    "Report": "דוח",
    "Manage": "ניהול",
    # Filters
    "Period": "תקופה",
    "Property": "נכס",
    "Range": "טווח",
    "All Properties": "כל הנכסים",
    "This Month": "החודש",
    "This Year": "השנה",
    "Custom Month": "חודש מותאם",
    "Custom Year": "שנה מותאמת",
    "Go": "עבור",
    "All Time": "כל הזמן",
    "Pick a Month": "בחר חודש",
    "Last 6 Months": "6 חודשים אחרונים",
    "Last 1 Year": "שנה אחרונה",
    "Last 2 Years": "שנתיים אחרונות",
    "Last 3 Years": "3 שנים אחרונות",
    "Last 5 Years": "5 שנים אחרונות",
    "Month": "חודש",
    "Year": "שנה",
    "Apply": "החל",
    "Summary": "סיכום",
    "By Category": "לפי קטגוריה",
    "no statement data for this period yet": "אין עדיין נתוני דוח לתקופה זו",
    "No monthly_statement data yet for this property.": "אין עדיין נתוני דוח לנכס זה.",
    # Landing page
    "Metric": "מדד",
    "Total": "סה\"כ",
    "Income": "הכנסה",
    "Expense": "הוצאה",
    "Checkpoint": "נקודת ביניים",
    "Final result": "תוצאה סופית",
    "Understand This Report": "הבנת הדוח",
    "No report data for this month yet.": "אין עדיין נתוני דוח לחודש זה.",
    "How we got there": "איך הגענו לתוצאה",
    "Rental Income": "הכנסה משכירות",
    "Rent": "שכירות",
    "Total Property Expenses": "סך הוצאות הנכס",
    "Property Expenses": "הוצאות הנכס",
    "Expenses": "הוצאות",
    "Net Operating Income": "רווח תפעולי נקי",
    "Net (NOI)": "נטו (NOI)",
    "Net After Mortgage": "נטו לאחר משכנתא",
    "Net": "נטו",
    "Balance": "יתרה",
    "Accumulated Balance": "יתרה שנצברה",
    "Still with Overland, not yet transferred — portfolio-wide, as of now": (
        "עדיין אצל אוברלנד, טרם הועבר — עבור כלל התיק, נכון לעכשיו"
    ),
    "Net Operating Income — Last {n} Months": "רווח תפעולי נקי — {n} חודשים אחרונים",
    "Annual Yield": "תשואה שנתית",
    "3Y": "3 שנים",
    "6Y": "6 שנים",
    "All": "הכל",
    "No property values set yet - add them in Manage to see this chart.": (
        "עדיין לא הוגדר שווי לנכסים - הוסף אותו בעמוד הניהול כדי לראות גרף זה."
    ),
    # Trends summary series
    "Net Owner Funds": "כספי בעלים נטו",
    "Beginning Balance": "יתרת פתיחה",
    "Ending Balance": "יתרת סגירה",
    "Unpaid Bills": "חשבונות לתשלום",
    "Property Reserve": "רזרבת נכס",
    # Expense taxonomy (category series / manage forms)
    "Rent Income": "הכנסת שכירות",
    "Management Fee": "דמי ניהול",
    "Tenant Placement Fee": "דמי איתור שוכר",
    "Maintenance / Repair": "אחזקה / תיקונים",
    "Property Tax": "ארנונה",
    "Annual State Fee": "אגרה שנתית",
    "Legal / Professional Fee": "שכר טרחה משפטי / מקצועי",
    "Water Bill": "חשבון מים",
    "Sewer Bill": "חשבון ביוב",
    "Insurance": "ביטוח",
    "Tax Prep Fee": "שכר טרחת הכנת דוח מס",
    "Other Expense": "הוצאה אחרת",
    "Internal Transfer (Between Properties)": "העברה פנימית (בין נכסים)",
    "Security Deposit Transfer": "העברת פיקדון",
    "Owner Distribution / Contribution": "חלוקה / הפקדת בעלים",
    # Manage page
    "Upload New Reports": "העלאת דוחות חדשים",
    "Select the report files (zip or individual files, as downloaded).": (
        "בחר את קובצי הדוח (קובץ zip או קבצים בודדים, כפי שהורדו)."
    ),
    "Drop files here, or click to browse": "גרור קבצים לכאן, או לחץ לבחירה",
    "Upload": "העלה",
    "Property Values Today": "שווי הנכסים היום",
    "Purchase price feeds the Annual Yield chart on the Home page. Today's value is an automated estimate, refreshed automatically about once a day.": (
        "מחיר הרכישה מזין את גרף התשואה השנתית בעמוד הבית. השווי היום הוא הערכה אוטומטית, "
        "מתעדכנת אוטומטית בערך פעם ביום."
    ),
    "Purchase Price (USD)": "מחיר רכישה (דולר)",
    "Not available yet": "עדיין לא זמין",
    "Updated": "עודכן",
    "Save": "שמור",
    "Yearly Tax Payment": "תשלום מס שנתי",
    "Provider": "ספק",
    "Amount Paid (USD)": "סכום ששולם (דולר)",
    "What It Covers": "על מה זה מכסה",
    "Filed Date": "תאריך הגשה",
    "Add Tax Payment": "הוסף תשלום מס",
    "Amount": "סכום",
    "Filed": "הוגש",
    "Covers": "מכסה",
    "Transfer to Israel": "העברה לישראל",
    "Amount Sent (USD)": "סכום שנשלח (דולר)",
    "Fee (USD)": "עמלה (דולר)",
    "Note": "הערה",
    "Add Transfer": "הוסף העברה",
    "Amount Sent": "סכום שנשלח",
    "Fee": "עמלה",
    "No mortgage on file yet.": "אין עדיין משכנתא רשומה.",
    "No tax payments recorded yet.": "לא נרשמו עדיין תשלומי מס.",
    "No transfers recorded yet.": "לא נרשמו עדיין העברות.",
    # Tables page
    "Tables": "טבלאות",
    "Swipe left/right to switch tables": "החלק ימינה/שמאלה כדי להחליף טבלה",
    "Properties": "נכסים",
    "Expense Types": "סוגי הוצאה",
    "Upload Batches": "אצוות העלאה",
    "Documents": "מסמכים",
    "Transactions": "תנועות",
    "Monthly Statements": "דוחות חודשיים",
    "Tax Payments": "תשלומי מס",
    "Transfers": "העברות",
    "ID": "מזהה",
    "Nickname": "כינוי",
    "Address": "כתובת",
    "Unit Details": "פרטי יחידה",
    "Purchase Info": "פרטי רכישה",
    "Created": "נוצר",
    "Code": "קוד",
    "Label": "תווית",
    "Income?": "הכנסה?",
    "Operating?": "תפעולי?",
    "Uploaded": "הועלה",
    "Source": "מקור",
    "Files": "קבצים",
    "Notes": "הערות",
    "Type": "סוג",
    "Filename": "שם קובץ",
    "Status": "סטטוס",
    "Category": "קטגוריה",
    "Date": "תאריך",
    "Description": "תיאור",
    "Gross Income": "הכנסה גולמית",
    "NOI": "רווח תפעולי נקי",
    "Monthly Payment": "תשלום חודשי",
    "Principal Balance": "יתרת קרן",
}

# Server-built status messages (routes/manage.py) - format-string templates,
# translated then filled in, since the exact text varies (a batch's file
# count, a property name) but doesn't need per-instance dict entries.
MESSAGE_TEMPLATES = {
    "No files selected.": "לא נבחרו קבצים.",
    "Uploaded batch processed: {count} file(s) ingested": "אצווה הועלתה: {count} קבצים נקלטו",
    ", {count} need review": ", {count} דורשים בדיקה",
    "Couldn't save mortgage - check the numbers/date.": "לא ניתן היה לשמור את המשכנתא - בדוק את המספרים/התאריך.",
    "Mortgage updated.": "המשכנתא עודכנה.",
    "Couldn't save property values - check the numbers.": "לא ניתן היה לשמור את שווי הנכסים - בדוק את המספרים.",
    "Property values updated.": "שווי הנכסים עודכן.",
    "Tax payment needs a valid year.": "תשלום המס דורש שנה תקינה.",
    "Couldn't save the tax payment - check the amount/date.": "לא ניתן היה לשמור את תשלום המס - בדוק את הסכום/התאריך.",
    "Tax payment for {year} recorded.": "תשלום המס עבור {year} נרשם.",
    "Transfer needs a month/year.": "ההעברה דורשת חודש/שנה.",
    "Couldn't save the transfer - check the amount/fee.": "לא ניתן היה לשמור את ההעברה - בדוק את הסכום/העמלה.",
    "Transfer for {when} recorded.": "ההעברה עבור {when} נרשמה.",
}


def translate(text, lang):
    if lang != "he" or text is None:
        return text
    return TRANSLATIONS.get(text, text)


def translate_message(template, lang, **kwargs):
    """Translate a MESSAGE_TEMPLATES format string, then fill it in -
    kwargs are plain values (numbers/dates/names), never re-translated."""
    if lang == "he":
        template = MESSAGE_TEMPLATES.get(template, template)
    return template.format(**kwargs)
