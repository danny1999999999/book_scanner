// FastAPI v3.1 旋轉增強通用功能
console.log("FastAPI旋轉增強書籍識別系統 v3.1 載入完成");

// 通用工具函數
function showMessage(message, type = 'info') {
    console.log(type + ': ' + message);
}

function hideMessage() {
    console.log('hideMessage called');
}

// 格式化文件大小
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 檢查瀏覽器支援
function checkBrowserSupport() {
    const support = {
        getUserMedia: !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia),
        fileReader: !!(window.FileReader),
        canvas: !!(document.createElement('canvas').getContext),
        formData: !!(window.FormData)
    };
    
    console.log('瀏覽器支援狀態:', support);
    return support;
}

// 初始化檢查
document.addEventListener('DOMContentLoaded', function() {
    checkBrowserSupport();
    console.log('FastAPI v3.1 旋轉增強系統初始化完成');
});