// FastAPI 記錄分析頁面 JavaScript
let allBooks = [];

// 載入書籍記錄
async function loadBooks() {
    try {
        console.log('開始載入FastAPI書籍記錄...');
        const response = await fetch('/api/books');
        
        if (!response.ok) {
            throw new Error('HTTP ' + response.status);
        }
        
        const result = await response.json();
        console.log('FastAPI回應:', result);
        
        let books = [];
        if (result.success && Array.isArray(result.data)) {
            books = result.data;
        } else if (Array.isArray(result)) {
            books = result;
        } else {
            console.error('未知的回應格式:', result);
            books = [];
        }
        
        allBooks = books;
        console.log('載入書籍數量:', allBooks.length);
        
        updateStats(allBooks);
        displayBooks(allBooks);
        
    } catch (error) {
        console.error('載入書籍失敗:', error);
        const container = document.getElementById('booksContainer');
        container.innerHTML = 
            '<div class="empty-state">' +
                '<h3>❌ FastAPI載入失敗</h3>' +
                '<p>錯誤: ' + error.message + '</p>' +
                '<button onclick="loadBooks()" class="btn btn-primary">重新載入</button>' +
            '</div>';
    }
}

// 更新統計數據
function updateStats(books) {
    if (!Array.isArray(books)) {
        console.error('books 不是陣列:', books);
        return;
    }
    
    const now = new Date();
    const oneWeekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    
    let enhancedBooks = 0;
    let recentBooks = 0;
    let rotationDetected = 0;
    
    books.forEach(book => {
        if (book.has_clip || book.tech_type === '本地CLIP' || book.tech_type === 'FastAPI Enhanced') {
            enhancedBooks++;
        }
        if (book.created_at && new Date(book.created_at) > oneWeekAgo) {
            recentBooks++;
        }
        if (book.rotation_angle !== undefined && book.rotation_angle !== null) {
            rotationDetected++;
        }
    });

    document.getElementById('totalBooks').textContent = books.length;
    document.getElementById('enhancedBooks').textContent = enhancedBooks;
    document.getElementById('recentBooks').textContent = recentBooks;
    document.getElementById('rotationDetected').textContent = rotationDetected;
}

// 顯示書籍列表
function displayBooks(books) {
    const container = document.getElementById('booksContainer');
    
    if (!books || books.length === 0) {
        container.innerHTML = 
            '<div class="empty-state">' +
                '<h3>📚 目前沒有書籍記錄</h3>' +
                '<p>🎯 這個資料庫還是空的！</p>' +
                '<p>📋 請先執行以下步驟：</p>' +
                '<ol style="text-align: left; max-width: 400px; margin: 20px auto;">' +
                    '<li>前往 <a href="/admin">📚 管理頁面</a></li>' +
                    '<li>拍照或上傳書籍封面</li>' +
                    '<li>填寫書名等資訊並儲存</li>' +
                    '<li>回到此頁面查看記錄</li>' +
                '</ol>' +
                '<p style="margin-top: 30px;">' +
                    '<a href="/admin" class="btn btn-primary">🚀 開始新增書籍</a>' +
                '</p>' +
            '</div>';
        return;
    }
    
    let html = '';
    
    books.forEach(book => {
        const createdDate = book.created_at ? 
            new Date(book.created_at).toLocaleString('zh-TW') : 
            '未知時間';
        
        let techBadge = '';
        if (book.tech_type === '本地CLIP' || book.has_clip || book.tech_type === 'FastAPI Enhanced') {
            techBadge = '<span class="enhanced-indicator">CLIP增強</span>';
        }
        
        const imageUrl = '/api/image/' + book.id + '?t=' + Date.now();
        
        html += '<div class="book-card">';
        html += '  <div class="book-image">';
        html += '    <img src="' + imageUrl + '" alt="' + book.title + '" style="display: block;">';
        html += '  </div>';
        html += '  <div class="book-info">';
        html += '    <h3 class="book-title">' + book.title + techBadge + '</h3>';
        
        if (book.isbn) {
            html += '    <div class="book-details">📖 ISBN: ' + book.isbn + '</div>';
        }
        if (book.url) {
            html += '    <div class="book-details">🔗 <a href="' + book.url + '" target="_blank" style="color: white;">相關連結</a></div>';
        }
        
        html += '    <div class="book-details">🗃️ 資料庫: book3.db</div>';
        html += '    <div class="book-details">⚡ FastAPI v3.1 處理</div>';
        html += '    <div class="book-meta">📅 新增時間: ' + createdDate + '</div>';
        html += '    <div style="margin-top: 15px;">';
        html += '      <button class="btn btn-danger" data-book-id="' + book.id + '">🗑️ 刪除</button>';
        html += '    </div>';
        html += '  </div>';
        html += '</div>';
    });
    
    container.innerHTML = html;
    
    // 使用事件委託處理刪除按鈕
    container.addEventListener('click', function(e) {
        if (e.target.classList.contains('btn-danger')) {
            const bookId = e.target.getAttribute('data-book-id');
            if (bookId) {
                deleteBook(parseInt(bookId));
            }
        }
    });
}

// 搜尋功能
document.getElementById('searchBox').addEventListener('input', function(e) {
    const searchTerm = e.target.value.toLowerCase();
    const filteredBooks = allBooks.filter(book => {
        return book.title.toLowerCase().includes(searchTerm) ||
               (book.isbn && book.isbn.toLowerCase().includes(searchTerm)) ||
               (book.url && book.url.toLowerCase().includes(searchTerm));
    });
    displayBooks(filteredBooks);
});

// 刪除書籍
async function deleteBook(bookId) {
    if (!confirm('確定要從 book3.db 刪除這本書籍嗎？')) return;

    try {
        const response = await fetch('/api/books/' + bookId, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert('✅ 書籍已從FastAPI系統成功刪除');
            allBooks = allBooks.filter(book => book.id !== bookId);
            updateStats(allBooks);
            displayBooks(allBooks);
        } else {
            alert('❌ FastAPI刪除失敗：' + result.message);
        }
    } catch (error) {
        console.error('刪除失敗:', error);
        alert('❌ FastAPI刪除失敗，請重試');
    }
}

// 頁面載入時初始化
document.addEventListener('DOMContentLoaded', loadBooks);