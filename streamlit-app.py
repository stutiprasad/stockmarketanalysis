import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Utility Functions
def get_stock_data(symbol, period='1y'):
    try:
        if not symbol.endswith('.NS'):
            symbol = f"{symbol}.NS"
        stock = yf.Ticker(symbol)
        hist = stock.history(period=period)
        if hist.empty:
            return None, None, None
        info = stock.info
        return hist, info, None
    except Exception as e:
        return None, None, str(e)

def format_large_number(num):
    if num >= 1e9:
        return f"₹{num/1e9:.2f}B"
    elif num >= 1e6:
        return f"₹{num/1e6:.2f}M"
    else:
        return f"₹{num:,.2f}"

def get_key_metrics(info):
    left_metrics = {
        'Market Cap': info.get('marketCap', 'N/A'),
        'PE Ratio': info.get('trailingPE', 'N/A'),
        'EPS': info.get('trailingEps', 'N/A'),
        '52 Week High': info.get('fiftyTwoWeekHigh', 'N/A'),
        '52 Week Low': info.get('fiftyTwoWeekLow', 'N/A')
    }
    
    right_metrics = {
        'Volume': info.get('volume', 'N/A'),
        'Dividend Yield': info.get('dividendYield', 'N/A'),
        'Beta': info.get('beta', 'N/A'),
        'Book Value': info.get('bookValue', 'N/A'),
        'Recommendation': info.get('recommendationKey', 'N/A').upper()
    }

    # Format metrics
    for key, value in left_metrics.items():
        if isinstance(value, (int, float)):
            if key == 'Market Cap':
                left_metrics[key] = format_large_number(value)
            else:
                left_metrics[key] = f"₹{value:,.2f}"

    for key, value in right_metrics.items():
        if isinstance(value, (int, float)):
            if key == 'Volume':
                right_metrics[key] = f"{value:,}"
            elif key == 'Dividend Yield':
                right_metrics[key] = f"{value*100:.2f}%" if value else 'N/A'
            else:
                right_metrics[key] = f"{value:.2f}"

    return left_metrics, right_metrics

@st.cache_data(ttl=3600)
def get_trading_signals(hist_data):
    df = hist_data.copy()
    
    # Calculate technical indicators
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA50'] = df['Close'].rolling(window=50).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    
    # RSI calculation
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # Generate signals
    signals = []
    current_price = df['Close'].iloc[-1]
    ma20 = df['MA20'].iloc[-1]
    ma50 = df['MA50'].iloc[-1]
    rsi = df['RSI'].iloc[-1]
    macd = df['MACD'].iloc[-1]
    signal_line = df['Signal_Line'].iloc[-1]
    
    # Add signals based on technical analysis
    if current_price > ma20 and current_price > ma50:
        signals.append(("🟢 Bullish", "Price above moving averages"))
    else:
        signals.append(("🔴 Bearish", "Price below moving averages"))
        
    if rsi > 70:
        signals.append(("⚠️ Overbought", f"RSI: {rsi:.2f}"))
    elif rsi < 30:
        signals.append(("⚠️ Oversold", f"RSI: {rsi:.2f}"))
    
    if macd > signal_line:
        signals.append(("📈 MACD Bullish", "MACD above signal line"))
    else:
        signals.append(("📉 MACD Bearish", "MACD below signal line"))
    
    return signals, df[['MA20', 'MA50', 'MA200', 'RSI', 'MACD', 'Signal_Line']]

@st.cache_data(ttl=1800)
def get_stock_news(symbol):
    try:
        symbol = symbol.replace('.NS', '')
        url = f"https://www.google.com/finance/quote/{symbol}:NSE"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            news_items = []
            
            news_divs = soup.find_all('div', {'class': 'yY3Lee'})
            for div in news_divs[:5]:
                title_elem = div.find('div', {'class': 'Yfwt5'})
                source_elem = div.find('div', {'class': 'sfyJob'})
                link_elem = div.find('a')
                
                if title_elem and link_elem:
                    news_items.append({
                        'title': title_elem.text.strip(),
                        'date': source_elem.text.strip() if source_elem else 'Recent',
                        'link': 'https://www.google.com' + link_elem['href'] if link_elem.get('href') else None
                    })
            
            return news_items
        return []
    except Exception as e:
        return []

# Main App
st.set_page_config(page_title="Indian Stock Analysis", page_icon="📈", layout="wide")

