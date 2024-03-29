from flask import session, Flask
from flask_socketio import SocketIO, join_room, leave_room, emit, disconnect
from flask_jwt_extended import JWTManager, decode_token
import mysql.connector
from flask_cors import CORS
from datetime import datetime, timedelta
import uuid
import base64
from config import SECRET_KEY

app = Flask(__name__)
CORS(app)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["JWT_SECRET_KEY"] = "SECRETKEY"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=30)
jwt = JWTManager(app)
socketio = SocketIO(app, cors_allowed_origins="*")

def create_connection():
    """Create a connection to the MySQL database."""
    try:
        connection = mysql.connector.connect(
            host="KhushRickShare.mysql.pythonanywhere-services.com",
            user="KhushRickShare",
            password="RickBase",
            database="KhushRickShare$RickBase"
        )
        print("Connected to MySQL database successfully")
        return connection
    except Exception as e:
        print("Error connecting to MySQL database:", e)
        return None

def create_room(user_id, cursor):
    """Create a new room."""
    try:
        room_id = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode('utf-8')[:8]
        current_time = datetime.utcnow()
        cursor.execute("INSERT INTO rooms (roomId, userId, max_users, time) VALUES (%s, %s, %s, %s)",
                       (room_id, user_id, 3, current_time))
        return room_id
    except Exception as e:
        print(f"Error creating room: {e}")
        return None

@socketio.on("connect", namespace="/chat")
def connect(auth):
    """Handle user connection."""
    token = auth.get("token")
    token_data = decode_token(token)
    user_id = token_data.get("sub")
    src = auth.get("src")
    destn = auth.get("destn")
    room_name = None

    connection = create_connection()
    if not connection:
        return None

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT roomId, max_users FROM rooms WHERE src = %s AND destination = %s", (src, destn))
            rooms_with_matching_src_dest = cursor.fetchall()

            for room in rooms_with_matching_src_dest:
                if room['max_users'] > 0:
                    room_name = room['roomId']
                    cursor.execute("UPDATE rooms SET max_users = max_users - 1 WHERE roomId = %s", (room_name,))
                    connection.commit()
                    break

            if room_name is None:
                room_name = create_room(user_id, cursor)
                if room_name:
                    cursor.execute("UPDATE rooms SET src = %s, destination = %s, max_users = max_users - 1 WHERE roomId = %s",
                                   (src, destn, room_name))
                    connection.commit()
            
        join_room(room_name)
        session['room_name'] = room_name
        session['user_id'] = user_id

        cursor.execute("SELECT username FROM users WHERE userId = %s", (user_id,))
        user = cursor.fetchone()
        if user:
            print(f"{user['username']} connected to room {room_name}")
            emit('user_joined', {'username': user['username']}, room=room_name)
    except Exception as e:
        print(f"Error connecting to room: {e}")
    finally:
        if connection:
            connection.close()

@socketio.on("disconnect", namespace="/chat")
def handle_disconnect():
    """Handle user disconnection."""
    user_id = session.get('user_id')
    room_name = session.get('room_name')

    if not user_id or not room_name:
        print("User disconnected but no session found")
        return

    connection = create_connection()
    if not connection:
        return None

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT username FROM users WHERE userId = %s", (user_id,))
            user = cursor.fetchone()

            if user:
                leave_room(room_name)
                print(f"{user['username']} disconnected from room {room_name}")
                emit('user_left', {'username': user['username']}, room=room_name)
            else:
                print("User not found in database")
    except Exception as e:
        print(f"Error handling disconnection: {e}")
    finally:
        if connection:
            connection.close()

    session.pop('room_name', None)
    session.pop('user_id', None)
    disconnect()

@socketio.on("message", namespace="/chat")
def handle_message(data):
    """Handle incoming messages."""
    user_id = session.get('user_id')
    room_name = session.get('room_name')

    if not user_id or not room_name:
        print("User or room not found")
        return

    connection = create_connection()
    if not connection:
        return None

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT username FROM users WHERE userId = %s", (user_id,))
            user = cursor.fetchone()

            if user:
                chat_id = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode('utf-8')[:8]
                cursor.execute("INSERT INTO chats (userId, message, chatId, time, roomId) VALUES (%s, %s, %s, %s, %s)",
                               (user_id, data['message'], chat_id, datetime.utcnow(), room_name))
                connection.commit()
                emit("message", {"username": user['username'], "message": data['message']}, room=room_name)
                print(f"Message from user {user['username']} in room {room_name}: {data['message']}")
            else:
                print("User not found in database")
    except Exception as e:
        print(f"Error handling message: {e}")
    finally:
        if connection:
            connection.close()

if __name__ == "__main__":
    socketio.run(app, allow_unsafe_werkzeug=True)
