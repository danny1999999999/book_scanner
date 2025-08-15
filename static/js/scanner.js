// 修改版 scanner.js - 手機優化版，按鈕移到視頻內部
console.log("FastAPI 書籍識別系統 v3.1 載入完成 - 手機優化版");

// ===========================================
// 全域變數
// ===========================================
let videoStream = null;
let isCapturing = false;
let cameraActive = false; // 新增：追蹤相機狀態

// ===========================================
// 工具函數
// ===========================================
function showMessage(message, type = 'info') {
    const messageElement = document.getElementById('message');
    if (messageElement) {
        messageElement.innerHTML = `<div class="message ${type}">${message}</div>`;
        messageElement.style.display = 'block';
        
        // 自動隱藏
        if (type === 'success' || type === 'warning') {
            setTimeout(() => {
                messageElement.style.display = 'none';
            }, 5000);
        }
    }
    console.log(type + ': ' + message);
}

function hideMessage() {
    const messageElement = document.getElementById('message');
    if (messageElement) {
        messageElement.style.display = 'none';
        messageElement.innerHTML = '';
    }
}

// ===========================================
// 按鈕狀態管理 - 修改為短文字版本
// ===========================================
function updateMainButton() {
    const mainBtn = document.getElementById('mainCameraBtn');
    const btnIcon = document.getElementById('mainBtnIcon');
    const btnText = document.getElementById('mainBtnText');
    
    if (!mainBtn || !btnIcon || !btnText) return;
    
    if (!cameraActive) {
        // 相機未啟動狀態
        btnIcon.textContent = '📷';
        btnText.textContent = '啟動';
        mainBtn.className = 'btn btn-video-main';
        mainBtn.disabled = false;
    } else {
        // 相機已啟動，可以拍照識別
        btnIcon.textContent = '🔍';
        btnText.textContent = 'AI辨識';
        mainBtn.className = 'btn btn-video-main identify-mode';
        mainBtn.disabled = isCapturing;
    }
}

// ===========================================
// 相機功能 - 增強版
// ===========================================

// 啟動相機 - 增強版（嘗試多種約束）
async function startCamera() {
    console.log('嘗試啟動相機...');
    
    try {
        showMessage('📷 正在啟動相機...', 'info');
        
        // 檢查基本支援
        if (!navigator.mediaDevices) {
            throw new Error('此瀏覽器不支援 mediaDevices');
        }
        
        if (!navigator.mediaDevices.getUserMedia) {
            throw new Error('此瀏覽器不支援 getUserMedia');
        }
        
        // 嘗試不同的約束
        console.log('🔍 正在尋找合適的相機設定...');
        const workingConstraints = await tryDifferentConstraints();
        
        if (!workingConstraints) {
            throw new Error('無法找到適用的相機設定');
        }
        
        console.log('✅ 使用約束:', workingConstraints);
        
        // 使用找到的約束啟動相機
        videoStream = await navigator.mediaDevices.getUserMedia(workingConstraints);
        console.log('✅ 成功獲取視頻流');
        
        const video = document.getElementById('video');
        if (!video) {
            throw new Error('找不到 video 元素');
        }
        
        // 設置視頻源
        video.srcObject = videoStream;
        
        // 等待可以播放
        return new Promise((resolve, reject) => {
            video.onloadedmetadata = () => {
                console.log('✅ 視頻元數據已載入');
                video.play().then(() => {
                    console.log('✅ 視頻開始播放');
                    
                    // 檢查實際使用的鏡頭類型
                    const videoTrack = videoStream.getVideoTracks()[0];
                    let cameraInfo = '';
                    if (videoTrack) {
                        const settings = videoTrack.getSettings();
                        if (settings.facingMode === 'environment') {
                            cameraInfo = ' (已啟用後置鏡頭 📱)';
                        } else if (settings.facingMode === 'user') {
                            cameraInfo = ' (使用前置鏡頭 🤳)';
                        } else {
                            cameraInfo = ' (相機類型未知)';
                        }
                        console.log('📹 相機詳細設定:', settings);
                    }
                    
                    // 更新狀態
                    cameraActive = true;
                    updateMainButton();
                    
                    // 更新其他按鈕狀態
                    const stopBtn = document.getElementById('stopCamera');
                    if (stopBtn) stopBtn.disabled = false;
                    
                    showMessage('📷 相機已啟動成功！' + cameraInfo, 'success');
                    
                    // 更新引導框狀態
                    const guideFrame = document.getElementById('guideFrame');
                    if (guideFrame) {
                        guideFrame.classList.add('detecting');
                    }
                    
                    updateGuideFrameStatus();
                    resolve();
                    
                }).catch((playError) => {
                    console.error('播放失敗:', playError);
                    reject(playError);
                });
            };
            
            video.onerror = (videoError) => {
                console.error('視頻錯誤:', videoError);
                reject(videoError);
            };
            
            // 10秒超時
            setTimeout(() => {
                reject(new Error('視頻載入超時'));
            }, 10000);
        });
        
    } catch (error) {
        console.error('啟動相機失敗:', error);
        console.error('錯誤詳情:', error.name, error.message);
        
        // 清理
        if (videoStream) {
            videoStream.getTracks().forEach(track => track.stop());
            videoStream = null;
        }
        
        cameraActive = false;
        updateMainButton();
        
        // 詳細的錯誤訊息
        let errorMessage = '❌ 無法啟動相機: ';
        
        if (error.name === 'NotAllowedError') {
            errorMessage += '權限被拒絕。請點擊瀏覽器網址列的相機圖示，選擇「允許」';
        } else if (error.name === 'NotFoundError') {
            errorMessage += '找不到相機設備。請確認相機已連接並且沒有被其他程式使用';
        } else if (error.name === 'NotReadableError') {
            errorMessage += '相機被其他應用程式佔用。請關閉其他使用相機的程式';
        } else if (error.name === 'OverconstrainedError') {
            errorMessage += '相機不支援所請求的設定。';
        } else if (error.name === 'SecurityError') {
            errorMessage += '安全錯誤。請使用 HTTPS 或 localhost';
        } else {
            errorMessage += error.message;
        }
        
        errorMessage += '\n\n💡 建議：\n1. 先點擊「測試相機」按鈕檢查\n2. 重新整理頁面重新授權\n3. 確認沒有其他程式使用相機';
        
        showMessage(errorMessage, 'error');
        
        // 重置按鈕狀態
        const stopBtn = document.getElementById('stopCamera');
        if (stopBtn) stopBtn.disabled = true;
    }
}

