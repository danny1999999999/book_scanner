# FastAPI版本書籍識別系統 - 旋轉變體增強版 (PostgreSQL完整版)
# 檔案名: app_postgresql_complete.py
# 資料庫: PostgreSQL

# ===== 標準函式庫 =====
import io
import os
import json
import uuid
import traceback
import logging
from pathlib import Path
from typing import Any, Annotated, Dict, List, Optional, Tuple
import base64
import pickle
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

# ===== 環境變數載入 =====
from dotenv import load_dotenv
load_dotenv()  # 🔥 載入 .env 檔案

# ===== PostgreSQL 相關 =====
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql
from psycopg2.pool import ThreadedConnectionPool

# ===== 基礎數值、影像庫 =====
import numpy as np
import torch
from PIL import Image

# ===== Transformer 與模型 =====
from transformers import CLIPModel, CLIPProcessor

# ===== 伺服器與框架 =====
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== PostgreSQL 配置類 =====
class DatabaseConfig:
    def __init__(self):
        self.host = os.getenv('DB_HOST', 'localhost')
        self.port = int(os.getenv('DB_PORT', '5433'))
        self.database = os.getenv('DB_NAME', 'book_recognition')
        self.user = os.getenv('DB_USER', 'postgres')
        self.password = os.getenv('DB_PASSWORD', 'postgres')
        self.pool = None
        
        # 初始化連接池
        self._init_connection_pool()
        
    def _init_connection_pool(self):
        """初始化連接池"""
        try:
            self.pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=20,
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                cursor_factory=RealDictCursor
            )
            logger.info("✅ PostgreSQL 連接池初始化成功")
        except Exception as e:
            logger.error(f"❌ 連接池初始化失敗: {e}")
            raise
    
    def get_connection(self):
        """從連接池獲取連接"""
        try:
            if self.pool:
                conn = self.pool.getconn()
                if conn:
                    return conn
            
            # 備用：直接連接
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                cursor_factory=RealDictCursor
            )
            conn.autocommit = False
            return conn
        except Exception as e:
            logger.error(f"資料庫連接失敗: {e}")
            raise
    
    def return_connection(self, conn):
        """歸還連接到池"""
        try:
            if self.pool and conn:
                self.pool.putconn(conn)
        except Exception as e:
            logger.error(f"歸還連接失敗: {e}")
    
    def close_all_connections(self):
        """關閉所有連接"""
        try:
            if self.pool:
                self.pool.closeall()
                logger.info("✅ 所有資料庫連接已關閉")
        except Exception as e:
            logger.error(f"❌ 關閉連接失敗: {e}")

# 創建資料庫配置實例
db_config = DatabaseConfig()

# 初始化 CLIP 模型
try:
    _clip_model = CLIPModel.from_pretrained("openai/clip-vit-large-patch14").eval()
    _clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-large-patch14")
    logger.info("✅ CLIP 模型初始化成功")
