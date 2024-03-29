from flask import Flask, current_app, request, jsonify, session
import hashlib
from flask_mail import Mail, Message
import random
import string,textwrap
from datetime import timedelta, datetime
from config import HOST, USER, PASSWORD, GMAIL, GMAIL_PASS
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt, get_jwt_identity, verify_jwt_in_request, decode_token
from urllib.parse import quote_plus
from flask_cors import CORS
from config import SECRET_KEY
import uuid,mysql
import base64

# conn parameters

app = Flask(__name__)
app.config.update(
    MAIL_SERVER="smtp.googlemail.com",
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=GMAIL,
    MAIL_PASSWORD=GMAIL_PASS
)
mail = Mail(app)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["JWT_SECRET_KEY"] = "SECRETKEY"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=30)
jwt = JWTManager(app)

CORS(app)
encoded_password = quote_plus(PASSWORD)
BlockList = set()

@app.route("/")
def home():
    return "Hello"

def generate_random_username():
    username = "user" + ''.join(random.choices(string.digits, k=3))
    return username


@app.route("/register", methods=["POST"])
def register():
    try:
        # Extract user data from the request
        data = request.json
        firstName = data["firstName"]
        lastName = data["lastName"]
        number = data["number"]
        email = data["email"]
        password_hash = hashlib.sha256(data["password"].encode("utf-8")).hexdigest()
        username = generate_random_username()

        try:
            connection = mysql.connector.connect(
            host="bh5rwfq4whcvk3uhwy4j-mysql.services.clever-cloud.com",
            user="uvcbblqallupmh7p",
            password="Q9V29KhWbpqzKNW8yEkL",
            database="bh5rwfq4whcvk3uhwy4j",
        )
            print("Connected to MySQL database successfully")
        except Exception as e:
            print("Error connecting to MySQL database:", e)
            return None

        # Generate unique user ID
        uniqueId = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode('utf-8')
        userId = uniqueId[:8]

        # Create a new conn to MySQL
        with connection.cursor() as cursor:
            # Execute SQL queries to insert user data
            sql_user = "INSERT INTO users (userId, fName, lName, number, email, password, username) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            cursor.execute(sql_user, (userId, firstName, lastName, number, email, password_hash, username))

            # Commit the transaction
            connection.commit()

            # Create a profile for the user
            sql_profile = "INSERT INTO profile (user_id, full_name, email, contact, gender) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(sql_profile, (userId, f"{firstName} {lastName}", email, number, ""))

            # Commit the transaction
            connection.commit()

            # Generate OTP for email verification
            otp = generate_otp()
            sql_otp = "UPDATE users SET otp = %s WHERE userId = %s"
            cursor.execute(sql_otp, (otp, userId))

            # Commit the transaction
            connection.commit()

            # Send OTP to the user's email
            otp_text = textwrap.dedent(f"""
            You are receiving this email because you have requested to authenticate your account.
            To proceed, please use the following One-Time Password (OTP):

            OTP: {otp}

            Please enter this OTP within the specified time frame to complete your verification process.
            Please note that this OTP is valid for a limited time and should not be shared with anyone.

            If you did not request this OTP or if you have any concerns regarding the security of your account, please contact our support team immediately at {GMAIL}.

            Thank you for choosing our service.

            Best regards,
            Rickshare
            """)
            msg = Message(subject="OTP for Account Authentication",
                          sender=GMAIL,
                          recipients=[email])
            msg.body = otp_text

            try:
                mail.send(msg)
                return jsonify({"message": "OTP sent to your email"}), 200
            except Exception as e:
                current_app.logger.error(f"Failed to send OTP email to {email}: {str(e)}")
                return jsonify({"message": "Failed to send OTP email. Please try again later."}), 500
            connection.close()
    except Exception as e:
        # Log any exceptions
        current_app.logger.error(f"Error during registration: {str(e)}")
        return jsonify({"message": f"An error occurred during registration. Please try again later. {e}"}), 500



def generate_otp(length=6):
    digits = string.digits
    otp = ''.join(random.choices(digits, k=length))
    return otp

