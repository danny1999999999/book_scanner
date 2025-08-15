// 攝影機相關的共用函數（目前功能已整合在各頁面中）
// 可在此添加共用的攝影機處理邏輯

console.log('攝影機模組已載入');

// 檢查瀏覽器是否支援getUserMedia
if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    console.warn('此瀏覽器不支援攝影機功能');
    alert('抱歉，您的瀏覽器不支援攝影機功能。請使用最新版本的 Chrome、Firefox 或 Safari。');
}