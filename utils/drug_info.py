import requests

# ─── Overdose / Max Daily Dose Database ───────────────────────────────────────
OVERDOSE_THRESHOLDS = {
    'paracetamol': {'max_per_day_mg': 4000, 'single_dose_mg': 1000, 'warning': 'Exceeding 4g/day causes severe liver damage.'},
    'ibuprofen':   {'max_per_day_mg': 3200, 'single_dose_mg': 800,  'warning': 'Risk of GI bleeding and kidney damage above limit.'},
    'aspirin':     {'max_per_day_mg': 4000, 'single_dose_mg': 1000, 'warning': 'High doses may cause Reye\'s syndrome or bleeding.'},
    'azithromycin':{'max_per_day_mg': 500,  'single_dose_mg': 500,  'warning': 'Do not exceed prescribed dose; cardiac risk.'},
    'pantoprazole':{'max_per_day_mg': 80,   'single_dose_mg': 40,   'warning': 'Long-term overuse causes vitamin B12 deficiency.'},
    'metformin':   {'max_per_day_mg': 2550, 'single_dose_mg': 1000, 'warning': 'Risk of lactic acidosis at high doses.'},
    'cetirizine':  {'max_per_day_mg': 10,   'single_dose_mg': 10,   'warning': 'Excessive drowsiness and heart rhythm changes.'},
    'omeprazole':  {'max_per_day_mg': 40,   'single_dose_mg': 20,   'warning': 'Bone fractures and electrolyte issues with overuse.'},
}

# Common brand → generic mapping
BRAND_TO_GENERIC = {
    'dolo 650': 'paracetamol',
    'crocin': 'paracetamol',
    'combiflam': 'ibuprofen',  # simplified
    'azithral 500': 'azithromycin',
    'brufen': 'ibuprofen',
    'disprin': 'aspirin',
    'ecosprin': 'aspirin',
    'pan 40': 'pantoprazole',
    'zyrtec': 'cetirizine',
    'cetriz': 'cetirizine',
    'glycomet': 'metformin',
    'omez': 'omeprazole',
}

def get_overdose_info(medicine_name: str):
    """Return overdose threshold info for a given medicine name (brand or generic)."""
    name_lower = medicine_name.lower().strip()
    generic = BRAND_TO_GENERIC.get(name_lower, name_lower)
    return OVERDOSE_THRESHOLDS.get(generic, None)

def check_overdose_risk(medicine_name: str, times_taken_today: int, dosage_str: str) -> dict:
    """
    Check if taking this medicine again today poses an overdose risk.
    Returns dict: { 'safe': bool, 'message': str, 'severity': 'ok'|'warning'|'danger' }
    """
    info = get_overdose_info(medicine_name)
    if not info:
        return {'safe': True, 'message': 'No overdose data available for this medicine.', 'severity': 'ok'}

    # Try to extract mg from dosage string e.g. "500mg", "650 mg"
    import re
    mg_match = re.search(r'(\d+(?:\.\d+)?)\s*mg', dosage_str, re.IGNORECASE)
    if not mg_match:
        return {'safe': True, 'message': f'Could not parse dosage amount from "{dosage_str}".', 'severity': 'ok'}

    single_mg = float(mg_match.group(1))
    total_today = single_mg * times_taken_today
    max_daily  = info['max_per_day_mg']
    after_next = total_today + single_mg

    if after_next > max_daily:
        return {
            'safe': False,
            'message': (
                f"🚨 OVERDOSE ALERT for {medicine_name.title()}!\n"
                f"You've taken {int(total_today)}mg today. Taking another {int(single_mg)}mg "
                f"would bring you to {int(after_next)}mg, exceeding the safe daily limit of {max_daily}mg.\n"
                f"⚠️ {info['warning']}\nPlease consult your doctor immediately."
            ),
            'severity': 'danger'
        }
    elif total_today >= max_daily * 0.75:
        return {
            'safe': True,
            'message': (
                f"⚠️ HIGH DOSE WARNING for {medicine_name.title()}!\n"
                f"You've taken {int(total_today)}mg today (daily limit: {max_daily}mg). "
                f"You're approaching the maximum safe dose. Take with caution."
            ),
            'severity': 'warning'
        }
    else:
        return {
            'safe': True,
            'message': f"✅ {medicine_name.title()} dose is within safe limits ({int(total_today)}mg of {max_daily}mg daily max).",
            'severity': 'ok'
        }