// 停止相機
function stopCamera() {
    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
        videoStream = null;
        
        const video = document.getElementById('video');
        if (video) {
            video.srcObject = null;
        }
        
        // 更新狀態
        cameraActive = false;
        updateMainButton();
        
        // 重置按鈕狀態
        const stopBtn = document.getElementById('stopCamera');
        if (stopBtn) stopBtn.disabled = true;
        
        // 重置引導框狀態
        const guideFrame = document.getElementById('guideFrame');
        if (guideFrame) {
            guideFrame.classList.remove('detecting', 'found', 'error');
        }
        
        // 更新狀態文字
        updateGuideFrameStatus();
        
        showMessage('📴 相機已關閉', 'warning');
    }
}

// 拍照識別
async function capturePhoto() {
    if (isCapturing) return;
    
    try {
        isCapturing = true;
        updateMainButton(); // 更新按鈕狀態（變為禁用）
        
        // 顯示 Loading 動畫
        showLoading();
        
        const video = document.getElementById('video');
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        
        // 設置canvas尺寸
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        
        // 繪製當前視頻幀
        ctx.drawImage(video, 0, 0);
        
        // 更新引導框狀態
        const guideFrame = document.getElementById('guideFrame');
        if (guideFrame) {
            guideFrame.classList.remove('detecting');
            guideFrame.classList.add('found');
        }
        
        // 轉換為blob
        canvas.toBlob(async (blob) => {
            if (blob) {
                try {
                    // 發送識別請求
                    const formData = new FormData();
                    formData.append('image', blob, 'camera_capture.jpg');
                    
                    const response = await fetch('/api/identify_book_file', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const result = await response.json();
                    
                    // 顯示結果彈出層，並傳入拍照的 blob
                    showResultModal(result, blob);
                    
                } catch (error) {
                    console.error('識別失敗:', error);
                    hideLoading();
                    showMessage('❌ 識別過程發生錯誤: ' + error.message, 'error');
                    
                    // 重置引導框
                    if (guideFrame) {
                        guideFrame.classList.remove('found');
                        guideFrame.classList.add('error');
                        setTimeout(() => {
                            guideFrame.classList.remove('error');
                            guideFrame.classList.add('detecting');
                        }, 2000);
                    }
                } finally {
                    isCapturing = false;
                    updateMainButton(); // 恢復按鈕狀態
                    
                    // 不在這裡重置引導框，讓結果層關閉時再重置
                    // 這樣用戶在查看結果時引導框保持 found 狀態
                }
            } else {
                hideLoading();
                isCapturing = false;
                updateMainButton();
            }
        }, 'image/jpeg', 0.8);
        
    } catch (error) {
        console.error('拍照失敗:', error);
        hideLoading();
        showMessage('❌ 拍照失敗: ' + error.message, 'error');
        isCapturing = false;
        updateMainButton();
    }
}

// 主要按鈕點擊處理 - 新增
async function handleMainButtonClick() {
    console.log('主按鈕被點擊，當前相機狀態:', cameraActive);
    
    if (!cameraActive) {
        // 相機未啟動，執行啟動相機
        await startCamera();
    } else {
        // 相機已啟動，執行拍照識別
        await capturePhoto();
    }
}

// 測試相機功能 - 優先測試後置鏡頭
async function testCamera() {
    console.log('🔧 開始相機測試...');
    showMessage('🔧 正在測試相機支援...', 'info');
    
    try {
        // 1. 檢查基本支援
        console.log('1. 檢查 navigator.mediaDevices:', !!navigator.mediaDevices);
        console.log('2. 檢查 getUserMedia:', !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia));
        console.log('3. 檢查協議:', location.protocol);
        console.log('4. 檢查主機:', location.hostname);
        
        // 2. 檢查可用設備
        if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
            console.log('5. 檢查設備列表...');
            const devices = await navigator.mediaDevices.enumerateDevices();
            const videoDevices = devices.filter(device => device.kind === 'videoinput');
            console.log('🎥 找到視頻設備:', videoDevices.length, '個');
            videoDevices.forEach((device, index) => {
                console.log(`   設備 ${index + 1}:`, device.label || '未命名設備', device.deviceId);
            });
            
            if (videoDevices.length === 0) {
                showMessage('❌ 沒有找到任何相機設備', 'error');
                return;
            }
        }
        
        // 3. 測試後置鏡頭
        console.log('6. 測試後置鏡頭（手機背面鏡頭）...');
        try {
            const backCameraStream = await navigator.mediaDevices.getUserMedia({ 
                video: { facingMode: 'environment' } 
            });
            console.log('✅ 後置鏡頭測試成功');
            
            // 檢查鏡頭資訊
            const videoTrack = backCameraStream.getVideoTracks()[0];
            if (videoTrack) {
                const settings = videoTrack.getSettings();
                console.log('📹 後置鏡頭設定:', settings);
            }
            
            backCameraStream.getTracks().forEach(track => track.stop());
            showMessage('✅ 測試通過！找到後置鏡頭，適合拍攝書籍', 'success');
            return;
            
        } catch (backCameraError) {
            console.log('⚠️ 後置鏡頭不可用:', backCameraError.name);
            
            // 4. 測試任意鏡頭
            console.log('7. 測試任意可用鏡頭...');
            try {
                const anyStream = await navigator.mediaDevices.getUserMedia({ video: true });
                console.log('✅ 找到可用鏡頭（可能是前置鏡頭）');
                
                const videoTrack = anyStream.getVideoTracks()[0];
                if (videoTrack) {
                    const settings = videoTrack.getSettings();
                    const cameraType = settings.facingMode === 'user' ? '前置鏡頭' : 
                                      settings.facingMode === 'environment' ? '後置鏡頭' : '未知類型鏡頭';
                    console.log(`📹 檢測到: ${cameraType}`);
                }
                
                anyStream.getTracks().forEach(track => track.stop());
                showMessage('⚠️ 測試通過！但只找到前置鏡頭，可能影響拍攝效果', 'warning');
                
            } catch (anyError) {
                console.error('❌ 所有鏡頭測試失敗:', anyError);
                showMessage(`❌ 相機測試失敗: ${anyError.message}`, 'error');
            }
        }
        
    } catch (error) {
        console.error('❌ 測試過程失敗:', error);
        showMessage(`❌ 測試失敗: ${error.message}`, 'error');
    }
}

