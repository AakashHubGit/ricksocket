import mysql.connector

USER = "root"
HOST = "localhost"
PASSWORD = "2792242584Arya"
SECRET_KEY = "1234"
GMAIL = "rickshare.radikle@gmail.com"
GMAIL_PASS = "pjis afkl jtjx brwp"

def create_db_connection():
    try:
        connection = mysql.connector.connect(
            host="sql306.infinityfree.com",
            user="if0_36266453",
            password="RickBase",
            database="if0_36266453_rickbase",
        )
        print("Connected to MySQL database successfully")
        return connection
    except Exception as e:
        print("Error connecting to MySQL database:", e)
        return None