except Exception as e:
    logger.error(f"❌ CLIP 模型初始化失敗: {e}")
    _clip_model = None
    _clip_processor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理"""
    # 啟動事件
    try:
        ensure_table()
        logger.info("✅ PostgreSQL資料庫表格檢查完成")
    except Exception as e:
        logger.error(f"❌ PostgreSQL資料庫初始化失敗: {e}")
    
    yield
    
    # 關閉事件
    try:
        db_config.close_all_connections()
        logger.info("✅ 應用關閉，所有資源已清理")
    except Exception as e:
        logger.error(f"❌ 關閉應用時發生錯誤: {e}")

app = FastAPI(title="FastAPI 旋轉增強版書籍識別系統 v3.1 (PostgreSQL完整版)", lifespan=lifespan)

# 確保目錄存在
static_dir = Path(__file__).parent / "static"
covers_dir = static_dir / "covers"
templates_dir = Path(__file__).parent / "templates2"

static_dir.mkdir(exist_ok=True)
covers_dir.mkdir(exist_ok=True)
templates_dir.mkdir(exist_ok=True)

# 掛載靜態文件和模板
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates2")

# ===== Pydantic 模型定義 =====
class BookModel(BaseModel):
    title: str
    isbn: Optional[str] = ""
    url: Optional[str] = ""
    image: str

class SystemStatus(BaseModel):
    clip_available: bool
    clip_status: str
    enhanced_clip_model: bool
    rotation_support: bool
    device: str
    model_name: str
    enhancement_features: List[str]
    current_model: Dict[str, Any]
    compatibility_status: str

class BookResponse(BaseModel):
    id: Optional[int]
    title: str
    isbn: Optional[str] = ""
    url: Optional[str] = ""
    similarity_score: Optional[float]
    comparison_method: Optional[str]
    rotation_angle: Optional[int]
    details: Optional[Dict[str, Any]] = None

class ApiResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    book: Optional[BookResponse] = None
    data: Optional[Any] = None

# ===== 全域異常處理器 =====
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全域異常處理器，確保所有錯誤都返回JSON格式"""
    logger.error(f"全域異常: {exc}")
    logger.error(f"異常詳情: {traceback.format_exc()}")
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": f"伺服器內部錯誤: {str(exc)}",
            "error_type": type(exc).__name__,
            "detail": "請檢查伺服器日誌以獲取更多資訊"
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP 異常處理器"""
    logger.error(f"HTTP 異常: {exc.status_code} - {exc.detail}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "error_type": "HTTPException",
            "status_code": exc.status_code
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """請求驗證錯誤處理器"""
    logger.error(f"請求驗證錯誤: {exc}")
    
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "請求資料格式錯誤",
            "error_type": "ValidationError",
            "errors": exc.errors()
        }
    )

# ===== 資料庫操作函數 =====
def ensure_table():
    """確保資料庫表格存在並更新結構 - PostgreSQL版本"""
    logger.info(f"🔧 檢查PostgreSQL資料庫表格")
    
    conn = None
    try:
        conn = db_config.get_connection()
        cursor = conn.cursor()
        
        # 檢查 books 表格是否存在
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'books'
            );
        """)
        books_table_exists = cursor.fetchone()[0]
        
        if books_table_exists:
            # 檢查 books 表格的欄位結構
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'books'
                ORDER BY ordinal_position;
            """)
            columns_info = cursor.fetchall()
            column_names = [col['column_name'] for col in columns_info]
            logger.info(f"📋 現有 books 表格欄位: {column_names}")
            
            # 檢查是否缺少 cover_path 欄位
            if 'cover_path' not in column_names:
                logger.info("⚡ 添加 cover_path 欄位")
                cursor.execute("ALTER TABLE books ADD COLUMN cover_path TEXT")
            
            # 檢查是否缺少 created_at 欄位
            if 'created_at' not in column_names:
                logger.info("⚡ 添加 created_at 欄位")
                cursor.execute("ALTER TABLE books ADD COLUMN created_at TIMESTAMP DEFAULT NOW()")
                cursor.execute("UPDATE books SET created_at = NOW() WHERE created_at IS NULL")
                logger.info("⏰ 已為現有記錄設置創建時間")
        else:
            # 建立新的 books 表格
            logger.info("🆕 建立新的 books 表格")
            cursor.execute("""
                CREATE TABLE books (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    isbn TEXT,
                    url TEXT,
                    cover_path TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

        # 建立 cover_embeddings 表格
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cover_embeddings (
                book_id INTEGER PRIMARY KEY,
                vector BYTEA,
                FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE CASCADE
            );
        """)
        
        # 添加索引提升性能
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_books_title 
            ON books USING btree (title);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_books_created_at 
            ON books USING btree (created_at DESC);
        """)
        
        # 檢查現有資料
        cursor.execute("SELECT COUNT(*) FROM books")
        book_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM cover_embeddings")
        embedding_count = cursor.fetchone()[0]
        
        logger.info(f"📚 現有書籍記錄: {book_count}")
        logger.info(f"🧠 現有向量記錄: {embedding_count}")
        
        # 顯示幾筆書籍資料
        if book_count > 0:
            cursor.execute("SELECT id, title, cover_path FROM books ORDER BY id DESC LIMIT 3")
            recent_books = cursor.fetchall()
            logger.info("📖 最近的書籍:")
            for book in recent_books:
                logger.info(f"   ID: {book['id']}, 標題: '{book['title']}', 封面: '{book['cover_path'] or '無'}'")
        
        conn.commit()
        
    except Exception as e:
        logger.error(f"資料庫表格檢查失敗: {e}")
        logger.error(f"詳細錯誤: {traceback.format_exc()}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            db_config.return_connection(conn)

def save_uploaded_image(image_data: bytes, book_id: int) -> str:
    """儲存上傳的圖片到 static/covers 目錄"""
    try:
        # 生成檔案名稱
        filename = f"book_{book_id}_{uuid.uuid4().hex[:8]}.jpg"
        file_path = covers_dir / filename
        
        # 儲存圖片
        with open(file_path, 'wb') as f:
            f.write(image_data)
        
        return str(file_path)
    except Exception as e:
        logger.error(f"儲存圖片失敗: {e}")
        return ""

def detect_cartoon_book_simple(pil_image):
    """簡單檢測卡通風格書籍"""
    try:
        import numpy as np
        img_array = np.array(pil_image)
        
        # 1. 檢測主要顏色
        r_mean = np.mean(img_array[:, :, 0])
        g_mean = np.mean(img_array[:, :, 1])
        b_mean = np.mean(img_array[:, :, 2])
        
        # 2. 檢測顏色飽和度
        color_variance = np.var([r_mean, g_mean, b_mean])
        
        # 3. 粗略判斷 - 確保返回 Python bool
        is_cartoon = bool(color_variance > 500)
        
        logger.info(f"🎨 顏色分析: R={r_mean:.1f}, G={g_mean:.1f}, B={b_mean:.1f}, 變異數={color_variance:.1f}")
        logger.info(f"🎨 卡通書籍判定: {is_cartoon}")
        
        return is_cartoon
        
    except Exception as e:
        logger.error(f"卡通檢測失敗: {e}")
        return False

async def save_book_with_rotation_enhanced(
    title: str,
    isbn: str,
    url: str,
    image_file: Any
) -> Tuple[bool, str]:
    """
    管理流程：建表 → 儲存 metadata → 計算 CLIP embedding → 寫入向量 - PostgreSQL版本
    """
    conn = None
    try:
        # 檢查 CLIP 模型是否可用
        if _clip_model is None or _clip_processor is None:
            return False, "CLIP 模型未正確初始化"
        
        # 1) 確保表存在
        ensure_table()
        
        # 2) 讀取圖片資料
        if hasattr(image_file, 'read'):
            if asyncio.iscoroutinefunction(image_file.read):
                img_bytes = await image_file.read()
            else:
                img_bytes = image_file.read()
        elif isinstance(image_file, str):
            # 處理 base64 字串
            if image_file.startswith("data:") and "," in image_file:
                _, b64 = image_file.split(",", 1)
            else:
                b64 = image_file
            img_bytes = base64.b64decode(b64)
        else:
            return False, "無效的圖片資料"

        # 3) 儲存書本 metadata - PostgreSQL版本
        logger.info(f"📝 使用PostgreSQL資料庫")
        conn = db_config.get_connection()
        cursor = conn.cursor()
        
        # 插入時明確設定 created_at
        cursor.execute("""
            INSERT INTO books(title, isbn, url, cover_path, created_at) 
            VALUES(%s, %s, %s, %s, NOW()) 
            RETURNING id
        """, (title, isbn, url, ""))
        
        book_id = cursor.fetchone()[0]
        logger.info(f"📚 新增書籍 ID: {book_id}, 標題: {title}")
        
        # 4) 儲存圖片檔案
        cover_path = save_uploaded_image(img_bytes, book_id)
        if cover_path:
            cursor.execute(
                "UPDATE books SET cover_path = %s WHERE id = %s",
                (cover_path, book_id)
            )
            logger.info(f"🖼️ 圖片已儲存: {cover_path}")

        # 5) 計算向量
        pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        inputs = _clip_processor(images=pil_img, return_tensors="pt")
        with torch.no_grad():
            emb = _clip_model.get_image_features(**inputs).numpy().flatten()

        # 6) 寫入 cover_embeddings - PostgreSQL使用BYTEA
        cursor.execute("""
            INSERT INTO cover_embeddings(book_id, vector) 
            VALUES(%s, %s) 
            ON CONFLICT (book_id) 
            DO UPDATE SET vector = EXCLUDED.vector
        """, (book_id, emb.tobytes()))
        
        logger.info(f"🧠 向量已儲存，維度: {len(emb)}")

        # 7) 提交並關閉
        conn.commit()
        return True, f"書籍與向量已建立 (ID: {book_id})"
        
    except Exception as e:
        logger.error(f"❌ 儲存書籍失敗: {e}")
        logger.error(f"詳細錯誤: {traceback.format_exc()}")
        if conn:
            conn.rollback()
        return False, f"儲存失敗: {str(e)}"
    finally:
        if conn:
            db_config.return_connection(conn)

async def identify_book_with_rotation_enhanced(image_file):
    """加入卡通書處理的識別函數 - PostgreSQL版本"""
    conn = None
    try:
        # 檢查 CLIP 模型是否可用
        if _clip_model is None or _clip_processor is None:
            return {}, "CLIP 模型未正確初始化"
        
        ensure_table()

        # 讀取圖片
        if hasattr(image_file, "read"):
            read_fn = image_file.read
            if asyncio.iscoroutinefunction(read_fn):
                img_bytes = await read_fn()
            else:
                img_bytes = read_fn()
        else:
            return {}, "無效的檔案物件"

        pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        # 檢測是否為卡通風格書籍
        is_cartoon = detect_cartoon_book_simple(pil_img)
        
        # 載入資料庫 - PostgreSQL版本
        logger.info(f"🔍 從PostgreSQL載入向量")
        conn = db_config.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT book_id, vector FROM cover_embeddings")
        rows = cursor.fetchall()
        
        db_items = []
        for row in rows:
            book_id = row['book_id']
            vector_bytes = row['vector']
            # PostgreSQL BYTEA 需要直接使用 bytes
            if isinstance(vector_bytes, memoryview):
                vector_bytes = vector_bytes.tobytes()
            vector = np.frombuffer(vector_bytes, dtype=np.float32)
            db_items.append((book_id, vector))
        
        logger.info(f"📊 找到 {len(db_items)} 個向量記錄")

        if not db_items:
            return {}, "資料庫中沒有書籍記錄"

        # 根據書籍類型調整閾值
        if is_cartoon:
            HIGH_CONFIDENCE_THRESHOLD = 0.75  # 降低5%
            LOW_CONFIDENCE_THRESHOLD = 0.60   # 降低5%
            MIN_GAP_REQUIRED = 0.12
            logger.info(f"🎨 檢測到卡通風格書籍，使用調整後閾值")
        else:
            HIGH_CONFIDENCE_THRESHOLD = 0.70  # 降低5%
            LOW_CONFIDENCE_THRESHOLD = 0.55   # 降低5%
            MIN_GAP_REQUIRED = 0.08

        # 四角度旋轉比對
        best = {"book_id": None, "score": -1.0, "rotation": 0}
        all_scores = []
        
        for angle in (0, 90, 180, 270):
            rotated = pil_img.rotate(angle, expand=True)
            inputs = _clip_processor(images=rotated, return_tensors="pt")
            with torch.no_grad():
                emb = _clip_model.get_image_features(**inputs).numpy().flatten()
            
            for book_id, db_emb in db_items:
                # 針對卡通書籍使用改良的相似度計算
                if is_cartoon:
                    # 方法1: 標準餘弦相似度
                    dot = float(np.dot(emb, db_emb))
                    norm = float(np.linalg.norm(emb) * np.linalg.norm(db_emb))
                    cosine_sim = dot / norm if norm else 0.0
                    
                    # 方法2: 歐幾里得距離補償
                    euclidean_dist = float(np.linalg.norm(emb - db_emb))
                    euclidean_sim = 1 / (1 + euclidean_dist)
                    
                    # 融合兩種方法
                    score = 0.7 * cosine_sim + 0.3 * euclidean_sim
                else:
                    # 普通書籍使用標準餘弦相似度
                    dot = float(np.dot(emb, db_emb))
                    norm = float(np.linalg.norm(emb) * np.linalg.norm(db_emb))
                    score = dot / norm if norm else 0.0
                
                all_scores.append(score)
                
                if score > best["score"]:
                    best.update({"book_id": book_id, "score": score, "rotation": angle})

        logger.info(f"🎯 最佳匹配: ID={best['book_id']}, 分數={best['score']:.3f}, 角度={best['rotation']}°")

        # 分析分數分布
        if all_scores:
            max_score = max(all_scores)
            second_max = sorted(all_scores, reverse=True)[1] if len(all_scores) > 1 else 0
            score_gap = max_score - second_max
            
            logger.info(f"📊 分數分析: 最高={max_score:.3f}, 第二高={second_max:.3f}, 差距={score_gap:.3f}")
            logger.info(f"🔍 需要差距: {MIN_GAP_REQUIRED:.3f}, 卡通書: {is_cartoon}")

            # 智能判斷邏輯
            if best["book_id"] and best["score"] >= HIGH_CONFIDENCE_THRESHOLD and score_gap >= MIN_GAP_REQUIRED:
                result_type = "high_confidence"
                
            elif best["book_id"] and best["score"] >= LOW_CONFIDENCE_THRESHOLD and score_gap >= MIN_GAP_REQUIRED:
                result_type = "medium_confidence"
                
            elif best["book_id"] and best["score"] >= LOW_CONFIDENCE_THRESHOLD:
                # 分數差距不足時標記為不確定
                result_type = "low_confidence_similar"
                logger.info(f"⚠️ 分數差距不足 ({score_gap:.3f} < {MIN_GAP_REQUIRED:.3f})，標記為不確定匹配")
                
            else:
                result_type = "unknown_book"
        else:
            result_type = "unknown_book"

        # 返回結果處理
        if result_type == "unknown_book":
            return {
                "unknown_book": True,
                "best_match_score": round(best["score"] * 100, 2),
                "suggestion": "這可能是資料庫中沒有的新書" + 
                             ("（卡通書籍檢測較嚴格）" if is_cartoon else ""),
                "action_needed": "add_new_book",
                "cartoon_detected": is_cartoon
            }, ""

        elif result_type == "low_confidence_similar":
            # 對不確定的匹配要求用戶確認
            cursor.execute("SELECT title, isbn, url FROM books WHERE id = %s", (best["book_id"],))
            row = cursor.fetchone()
            
            if row:
                return {
                    "uncertain_match": True,
                    "id": best["book_id"],
                    "title": row['title'],
                    "isbn": row['isbn'] or "",
                    "url": row['url'] or "",
                    "similarity_score": round(best["score"] * 100, 2),
                    "comparison_method": "CLIP 旋轉增強 (卡通書模式)" if is_cartoon else "CLIP 旋轉增強",
                    "rotation_angle": best["rotation"],
                    "warning": "識別信心較低，請確認是否為正確書籍" + 
                              ("（卡通書籍容易混淆）" if is_cartoon else ""),
                    "details": {
                        "confidence_level": "低",
                        "processing_type": "FastAPI Enhanced",
                        "score_gap": round(score_gap * 100, 2) if 'score_gap' in locals() else 0,
                        "cartoon_detected": is_cartoon,
                        "gap_required": round(MIN_GAP_REQUIRED * 100, 2)
                    }
                }, ""

        else:
            # 正常的高/中信心識別
            cursor.execute("SELECT title, isbn, url FROM books WHERE id = %s", (best["book_id"],))
            row = cursor.fetchone()
            
            if row:
                result = {
                    "id": best["book_id"],
                    "title": row['title'],
                    "isbn": row['isbn'] or "",
                    "url": row['url'] or "",
                    "similarity_score": round(best["score"] * 100, 2),
                    "comparison_method": "CLIP 旋轉增強 (卡通書模式)" if is_cartoon else "CLIP 旋轉增強",
                    "rotation_angle": best["rotation"],
                    "details": {
                        "confidence_level": "高" if result_type == "high_confidence" else "中",
                        "processing_type": "FastAPI Enhanced",
                        "score_gap": round(score_gap * 100, 2) if 'score_gap' in locals() else 0,
                        "cartoon_detected": is_cartoon
                    }
                }
                logger.info(f"✅ 識別成功: {row['title']}")
                return result, ""

        return {}, "未找到匹配的書籍"
        
    except Exception as e:
        logger.error(f"❌ 識別失敗: {e}")
        logger.error(f"詳細錯誤: {traceback.format_exc()}")
        return {}, f"識別過程發生錯誤: {str(e)}"
    finally:
        if conn:
            db_config.return_connection(conn)

def check_enhanced_clip_status() -> str:
    try:
        if _clip_model is None or _clip_processor is None:
            return "uninstalled"
        _ = _clip_model.get_image_features
        return "normal"
    except ModuleNotFoundError:
        return "uninstalled"
    except Exception:
        return "load_failed"

def convert_numpy_types(obj):
    """
    完整轉換所有 numpy 類型為 Python 原生類型
    """
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):  # 🔥 關鍵：處理 numpy.bool
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy_types(v) for v in obj]
    elif hasattr(obj, 'item'):  # torch 張量等
        try:
            return obj.item()
        except:
            return str(obj)
    else:
        return obj