# ─── Indian Medicines DB ───────────────────────────────────────────────────────

def search_drug_info(drug_name):
    """Search OpenFDA API for drug info."""
    try:
        url = f"https://api.fda.gov/drug/label.json?search=openfda.brand_name:{drug_name}&limit=1"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'results' in data and data['results']:
                result = data['results'][0]
                return {
                    'brand_name':   result.get('openfda', {}).get('brand_name', ['N/A'])[0],
                    'generic_name': result.get('openfda', {}).get('generic_name', ['N/A'])[0],
                    'manufacturer': result.get('openfda', {}).get('manufacturer_name', ['N/A'])[0],
                    'purpose':      result.get('purpose', ['N/A'])[0] if 'purpose' in result else 'N/A',
                    'warnings':     result.get('warnings', ['N/A'])[0] if 'warnings' in result else 'N/A',
                    'dosage':       result.get('dosage_and_administration', ['N/A'])[0] if 'dosage_and_administration' in result else 'N/A',
                    'indications':  result.get('indications_and_usage', ['N/A'])[0] if 'indications_and_usage' in result else 'N/A',
                }
        return None
    except Exception:
        return None

def get_indian_medicine_info(medicine_name):
    """Get information about common Indian medicines."""
    indian_medicines = {
        'dolo 650': {
            'generic_name': 'Paracetamol 650mg',
            'manufacturer': 'Micro Labs',
            'purpose': 'Pain relief and fever reduction',
            'dosage': '1 tablet every 4-6 hours, max 4 tablets per day (2600mg/day for 650mg tablets)',
            'warnings': 'Do not exceed 4 tablets/day. Avoid alcohol. Consult doctor if pregnant.',
            'price_range': '₹30-40 for 15 tablets',
            'max_daily_dose': '2600mg (4 tablets of 650mg)',
        },
        'crocin': {
            'generic_name': 'Paracetamol 500mg',
            'manufacturer': 'GSK',
            'purpose': 'Pain relief and fever reduction',
            'dosage': '1-2 tablets every 4-6 hours, max 8 tablets per day',
            'warnings': 'Avoid alcohol. Liver damage risk if overdosed. Max 4g/day.',
            'price_range': '₹15-25 for 15 tablets',
            'max_daily_dose': '4000mg (8 tablets of 500mg)',
        },
        'combiflam': {
            'generic_name': 'Ibuprofen 400mg + Paracetamol 325mg',
            'manufacturer': 'Sanofi',
            'purpose': 'Pain relief, fever, inflammation',
            'dosage': '1 tablet every 6-8 hours, max 3 tablets per day',
            'warnings': 'Take with food. Not for long-term use. Avoid if kidney/liver issues.',
            'price_range': '₹25-35 for 20 tablets',
            'max_daily_dose': '3 tablets/day',
        },
        'azithral 500': {
            'generic_name': 'Azithromycin 500mg',
            'manufacturer': 'Alembic Pharma',
            'purpose': 'Antibiotic for bacterial infections',
            'dosage': '1 tablet daily for 3-5 days as prescribed',
            'warnings': 'Complete full course. Prescription required. Cardiac risk if overdosed.',
            'price_range': '₹100-150 for 3 tablets',
            'max_daily_dose': '500mg/day',
        },
        'pantoprazole': {
            'generic_name': 'Pantoprazole 40mg',
            'manufacturer': 'Various',
            'purpose': 'Reduces stomach acid, treats GERD',
            'dosage': '1 tablet 30 minutes before breakfast',
            'warnings': 'Long-term use may cause vitamin B12 deficiency. Max 80mg/day.',
            'price_range': '₹50-80 for 15 tablets',
            'max_daily_dose': '80mg/day',
        },
    }
    name_lower = medicine_name.lower().strip()
    return indian_medicines.get(name_lower, None)