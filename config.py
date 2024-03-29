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
            host="bh5rwfq4whcvk3uhwy4j-mysql.services.clever-cloud.com",
            user="uvcbblqallupmh7p",
            password="Q9V29KhWbpqzKNW8yEkL",
            database="bh5rwfq4whcvk3uhwy4j",
        )
        print("Connected to MySQL database successfully")
        return connection
    except Exception as e:
        print("Error connecting to MySQL database:", e)
        return None

connection = create_db_connection()