# ===== HTML路由 =====
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主頁"""
    clip_status = check_enhanced_clip_status()
    clip_ok = clip_status == "normal"
    
    context = {
        "request": request,
        "clip_status": clip_status,
        "clip_ok": clip_ok,
        "status_class": "status-normal" if clip_ok else "status-error"
    }
    
    return templates.TemplateResponse("index.html", context)

@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    """書籍管理頁面"""
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/scanner", response_class=HTMLResponse)
async def scanner(request: Request):
    """掃描識別頁面"""
    return templates.TemplateResponse("scanner.html", {"request": request})

@app.get("/records", response_class=HTMLResponse)
async def records(request: Request):
    """記錄分析頁面"""
    return templates.TemplateResponse("records.html", {"request": request})

@app.get("/model_status", response_class=HTMLResponse)
async def model_status(request: Request):
    """系統狀態監控頁面"""
    return templates.TemplateResponse("model_status.html", {"request": request})

# ===== 核心API路由 =====
@app.post("/api/save_book", response_model=ApiResponse)
async def api_save_book(book_data: BookModel):
    """儲存書籍 - JSON格式"""
    try:
        logger.info(f"開始儲存書籍: {book_data.title}")
        
        # 驗證必要欄位
        if not book_data.title or not book_data.title.strip():
            return ApiResponse(
                success=False,
                message="書名不能為空"
            )
        
        if not book_data.image:
            return ApiResponse(
                success=False,
                message="圖片資料不能為空"
            )
        
        success, message = await save_book_with_rotation_enhanced(
            book_data.title.strip(),
            book_data.isbn.strip() if book_data.isbn else "",
            book_data.url.strip() if book_data.url else "",
            book_data.image
        )
        
        if success:
            logger.info(f"書籍儲存成功: {book_data.title}")
        else:
            logger.warning(f"書籍儲存失敗: {message}")
        
        return ApiResponse(
            success=success,
            message=message
        )
        
    except Exception as e:
        logger.error(f"儲存書籍異常: {e}")
        logger.error(f"詳細錯誤: {traceback.format_exc()}")
        return ApiResponse(
            success=False,
            message=f"FastAPI儲存錯誤: {str(e)}"
        )

@app.post("/api/save_book_file", response_model=ApiResponse)
async def api_save_book_file(
    title: Annotated[str, Form()],
    isbn: Annotated[str, Form()] = "",
    url: Annotated[str, Form()] = "",
    image: UploadFile = File(...)
):
    """儲存書籍 - 檔案上傳格式"""
    try:
        logger.info(f"開始儲存書籍檔案: {title}")
        
        # 驗證必要欄位
        if not title or not title.strip():
            return ApiResponse(
                success=False,
                message="書名不能為空"
            )
        
        # 驗證檔案
        if not image.content_type or not image.content_type.startswith('image/'):
            return ApiResponse(
                success=False,
                message=f"不支援的檔案類型: {image.content_type}"
            )
        
        # 檢查檔案大小
        content = await image.read()
        if len(content) == 0:
            return ApiResponse(
                success=False,
                message="上傳的檔案為空"
            )
        
        if len(content) > 10 * 1024 * 1024:  # 10MB
            return ApiResponse(
                success=False,
                message=f"檔案過大: {len(content) / 1024 / 1024:.1f}MB (限制: 10MB)"
            )
        
        # 重置檔案指針
        await image.seek(0)
        
        success, message = await save_book_with_rotation_enhanced(
            title.strip(),
            isbn.strip(),
            url.strip(),
            image
        )
        
        if success:
            logger.info(f"書籍檔案儲存成功: {title}")
        else:
            logger.warning(f"書籍檔案儲存失敗: {message}")
        
        return ApiResponse(
            success=success,
            message=message
        )
        
    except Exception as e:
        logger.error(f"儲存書籍檔案異常: {e}")
        logger.error(f"詳細錯誤: {traceback.format_exc()}")
        return ApiResponse(
            success=False,
            message=f"FastAPI檔案儲存錯誤: {str(e)}"
        )

@app.post("/api/identify_book")
async def api_identify_book(book_data: BookModel):
    """識別書籍 - JSON格式"""
    try:
        logger.info(f"開始識別書籍 - JSON格式")
        
        if not book_data.image:
            return {"success": False, "message": "圖片資料不能為空"}
        
        image_str = book_data.image
        if image_str.startswith("data:") and "," in image_str:
            _, b64data = image_str.split(",", 1)
        else:
            b64data = image_str

        try:
            image_bytes = base64.b64decode(b64data)
            if len(image_bytes) == 0:
                raise ValueError("Base64 解碼後圖片為空")
        except Exception as e:
            logger.error(f"Base64 解碼失敗: {e}")
            return {"success": False, "message": f"圖片格式錯誤: {str(e)}"}

        fake_file = io.BytesIO(image_bytes)
        fake_file.name = "upload.png"
        fake_file.seek(0)

        # 呼叫識別函數
        result, error = await identify_book_with_rotation_enhanced(fake_file)

        if result:
            logger.info(f"識別成功: {result.get('title', 'Unknown')}")
            
            # 完全轉換所有類型
            clean_result = convert_numpy_types(result)
            
            return {
                "success": True,
                "book": clean_result,
                "message": "識別成功"
            }
        else:
            logger.warning(f"識別失敗: {error}")
            return {"success": False, "message": error or "未找到匹配的書籍"}
            
    except Exception as e:
        logger.error(f"識別過程異常: {e}")
        logger.error(f"詳細錯誤: {traceback.format_exc()}")
        return {"success": False, "message": f"FastAPI 處理錯誤: {str(e)}"}

@app.post("/api/identify_book_file")
async def api_identify_book_file(image: UploadFile = File(...)):
    """識別書籍 - 檔案上傳格式"""
    try:
        logger.info(f"開始識別書籍 - 檔案格式: {image.filename}")
        
        if not image.content_type or not image.content_type.startswith('image/'):
            return {"success": False, "message": f"不支援的檔案類型: {image.content_type}"}
        
        content = await image.read()
        file_size = len(content)
        
        if file_size > 10 * 1024 * 1024:
            return {"success": False, "message": f"檔案過大: {file_size / 1024 / 1024:.1f}MB (限制: 10MB)"}
        
        if file_size == 0:
            return {"success": False, "message": "上傳的檔案為空"}
        
        await image.seek(0)
        
        # 呼叫識別函數
        result, error = await identify_book_with_rotation_enhanced(image)

        if result:
            logger.info(f"識別成功: {result.get('title', 'Unknown')}")
            
            # 完全轉換所有類型
            clean_result = convert_numpy_types(result)
            
            return {
                "success": True,
                "book": clean_result,
                "message": "識別成功"
            }
        else:
            logger.warning(f"識別失敗: {error}")
            return {"success": False, "message": error or "未找到匹配的書籍"}
            
    except Exception as e:
        logger.error(f"檔案識別過程異常: {e}")
        logger.error(f"詳細錯誤: {traceback.format_exc()}")
        return {"success": False, "message": f"FastAPI 檔案處理錯誤: {str(e)}"}

@app.get("/api/books")
async def api_books():
    """取得所有書籍記錄 - PostgreSQL版本"""
    conn = None
    try:
        logger.info("📡 FastAPI PostgreSQL /api/books 被呼叫")
        
        ensure_table()
        
        conn = db_config.get_connection()
        cursor = conn.cursor()
        
        # 檢查表格結構
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'books'
            ORDER BY ordinal_position;
        """)
        columns_info = cursor.fetchall()
        column_names = [col['column_name'] for col in columns_info]
        logger.info(f"📋 books 表格欄位: {column_names}")
        
        # 查詢所有書籍
        cursor.execute("""
            SELECT id, title, isbn, url, cover_path, created_at 
            FROM books 
            ORDER BY id DESC
        """)
        books_data = cursor.fetchall()
        
        logger.info(f"📊 資料庫查詢結果: {len(books_data)} 筆記錄")
        
        books = []
        for i, book in enumerate(books_data):
            book_data = {
                'id': book['id'],
                'title': book['title'],
                'isbn': book['isbn'] or '',
                'url': book['url'] or '',
                'cover_path': book['cover_path'] or '',
                'created_at': book['created_at'].isoformat() if book['created_at'] else None,
                'has_clip': True,
                'tech_type': 'FastAPI Enhanced (PostgreSQL)'
            }
            books.append(book_data)
            if i < 3:
                logger.info(f"   📖 書籍 {i+1}: ID={book_data['id']}, 標題='{book_data['title']}', 封面='{book_data['cover_path'] or '無'}'")
        
        logger.info(f"📊 FastAPI PostgreSQL總共回傳 {len(books)} 本書籍")
        
        return {
            'success': True,
            'data': books,
            'total': len(books),
            'system': 'FastAPI v3.1 (PostgreSQL)',
            'database': f"PostgreSQL - {db_config.database}",
            'table_columns': column_names
        }
        
    except Exception as e:
        logger.error(f"❌ FastAPI PostgreSQL /api/books 錯誤: {e}")
        logger.error(f"詳細錯誤: {traceback.format_exc()}")
        return {
            'success': False, 
            'message': f'FastAPI PostgreSQL載入失敗: {str(e)}',
            'error_type': type(e).__name__
        }
    finally:
        if conn:
            db_config.return_connection(conn)

