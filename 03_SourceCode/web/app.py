import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import time

st.set_page_config(page_title="SOC Honeypot Dashboard", page_icon="🛡️", layout="wide")

st.title("🛡️ SOC HONEYPOT REAL-TIME MONITORING DASHBOARD")
st.markdown("---")

DB_URI = "postgresql+psycopg2://soc_admin:123456@soc_postgres:5432/honeypot_soc"

@st.cache_data(ttl=3)
def load_data():
    try:
        engine = create_engine(DB_URI)
        query = "SELECT * FROM incidents ORDER BY created_at DESC;"
        df = pd.read_sql(query, engine)
        return df
    except Exception as e:
        st.error(f"Lỗi kết nối CSDL: {e}")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    # 1. Các chỉ số Tổng quan Metric
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🔥 Tổng số đợt tấn công", len(df))
    col2.metric("🌐 IP Tấn công duy nhất", df['src_ip'].nunique())
    col3.metric("👤 Top Username", df['username'].mode()[0] if not df['username'].empty else "N/A")
    col4.metric("📍 Quốc gia hàng đầu", df['country'].mode()[0] if not df['country'].empty else "N/A")

    st.markdown("---")

    # 2. LOGIC CHIA TRANG (PAGINATION)
    st.subheader("📋 Bảng Nhật Ký Sự Cố An Ninh (Incidents Log)")

    # Cấu hình số dòng trên 1 trang (Mặc định: 10 dòng/trang)
    PAGE_SIZE = 10
    total_rows = len(df)
    total_pages = (total_rows - 1) // PAGE_SIZE + 1 if total_rows > 0 else 1

    # Thanh chọn trang và thông tin tổng quan
    p_col1, p_col2 = st.columns([1, 4])
    with p_col1:
        current_page = st.number_input("Trang", min_value=1, max_value=total_pages, value=1, step=1)
    with p_col2:
        st.caption(f"\n\nHiển thị **{total_rows}** sự cố | Trang **{current_page}/{total_pages}** ({PAGE_SIZE} dòng/trang)")

    # Cắt slice dữ liệu theo trang hiện tại
    start_idx = (current_page - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_df = df.iloc[start_idx:end_idx].copy()

    # Đặt chỉ số STT tăng dần 1, 2, 3... tương ứng với từng dòng trên trang đó
    page_df.index = range(start_idx + 1, start_idx + len(page_df) + 1)

    # Hiển thị bảng
    st.dataframe(
        page_df[['created_at', 'src_ip', 'country', 'city', 'isp', 'username', 'password', 'event_id']],
        use_container_width=True
    )
else:
    st.info("Chưa ghi nhận dữ liệu tấn công nào trong CSDL.")

time.sleep(5)
st.rerun()