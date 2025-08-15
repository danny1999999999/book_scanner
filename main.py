# main.py - Railway 入口點
from app_3 import app

# Railway 會自動偵測這個檔案並啟動
if __name__ == "__main__":
    import uvicorn
    import os
    
    port = int(os.getenv('PORT', '8000'))
    uvicorn.run(app, host="0.0.0.0", port=port)