@app.delete("/api/books/{book_id}")
async def api_delete_book(book_id: int):
    """刪除書籍記錄 - PostgreSQL版本"""
    conn = None
    try:
        logger.info(f"🗑️ 刪除書籍 ID: {book_id}")
        conn = db_config.get_connection()
        cursor = conn.cursor()
        
        # 取得書籍資訊以刪除檔案
        cursor.execute('SELECT cover_path FROM books WHERE id = %s', (book_id,))
        book = cursor.fetchone()
        
        if book and book['cover_path'] and os.path.exists(book['cover_path']):
            try:
                os.remove(book['cover_path'])
                logger.info(f"✅ 已刪除檔案: {book['cover_path']}")
            except Exception as e:
                logger.warning(f"⚠️ 刪除檔案失敗: {book['cover_path']}, {e}")
        
        # 從資料庫刪除記錄 (CASCADE 會自動刪除 cover_embeddings)
        cursor.execute('DELETE FROM books WHERE id = %s', (book_id,))
        
        conn.commit()
        logger.info(f"✅ FastAPI PostgreSQL書籍 ID {book_id} 已刪除")
        
        return {
            'success': True, 
            'message': 'FastAPI PostgreSQL書籍已成功刪除'
        }
        
    except Exception as e:
        logger.error(f"❌ FastAPI PostgreSQL刪除書籍失敗: {e}")
        logger.error(f"詳細錯誤: {traceback.format_exc()}")
        if conn:
            conn.rollback()
        return {
            'success': False, 
            'message': f'FastAPI PostgreSQL刪除失敗: {str(e)}'
        }
    finally:
        if conn:
            db_config.return_connection(conn)