@app.route("/username", methods=["GET"])
@jwt_required()
def username():
    try:
        userId = get_jwt_identity()
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
        with connection.cursor() as cursor:
            # Fetch user by userId
            sql_select_user = "SELECT * FROM users WHERE userId = %s"
            cursor.execute(sql_select_user, (userId,))
            user = cursor.fetchone()

            if user:
                return jsonify({"message": "Username found", "username": user[0]}), 200
            else:
                return jsonify({"message": "Username not found"}), 404
        connection.close()
    except Exception as e:
        current_app.logger.error(f"Error fetching username: {str(e)}")
        return jsonify({"message": "Error fetching username", "error": str(e)}), 500


@app.route("/users", methods=["GET"])
@jwt_required()
def get_users():
    try:
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
        with connection.cursor() as cursor:
            # Fetch all users
            sql_select_all_users = "SELECT userId, username FROM users"
            cursor.execute(sql_select_all_users)
            users = cursor.fetchall()

            if users:
                user_list = [{"userId": user[0], "username": user[1]} for user in users]
                return jsonify({"message": "Users found", "users": user_list}), 200
            else:
                return jsonify({"message": "No users found"}), 404
        connection.close()
    except Exception as e:
        current_app.logger.error(f"Error fetching users: {str(e)}")
        return jsonify({"message": "Error fetching users", "error": str(e)}), 500

@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.json
        if "email" not in data or "password" not in data:
            return jsonify({"message": "Fields Required"}), 400

        email = data["email"]
        password = data["password"]

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

        cursor = connection.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        connection.close()

        if user:
            hashed_password = hashlib.sha256(password.encode("utf-8")).hexdigest()
            if user[3] == hashed_password:  # Assuming password column is at index 6
                access_token = create_access_token(identity=user[5])  # Assuming userId column is at index 0
                return jsonify({"message": "Successfully Logged in", "access_token": access_token, "isBan": user[6]}), 200  # Assuming isBan column is at index 8
            else:
                return jsonify({"message": "Incorrect password"}), 401
        else:
            return jsonify({"message": "User not found"}), 404

    except Exception as e:
        # Log any exceptions
        current_app.logger.error(f"Error in login route: {str(e)}")
        return jsonify({"message": f"An error occurred while logging in. Please try again later. {e}"}), 500


@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    try:
        data = request.json
        if "otp" not in data or "email" not in data:
            return jsonify({"message": "OTP and email are required"}), 400

        otp = data["otp"]
        email = data["email"]

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

        cursor = connection.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        connection.close()

        if not user:
            return jsonify({"message": "User not found"}), 404

        stored_otp = user[7]  # Assuming the OTP column is at index 7, adjust this accordingly

        if not stored_otp:
            return jsonify({"message": "OTP not found in database. Please try again."}), 400

        if otp == stored_otp:
            return jsonify({"message": "Successfully Registered"}), 200
        else:
            return jsonify({"message": f"Invalid OTP {type(otp)} {type(stored_otp)}"}), 401

    except Exception as e:
        # Log any exceptions
        current_app.logger.error(f"Error in verify_otp route: {str(e)}")
        return jsonify({"message": f"An error occurred while verifying OTP. Please try again later. {e}"}), 500

@app.route("/forgotpasswd", methods=["POST"])
def forgot():
    data = request.json
    if not data:
        return jsonify({"message": "Data not provided"}), 400

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
            # Fetch user by email
            sql_select_user = "SELECT * FROM users WHERE email = %s"
            cursor.execute(sql_select_user, (data["email"],))
            user = cursor.fetchone()

            if user:
                # Generate new password hash
                new_password_hash = hashlib.sha256(data["password"].encode("utf-8")).hexdigest()

                # Update user's password
                sql_update_password = "UPDATE users SET password = %s WHERE userId = %s"
                cursor.execute(sql_update_password, (new_password_hash, user['userId']))
                connection.commit()
                connection.close()
                # Send email notification
                content = textwrap.dedent(f"""
                    Dear {user['fName']},

                    This email is to inform you that your password for Rickshare has been successfully changed.

                    If you did not initiate this change, please contact our support team immediately at {GMAIL}.

                    Thank you for using Rickshare.

                    Best regards,
                    Rickshare
                """)
                msg = Message(subject=f"Password Changed",
                              sender=GMAIL,
                              recipients=[user['email']])
                msg.body = content

                mail.send(msg)

                return jsonify({"message": "Password changed successfully and email sent"}), 200
            else:
                return jsonify({"message": "User not found"}), 404

    except Exception as e:
        current_app.logger.error(f"Failed to change password: {str(e)}")
        return jsonify({"message": "Failed to change password. Please try again later."}), 500


