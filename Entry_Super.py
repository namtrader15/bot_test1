from binance.client import Client
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, f1_score
import numpy as np
from datetime import datetime
import pytz

# Hàm tính xác suất kết hợp của hai mô hình không hoàn toàn độc lập
def combined_probability(p1, p2):
    combined_prob = p1 + p2 - (p1 * p2)
    return combined_prob

def get_realtime_klines(client, symbol, interval, lookback, end_time=None):
    if end_time:
        klines = client.futures_klines(symbol=symbol, interval=interval, endTime=int(end_time.timestamp() * 1000), limit=lookback)
    else:
        klines = client.futures_klines(symbol=symbol, interval=interval, limit=lookback)
    data = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 
                                         'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])
    data[['open', 'high', 'low', 'close']] = data[['open', 'high', 'low', 'close']].astype(float)
    data['volume'] = data['volume'].astype(float)
    
    # Tính giá trị Heikin-Ashi
    ha_open = (data['open'].shift(1) + data['close'].shift(1)) / 2
    ha_open.iloc[0] = (data['open'].iloc[0] + data['close'].iloc[0]) / 2
    ha_close = (data['open'] + data['high'] + data['low'] + data['close']) / 4
    ha_high = pd.concat([data['high'], ha_open, ha_close], axis=1).max(axis=1)
    ha_low = pd.concat([data['low'], ha_open, ha_close], axis=1).min(axis=1)
    
    # Thay thế giá trị nến Nhật bằng giá trị Heikin-Ashi trong DataFrame
    data['open'] = ha_open
    data['high'] = ha_high
    data['low'] = ha_low
    data['close'] = ha_close
    return data

def calculate_rsi(data, window):
    delta = data['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(data, slow=26, fast=12, signal=9):
    exp1 = data['close'].ewm(span=fast, adjust=False).mean()
    exp2 = data['close'].ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def analyze_trend(client, interval, name, end_time=None):
    # Lấy dữ liệu thời gian thực
    symbol = 'BTCUSDT'
    lookback = 1000
    data = get_realtime_klines(client, symbol, interval, lookback, end_time)
    rsi = calculate_rsi(data, 14)
    macd, signal_line = calculate_macd(data)

    # Tạo biến target cho học máy (1: giá tăng, 0: giá giảm)
    data['target'] = (data['close'].shift(-1) > data['close']).astype(int)

    # Chuẩn bị dữ liệu cho mô hình học máy
    data['rsi'] = rsi
    data['macd'] = macd
    data['signal_line'] = signal_line
    features = data[['rsi', 'macd', 'signal_line']].dropna()
    target = data['target'].dropna()

    # Đảm bảo rằng features và target có cùng số lượng hàng
    min_length = min(len(features), len(target))
    features = features.iloc[:min_length]
    target = target.iloc[:min_length]

    # Chuẩn hóa dữ liệu
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)

    # Chia dữ liệu thành tập huấn luyện và tập kiểm tra
    X_train, X_test, y_train, y_test = train_test_split(features_scaled, target, test_size=0.2, random_state=42)

    # Tuning Hyperparameters
    param_grid = {
        'C': [0.01, 0.1, 1, 10, 100, 1000],
        'solver': ['liblinear', 'saga', 'newton-cg', 'lbfgs']
    }
    grid = GridSearchCV(LogisticRegression(max_iter=1000), param_grid, refit=True, verbose=0)
    grid.fit(X_train, y_train)

    # Dự đoán trên tập kiểm tra
    y_pred = grid.predict(X_test)

    # Đánh giá mô hình
    accuracy = accuracy_score(y_test, y_pred) * 100  # Chuyển sang dạng %
    f1 = f1_score(y_test, y_pred) * 100  # Chuyển sang dạng %

    # Dự đoán xu hướng giá thời gian thực
    latest_features = features_scaled[-1].reshape(1, -1)
    prediction_prob = grid.predict_proba(latest_features)[0]
    prediction = grid.predict(latest_features)

    # Xác định xu hướng dựa trên ngưỡng
    trend = prediction[0]

    return trend, accuracy, f1

# Hàm trả về kết quả xu hướng cuối cùng
def get_final_trend(client):
    # Phân tích xu hướng cho hai khung thời gian
    trend_h1, accuracy_h1, f1_h1 = analyze_trend(client, Client.KLINE_INTERVAL_1HOUR, "H1")
    trend_h4, accuracy_h4, f1_h4 = analyze_trend(client, Client.KLINE_INTERVAL_4HOUR, "H4")

    # Tính xác suất kết hợp
    combined_acc = combined_probability(accuracy_h1 / 100, accuracy_h4 / 100)

    # Kiểm tra các điều kiện để quyết định kết quả
    if (trend_h1 == 1 and trend_h4 == 1 and combined_acc >= 0.88) or \
       (trend_h1 == 1 and accuracy_h1 >= 70 and f1_h1 >= 70) or \
       (trend_h4 == 1 and accuracy_h4 >= 70 and f1_h4 >= 70):
        return "Xu hướng tăng"
        
    elif (trend_h1 == 0 and trend_h4 == 0 and combined_acc >= 0.88) or \
         (trend_h1 == 0 and accuracy_h1 >= 70 and f1_h1 >= 70) or \
         (trend_h4 == 0 and accuracy_h4 >= 70 and f1_h4 >= 70):
        return "Xu hướng giảm"
        
    else:
        return "Xu hướng không rõ ràng"



