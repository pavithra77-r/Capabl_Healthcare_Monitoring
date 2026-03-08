import csv
import os

CSV_FILE = 'data/medications.csv'

def create_csv():
    """Create CSV file if it doesn't exist"""
    if not os.path.exists('data'):
        os.makedirs('data')
    
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['name', 'dosage', 'time', 'frequency', 'notes'])
        print("✅ CSV file created!")

def add_medication_csv(name, dosage, time, frequency, notes=""):
    """Add medication to CSV"""
    with open(CSV_FILE, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([name, dosage, time, frequency, notes])
    return True

def get_medications_csv():
    """Read all medications from CSV"""
    medications = []
    
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                medications.append(row)
    
    return medications

def delete_medication_csv(med_name, med_time):
    """Delete medication from CSV"""
    medications = get_medications_csv()
    
    with open(CSV_FILE, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=['name', 'dosage', 'time', 'frequency', 'notes'])
        writer.writeheader()
        
        for med in medications:
            if not (med['name'] == med_name and med['time'] == med_time):
                writer.writerow(med)
    
    return True

if __name__ == "__main__":
    create_csv()