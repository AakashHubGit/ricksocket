from flask import session, Flask, request
from flask_socketio import SocketIO, join_room, emit, disconnect
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, decode_token
import mysql.connector
from flask_cors import CORS
from datetime import datetime, timedelta
import uuid
import base64
from config import SECRET_KEY

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["JWT_SECRET_KEY"] = "SECRETKEY"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=30)
jwt = JWTManager(app)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Create database connection pool
db_connection_pool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="my_pool",
    pool_size=5,
    pool_reset_session=True,
    host="bh5rwfq4whcvk3uhwy4j-mysql.services.clever-cloud.com",
    user="uvcbblqallupmh7p",
    password="Q9V29KhWbpqzKNW8yEkL",
    database="bh5rwfq4whcvk3uhwy4j"
)

# Function to get a database connection from the pool
def get_db_connection():
    try:
        return db_connection_pool.get_connection()
    except mysql.connector.Error as e:
        print("Error connecting to MySQL database:", e)
        return None

def find_or_create_room(src, destn, connection):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT roomId FROM rooms WHERE src = %s AND destination = %s AND max_users > 0", (src, destn))
        room = cursor.fetchone()
        if room:
            return room['roomId']
        else:
            return create_room(src, destn, connection)
    finally:
        cursor.close()

# Function to create a new room
def create_room(src, destn, connection):
    room_id = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode('utf-8')[:8]
    cursor = connection.cursor()

    sql_query = "INSERT INTO rooms (roomId, src, destination, max_users, time) VALUES (%s, %s, %s, %s, %s)"
    current_time = datetime.utcnow()

    cursor.execute(sql_query, (room_id, src, destn, 3, current_time))
    connection.commit()

    cursor.close()
    return room_id

# Routes and SocketIO event handlers

@app.route('/connect', methods=['POST'])
def connect():
    try:
        # Parse request data and get user details
        data = request.get_json()
        token = data.get("token")
        user_id = decode_token(token).get("sub") if token else None

        # Get room details
        src = data.get("src")
        destn = data.get("destn")

        # Get database connection
        connection = get_db_connection()
        if not connection:
            return "Failed to connect to the database", 500

        # Fetch user details from the database
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM users WHERE userId = %s", (user_id,))
            user = cursor.fetchone()

        # Find or create room and join if successful
        if user:
            room_name = find_or_create_room(src, destn, connection)
            if room_name:
                join_room(room_name)
                session['room_name'] = room_name
                session['user_id'] = user_id

                emit('user_joined', {'username': user_id}, room=room_name)
    except Exception as e:
        print(f"Error connecting to room: {e}")
    finally:
        if connection:
            connection.close()

    return "Connected to room", 200

@app.route('/disconnect', methods=['POST'])
def handle_disconnect():
    user_id = session.get('user_id')
    room_name = session.get('room_name')

    if user_id and room_name:
        connection = get_db_connection()
        if not connection:
            return "Failed to connect to the database", 500

        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT username FROM users WHERE userId = %s", (user_id,))
        user = cursor.fetchone()

        if user:
            leave_room(room_name)
            emit('user_left', {'username': user['username']}, room=room_name)
            print(f"{user['username']} disconnected from room {room_name}")
        else:
            print("User not found in database")

        cursor.close()
        connection.close()
    else:
        print("User disconnected but no session found")

    session.pop('room_name', None)
    session.pop('user_id', None)
    disconnect()

    return "Disconnected from room", 200

@app.route('/message', methods=['POST'])
@jwt_required()
def handle_message():
    user_id = session.get('user_id')
    room_name = session.get('room_name')

    if user_id and room_name:
        message = request.get_json().get("message")

        connection = get_db_connection()
        if not connection:
            return "Failed to connect to the database", 500

        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT username FROM users WHERE userId = %s", (user_id,))
        user = cursor.fetchone()

        if user:
            chat_id = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode('utf-8')[:8]
            sql_insert = "INSERT INTO chats (userId, message, chatId, time, roomId) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(sql_insert, (user_id, message, chat_id, datetime.utcnow(), room_name))
            connection.commit()
            emit("message", {"username": user['username'], "message": message}, room=room_name)
            print(f"Message from user {user['username']} in room {room_name}: {message}")
        else:
            print("User not found in database")

        cursor.close()
        connection.close()
    else:
        print("User or room not found")

    return "Message handled", 200

if __name__ == "__main__":
    socketio.run(app, allow_unsafe_werkzeug=True)
