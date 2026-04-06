"""
UPower Database Setup Script
Run: python setup_db.py
Reset: python setup_db.py --reset
"""
import mysql.connector
import sys

HOST     = 'localhost'
USER     = 'root'
PASSWORD = 'rootouassim'
DATABASE = 'system_foundation'
RESET = '--reset' in sys.argv

def main():
    print('=' * 50)
    print('  UPOWER DATABASE SETUP')
    print('=' * 50)

    print('\n[1/4] Connecting to MySQL...')
    try:
        conn = mysql.connector.connect(host=HOST, user=USER, passwd=PASSWORD)
        cur = conn.cursor()
        print(f'  OK Connected as {USER}@{HOST}')
    except mysql.connector.Error as err:
        print(f'  FAILED: {err}')
        return

    print(f'\n[2/4] Setting up database "{DATABASE}"...')
    if RESET:
        cur.execute(f"DROP DATABASE IF EXISTS {DATABASE}")
        print('  Dropped existing database (--reset mode)')
    cur.execute(f"CREATE DATABASE IF NOT EXISTS {DATABASE}")
    cur.execute(f"USE {DATABASE}")
    conn.commit()
    print(f'  OK Database "{DATABASE}" ready')

    print('\n[3/4] Creating tables...')
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gym_options (
            gym_id INT AUTO_INCREMENT PRIMARY KEY,
            gym_name VARCHAR(50) NOT NULL,
            option_name VARCHAR(100) NOT NULL,
            base_price DECIMAL(10,2) NOT NULL,
            joining_fee DECIMAL(10,2) NOT NULL,
            is_addon BOOLEAN DEFAULT FALSE,
            discount_eligible BOOLEAN DEFAULT TRUE,
            student_discount_pct DECIMAL(5,2) NOT NULL DEFAULT 0,
            pensioner_discount_pct DECIMAL(5,2) NOT NULL DEFAULT 0
        )
    """)
    print('  OK Table "gym_options" created')

    cur.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INT AUTO_INCREMENT PRIMARY KEY,
            membership_id VARCHAR(20) UNIQUE NOT NULL,
            member_fullname VARCHAR(100) NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            date_of_birth DATE NOT NULL,
            age INT NOT NULL,
            gender ENUM('Male','Female','Other','Rather not say') NOT NULL DEFAULT 'Rather not say',
            status VARCHAR(50) NOT NULL,
            gym_name VARCHAR(50) NOT NULL,
            gym_option VARCHAR(100) DEFAULT NULL,
            addons VARCHAR(255) DEFAULT NULL,
            total_monthly_price DECIMAL(10,2) NOT NULL,
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
        )
    """)
    print('  OK Table "members" created')
    conn.commit()

    print('\n[4/4] Seeding gym options...')
    cur.execute("SELECT COUNT(*) FROM gym_options")
    count = cur.fetchone()[0]
    if count > 0 and not RESET:
        print(f'  OK Already has {count} rows - skipping')
    else:
        if count > 0: cur.execute("DELETE FROM gym_options")
        options = [
            ('uGym','Super Off-Peak',16,10,0,1,20,15),('uGym','Off-Peak',21,10,0,1,20,15),
            ('uGym','Anytime',30,10,0,1,20,15),('uGym','Swimming Pool (standalone)',25,10,0,1,20,15),
            ('uGym','Swimming Pool (add-on)',15,10,1,1,20,15),('uGym','Classes (standalone)',20,10,0,1,20,15),
            ('uGym','Classes (add-on)',10,10,1,1,20,15),('uGym','Massage (standalone)',30,10,0,0,20,15),
            ('uGym','Massage (add-on)',25,10,1,0,20,15),('uGym','Physiotherapy (standalone)',25,10,0,0,20,15),
            ('uGym','Physiotherapy (add-on)',20,10,1,0,20,15),
            ('Power Zone','Super Off-Peak',13,30,0,1,15,20),('Power Zone','Off-Peak',19,30,0,1,15,20),
            ('Power Zone','Anytime',24,30,0,1,15,20),('Power Zone','Swimming Pool (standalone)',20,30,0,1,15,20),
            ('Power Zone','Swimming Pool (add-on)',12.5,30,1,1,15,20),('Power Zone','Classes (standalone)',20,30,0,1,15,20),
            ('Power Zone','Classes (add-on)',0,30,1,1,15,20),('Power Zone','Massage (standalone)',30,30,0,0,15,20),
            ('Power Zone','Massage (add-on)',25,30,1,0,15,20),('Power Zone','Physiotherapy (standalone)',30,30,0,0,15,20),
            ('Power Zone','Physiotherapy (add-on)',25,30,1,0,15,20),
        ]
        cur.executemany("""INSERT INTO gym_options
            (gym_name,option_name,base_price,joining_fee,is_addon,discount_eligible,student_discount_pct,pensioner_discount_pct)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""", options)
        conn.commit()
        print(f'  OK Seeded {len(options)} gym options')

    cur.execute("SELECT COUNT(*) FROM gym_options"); o = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM members"); m = cur.fetchone()[0]
    cur.close(); conn.close()

    print('\n' + '=' * 50)
    print('  SETUP COMPLETE!')
    print(f'  Database:    {DATABASE}')
    print(f'  gym_options: {o} rows')
    print(f'  members:     {m} rows')
    print('=' * 50)
    print('\n  Now run:  python app.py')
    print('  Then open: http://127.0.0.1:5000/home\n')

if __name__ == '__main__':
    main()