// 嘗試不同的相機約束（手機優先後置鏡頭）
async function tryDifferentConstraints() {
    const constraintsList = [
        // 手機後置鏡頭 - 最高解析度
        { 
            video: { 
                facingMode: 'environment',
                width: { ideal: 1920 },
                height: { ideal: 1080 }
            }
        },
        // 手機後置鏡頭 - 中等解析度
        { 
            video: { 
                facingMode: 'environment',
                width: { ideal: 1280 },
                height: { ideal: 720 }
            }
        },
        // 手機後置鏡頭 - 基本解析度
        { 
            video: { 
                facingMode: 'environment',
                width: 640,
                height: 480
            }
        },
        // 手機後置鏡頭 - 最基本
        { 
            video: { 
                facingMode: 'environment'
            }
        },
        // 備用：任意鏡頭 - 高解析度
        { 
            video: { 
                width: { ideal: 1280 },
                height: { ideal: 720 }
            }
        },
        // 備用：任意鏡頭 - 基本解析度
        { video: { width: 640, height: 480 } },
        // 最基本
        { video: true }
    ];
    
    for (let i = 0; i < constraintsList.length; i++) {
        const constraints = constraintsList[i];
        const cameraType = constraints.video.facingMode === 'environment' ? '後置鏡頭' : '任意鏡頭';
        console.log(`🔍 嘗試 ${cameraType} - 約束 ${i + 1}:`, constraints);
        
        try {
            const stream = await navigator.mediaDevices.getUserMedia(constraints);
            console.log(`✅ ${cameraType} 約束 ${i + 1} 成功`);
            
            // 檢查是否真的是後置鏡頭
            const videoTrack = stream.getVideoTracks()[0];
            if (videoTrack) {
                const settings = videoTrack.getSettings();
                console.log('📹 相機設定:', {
                    facingMode: settings.facingMode,
                    width: settings.width,
                    height: settings.height,
                    deviceId: settings.deviceId
                });
                
                if (settings.facingMode) {
                    console.log(`🎯 使用相機: ${settings.facingMode === 'environment' ? '後置鏡頭' : '前置鏡頭'}`);
                }
            }
            
            stream.getTracks().forEach(track => track.stop());
            return constraints; // 返回成功的約束
        } catch (error) {
            console.log(`❌ ${cameraType} 約束 ${i + 1} 失敗:`, error.name);
        }
    }
    
    return null; // 所有約束都失敗
}