@app.get("/api/image/{book_id}")
async def api_get_image(book_id: int):
    """取得書籍封面圖片 - PostgreSQL版本"""
    conn = None
    try:
        conn = db_config.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT title, cover_path FROM books WHERE id = %s", (book_id,))
        result = cursor.fetchone()
        
        if not result:
            logger.error(f"❌ 書籍 ID {book_id} 不存在於 PostgreSQL")
            raise HTTPException(status_code=404, detail=f"書籍 ID {book_id} 不存在")
        
        title, cover_path = result['title'], result['cover_path']
        logger.info(f"🖼️ 查詢書籍 {book_id} '{title}' 的圖片，路徑: {cover_path or '無'}")
        
        if cover_path and os.path.exists(cover_path):
            logger.info(f"✅ 回傳圖片檔案: {cover_path}")
            return FileResponse(cover_path, media_type='image/jpeg')
        
        # 回傳預設的 SVG
        logger.info(f"⚠️ 圖片不存在，回傳預設 SVG")
        safe_title = title[:10] + "..." if len(title) > 10 else title
        default_svg = f'''<svg width="80" height="110" xmlns="http://www.w3.org/2000/svg">
            <rect width="80" height="110" fill="#f0f0f0" stroke="#ccc" stroke-width="2" rx="5"/>
            <text x="40" y="25" text-anchor="middle" font-family="Arial" font-size="10" fill="#666">📖</text>
            <text x="40" y="45" text-anchor="middle" font-family="Arial" font-size="8" fill="#333">{safe_title}</text>
            <text x="40" y="60" text-anchor="middle" font-family="Arial" font-size="6" fill="#999">ID: {book_id}</text>
            <text x="40" y="75" text-anchor="middle" font-family="Arial" font-size="6" fill="#ccc">無封面圖片</text>
        </svg>'''
        
        return Response(content=default_svg, media_type="image/svg+xml")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 取得圖片失敗: {e}")
        logger.error(f"詳細錯誤: {traceback.format_exc()}")
        error_svg = f'''<svg width="80" height="110" xmlns="http://www.w3.org/2000/svg">
            <rect width="80" height="110" fill="#ffe6e6" stroke="#ff9999" stroke-width="2" rx="5"/>
            <text x="40" y="30" text-anchor="middle" font-family="Arial" font-size="12" fill="#cc0000">❌</text>
            <text x="40" y="50" text-anchor="middle" font-family="Arial" font-size="8" fill="#cc0000">載入失敗</text>
            <text x="40" y="65" text-anchor="middle" font-family="Arial" font-size="6" fill="#cc0000">ID: {book_id}</text>
        </svg>'''
        
        return Response(content=error_svg, media_type="image/svg+xml")
    finally:
        if conn:
            db_config.return_connection(conn)

