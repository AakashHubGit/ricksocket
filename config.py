import mysql.connector

USER = "root"
HOST = "localhost"
PASSWORD = "2792242584Arya"
SECRET_KEY = "1234"
GMAIL = "rickshare.radikle@gmail.com"
GMAIL_PASS = "pjis afkl jtjx brwp"

def connection():
    try:
        connection = mysql.connector.connect(
            host="KhushRickShare.mysql.pythonanywhere-services.com",
            user="KhushRickShare",
            password="RickBase",
            database="KhushRickShare$RickBase",
        )
        print("Connected to MySQL database successfully")
        return connection
    except Exception as e:
        print("Error connecting to MySQL database:", e)
        return None