@app.route("/report", methods=["POST"])
@jwt_required()
def report():
    userId = get_jwt_identity()
    user = Users.query.filter_by(userId=userId).first()
    data = request.json
    extraInfo = data["extraInfo"]
    reportUser = data["user"]

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

    if not data:
        return jsonify({"message": "No data provided"}), 400
    else:
        content = f"This is the report details and the mentioned users are:\n"
        content += f"Reported User: {reportUser}\n"
        for details in data["list"]:
            content += f"{details}\n"
        content += f"Detailed Message: {extraInfo}"

        try:
            with connection.cursor() as cursor:
                # Execute SQL query to insert report details
                sql_insert_report = "INSERT INTO reports (user_id, reported_user, details) VALUES (%s, %s, %s)"
                cursor.execute(sql_insert_report, (userId, reportUser, content))
                connection.commit()
                connection.close()
                # Send email with report details
                msg = Message(subject=f"Report User Details from {user.fName}",
                              sender=GMAIL,
                              recipients=["durgesh.d1805@gmail.com", "rahuldhanak11@gmail.com"])
                msg.body = content
                mail.send(msg)
                return jsonify({"message": "Report sent successfully"}), 200
        except Exception as e:
            current_app.logger.error(f"Failed to send report details: {str(e)}")
            return jsonify({"message": "Failed to send report details. Please try again later."}), 500

@jwt.token_in_blocklist_loader
def check_in_blocklist_loader(jwt_header, jwt_payload):
    return jwt_payload["jti"] in BlockList


@jwt.revoked_token_loader
def revoked_token_callback(jwt_header, jwt_payload):
    return jsonify({
        "message": "User has been logged out",
        "error": "token revoked"
    }), 401


@app.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    token = get_jwt()["jti"]
    BlockList.add(token)
    return jsonify({"message": "User logged out successfully"})


@app.route("/user/profile", methods=["GET"])
@jwt_required()
def profile():
    try:
        userId = get_jwt_identity()
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
        # Establish a cursor to execute SQL queries
        with connection.cursor() as cursor:
            # Execute SQL query to retrieve user profile
            sql_query = "SELECT u.userId, u.fName, u.lName, u.email, p.contact, p.gender " \
                        "FROM users u " \
                        "JOIN profile p ON u.userId = p.user_id " \
                        "WHERE u.userId = %s"
            cursor.execute(sql_query, (userId,))
            profile_data = cursor.fetchone()
            connection.close()
            if profile_data:
                # Extract profile data from the query result
                userId, firstName, lastName, email, contact, gender = profile_data
                return jsonify({
                    "userId": userId,
                    "firstName": firstName,
                    "lastName": lastName,
                    "email": email,
                    "contact": contact,
                    "gender": gender
                }), 200
            else:
                return jsonify({"message": "Profile not found"}), 404
    except Exception as e:
        return jsonify({"message": f"Error fetching user profile: {str(e)}"}), 500



@app.route("/chat", methods=["GET", "POST"])
@jwt_required()
def chat():
    return jsonify({"data": "Welcome to chat"})

if __name__ == "__main__":
    app.run()



# {
#     "firstName": "gangesh",
#     "lastName": "dubey",
#     "email":"gangesh1901@gmail.com",
#     "number":"1234567890",
#     "password":"12345678"
# }

# {
#     "email":"gangesh1901@gmail.com",
#     "password":"12345678"
# }

# {
#     "userId" : "lViG4yZB"
# }