# ===== 系統監控API =====
@app.get("/api/model_info", response_model=SystemStatus)
async def api_model_info():
    """取得系統模型信息"""
    try:
        current_model_info = {
            'available': _clip_model is not None and _clip_processor is not None,
            'name': 'CLIP ViT-Large/14',
            'dimension': 768,
            'device': 'CPU'
        }
        
        enhancement_features = [
            '360度旋轉支援',
            '智能角度檢測', 
            '多重CLIP嵌入',
            'FastAPI異步處理',
            '階段式識別策略',
            'PostgreSQL專用資料庫',
            '連接池管理',
            '用戶回饋系統',
            '調試工具'
        ]
        
        clip_status = check_enhanced_clip_status()
        
        return SystemStatus(
            clip_available=clip_status == "normal",
            clip_status=clip_status,
            enhanced_clip_model=True,
            rotation_support=True,
            device="CPU",
            model_name="CLIP ViT-Large/14",
            enhancement_features=enhancement_features,
            current_model=current_model_info,
            compatibility_status='compatible'
        )
        
    except Exception as e:
        logger.error(f"❌ 取得模型信息失敗: {e}")
        return SystemStatus(
            clip_available=False,
            clip_status="錯誤",
            enhanced_clip_model=False,
            rotation_support=False,
            device="未知",
            model_name="錯誤",
            enhancement_features=[],
            current_model={'available': False, 'name': 'Error', 'dimension': 0, 'device': 'Unknown'},
            compatibility_status='model_changed'
        )

