@echo off
cd /d "C:\Users\yaououzhong\Work\boss-resume-filter"
streamlit run src/web/app_rough.py --server.port 8501 --server.address 0.0.0.0 --server.headless=true