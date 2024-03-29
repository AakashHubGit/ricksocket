from flask import session,Flask
from flask_socketio import SocketIO, join_room, leave_room, send, emit, disconnect
import mysql

app = Flask(__name__)
socketio = SocketIO(app,cors_allowed_origins="*")

def create_room(user_id):
    try:
        # Generate a unique room ID
        room = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode('utf-8')[:8]

        try:
            connection = mysql.connector.connect(
            host="KhushRickShare.mysql.pythonanywhere-services.com",
            user="KhushRickShare",
            password="RickBase",
            database="KhushRickShare$RickBase",
        )
            print("Connected to MySQL database successfully")
        except Exception as e:
            print("Error connecting to MySQL database:", e)
            return None

        # Prepare SQL query to insert a new room into the database
        sql_query = "INSERT INTO rooms (roomId, userId, max_users, time) VALUES (%s, %s, %s, %s)"

        # Get the current timestamp
        current_time = datetime.utcnow()

        # Execute the SQL query
        with conn.cursor() as cursor:
            cursor.execute(sql_query, (room, user_id, 3, current_time))
            connection.commit()
        connection.close()
        return room
    except Exception as e:
        # Log any exceptions
        print(f"Error creating room: {e}")
        return None

@socketio.on("connect", namespace="/chat")
def connect(auth):
    token = auth.get("token")
    token_data = decode_token(token)
    user_id = token_data.get("sub")
    src = auth.get("src")
    destn = auth.get("destn")
    room_name = None

    try:
        connection = mysql.connector.connect(
        host="KhushRickShare.mysql.pythonanywhere-services.com",
        user="KhushRickShare",
        password="RickBase",
        database="KhushRickShare$RickBase",
    )
        print("Connected to MySQL database successfully")
    except Exception as e:
        print("Error connecting to MySQL database:", e)
        return None

    try:
        with connection.cursor() as cursor:
            # Check if there are existing rooms with matching src and destn
            sql_query = "SELECT roomId, max_users FROM rooms WHERE src = %s AND destination = %s"
            cursor.execute(sql_query, (src, destn))
            rooms_with_matching_src_dest = cursor.fetchall()

            # Iterate through the matching rooms
            for room in rooms_with_matching_src_dest:
                if room['max_users'] > 0:
                    room_name = room['roomId']
                    # Reduce the max_users count for the room
                    sql_update = "UPDATE rooms SET max_users = max_users - 1 WHERE roomId = %s"
                    cursor.execute(sql_update, (room_name,))
                    connection.commit()
                    break

            # If no room was found, create a new room
            if room_name is None:
                room_name = create_room(user_id)
                if room_name:
                    # Update the newly created room with src, destn, and reduced max_users count
                    sql_update = "UPDATE rooms SET src = %s, destination = %s, max_users = max_users - 1 WHERE roomId = %s"
                    cursor.execute(sql_update, (src, destn, room_name))
                    connection.commit()
            
        # Join the room
        join_room(room_name)
        session['room_name'] = room_name
        session['user_id'] = user_id

        # Get the username from the user_id
        with connection.cursor() as cursor:
            # Assuming Users is a table in your database
            sql_query = "SELECT username FROM users WHERE userId = %s"
            cursor.execute(sql_query, (user_id,))
            user = cursor.fetchone()
            if user:
                print(f"{user['username']} connected to room {room_name}")
                emit('user_joined', {'username': user['username']}, room=room_name)
    except Exception as e:
        print(f"Error connecting to room: {e}")

@socketio.on("disconnect", namespace="/chat")
def handle_disconnect():
    user_id = session.get('user_id')
    room_name = session.get('room_name')
    if user_id and room_name:
        try:
            with connection.cursor() as cursor:
                # Get the user's username
                sql_query = "SELECT username FROM users WHERE userId = %s"
                cursor.execute(sql_query, (user_id,))
                user = cursor.fetchone()

                if user:
                    # Leave the room
                    leave_room(room_name)
                    print(f"{user['username']} disconnected from room {room_name}")
                    emit('user_left', {'username': user['username']}, room=room_name)
                else:
                    print("User not found in database")
        except Exception as e:
            print(f"Error handling disconnection: {e}")
    else:
        print("User disconnected but no session found")

    session.pop('room_name', None)
    session.pop('user_id', None)
    disconnect()

@socketio.on("message", namespace="/chat")
def handle_message(data):
    chat_id = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode('utf-8')[:8]
    user_id = session.get('user_id')
    room_name = session.get('room_name')
    if user_id and room_name:
        try:
            with connection.cursor() as cursor:
                # Get the user's username
                sql_query = "SELECT username FROM users WHERE userId = %s"
                cursor.execute(sql_query, (user_id,))
                user = cursor.fetchone()

                if user:
                    # Insert the new chat message
                    sql_insert = "INSERT INTO chats (userId, message, chatId, time, roomId) VALUES (%s, %s, %s, %s, %s)"
                    cursor.execute(sql_insert, (user_id, data['message'], chat_id, datetime.utcnow(), room_name))
                    connection.commit()

                    # Emit the message to the room
                    emit("message", {"username": user['username'], "message": data['message']}, room=room_name)
                    print(f"Message from user {user['username']} in room {room_name}: {data['message']}")
                else:
                    print("User not found in database")
        except Exception as e:
            print(f"Error handling message: {e}")
    else:
        print("User or room not found")


if __name__ == "__main__":
    socketio.run(app)