// ===========================================
// 檔案上傳功能
// ===========================================

// 處理檔案上傳
async function handleFileUpload(file) {
    if (!file.type.startsWith('image/')) {
        showMessage('❌ 請選擇圖片檔案', 'error');
        return;
    }
    
    if (file.size > 10 * 1024 * 1024) {
        showMessage('❌ 檔案過大，請選擇小於10MB的圖片', 'error');
        return;
    }
    
    try {
        showMessage('🔍 正在識別上傳的圖片...', 'info');
        
        // 顯示上傳的圖片
        displayUploadedImage(file);
        
        // 發送識別請求
        const formData = new FormData();
        formData.append('image', file);
        
        const response = await fetch('/api/identify_book_file', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        displayIdentificationResult(result);
        
    } catch (error) {
        console.error('上傳識別失敗:', error);
        showMessage('❌ 上傳識別失敗: ' + error.message, 'error');
    }
}

// ===========================================
// 顯示結果功能
// ===========================================

// 顯示拍攝的圖片
function displayCapturedImage(blob) {
    const url = URL.createObjectURL(blob);
    const scanResult = document.getElementById('scanResult');
    const scannedImage = document.getElementById('scannedImage');
    const imageProcessInfo = document.getElementById('imageProcessInfo');
    
    if (scanResult && scannedImage) {
        scannedImage.src = url;
        scanResult.style.display = 'block';
        
        if (imageProcessInfo) {
            imageProcessInfo.textContent = `相機拍攝 • ${(blob.size / 1024).toFixed(1)} KB`;
        }
    }
}

// 顯示上傳的圖片
function displayUploadedImage(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        const scanResult = document.getElementById('scanResult');
        const scannedImage = document.getElementById('scannedImage');
        const imageProcessInfo = document.getElementById('imageProcessInfo');
        
        if (scanResult && scannedImage) {
            scannedImage.src = e.target.result;
            scanResult.style.display = 'block';
            
            if (imageProcessInfo) {
                imageProcessInfo.textContent = `已上傳 • ${(file.size / 1024).toFixed(1)} KB`;
            }
        }
    };
    reader.readAsDataURL(file);
}

// 顯示 Loading 動畫
function showLoading() {
    const loadingOverlay = document.getElementById('loadingOverlay');
    if (loadingOverlay) {
        loadingOverlay.style.display = 'flex';
    }
}

