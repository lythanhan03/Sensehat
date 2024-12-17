from flask import Flask, jsonify
from sense_emu import SenseHat
import time
import numpy as np
import mysql.connector
import pyrebase
import threading

# Cấu hình Firebase
config = {
    "apiKey": "AIzaSyAKEGphm59cE8RpPABFZnfmo6eXeeVHGgk",
    "authDomain": "thanhan-d0c5d.firebaseapp.com",
    "databaseURL": "https://thanhan-d0c5d-default-rtdb.firebaseio.com",
    "projectId": "thanhan-d0c5d",
    "storageBucket": "thanhan-d0c5d.appspot.com",
    "messagingSenderId": "81170842308",
    "appId": "1:81170842308:web:123814d903675b546dbf91",
    "measurementId": "G-TV3Y38Y7HT"
}

# Cấu hình MariaDB
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'thanhan',
    'database': 'sensor_data'
}

# Flask khởi tạo
app = Flask(__name__)

# Khởi tạo Firebase và SenseHAT
firebase = pyrebase.initialize_app(config)
database = firebase.database()
sense = SenseHat()

# Biến lưu trữ giá trị đã lọc
latest_data = {"temperature": 0, "humidity": 0, "timestamp": ""}

# Kết nối MariaDB
def connect_to_mariadb():
    try:
        connection = mysql.connector.connect(**db_config)
        if connection.is_connected():
            print("Đã kết nối thành công đến MariaDB")
            return connection
    except mysql.connector.Error as e:
        print(f"Lỗi kết nối MariaDB: {e}")
        return None

# Ghi nhiệt độ gốc vào MariaDB
def write_initial_temperature_to_sql(connection, temperature):
    cursor = connection.cursor()
    query = "INSERT INTO raw_temperature (temperature, timestamp) VALUES (%s, %s)"
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(query, (temperature, timestamp))
    connection.commit()
    print(f"Đã ghi nhiệt độ gốc vào MariaDB: {temperature} °C")

# Hàm lọc giá trị trung bình từ danh sách nhiệt độ
def filter_temperature(temperature_list):
    if len(temperature_list) == 0:
        return 0
    return round(np.mean(temperature_list), 2)

# Đẩy dữ liệu lên Firebase và cập nhật web
def push_optimized_data():
    global latest_data
    temperature_list = []  # Lưu trữ các giá trị nhiệt độ để lọc
    connection = connect_to_mariadb()
    if connection is None:
        print("Không thể kết nối đến MariaDB, dừng chương trình.")
        return

    while True:
        try:
            # Đọc nhiệt độ và độ ẩm từ SenseHAT
            current_temp = round(sense.get_temperature(), 2)
            humidity = round(sense.get_humidity(), 2)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

            # Lưu nhiệt độ gốc vào MariaDB
            write_initial_temperature_to_sql(connection, current_temp)

            # Lưu vào danh sách để lọc
            temperature_list.append(current_temp)
            if len(temperature_list) > 5:  # Giới hạn bộ lọc trung bình 5 phần tử
                temperature_list.pop(0)

            # Tính nhiệt độ đã lọc
            filtered_temp = filter_temperature(temperature_list)

            # Cập nhật dữ liệu mới nhất (chỉ gửi giá trị đã lọc)
            latest_data = {
                "temperature": filtered_temp,
                "humidity": humidity,
                "timestamp": timestamp
            }

            # Đẩy dữ liệu đã lọc lên Firebase
            database.child("filtered_data").push(latest_data)
            print("Đã cập nhật dữ liệu lọc:", latest_data)

            time.sleep(5)  # Tạm dừng 5 giây

        except Exception as e:
            print("Lỗi xảy ra:", e)

# Route Flask để hiển thị dữ liệu
@app.route("/")
def index():
    return f"""
    <h1> Du lieu senhat </h1>
    <p><strong>Sinh viên:</strong> Lý Thành An</p>
    <p><strong>Gia tri T cập nhật:</strong></p>
    <ul>
        <li>Temperature (Nhiệt độ): {latest_data['temperature']} °C</li>
        <li>Humidity (Độ ẩm): {latest_data['humidity']}%</li>
        <li>Timestamp (Thời gian): {latest_data['timestamp']}</li>
    </ul>
    """

@app.route("/api/data", methods=["GET"])
def api_data():
    return jsonify(latest_data)

# Chạy Flask server trong một luồng riêng biệt
def run_flask():
    app.run(host="0.0.0.0", port=5000)

# Chạy chương trình
if __name__ == "__main__":
    print("Bắt đầu ghi dữ liệu và khởi chạy Flask server...")

    # Chạy Flask trong một luồng riêng
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Chạy chức năng đẩy dữ liệu
    try:
        push_optimized_data()
    except KeyboardInterrupt:
        print("Đã dừng chương trình!")
