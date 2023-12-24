from flask import Flask,flash,render_template,jsonify, request,url_for,redirect,session,g
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from bson import ObjectId
from flask_wtf import FlaskForm
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from wtforms import StringField, PasswordField, SubmitField, SelectField, FloatField
from wtforms.validators import DataRequired, Email , Length, EqualTo, ValidationError
import sqlite3
from flask_socketio import SocketIO,emit
from flask_caching import Cache 
from dotenv import load_dotenv
import logging
import os
import folium 
import datetime
from flask_socketio import SocketIO,join_room
import random
from wtforms import TextAreaField
from flask_debugtoolbar import DebugToolbarExtension

load_dotenv()
app = Flask(__name__)
client = MongoClient(os.getenv('MONGO_DB_URL'))
db = client['jobs']
collection = db['job_details']
hovaten = db['infos']
cart = db["cart"]
app.secret_key = 'secret_key'
app.config['SECRET_KEY'] = 'your_secret_key'
chat_messages = []
socketio = SocketIO(app)


cache = Cache(app, config={'CACHE_TYPE': 'simple'})
logging.basicConfig(filename='app.log', level=logging.INFO, format=f'%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')

class ChatForm(FlaskForm):
    message_content = TextAreaField('Message', validators=[DataRequired()])

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect('./users.db')
        create_table(db)
    return db

def create_table(db):
    cursor = db.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, password TEXT, email TEXT, is_driver INTEGER DEFAULT 0, location TEXT, car_type TEXT, book_id INTEGER DEFAULT 0, is_accepted INTEGER DEFAULT 0)')
    db.commit()
    cursor.close()
    
    # Check if the 'is_driver' column exists in the 'users' table
    cursor = db.cursor()
    cursor.execute('PRAGMA table_info(users)')
    columns = cursor.fetchall()
    cursor.close()

    location_column_exists = any(column[1] == 'location' for column in columns)

    if not location_column_exists:
        # Add the 'location' column to the 'users' table
        cursor = db.cursor()
        cursor.execute('ALTER TABLE users ADD COLUMN location TEXT')
        db.commit()
        cursor.close()

    is_driver_column_exists = any(column[1] == 'is_driver' for column in columns)

    cursor = db.cursor()
    # Add payment-related columns to the invoices table
    cursor.execute('CREATE TABLE IF NOT EXISTS invoices (id INTEGER PRIMARY KEY, user_id INTEGER, driver_id INTEGER, amount REAL, is_paid INTEGER DEFAULT 0)')
    cursor.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, sender_id INTEGER, receiver_id INTEGER, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
    db.commit()
    cursor.close()

    if not is_driver_column_exists:
        # Add the 'is_driver' column to the 'users' table
        cursor = db.cursor()
        cursor.execute('ALTER TABLE users ADD COLUMN is_driver INTEGER DEFAULT 0')
        db.commit()
        cursor.close()

    # Check if the driver user exists and insert if not
    cursor = db.cursor()
    cursor.execute('SELECT id FROM users WHERE username = ?', ('thanhthu',))
    driver_exists = cursor.fetchone()
    cursor.close()
    if not driver_exists:
        cursor = db.cursor()
        cursor.execute('INSERT INTO users (username, password, email, is_driver, car_type) VALUES (?, ?, ?, ?, ?)',
                       ('thanhthu', '16112004', 'luuthanhthu16112004@gmail.com', 1, 'small'))  # 1 represents an driver user
        db.commit()
        cursor.close()
    cursor = db.cursor()
    cursor.execute('SELECT name FROM sqlite_master WHERE type="table" AND name="rides"')
    rides_table_exists = cursor.fetchone()
    cursor.close()

    if not rides_table_exists:
    # Create the 'rides' table with the 'username' and 'destination' columns
        cursor = db.cursor()
        cursor.execute('CREATE TABLE rides (id INTEGER PRIMARY KEY, user_id INTEGER, username TEXT, time TEXT, car_type TEXT, destination TEXT, is_accepted INTEGER DEFAULT 0)')
        db.commit()
        cursor.close()


