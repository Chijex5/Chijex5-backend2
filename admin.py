import os
import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# MySQL connection configuration from .env
config = {
    'host': os.getenv('MYSQL_HOST'),
    'user': os.getenv('MYSQL_USER'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'database': os.getenv('MYSQL_DB'),
    'port': os.getenv('MYSQL_PORT'),
}

# Connect to MySQL
try:
    conn = mysql.connector.connect(**config)
    cursor = conn.cursor()
    print("Connected to the database successfully!")
except mysql.connector.Error as err:
    print(f"Error: {err}")
    exit(1)

# Collect email and password from user input
email = input("Enter admin email: ").strip()
password = input("Enter admin password: ").strip()

# Hash the password
hashed_password = generate_password_hash(password)

# Insert the new admin with current time
created_at = datetime.now()

try:
    cursor.execute("""
        INSERT INTO admins (email, password, created_at) 
        VALUES (%s, %s, %s)
    """, (email, hashed_password, created_at))
    
    conn.commit()
    print("New admin created successfully!")
except mysql.connector.Error as err:
    print(f"Error: {err}")
    conn.rollback()
finally:
    cursor.close()
    conn.close()