// 隱藏 Loading 動畫
function hideLoading() {
    const loadingOverlay = document.getElementById('loadingOverlay');
    if (loadingOverlay) {
        loadingOverlay.style.display = 'none';
    }
}

// 顯示結果彈出層（包含拍照圖片）
function showResultModal(result, capturedBlob = null) {
    hideLoading(); // 先隱藏 loading
    
    const modal = document.getElementById('resultModal');
    const content = document.getElementById('resultContent');
    const capturedPhotoImg = document.getElementById('capturedPhotoImg');
    
    if (!modal || !content) return;
    
    // 顯示拍照的圖片
    if (capturedBlob && capturedPhotoImg) {
        const url = URL.createObjectURL(capturedBlob);
        capturedPhotoImg.src = url;
        
        // 清理之前的 URL（防止記憶體洩漏）
        capturedPhotoImg.onload = () => {
            if (capturedPhotoImg.previousUrl) {
                URL.revokeObjectURL(capturedPhotoImg.previousUrl);
            }
            capturedPhotoImg.previousUrl = url;
        };
    }
    
    let html = '';
    
    if (result.success && result.book) {
        const book = result.book;
        const similarity = book.similarity_score || 0;
        
        // 判斷相似度等級
        let similarityClass = 'similarity-low';
        let similarityText = '';
        
        if (similarity >= 81) {
            similarityClass = 'similarity-high';
            similarityText = '辨識成功';
        } else if (similarity >= 60) {
            similarityClass = 'similarity-medium';
            similarityText = '中等相似度';
        } else {
            similarityClass = 'similarity-low';
            similarityText = '相似度低';
        }
        
        html = `
            <div class="result-title">${similarity >= 81 ? '✅ 辨識成功！' : '⚠️ 相似度偏低'}</div>
            <div class="result-book-title">${book.title}</div>
            <div class="result-similarity">
                相似度: <span class="${similarityClass}">${similarity}%</span>
            </div>
        `;
        
        if (book.url) {
            html += `
                <div class="result-url">
                    <a href="${book.url}" target="_blank">📖 查看詳情</a>
                </div>
            `;
        }
        
        // 如果相似度低於81%，顯示警告
        if (similarity < 81) {
            html += `
                <div class="low-confidence-warning">
                    相似度低，建議重新辨識以獲得更準確的結果
                </div>
            `;
        }
        
    } else if (result.book && result.book.unknown_book) {
        html = `
            <div class="result-title">❓ 未知書籍</div>
            <div class="low-confidence-warning">
                ${result.book.suggestion || '這可能是資料庫中沒有的新書，請重新辨識或確認書籍擺放角度'}
            </div>
        `;
        
    } else {
        html = `
            <div class="result-title">❌ 辨識失敗</div>
            <div class="low-confidence-warning">
                ${result.message || '無法辨識此書籍，請重新辨識'}
            </div>
        `;
    }
    
    content.innerHTML = html;
    modal.style.display = 'block';  // 確保使用 'block' 而不是 'flex'
    
    console.log('✅ 結果彈出層已顯示');
    
    // 確保視頻流繼續運行
    if (cameraActive && videoStream) {
        console.log('📹 視頻流繼續運行');
    }
}

// 隱藏結果彈出層
function hideResultModal() {
    console.log('🚪 正在關閉結果彈出層...');
    
    const modal = document.getElementById('resultModal');
    const capturedPhotoImg = document.getElementById('capturedPhotoImg');
    
    if (modal) {
        modal.style.display = 'none';
        console.log('✅ 結果彈出層已隱藏');
    } else {
        console.error('❌ 找不到 resultModal 元素');
    }
    
    // 清理圖片 URL 防止記憶體洩漏
    if (capturedPhotoImg && capturedPhotoImg.previousUrl) {
        URL.revokeObjectURL(capturedPhotoImg.previousUrl);
        capturedPhotoImg.previousUrl = null;
        capturedPhotoImg.src = '';
        console.log('🧹 已清理圖片資源');
    }
    
    // 確保相機繼續運行並準備下次掃描
    if (cameraActive && videoStream) {
        console.log('📹 關閉結果層，相機繼續掃描準備中...');
        
        // 重置引導框為檢測狀態
        const guideFrame = document.getElementById('guideFrame');
        if (guideFrame) {
            guideFrame.classList.remove('found', 'error');
            guideFrame.classList.add('detecting');
            console.log('🎯 引導框已重置為檢測狀態');
        }
        
        // 確保按鈕狀態正確
        updateMainButton();
        console.log('🔄 按鈕狀態已更新');
    }
}