@app.get("/api/status", response_model=SystemStatus)
async def api_status():
    """取得系統狀態"""
    return await api_model_info()

@app.get("/api/health")
async def api_health():
    """API 健康檢查"""
    conn = None
    try:
        ensure_table()
        
        conn = db_config.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM books")
        book_count = cursor.fetchone()[0]
        
        clip_status = check_enhanced_clip_status()
        
        return {
            "success": True,
            "status": "healthy",
            "database": {
                "connected": True,
                "book_count": book_count,
                "type": "PostgreSQL",
                "host": db_config.host,
                "database": db_config.database
            },
            "clip_model": {
                "status": clip_status,
                "available": clip_status == "normal"
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"健康檢查失敗: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )
    finally:
        if conn:
            db_config.return_connection(conn)

# ===== 用戶互動API =====
@app.post("/api/report_incorrect_match")
async def api_report_incorrect_match(request: dict):
    """回報錯誤匹配 - PostgreSQL版本"""
    conn = None
    try:
        book_id = request.get('book_id')
        feedback = request.get('user_feedback')
        
        logger.info(f"收到錯誤回報: book_id={book_id}, feedback={feedback}")
        
        # 可以選擇性地將回報記錄到資料庫
        if book_id:
            conn = db_config.get_connection()
            cursor = conn.cursor()
            
            # 檢查書籍是否存在
            cursor.execute("SELECT title FROM books WHERE id = %s", (book_id,))
            book = cursor.fetchone()
            
            if book:
                logger.info(f"📝 錯誤回報記錄：書籍'{book['title']}'(ID:{book_id}) - {feedback}")
                # 這裡可以建立一個feedback表來記錄用戶回饋
        
        return {
            "success": True,
            "message": "回報已記錄，謝謝您的反饋"
        }
        
    except Exception as e:
        logger.error(f"回報錯誤匹配異常: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"回報失敗: {str(e)}"
            }
        )
    finally:
        if conn:
            db_config.return_connection(conn)

@app.post("/api/suggest_new_book")
async def api_suggest_new_book(request: dict):
    """建議新增書籍 - JSON格式 PostgreSQL版本"""
    try:
        title = request.get('title', '').strip()
        isbn = request.get('isbn', '').strip()
        url = request.get('url', '').strip()
        image = request.get('image', '')
        
        if not title:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "書名不能為空"
                }
            )
        
        logger.info(f"收到新書建議: {title}")
        
        success, message = await save_book_with_rotation_enhanced(
            title, isbn, url, image
        )
        
        return {
            "success": success,
            "message": message if success else f"建議處理失敗: {message}"
        }
        
    except Exception as e:
        logger.error(f"建議新書異常: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"建議處理失敗: {str(e)}"
            }
        )

@app.post("/api/suggest_new_book_file")
async def api_suggest_new_book_file(
    title: Annotated[str, Form()],
    isbn: Annotated[str, Form()] = "",
    url: Annotated[str, Form()] = "",
    image: UploadFile = File(...)
):
    """建議新增書籍 - 檔案格式 PostgreSQL版本"""
    try:
        if not title.strip():
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "書名不能為空"
                }
            )
        
        logger.info(f"收到新書檔案建議: {title}")
        
        success, message = await save_book_with_rotation_enhanced(
            title.strip(), isbn.strip(), url.strip(), image
        )
        
        return {
            "success": success,
            "message": message if success else f"建議處理失敗: {message}"
        }
        
    except Exception as e:
        logger.error(f"建議新書檔案異常: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"建議處理失敗: {str(e)}"
            }
        )

