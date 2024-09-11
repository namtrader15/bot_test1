from binance.client import Client
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

def get_realtime_klines(symbol, interval, lookback, client, end_time=None):
    if end_time:
        klines = client.futures_klines(symbol=symbol, interval=interval, endTime=int(end_time.timestamp() * 1000), limit=lookback)
    else:
        klines = client.futures_klines(symbol=symbol, interval=interval, limit=lookback)
    data = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 
                                         'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])
    data[['open', 'high', 'low', 'close']] = data[['open', 'high', 'low', 'close']].astype(float)
    data['volume'] = data['volume'].astype(float)

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

def analyze_trend(interval, client):
    # Lấy dữ liệu thời gian thực
    symbol = 'BTCUSDT'
    lookback = 1000  # Giới hạn số lượng nến tối đa là 1000
    data = get_realtime_klines(symbol, interval, lookback, client)
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

    # Huấn luyện mô hình Logistic Regression
    model = LogisticRegression(max_iter=1000, solver='lbfgs')
    model.fit(X_train, y_train)

    # Dự đoán xu hướng giá thời gian thực
    latest_features = features_scaled[-1].reshape(1, -1)
    prediction_prob = model.predict_proba(latest_features)[0]
    prediction = model.predict(latest_features)

    # Ngưỡng cho xu hướng không rõ ràng
    threshold = 0.45

    # Xác định xu hướng dựa trên ngưỡng
    if prediction_prob[1] > 1 - threshold:
        trend = 1  # Xu hướng tăng
    elif prediction_prob[1] < threshold:
        trend = 0  # Xu hướng giảm
    else:
        trend = None  # Xu hướng không rõ ràng

    return trend

def get_final_trend():
    # Khởi tạo client Binance với API Key và Secret
    api_key = 'YOUR_API_KEY'
    api_secret = 'YOUR_API_SECRET'
    client = Client(api_key, api_secret, tld='com', testnet=False)

    # Phân tích xu hướng cho ba khung thời gian
    trend_1m = analyze_trend(Client.KLINE_INTERVAL_1MINUTE, client)
    trend_15m = analyze_trend(Client.KLINE_INTERVAL_15MINUTE, client)
    trend_4h = analyze_trend(Client.KLINE_INTERVAL_4HOUR, client)

    # Kiểm tra kết quả từ ba khung thời gian để đưa ra kết quả cuối cùng
    if trend_1m == 1 and trend_15m == 1 and trend_4h == 1:
        final_trend = "Xu Hướng Tăng!"
    elif trend_1m == 0 and trend_15m == 0 and trend_4h == 0:
        final_trend = "Xu Hướng Giảm!"
    elif trend_1m is None and trend_15m is None and trend_4h is None:
        final_trend = "Xu hướng không rõ ràng!"
    else:
        final_trend = "Xu hướng chưa rõ ràng!"

    return final_trend