class User(UserMixin):
    def __init__(self, id):
        self.id = id
        self.username = None  # Set the usename here
        self.password = None  # Set the password here
        self.email = None     # Set the email here
        self.is_driver = 0
        self.cart = []
        self.location = None 
        self.car_type="None"
        self.book_id=0

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    cursor.close()

    if user_data:
        user_id, username, password, email, is_driver, location, car_type, book_id, is_accepted = user_data
        user = User(str(user_id))
        user.username = username
        user.password = password
        user.email = email
        user.is_driver = is_driver
        user.location = location if location else generate_user_location(user_id)
        user.car_type = car_type
        user.book_id = book_id
        user.is_accepted = is_accepted
        return user

def generate_user_location(user_id):
    # Check if the user already has a location
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT location FROM users WHERE id = ?', (user_id,))
    existing_location = cursor.fetchone()
    cursor.close()

    if existing_location and existing_location[0] is not None:
        # If the user already has a location, return the existing location
        return existing_location[0]
    else:
        # Generate and store a new location for the user
        latitude = random.uniform(35, 71)
        longitude = random.uniform(-25, 40)
        location = f"{latitude},{longitude}"

        # Insert the location into the database
        cursor = db.cursor()
        cursor.execute('UPDATE users SET location = ? WHERE id = ?', (location, user_id))
        db.commit()
        cursor.close()

        return location

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('show_map'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
        user_data = cursor.fetchone()
        cursor.close()

        if user_data:
            user_id = user_data[0]
            user = User(str(user_id))
            user.username = username
            user.password = password
            login_user(user)
            return redirect(url_for('show_map'))
        else:
            flash('Login failed. Check your username or password', 'Login failed')

    return render_template('login.html')



@app.route('/login_driver', methods=['GET', 'POST'])
def login_driver():
    if current_user.is_authenticated and current_user.is_driver == 1:
        return redirect(url_for('driver_map'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ? AND password = ? AND is_driver = 1', (username, password))
        driver_data = cursor.fetchone()
        cursor.close()

        if driver_data:
            user_id = driver_data[0]
            user = User(str(user_id))
            user.username = username
            user.password = password
            user.is_driver = 1  # Set is_driver to True for driver
            login_user(user)
            return redirect(url_for('driver_orders'))
        else:
            flash('driver login failed. Check your username or password', 'danger')

    return render_template('login_driver.html')

@app.before_request
def log_request_info():
    if request.method == 'POST':
        logging.info(f"Items in Cart: {cart.find()}")
    logging.info(f"Request Method: {request.method}")
    logging.info(f"Request URL: {request.url}")
    logging.info(f"Request Headers: {dict(request.headers)}")
    logging.info(f"Request Data: {request.get_data()}")

@app.after_request
def log_response_info(response):
    if request.method == 'POST':
        logging.info(f"Items in Cart: {cart.find()}")
    logging.info(f"Response Status Code: {response.status_code}")
    logging.info(f"Response Headers: {dict(response.headers)}")
    logging.info(f"Response Data: {response.get_data()}")
    return response



@app.route('/')
def home():
    jobs = list(collection.find())
    return render_template('home.html',user=current_user,jobs=jobs)

@app.route('/profile')
@login_required
def profile():
    jobs = list(collection.find())
    user_id = current_user.id
    user_contact_info = hovaten.find_one({'user_id': user_id})
    return render_template('profile.html', user=current_user, jobs=jobs, user_contact_info=user_contact_info)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

class RegistrationForm(FlaskForm):
    username = StringField('Username',validators=[DataRequired(),Length(min=4,max=20)])
    email = StringField('Email',validators=[DataRequired(),Email()])
    password = PasswordField('Password', validators=[DataRequired(),Length(min=0)])
    confirm_password = PasswordField('Confirm Password',validators = [DataRequired(),
EqualTo('password')])
    submit = SubmitField('Signup')
    def validate_username(self, field):
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id FROM users WHERE username = ?', (field.data,))
        existing_user = cursor.fetchone()
        cursor.close()
        if existing_user:
            raise ValidationError('This username is already taken. Please choose a different one.')

class DriverRegistrationForm(RegistrationForm):
    car_type = SelectField('Car Type', choices=[('big'), ('small')],
                           validators=[DataRequired()])
    submit = SubmitField('Sign Up as Driver')

    def validate_username(self, field):
        # Your existing validation logic
        super().validate_username(field)

class ContactInfoForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    contact_information = StringField('Contact Information', validators=[DataRequired()])

class PaymentForm(FlaskForm):
    amount = FloatField('Amount', validators=[DataRequired()])
    submit = SubmitField('Pay')
    
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()

    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data

        db = get_db()
        cursor = db.cursor()
        cursor.execute('INSERT INTO users (username, password, email) VALUES (?, ?, ?)', (username, password, email))
        db.commit()
        cursor.close()

        # Get the user ID of the newly registered user
        cursor = db.cursor()
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        user_id = cursor.fetchone()[0]
        cursor.close()

        # Generate and store the user location
        generate_user_location(user_id)

        return redirect(url_for('login'))

    return render_template('register.html', form=form)

@app.route('/register_driver', methods=['GET', 'POST'])
def register_driver():
    form = DriverRegistrationForm()

    if form.validate_on_submit():
        # Your existing registration logic
        username = form.username.data
        email = form.email.data
        password = form.password.data
        car_type = form.car_type.data

        db = get_db()
        cursor = db.cursor()
        cursor.execute('INSERT INTO users (username, password, email, car_type, is_driver) VALUES (?, ?, ?, ?, 1)',
                       (username, password, email, car_type))
        db.commit()
        cursor.close()

        # Get the user ID of the newly registered driver
        cursor = db.cursor()
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        user_id = cursor.fetchone()[0]
        cursor.close()

        # Generate and store the user location
        generate_user_location(user_id)

        return redirect(url_for('login'))

    return render_template('register_driver.html', form=form)


@app.route('/registration-success')
def registration_success():
    return 'Registration successful'

@app.route('/map')
@login_required
def show_map():
    if current_user.is_driver != 1 :
    # Render the map template and pass latitude and longitude
        return render_template('map.html', current_user= current_user)
    else :
        return redirect(url_for('show_driver_map'))
    
@app.route('/driver_map')
@login_required
def show_driver_map():
    if current_user.is_driver != 0 :
    # Render the map template and pass latitude and longitude
        return render_template('driver_map.html', current_user= current_user)

@app.route('/update_location', methods=['POST'])
@login_required
def update_location():
    user_id = current_user.id
    data = request.get_json()

    if 'location' in data:
        new_location = data['location']
        # Update the user's location in the database
        db = get_db()
        cursor = db.cursor()
        cursor.execute('UPDATE users SET location = ? WHERE id = ?', (','.join(map(str, new_location)), user_id))
        db.commit()
        cursor.close()

        return jsonify(success=True)
    else:
        return jsonify(success=False, error="Invalid data")
    
@app.route('/user_locations')
@login_required
def user_locations():
    user_location = current_user.location
    # Retrieve information about all users
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT id, username, email, location FROM users')
    users_info = cursor.fetchall()
    cursor.close()

    # Convert the location from string to a tuple of latitude and longitude
    latitude, longitude = map(float, user_location.split(','))
    users_info = [{'id': user[0], 'username': user[1], 'email': user[2], 'location': (longitude, latitude)} for user in users_info]

    return render_template('user_locations.html', users_info=users_info)

@app.route('/display_users')
@login_required
def display_users():
    # Retrieve information about all users
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT id, username, email, is_driver, location, car_type, book_id, is_accepted FROM users')
    users_info = cursor.fetchall()
    cursor.close()

    return render_template('display_users.html', users_info=users_info)

@app.errorhandler(404)
def not_found_error(error):
    return render_template('home.html'), 404

@app.errorhandler(500)
def not_found_error(error):
    return render_template('home.html'), 500

class RideForm(FlaskForm):
    time = StringField('Time', default=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M'))
    car_type = StringField('Car Type', validators=[DataRequired()])
    destination = StringField('Destination', validators=[DataRequired()])  # Add a field for destination


@app.route('/book_uber', methods=['GET', 'POST'])
@login_required
def book_uber():
    form = RideForm()

    if form.validate_on_submit():
        # Get the selected car type and destination
        car_type = form.car_type.data
        destination = form.destination.data

        # Fetch the user name
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT username FROM users WHERE id = ?', (current_user.id,))
        username = cursor.fetchone()[0]
        cursor.close()

        # Insert the ride details into the database
        ride_details = {
            'user_id': current_user.id,
            'username': username,
            'time': form.time.data,
            'car_type': car_type,
            'destination': destination,  # Add the destination to the ride details
            'is_accepted': 0
        }
        cursor = db.cursor()
        cursor.execute('INSERT INTO rides (user_id, username, time, car_type, destination, is_accepted) VALUES (?, ?, ?, ?, ?, ?)',
                       (current_user.id, username, form.time.data, car_type, destination, 0))
        db.commit()

        # Update the user's book_id in the database
        ride_id = cursor.lastrowid
        cursor.execute('UPDATE users SET book_id = ? WHERE id = ?', (ride_id, current_user.id))
        db.commit()

        cursor.close()

        flash('Ride booked successfully', 'success')
        return redirect(url_for('waiting_page'))

    return render_template('book_uber.html', form=form)

@app.route('/display_rides')
@login_required
def display_rides():
    # Retrieve information about all rides
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM rides')
    rides_info = cursor.fetchall()
    cursor.close()

    return render_template('display_rides.html', rides_info=rides_info)


@app.route('/waiting_page')
@login_required
def waiting_page():
    # Retrieve the ride information for the current user
    db = get_db()
    cursor = db.cursor()
    user_id = current_user.id
    cursor.execute('SELECT * FROM rides WHERE user_id = ? ORDER BY time DESC LIMIT 1', (user_id,))
    ride_info = cursor.fetchone()
    cursor.close()
    if current_user.is_accepted==1 :
        return redirect(url_for('chat', room_id=current_user.book_id))

    print("Ride Info:", ride_info)  # Add this line for debugging
    return render_template('waiting_page.html', ride_info=ride_info)

@app.route('/driver_map')
@login_required
def driver_map():
    user_location = current_user.location
    latitude, longitude = map(float, user_location.split(','))

    # Create a map centered at the driver's location
    map_obj = folium.Map(location=[latitude, longitude], zoom_start=13)

    return render_template('driver_map.html', latitude=latitude, longitude=longitude, map_content=map_obj._repr_html_(), current_user=current_user)

@app.route('/driver_orders')
@login_required
def driver_orders():
    # Retrieve the driver's car type
    car_type = current_user.car_type

    # Retrieve all ride requests that match the driver's car type and haven't been accepted
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM rides WHERE is_accepted = 0 AND car_type = ?', (car_type,))
    ride_requests = cursor.fetchall()
    cursor.close()

    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?',(current_user.id))
    skip = cursor.fetchall()
    cursor.close()
    if current_user.is_accepted==1 :
        return redirect(url_for('chat', room_id=current_user.book_id))

    return render_template('driver_orders.html', ride_requests=ride_requests)

# Modify the 'accept_ride' route to include socketio.emit for ride acceptance
@app.route('/accept_ride/<ride_id>')
@login_required
def accept_ride(ride_id):
    # Update the ride to indicate that it has been accepted by the driver
    db = get_db()
    cursor = db.cursor()
    cursor.execute('UPDATE rides SET is_accepted = 1 WHERE id = ?', (ride_id,))
    db.commit()

        # Fetch the user_id and book_id associated with the accepted ride
    cursor.execute('SELECT user_id FROM rides WHERE id = ?', (ride_id,))
    user_id = cursor.fetchone()[0]
    cursor.execute('SELECT id FROM rides WHERE id = ?', (ride_id,))
    book_id = cursor.fetchone()[0]

    cursor.execute('INSERT INTO invoices (user_id, driver_id, amount) VALUES (?, ?, ?)',
                   (user_id, current_user.id, calculate_fare(ride_id)))
    

    # Update both the driver and user with is_accepted status and update book_id
    cursor.execute('UPDATE users SET is_accepted = 1, book_id = ? WHERE id IN (?, ?)', (book_id, current_user.id, user_id))
    db.commit()
    cursor.close()

    # Emit a socketio event to notify the user that the ride has been accepted
    socketio.emit('ride_accepted', {'ride_id': ride_id}, room=f'user_{user_id}')

    flash('Ride accepted successfully', 'success')

    # Redirect the driver to the chatting page
    return redirect(url_for('chat', room_id=book_id))

def calculate_fare(ride_id):
    # Fetch ride details and calculate fare based on your criteria
    # You might need to use external APIs or algorithms to calculate distance, time, etc.
    # For simplicity, let's assume a fixed fare for now
    return 10.0

@app.route('/chat/<int:room_id>', methods=['GET', 'POST'])
@login_required
def chat(room_id):
    form = ChatForm()

    if request.method == 'POST' and form.validate_on_submit():
        content = form.message_content.data

        # Insert the new message into the database
        db = get_db()
        cursor = db.cursor()
        cursor.execute('INSERT INTO messages (sender_id, receiver_id, content) VALUES (?, ?, ?)',
                       (current_user.id, room_id, content))
        db.commit()
        cursor.close()

    # Fetch the chat history for the given room_id
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT m.id, m.sender_id, m.content, m.timestamp, u.username FROM messages m JOIN users u ON m.sender_id = u.id WHERE (m.receiver_id = ?) ORDER BY m.id',
               (room_id,))


    chat_history = cursor.fetchall()
    cursor.close()

    # Convert timestamp to a human-readable format
    chat_history = [{'id': message[0], 'sender_id': message[1], 'content': message[2], 'timestamp': (message[3]), 'username':(message[4])} for message in chat_history]

    return render_template('chat.html', form=form, room_id=room_id, chat_history=chat_history)

@app.route('/view_messages')
@login_required
def view_messages():
    # Retrieve all messages from the database
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM messages ORDER BY timestamp ASC')
    messages = cursor.fetchall()
    cursor.close()

    # Convert timestamp to a human-readable format
    messages = [{'sender_id': message[1],'room':message[2], 'content': message[3]} for message in messages]

    return render_template('view_messages.html', messages=messages)

@app.route('/payment/<invoice_id>', methods=['GET', 'POST'])
@login_required
def payment(invoice_id):
    form = PaymentForm()

    if form.validate_on_submit():
        amount_paid = form.amount.data

        # Check if the user's data is already in the invoices table
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT user_id, driver_id FROM invoices WHERE id = ?', (invoice_id,))
        invoice_data = cursor.fetchone()
        cursor.close()

        if invoice_data:
            # If the user's data is already present, update the invoice to mark it as paid
            cursor = db.cursor()
            cursor.execute('UPDATE invoices SET is_paid = 1 WHERE id = ?', (invoice_id,))
            db.commit()
            cursor.close()
        else:
            # If the user's data is not present, insert it into the invoices table
            cursor = db.cursor()
            cursor.execute('INSERT INTO invoices (id, user_id, driver_id, amount, is_paid) VALUES (?, ?, ?, ?, 1)',
                           (invoice_id, current_user.id, current_user.id, amount_paid))
            db.commit()
            cursor.close()

        # Update the user's and driver's is_accepted status to 0
        cursor = db.cursor()
        cursor.execute('UPDATE users SET is_accepted = 0 WHERE book_id = ?', (current_user.book_id,))
        db.commit()
        cursor.close()

        flash('Payment successful. Ride completed.', 'success')
        return redirect(url_for('profile'))

    return render_template('payment.html', form=form, invoice_id=invoice_id)


@app.route('/earnings')
@login_required
def earnings():
    # Ensure the user is a driver
    if not current_user.is_driver:
        flash('You do not have permission to view earnings.', 'danger')
        return redirect(url_for('profile'))

    # Retrieve information about the driver's payments
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM invoices ')
    earnings_info = cursor.fetchall()
    cursor.close()

    return render_template('earnings.html', earnings_info=earnings_info)


if __name__ == '__main__':
    app.run(debug=True)