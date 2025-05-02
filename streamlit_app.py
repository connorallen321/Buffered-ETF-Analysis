import streamlit as st
import openai
import yfinance as yf
import re
import matplotlib.pyplot as plt

st.set_page_config(page_title="Buffered ETF Chart", layout="centered")

st.title("📊 Buffered ETF Visualizer")
st.write("Enter a First Trust Buffered ETF ticker (e.g., `DAPR`, `FAPR`) to generate a payoff chart.")

openai.api_key = st.secrets["OPENAI_API_KEY"]

def get_current_price(ticker):
    try:
        t = yf.Ticker(ticker)
        price = t.info.get('regularMarketPrice', None)
        if not price:
            hist = t.history(period="1d")
            if not hist.empty:
                price = hist['Close'].iloc[-1]
        return price
    except:
        return None

def get_buffered_etf_data_from_gpt(ticker, current_price):
    prompt = f"""
For the First Trust Buffered ETF with ticker {ticker}, using a current price of ${current_price:.2f}, return realistic values:

Cap must be ~10-15% above current price  
Buffer Start just below current  
Buffer End ~8-10% below buffer start  
Floor is $0

Respond only as:
Cap: $XX.XX  
Buffer Start: $XX.XX  
Buffer End: $XX.XX
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You return only structured ETF data."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )

        result = response.choices[0].message["content"]
        cap = float(re.search(r'Cap:\s*\$(\d+\.\d+)', result).group(1))
        buffer_start = float(re.search(r'Buffer Start:\s*\$(\d+\.\d+)', result).group(1))
        buffer_end = float(re.search(r'Buffer End:\s*\$(\d+\.\d+)', result).group(1))
        if not (cap > buffer_start > buffer_end):
            return None, None, None
        return cap, buffer_start, buffer_end
    except:
        return None, None, None

def draw_chart(cap, current, buffer_start, buffer_end, floor=0.0):
    buffer_start, buffer_end = max(buffer_start, buffer_end), min(buffer_start, buffer_end)
    segments = []

    segments.append((current, cap, 'green', f'Upside to Cap ({(cap / current - 1) * 100:.1f}%)'))

    if current > buffer_start:
        segments.append((buffer_start, current, 'red', f'Initial Downside ({(current - buffer_start) / current * 100:.1f}%)'))
        segments.append((buffer_end, buffer_start, 'gray', f'Buffer Zone ({(buffer_start - buffer_end) / current * 100:.1f}%)'))
    else:
        segments.append((buffer_end, current, 'gray', f'Buffer Zone ({(current - buffer_end) / current * 100:.1f}%)'))

    unbuffered_top = min(current, buffer_end)
    segments.append((floor, unbuffered_top, 'darkred', f'Unbuffered Loss ({(unbuffered_top - floor) / current * 100:.1f}%)'))

    fig, ax = plt.subplots(figsize=(4, 10))
    for bottom, top, color, label in segments:
        height = top - bottom
        ax.bar(0, height, bottom=bottom, width=0.5, color=color, edgecolor='black')
        ax.text(1.0, bottom + height / 2, label, va='center', ha='left', fontsize=10)
    ax.axhline(y=current, color='black', linestyle='--', linewidth=1)
    ax.text(-0.3, current, f'Current\n{current:.2f}', va='center', ha='right', fontsize=10, fontweight='bold')
    ax.set_xticks([])
    ax.set_xlim(-1, 2.5)
    ax.set_ylim(0, cap + cap * 0.05)
    ax.set_ylabel("Price Range")
    ax.set_title("Buffered ETF Payoff Chart", fontsize=13, fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    st.pyplot(fig)

ticker = st.text_input("Enter Ticker (e.g. DAPR)", value="DAPR")

if ticker:
    if st.button("Generate Chart"):
        current = get_current_price(ticker)
        if not current:
            st.error("Could not fetch current price.")
        else:
            cap, buffer_start, buffer_end = get_buffered_etf_data_from_gpt(ticker, current)
            if None in [cap, buffer_start, buffer_end]:
                st.error("GPT failed to generate valid levels.")
            else:
                st.success(f"Cap: ${cap:.2f} | Buffer Start: ${buffer_start:.2f} | Buffer End: ${buffer_end:.2f} | Current: ${current:.2f}")
                draw_chart(cap, current, buffer_start, buffer_end)