# ===== 調試API =====
@app.get("/api/debug/database")
async def api_debug_database():
    """調試端點：檢查資料庫狀態 - PostgreSQL版本"""
    conn = None
    try:
        result = {
            "database_type": "PostgreSQL",
            "host": db_config.host,
            "port": db_config.port,
            "database": db_config.database,
            "user": db_config.user,
            "connection_pool": {
                "available": db_config.pool is not None,
                "pool_info": "ThreadedConnectionPool" if db_config.pool else "None"
            }
        }
        
        conn = db_config.get_connection()
        cursor = conn.cursor()
        
        # 檢查資料庫版本
        cursor.execute("SELECT version()")
        result["postgresql_version"] = cursor.fetchone()[0]
        
        # 檢查所有表格
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = [row[0] for row in cursor.fetchall()]
        result["tables"] = tables
        
        # 檢查 books 表格結構
        if "books" in tables:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'books'
                ORDER BY ordinal_position
            """)
            books_columns = [
                {
                    "name": row[0], 
                    "type": row[1], 
                    "nullable": row[2] == 'YES', 
                    "default": row[3]
                } 
                for row in cursor.fetchall()
            ]
            result["books_table_structure"] = books_columns
            
            # 書籍總數
            cursor.execute("SELECT COUNT(*) FROM books")
            result["books_count"] = cursor.fetchone()[0]
            
            # 最近的書籍
            column_names = [col["name"] for col in books_columns]
            if "cover_path" in column_names:
                cursor.execute("""
                    SELECT id, title, cover_path, created_at 
                    FROM books 
                    ORDER BY id DESC 
                    LIMIT 5
                """)
                result["recent_books"] = [
                    {
                        "id": row[0], 
                        "title": row[1], 
                        "cover_path": row[2],
                        "created_at": row[3].isoformat() if row[3] else None
                    } 
                    for row in cursor.fetchall()
                ]
            else:
                cursor.execute("SELECT id, title FROM books ORDER BY id DESC LIMIT 5")
                result["recent_books"] = [
                    {"id": row[0], "title": row[1], "cover_path": "欄位不存在"} 
                    for row in cursor.fetchall()
                ]
        
        # 檢查 cover_embeddings 表格
        if "cover_embeddings" in tables:
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'cover_embeddings'
                ORDER BY ordinal_position
            """)
            embeddings_columns = [
                {"name": row[0], "type": row[1]} 
                for row in cursor.fetchall()
            ]
            result["embeddings_table_structure"] = embeddings_columns
            
            cursor.execute("SELECT COUNT(*) FROM cover_embeddings")
            result["embeddings_count"] = cursor.fetchone()[0]
            
            cursor.execute("SELECT book_id FROM cover_embeddings ORDER BY book_id DESC LIMIT 5")
            result["recent_embeddings"] = [row[0] for row in cursor.fetchall()]
        
        # 檢查索引
        cursor.execute("""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename = 'books'
        """)
        result["books_indexes"] = [
            {"name": row[0], "definition": row[1]} 
            for row in cursor.fetchall()
        ]
        
        # 資料庫大小
        cursor.execute("""
            SELECT pg_size_pretty(pg_database_size(%s))
        """, (db_config.database,))
        result["database_size"] = cursor.fetchone()[0]
        
        return result
        
    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e), 
            "traceback": traceback.format_exc(),
            "database_type": "PostgreSQL",
            "connection_error": True
        }
        logger.error(f"❌ PostgreSQL調試檢查失敗: {error_result}")
        return error_result
    finally:
        if conn:
            db_config.return_connection(conn)

@app.post("/api/debug/fix_database")
async def api_fix_database():
    """修復資料庫結構 - PostgreSQL版本"""
    conn = None
    try:
        logger.info("🔧 開始修復PostgreSQL資料庫結構")
        
        # 重新執行表格檢查和修復
        ensure_table()
        
        conn = db_config.get_connection()
        cursor = conn.cursor()
        
        # 檢查表格結構
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'books'
            ORDER BY ordinal_position
        """)
        books_columns = [f"{row[0]}({row[1]})" for row in cursor.fetchall()]
        
        # 統計資料
        cursor.execute("SELECT COUNT(*) FROM books")
        books_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM cover_embeddings")
        embeddings_count = cursor.fetchone()[0]
        
        # 檢查索引是否存在
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'books'
        """)
        indexes = [row[0] for row in cursor.fetchall()]
        
        # 如果索引不存在，重新建立
        required_indexes = ["idx_books_title", "idx_books_created_at"]
        missing_indexes = [idx for idx in required_indexes if idx not in indexes]
        
        if missing_indexes:
            logger.info(f"🔨 重新建立缺失的索引: {missing_indexes}")
            for idx in missing_indexes:
                if idx == "idx_books_title":
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_title ON books USING btree (title)")
                elif idx == "idx_books_created_at":
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_created_at ON books USING btree (created_at DESC)")
        
        conn.commit()
        
        result = {
            "success": True,
            "message": "PostgreSQL資料庫結構已修復",
            "books_columns": books_columns,
            "books_count": books_count,
            "embeddings_count": embeddings_count,
            "existing_indexes": indexes,
            "missing_indexes_fixed": missing_indexes,
            "database_type": "PostgreSQL",
            "host": db_config.host,
            "database": db_config.database
        }
        
        logger.info(f"✅ PostgreSQL修復完成: {result}")
        return result
        
    except Exception as e:
        if conn:
            conn.rollback()
        
        error_result = {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "database_type": "PostgreSQL"
        }
        logger.error(f"❌ PostgreSQL修復失敗: {error_result}")
        return error_result
    finally:
        if conn:
            db_config.return_connection(conn)



# ===== 主程式入口點 =====
if __name__ == "__main__":
    logger.info("\n🚀 啟動 FastAPI 旋轉增強版書籍識別系統 v3.1 (PostgreSQL完整版)")
    logger.info("📋 功能特色：")
    logger.info("   • PostgreSQL 資料庫支援")
    logger.info("   • 連接池管理")
    logger.info("   • 完整錯誤處理")
    logger.info("   • 環境變數配置")
    logger.info("   • 生命週期管理")
    logger.info("   • 用戶回饋系統")
    logger.info("   • 調試工具")
    logger.info("   • 360度旋轉識別")
    logger.info("   • 卡通書籍檢測")
    logger.info("\n📡 服務地址：")
    logger.info("   主頁: http://localhost:8000")
    logger.info("   管理: http://localhost:8000/admin")
    logger.info("   識別: http://localhost:8000/scanner") 
    logger.info("   記錄: http://localhost:8000/records")
    logger.info("   監控: http://localhost:8000/model_status")
    logger.info("   健康: http://localhost:8000/api/health")
    logger.info("   調試: http://localhost:8000/api/debug/database")
    logger.info("   API文檔: http://localhost:8000/docs")
    logger.info("   ReDoc: http://localhost:8000/redoc")
    
    # 使用環境變數配置啟動參數
    host = os.getenv('APP_HOST', '127.0.0.1')
    port = int(os.getenv('APP_PORT', '8000'))
    
    uvicorn.run(
        "app_3:app", 
        host=host, 
        port=port, 
        reload=True,
        log_level="info"
    )