# Title and description
st.title("📈 Indian Stock Analysis Tool")
st.markdown("""
This tool provides comprehensive analysis of Indian stocks with:
- Real-time price data and technical indicators
- Trading signals and decision support
- Latest news and market data
""")

# Input section
col1, col2 = st.columns([2, 1])
with col1:
    stock_symbol = st.text_input(
        "Enter Stock Symbol (e.g., RELIANCE, TCS, INFY)",
        help="Enter the stock symbol without .NS suffix"
    ).upper()

with col2:
    period = st.selectbox(
        "Select Time Period",
        options=['1mo', '3mo', '6mo', '1y', '2y', '5y'],
        index=3
    )

if stock_symbol:
    hist_data, info, error = get_stock_data(stock_symbol, period)
    
    if error:
        st.error(f"Error fetching data: {error}")
    elif hist_data is None:
        st.error("No data found for the given stock symbol")
    else:
        # Display current price and change
        current_price = hist_data['Close'].iloc[-1]
        price_change = current_price - hist_data['Close'].iloc[-2]
        price_change_pct = (price_change / hist_data['Close'].iloc[-2]) * 100

        # Metrics row
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "Current Price",
                f"₹{current_price:,.2f}",
                f"{price_change:+,.2f} ({price_change_pct:+.2f}%)"
            )
        with col2:
            st.metric("Volume", f"{hist_data['Volume'].iloc[-1]:,}")
        with col3:
            st.metric(
                "52-Week Range",
                f"₹{hist_data['Low'].min():,.2f} - ₹{hist_data['High'].max():,.2f}"
            )

        # Trading Signals
        st.subheader("📊 Trading Signals & Analysis")
        signals, technical_data = get_trading_signals(hist_data)
        
        cols = st.columns(len(signals))
        for idx, (signal, description) in enumerate(signals):
            with cols[idx]:
                st.markdown(f"### {signal}")
                st.markdown(description)

        # Key metrics
        with st.expander("🔍 Key Financial Metrics", expanded=True):
            left_metrics, right_metrics = get_key_metrics(info)
            metrics_col1, metrics_col2 = st.columns(2)
            
            with metrics_col1:
                for metric, value in left_metrics.items():
                    st.write(f"**{metric}**")
                    st.write(value)
                    st.write("---")
                    
            with metrics_col2:
                for metric, value in right_metrics.items():
                    st.write(f"**{metric}**")
                    st.write(value)
                    st.write("---")

        # Main price chart
        st.subheader("📈 Technical Analysis")
        fig = go.Figure()
        
        fig.add_trace(go.Candlestick(
            x=hist_data.index,
            open=hist_data['Open'],
            high=hist_data['High'],
            low=hist_data['Low'],
            close=hist_data['Close'],
            name='OHLC'
        ))
        
        # Add moving averages
        for ma, color in [('MA20', 'blue'), ('MA50', 'orange'), ('MA200', 'red')]:
            fig.add_trace(go.Scatter(
                x=hist_data.index,
                y=technical_data[ma],
                name=f'{ma}-day MA',
                line=dict(color=color, width=1)
            ))

        fig.update_layout(
            title=f"{stock_symbol} Stock Price Chart",
            yaxis_title="Price (₹)",
            xaxis_title="Date",
            template="plotly_white",
            height=600
        )

        st.plotly_chart(fig, use_container_width=True)

        # Recent News
        st.subheader("📰 Recent News")
        news_items = get_stock_news(stock_symbol)
        
        if news_items:
            for news in news_items:
                st.markdown(f"**{news['title']}**")
                st.markdown(f"*{news['date']}*")
                if news['link']:
                    st.markdown(f"[Read more]({news['link']})")
                st.markdown("---")
        else:
            st.info(f"No recent news found for {stock_symbol}")

        # Download data
        download_data = hist_data.copy()
        download_data.index = download_data.index.strftime('%Y-%m-%d')
        
        for col in technical_data.columns:
            download_data[col] = technical_data[col]
            
        st.download_button(
            label="Download Data as CSV",
            data=download_data.to_csv(),
            file_name=f"{stock_symbol}_stock_data.csv",
            mime="text/csv"
        )
else:
    st.info("👆 Enter a stock symbol to begin analysis")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center'>
        Data provided by Yahoo Finance | Built with Streamlit
    </div>
    """,
    unsafe_allow_html=True
)