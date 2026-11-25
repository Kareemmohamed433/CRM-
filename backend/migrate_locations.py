import sqlite3
import os
import sys

# Ensure UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "crm.db")

def run_migration():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"Connecting to database at {DB_PATH}...")

    # 1. Create governorates table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS governorates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
        name_ar VARCHAR(100) NOT NULL,
        name_en VARCHAR(100) NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Create cities table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        governorate_id INTEGER NOT NULL REFERENCES governorates(id) ON DELETE CASCADE,
        company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
        name_ar VARCHAR(100) NOT NULL,
        name_en VARCHAR(100) NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. Create districts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS districts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city_id INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
        company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
        name_ar VARCHAR(100) NOT NULL,
        name_en VARCHAR(100) NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4. Safely add columns to projects
    cursor.execute("PRAGMA table_info(projects)")
    project_cols = [c[1] for c in cursor.fetchall()]
    if "governorate_id" not in project_cols:
        cursor.execute("ALTER TABLE projects ADD COLUMN governorate_id INTEGER REFERENCES governorates(id) ON DELETE SET NULL")
    if "city_id" not in project_cols:
        cursor.execute("ALTER TABLE projects ADD COLUMN city_id INTEGER REFERENCES cities(id) ON DELETE SET NULL")
    if "district_id" not in project_cols:
        cursor.execute("ALTER TABLE projects ADD COLUMN district_id INTEGER REFERENCES districts(id) ON DELETE SET NULL")
    if "is_active" not in project_cols:
        cursor.execute("ALTER TABLE projects ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1")

    # 5. Safely add columns to properties
    cursor.execute("PRAGMA table_info(properties)")
    prop_cols = [c[1] for c in cursor.fetchall()]
    if "governorate_id" not in prop_cols:
        cursor.execute("ALTER TABLE properties ADD COLUMN governorate_id INTEGER REFERENCES governorates(id) ON DELETE SET NULL")
    if "city_id" not in prop_cols:
        cursor.execute("ALTER TABLE properties ADD COLUMN city_id INTEGER REFERENCES cities(id) ON DELETE SET NULL")
    if "district_id" not in prop_cols:
        cursor.execute("ALTER TABLE properties ADD COLUMN district_id INTEGER REFERENCES districts(id) ON DELETE SET NULL")

    # 6. Safely add columns to followups
    cursor.execute("PRAGMA table_info(followups)")
    followup_cols = [c[1] for c in cursor.fetchall()]
    if "created_by_id" not in followup_cols:
        cursor.execute("ALTER TABLE followups ADD COLUMN created_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL")

    conn.commit()
    print("Schema migration completed successfully.")

    # 7. Seed standard Egyptian locations
    locations_tree = [
        {
            "gov_ar": "القاهرة", "gov_en": "Cairo",
            "cities": [
                {
                    "city_ar": "القاهرة الجديدة", "city_en": "New Cairo",
                    "districts": [
                        ("التجمع الخامس", "Fifth Settlement"),
                        ("التجمع الأول", "First Settlement"),
                        ("بيت الوطن", "Beit Al Watan"),
                        ("جنوب الأكاديمية", "South Academy"),
                        ("المربع الذهبي", "Golden Square"),
                    ]
                },
                {
                    "city_ar": "مدينة نصر", "city_en": "Nasr City",
                    "districts": [
                        ("الحي الأول", "First District"),
                        ("الحي السابع", "Seventh District"),
                        ("منطقة النادي الأهلي", "Al Ahly Club Zone"),
                    ]
                },
                {
                    "city_ar": "العاصمة الإدارية الجديدة", "city_en": "New Administrative Capital",
                    "districts": [
                        ("الحي السكني R7", "R7 Residential District"),
                        ("الحي السكني R8", "R8 Residential District"),
                        ("منطقة الأعمال المركزية CBD", "Central Business District"),
                    ]
                },
                {
                    "city_ar": "المعادي", "city_en": "El Maadi",
                    "districts": [
                        ("دجلة", "Degla"),
                        ("زهراء المعادي", "Zahraa El Maadi"),
                    ]
                },
                {
                    "city_ar": "الشروق", "city_en": "El Shorouk",
                    "districts": [
                        ("الحي الأول شرق", "First District East"),
                        ("حي النخيل", "El Nakheel District"),
                    ]
                }
            ]
        },
        {
            "gov_ar": "الجيزة", "gov_en": "Giza",
            "cities": [
                {
                    "city_ar": "السادس من أكتوبر", "city_en": "6th of October",
                    "districts": [
                        ("التوسعات الشمالية", "Northern Expansions"),
                        ("حدائق أكتوبر", "October Gardens"),
                        ("الحي المتميز", "Motamayez District"),
                    ]
                },
                {
                    "city_ar": "الشيخ زايد", "city_en": "Sheikh Zayed",
                    "districts": [
                        ("زايد الجديدة", "New Zayed"),
                        ("زايد ديونز", "Zayed Dunes"),
                        ("الحزام الأخضر", "Green Belt"),
                    ]
                }
            ]
        },
        {
            "gov_ar": "الساحل الشمالي ومطروح", "gov_en": "North Coast & Matrouh",
            "cities": [
                {
                    "city_ar": "الساحل الشمالي", "city_en": "North Coast",
                    "districts": [
                        ("سيدي عبد الرحمن", "Sidi Abdel Rahman"),
                        ("رأس الحكمة", "Ras El Hekma"),
                        ("الضبعة", "El Dabaa"),
                    ]
                }
            ]
        }
    ]

    from datetime import datetime
    now_str = datetime.utcnow().isoformat()

    for gov_data in locations_tree:
        cursor.execute("SELECT id FROM governorates WHERE name_ar = ? OR name_en = ?", (gov_data["gov_ar"], gov_data["gov_en"]))
        row = cursor.fetchone()
        if row:
            gov_id = row[0]
        else:
            cursor.execute("INSERT INTO governorates (name_ar, name_en, is_active, created_at) VALUES (?, ?, 1, ?)", (gov_data["gov_ar"], gov_data["gov_en"], now_str))
            gov_id = cursor.lastrowid

        for city_data in gov_data["cities"]:
            cursor.execute("SELECT id FROM cities WHERE governorate_id = ? AND (name_ar = ? OR name_en = ?)", (gov_id, city_data["city_ar"], city_data["city_en"]))
            c_row = cursor.fetchone()
            if c_row:
                city_id = c_row[0]
            else:
                cursor.execute("INSERT INTO cities (governorate_id, name_ar, name_en, is_active, created_at) VALUES (?, ?, ?, 1, ?)", (gov_id, city_data["city_ar"], city_data["city_en"], now_str))
                city_id = cursor.lastrowid

            for dist_ar, dist_en in city_data["districts"]:
                cursor.execute("SELECT id FROM districts WHERE city_id = ? AND (name_ar = ? OR name_en = ?)", (city_id, dist_ar, dist_en))
                d_row = cursor.fetchone()
                if not d_row:
                    cursor.execute("INSERT INTO districts (city_id, name_ar, name_en, is_active, created_at) VALUES (?, ?, ?, 1, ?)", (city_id, dist_ar, dist_en, now_str))

    conn.commit()
    print("Seed locations inserted successfully.")

    # 8. Link existing projects & properties to structured locations
    # Project 1: The Crest New Cairo (South Academy, New Cairo)
    cursor.execute("SELECT id FROM districts WHERE name_ar = 'جنوب الأكاديمية'")
    dist_sa = cursor.fetchone()
    if dist_sa:
        cursor.execute("SELECT city_id FROM districts WHERE id = ?", (dist_sa[0],))
        city_sa = cursor.fetchone()
        cursor.execute("SELECT governorate_id FROM cities WHERE id = ?", (city_sa[0],))
        gov_cairo = cursor.fetchone()
        cursor.execute("""
            UPDATE projects SET district_id = ?, city_id = ?, governorate_id = ? 
            WHERE name LIKE '%The Crest%' OR location LIKE '%South Academy%'
        """, (dist_sa[0], city_sa[0], gov_cairo[0]))

    # Project 2: Villette Heights (Golden Square, New Cairo)
    cursor.execute("SELECT id FROM districts WHERE name_ar = 'المربع الذهبي'")
    dist_gs = cursor.fetchone()
    if dist_gs:
        cursor.execute("SELECT city_id FROM districts WHERE id = ?", (dist_gs[0],))
        city_gs = cursor.fetchone()
        cursor.execute("SELECT governorate_id FROM cities WHERE id = ?", (city_gs[0],))
        gov_cairo = cursor.fetchone()
        cursor.execute("""
            UPDATE projects SET district_id = ?, city_id = ?, governorate_id = ? 
            WHERE name LIKE '%Villette%' OR location LIKE '%Golden Square%'
        """, (dist_gs[0], city_gs[0], gov_cairo[0]))

    # Project 3: Karmell New Zayed (New Zayed)
    cursor.execute("SELECT id FROM districts WHERE name_ar = 'زايد الجديدة'")
    dist_nz = cursor.fetchone()
    if dist_nz:
        cursor.execute("SELECT city_id FROM districts WHERE id = ?", (dist_nz[0],))
        city_nz = cursor.fetchone()
        cursor.execute("SELECT governorate_id FROM cities WHERE id = ?", (city_nz[0],))
        gov_giza = cursor.fetchone()
        cursor.execute("""
            UPDATE projects SET district_id = ?, city_id = ?, governorate_id = ? 
            WHERE name LIKE '%Karmell%' OR location LIKE '%New Zayed%'
        """, (dist_nz[0], city_nz[0], gov_giza[0]))

    # Project 4: Horizon Marina Palms (North Coast)
    cursor.execute("SELECT id FROM districts WHERE name_ar = 'رأس الحكمة'")
    dist_rh = cursor.fetchone()
    if dist_rh:
        cursor.execute("SELECT city_id FROM districts WHERE id = ?", (dist_rh[0],))
        city_rh = cursor.fetchone()
        cursor.execute("SELECT governorate_id FROM cities WHERE id = ?", (city_rh[0],))
        gov_nc = cursor.fetchone()
        cursor.execute("""
            UPDATE projects SET district_id = ?, city_id = ?, governorate_id = ? 
            WHERE name LIKE '%Horizon%' OR location LIKE '%North Coast%'
        """, (dist_rh[0], city_rh[0], gov_nc[0]))

    # Now update all properties based on their project
    cursor.execute("""
        UPDATE properties 
        SET governorate_id = (SELECT governorate_id FROM projects WHERE projects.id = properties.project_id),
            city_id = (SELECT city_id FROM projects WHERE projects.id = properties.project_id),
            district_id = (SELECT district_id FROM projects WHERE projects.id = properties.project_id)
        WHERE project_id IS NOT NULL
    """)

    conn.commit()
    conn.close()
    print("Location linking for projects & properties finished successfully!")

if __name__ == "__main__":
    run_migration()
