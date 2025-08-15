// FastAPI 管理頁面 JavaScript
let capturedImageData = null;
let uploadedFile = null;
let currentStream = null;

const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const fileInput = document.getElementById('fileInput');
const uploadArea = document.getElementById('uploadArea');
const uploadBtn = document.getElementById('uploadBtn');

// 攝影機控制
document.getElementById('startCamera').addEventListener('click', async () => {
    try {
        const constraints = {
            video: {
                facingMode: 'environment',
                width: { ideal: 1280 },
                height: { ideal: 720 }
            }
        };

        currentStream = await navigator.mediaDevices.getUserMedia(constraints);
        video.srcObject = currentStream;
        window.currentStream = currentStream; // 儲存到全域變數供清理使用
        
        document.getElementById('startCamera').disabled = true;
        document.getElementById('capturePhoto').disabled = false;
        document.getElementById('stopCamera').disabled = false;
        
        showMessage('✅ 攝影機已啟動', 'success');
    } catch (error) {
        console.error('攝影機啟動失敗:', error);
        showMessage('❌ 無法啟動攝影機：' + error.message, 'error');
    }
});

document.getElementById('capturePhoto').addEventListener('click', () => {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0);
    capturedImageData = canvas.toDataURL('image/jpeg', 0.8);
    uploadedFile = null;
    
    document.getElementById('capturedImage').src = capturedImageData;
    document.getElementById('captureResult').style.display = 'block';
    document.getElementById('bookForm').style.display = 'block';
    
    showMessage('📸 封面拍攝完成，準備生成旋轉變體', 'success');
});

document.getElementById('stopCamera').addEventListener('click', () => {
    if (currentStream) {
        currentStream.getTracks().forEach(track => track.stop());
        currentStream = null;
        window.currentStream = null;
        video.srcObject = null;
    }
    
    document.getElementById('startCamera').disabled = false;
    document.getElementById('capturePhoto').disabled = true;
    document.getElementById('stopCamera').disabled = true;
});

// 檔案上傳控制
uploadBtn.addEventListener('click', () => {
    fileInput.click();
});

uploadArea.addEventListener('click', (e) => {
    if (e.target === uploadArea || e.target.tagName === 'P') {
        fileInput.click();
    }
});

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = '#d4af37';
    uploadArea.style.background = 'rgba(212, 175, 55, 0.1)';
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.style.borderColor = '#d4c4b0';
    uploadArea.style.background = 'rgba(255, 253, 250, 0.5)';
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = '#d4c4b0';
    uploadArea.style.background = 'rgba(255, 253, 250, 0.5)';
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFileUpload(files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileUpload(e.target.files[0]);
    }
});

function handleFileUpload(file) {
    if (!file.type.startsWith('image/')) {
        showMessage('⚠️ 請選擇圖片檔案', 'error');
        return;
    }

    uploadedFile = file;
    capturedImageData = null;

    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('capturedImage').src = e.target.result;
        document.getElementById('captureResult').style.display = 'block';
        document.getElementById('bookForm').style.display = 'block';
        showMessage('✅ 封面上傳成功，準備生成旋轉變體', 'success');
    };
    reader.readAsDataURL(file);
}

// 書籍儲存
document.getElementById('saveBook').addEventListener('click', async () => {
    if (!capturedImageData && !uploadedFile) {
        showMessage('⚠️ 請先拍攝或上傳封面', 'error');
        return;
    }
    
    const title = document.getElementById('title').value.trim();
    if (!title) {
        showMessage('⚠️ 請填寫書名', 'error');
        return;
    }
    
    showMessage('🚀 FastAPI異步處理中，正在生成4個角度的旋轉變體...', 'success');
    
    try {
        let response;
        
        if (uploadedFile) {
            const formData = new FormData();
            formData.append('title', title);
            formData.append('isbn', document.getElementById('isbn').value.trim());
            formData.append('url', document.getElementById('url').value.trim());
            formData.append('image', uploadedFile);
            
            response = await fetch('/api/save_book_file', {
                method: 'POST',
                body: formData
            });
        } else {
            response = await fetch('/api/save_book', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: title,
                    isbn: document.getElementById('isbn').value.trim(),
                    url: document.getElementById('url').value.trim(),
                    image: capturedImageData
                })
            });
        }
        
        const result = await response.json();
        if (result.success) {
            showMessage('✅ ' + result.message, 'success');
            resetForm();
        } else {
            showMessage('❌ ' + result.message, 'error');
        }
    } catch (error) {
        showMessage('❌ FastAPI處理失敗: ' + error.message, 'error');
    }
});

document.getElementById('resetForm').addEventListener('click', resetForm);

function resetForm() {
    document.getElementById('title').value = '';
    document.getElementById('isbn').value = '';
    document.getElementById('url').value = '';
    document.getElementById('bookForm').style.display = 'none';
    document.getElementById('captureResult').style.display = 'none';
    capturedImageData = null;
    uploadedFile = null;
    fileInput.value = '';
}