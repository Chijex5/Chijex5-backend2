from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import uuid
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from datetime import datetime, timedelta
import json

from dotenv import load_dotenv
import os

load_dotenv()



app = Flask(__name__)

# MySQL Configuration
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB')
app.config['MYSQL_PORT'] = int(os.getenv('MYSQL_PORT'))  # Cast port to integer
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')

mysql = MySQL(app)

# Google Drive API credentials file
CORS(app)
# JWT Configuration
jwt = JWTManager(app)

# Admin login
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data['email']
    password = data['password']

    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM admins WHERE email = %s', (username,))
    admin = cursor.fetchone()
    cursor.close()

    if admin and check_password_hash(admin[2], password):
    # Set the expiration time to 1 day
        expires = timedelta(days=1)  # 1 day expiration

        # Create the access token with the specified expiration
        token = create_access_token(identity=admin[1], expires_delta=expires)
        return jsonify({'token': token}), 200

# Add product
SCOPES = ['https://www.googleapis.com/auth/drive.file']
credentials_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')

credentials_info = json.loads(credentials_json)
credentials = service_account.Credentials.from_service_account_file(credentials_info, scopes=SCOPES)
service = build('drive', 'v3', credentials=credentials)

# Function to upload file to Google Drive
def upload_image_to_drive(file):
    # Secure the filename
    filename = secure_filename(file.filename)
    
    # Define a temporary file path (e.g., saving to /tmp folder)
    temp_path = os.path.join('/tmp', filename)
    
    # Save the uploaded file to the temporary path
    file.save(temp_path)
    
    # Upload the file to Google Drive using the file path
    media = MediaFileUpload(temp_path, mimetype=file.mimetype)
    file_metadata = {'name': filename, 'parents': ['1mAUUgrtfUpsTWOaBaM8g0gZQAaURppG9']}
    
    # Upload the file
    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    # Change permissions to make it publicly accessible
    permission_body = {
        'role': 'reader',
        'type': 'anyone'
    }
    service.permissions().create(
        fileId=uploaded_file.get('id'),
        body=permission_body,
    ).execute()

    # Get the file's Google Drive ID
    file_id = uploaded_file.get('id')

    # Construct the direct image URL
    direct_image_url = f"https://drive.google.com/uc?id={file_id}"

    # Clean up the temporary file
    os.remove(temp_path)

    return direct_image_url


created_at = datetime.now()
# Add product (with image upload to Google Drive)
@app.route('/api/products', methods=['POST'])
@jwt_required()
def add_product():
    try:
        # Check if the request contains the image file
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400
        
        image = request.files['image']

        # Upload the image to Google Drive
        image_url = upload_image_to_drive(image)
        if not image_url:
            return jsonify({'error': 'Failed to upload image'}), 500
        
        # Extract other form fields
        name = request.form.get('name')
        price = request.form.get('price')
        section = request.form.get('section')

        # Validate form fields
        if not name or not price or not section:
            return jsonify({'error': 'Missing required fields'}), 400

        # Insert product into the database
        cursor = mysql.connection.cursor()
        cursor.execute('''INSERT INTO products (name, price, section, image_url, status, created_at, updated_at)
                          VALUES (%s, %s, %s, %s, %s, %s, %s)''', 
                       (name, price, section, image_url, "ACTIVE", created_at, created_at))
        mysql.connection.commit()
        cursor.close()

        return jsonify({'message': 'Product added successfully'}), 201

    except Exception as e:
        # Log the error and return a server error response
        print(f"Error adding product: {e}")
        return jsonify({'error': 'An error occurred while adding the product'}), 500
    
@app.route('/api/products', methods=['GET'])
def get_products():
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, name, price, image_url FROM products")
        rows = cursor.fetchall()
        cursor.close()

        # Format the response as a list of dictionaries
        products = [{'id': row[0], 'name': row[1], 'price': row[2], 'image_url': row[3]} for row in rows]

        return jsonify(products), 200

    except Exception as e:
        print(f"Error fetching products: {e}")
        return jsonify({'error': 'Failed to fetch products'}), 500

# Update product
@app.route('/api/products/<product_id>', methods=['PUT'])
@jwt_required()
def update_product(product_id):
    data = request.json
    name = data.get('name')
    price = data.get('price')
    section = data.get('section')
    image_url = data.get('image_url')

    cursor = mysql.connection.cursor()
    cursor.execute('''UPDATE products 
                      SET name = %s, price = %s, section = %s, image_url = %s 
                      WHERE id = %s''', 
                   (name, price, section, image_url, product_id))
    mysql.connection.commit()
    cursor.close()

    return jsonify({'message': 'Product updated successfully'}), 200

@app.route('/api/products/<product_id>', methods=['DELETE'])
@jwt_required()
def delete_product(product_id):
    cursor = mysql.connection.cursor()
    cursor.execute('DELETE FROM products WHERE id = %s', (product_id,))
    mysql.connection.commit()
    cursor.close()

    return jsonify({'message': 'Product deleted successfully'}), 200
# Update order status
@app.route('/update-order/<order_id>', methods=['PUT'])
@jwt_required()
def update_order(order_id):
    try:
        data = request.json
        status = data['status']

        cursor = mysql.connection.cursor()
        cursor.execute('''UPDATE orders 
                        SET status = %s, updated_at = %s 
                        WHERE id = %s''', 
                    (status, datetime.utcnow(), order_id))
        mysql.connection.commit()
        cursor.close()

        return jsonify({'message': 'Order updated successfully'}), 200
    except Exception as e:
        print(e)

@app.route('/api/product-list', methods=['GET'])
def get_product():
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT id, name, price, section, image_url FROM products')
    products = cursor.fetchall()
    cursor.close()

    # Convert the result to a list of dictionaries
    products_list = [{'id': row[0], 'name': row[1], 'price': row[2], 'section': row[3], 'image_url': row[4]} for row in products]

    return jsonify(products_list), 200

# Group orders by status
@app.route('/orders', methods=['GET'])
@jwt_required()
def get_orders():
    status = request.args.get('status')

    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM orders WHERE status = %s', (status,))
    orders = cursor.fetchall()
    cursor.close()

    return jsonify(orders), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)