from flask import session, Flask
from flask_socketio import SocketIO, join_room, leave_room, emit, disconnect
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt, get_jwt_identity, verify_jwt_in_request, decode_token
import mysql.connector
from flask_cors import CORS
from datetime import datetime, timedelta
from app import connection
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

# Function to create a new room
def create_room(user_id):
    try:
        room = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode('utf-8')[:8]
        cursor = connection.cursor()

        sql_query = "INSERT INTO rooms (roomId, userId, max_users, time) VALUES (%s, %s, %s, %s)"
        current_time = datetime.utcnow()

        cursor.execute(sql_query, (room, user_id, 3, current_time))
        connection.commit()

        cursor.close()
        return room
    except Exception as e:
        print(f"Error creating room: {e}")
        return None

# SocketIO event handlers
@socketio.on("connect", namespace="/chat")
@jwt_required()
def connect(auth):
    token = auth.get("token")
    user_id = get_jwt_identity()
    src = auth.get("src")
    destn = auth.get("destn")
    room_name = None

    try:
        cursor = connection.cursor()

        sql_query = "SELECT roomId, max_users FROM rooms WHERE src = %s AND destination = %s"
        cursor.execute(sql_query, (src, destn))
        rooms_with_matching_src_dest = cursor.fetchall()

        for room in rooms_with_matching_src_dest:
            if room[1] > 0:
                room_name = room[0]
                sql_update = "UPDATE rooms SET max_users = max_users - 1 WHERE roomId = %s"
                cursor.execute(sql_update, (room_name,))
                connection.commit()
                break

        if room_name is None:
            room_name = create_room(user_id)
            if room_name:
                sql_update = "UPDATE rooms SET src = %s, destination = %s, max_users = max_users - 1 WHERE roomId = %s"
                cursor.execute(sql_update, (src, destn, room_name))
                connection.commit()
            
        cursor.close()

        join_room(room_name)
        session['room_name'] = room_name
        session['user_id'] = user_id

        emit('user_joined', {'username': user_id}, room=room_name)
    except Exception as e:
        print(f"Error connecting to room: {e}")

@socketio.on("disconnect", namespace="/chat")
@jwt_required()
def handle_disconnect():
    user_id = session.get('user_id')
    room_name = session.get('room_name')
    if user_id and room_name:
        try:
            cursor = connection.cursor()

            sql_query = "SELECT username FROM users WHERE userId = %s"
            cursor.execute(sql_query, (user_id,))
            user = cursor.fetchone()

            if user:
                leave_room(room_name)
                emit('user_left', {'username': user['username']}, room=room_name)
                print(f"{user['username']} disconnected from room {room_name}")
            else:
                print("User not found in database")

            cursor.close()
        except Exception as e:
            print(f"Error handling disconnection: {e}")
    else:
        print("User disconnected but no session found")

    session.pop('room_name', None)
    session.pop('user_id', None)
    disconnect()

@socketio.on("message", namespace="/chat")
@jwt_required()
def handle_message(data):
    user_id = session.get('user_id')
    room_name = session.get('room_name')
    if user_id and room_name:
        try:
            cursor = connection.cursor()

            sql_query = "SELECT username FROM users WHERE userId = %s"
            cursor.execute(sql_query, (user_id,))
            user = cursor.fetchone()

            if user:
                chat_id = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode('utf-8')[:8]
                sql_insert = "INSERT INTO chats (userId, message, chatId, time, roomId) VALUES (%s, %s, %s, %s, %s)"
                cursor.execute(sql_insert, (user_id, data['message'], chat_id, datetime.utcnow(), room_name))
                connection.commit()
                emit("message", {"username": user['username'], "message": data['message']}, room=room_name)
                print(f"Message from user {user['username']} in room {room_name}: {data['message']}")
            else:
                print("User not found in database")

            cursor.close()

        except Exception as e:
            print(f"Error handling message: {e}")
    else:
        print("User or room not found")


if __name__ == "__main__":
    socketio.run(app, allow_unsafe_werkzeug=True)