// 重新辨識（實際上就是關閉結果層繼續掃描）
function retryIdentification() {
    console.log('🔄 重新辨識按鈕被點擊');
    hideResultModal();
    console.log('✅ 重新辨識：結果層已關閉，準備繼續掃描');
    
    // 不需要自動觸發拍照，讓用戶手動點擊按鈕
    // 這樣用戶可以重新調整書籍位置再拍攝
}

// ===========================================
// 方向處理 - 簡化版（框架已自適應，無需複雜處理）
// ===========================================
function updateGuideFrameStatus() {
    const guideStatus = document.getElementById('guideStatus');
    if (guideStatus) {
        // 檢查是否有視頻流來判斷用什麼文字
        if (videoStream) {
            const videoTrack = videoStream.getVideoTracks()[0];
            if (videoTrack) {
                const settings = videoTrack.getSettings();
                if (settings.facingMode === 'environment') {
                    guideStatus.textContent = '後置鏡頭已啟用，請拍攝書籍';
                } else if (settings.facingMode === 'user') {
                    guideStatus.textContent = '前置鏡頭模式，建議翻轉手機';
                } else {
                    guideStatus.textContent = '請將書籍放入框內';
                }
            } else {
                guideStatus.textContent = '請將書籍放入框內';
            }
        } else {
            guideStatus.textContent = '等待啟動相機...';
        }
    }
}

function initOrientationHandling() {
    // 簡單監聽方向變化
    if (screen.orientation) {
        screen.orientation.addEventListener('change', updateGuideFrameStatus);
    } else {
        window.addEventListener('orientationchange', updateGuideFrameStatus);
    }
    
    // 設置初始狀態
    updateGuideFrameStatus();
    
    console.log('📱 90%自適應框架已啟用，優先使用後置鏡頭');
}

// ===========================================
// 檔案上傳界面
// ===========================================
function initFileUpload() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');
    
    if (uploadBtn) {
        uploadBtn.addEventListener('click', () => {
            fileInput.click();
        });
    }
    
    if (uploadArea) {
        uploadArea.addEventListener('click', () => {
            fileInput.click();
        });
        
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileUpload(files[0]);
            }
        });
    }
    
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleFileUpload(e.target.files[0]);
            }
        });
    }
}

// ===========================================
// 事件綁定
// ===========================================
function initEventListeners() {
    // 主要按鈕 - 智能切換功能
    const mainCameraBtn = document.getElementById('mainCameraBtn');
    if (mainCameraBtn) {
        mainCameraBtn.addEventListener('click', handleMainButtonClick);
    }
    
    // 輔助按鈕
    const stopCameraBtn = document.getElementById('stopCamera');
    const testCameraBtn = document.getElementById('testCamera');
    
    if (stopCameraBtn) {
        stopCameraBtn.addEventListener('click', stopCamera);
    }
    
    if (testCameraBtn) {
        testCameraBtn.addEventListener('click', testCamera);
    }
    
    // 檔案上傳
    initFileUpload();
    
    console.log('📱 事件監聽器已綁定 - 手機優化模式');
}

// ===========================================
// 初始化
// ===========================================
function initScanner() {
    // 檢查瀏覽器支援
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showMessage('⚠️ 您的瀏覽器不支援相機功能，僅能使用檔案上傳', 'warning');
        const mainCameraBtn = document.getElementById('mainCameraBtn');
        if (mainCameraBtn) {
            mainCameraBtn.disabled = true;
            const btnIcon = document.getElementById('mainBtnIcon');
            const btnText = document.getElementById('mainBtnText');
            if (btnIcon) btnIcon.textContent = '📷';
            if (btnText) btnText.textContent = '不支援';
        }
    }
    
    // 初始化功能
    initOrientationHandling();
    initEventListeners();
    updateMainButton(); // 設置初始按鈕狀態
    
    console.log('✅ 掃描器系統初始化完成 - 手機優化版');
}

// 頁面載入後初始化
document.addEventListener('DOMContentLoaded', function() {
    initScanner();
    console.log('🎉 FastAPI 書籍識別系統載入完成！手機優化版 + 視頻內按鈕 + 透明引導文字');
});