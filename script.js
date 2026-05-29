

// Helper: Show Toast
function showToast(msg) {
    const toast = document.getElementById('toast');
    toast.innerText = msg;
    toast.classList.remove('hidden');
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 1500); // fade out after 1.5s
}

// Helper to guarantee execution after DOM is ready
function onDOMReady(fn) {
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        fn();
    } else {
        document.addEventListener('DOMContentLoaded', fn);
    }
}

async function bgFetchHtml(url, timeoutMs = 15000) {
    try {
        console.log(`[bgFetchHtml] Trying direct fetch for: ${url}`);
        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), timeoutMs);
        
        const response = await fetch(url, {
            signal: controller.signal,
            headers: {
                'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8'
            }
        });
        clearTimeout(id);
        if (response.ok) {
            const html = await response.text();
            if (html && html.trim().length > 0) {
                console.log(`[bgFetchHtml] Direct fetch succeeded! Length: ${html.length}`);
                return html;
            }
        }
    } catch (e) {
        console.warn(`[bgFetchHtml] Direct fetch failed/cors restricted:`, e);
    }
    
    // Fallback: Use iframe without sandbox to comply with --disable-web-security for cross-origin DOM access
    return new Promise((resolve) => {
        let iframe = document.getElementById('bgFetchIframe');
        if (!iframe) {
            iframe = document.createElement('iframe');
            iframe.id = 'bgFetchIframe';
            iframe.style.display = 'none';
            document.body.appendChild(iframe);
        }
        
        let isResolved = false;
        const complete = (html) => {
            if (!isResolved) {
                isResolved = true;
                iframe.onload = null;
                resolve(html);
            }
        };

        const timeout = setTimeout(() => {
            try {
                const doc = iframe.contentDocument || iframe.contentWindow.document;
                complete(doc.documentElement.outerHTML);
            } catch(e) {
                complete("");
            }
        }, timeoutMs);

        iframe.onload = () => {
            setTimeout(() => {
                try {
                    const doc = iframe.contentDocument || iframe.contentWindow.document;
                    const html = doc.documentElement.outerHTML;
                    if (html.includes('cf-browser-verification') || html.includes('Just a moment...')) {
                        setTimeout(() => {
                            try {
                                complete((iframe.contentDocument || iframe.contentWindow.document).documentElement.outerHTML);
                            } catch(e) { complete(""); }
                        }, 5000);
                    } else {
                        complete(html);
                    }
                } catch(e) {
                    complete("");
                }
            }, 1000);
        };
        
        iframe.src = url;
    });
}

// Initialize variables
let allVideos = [];
let homeVideos = [];
let currentContextMenuVideo = null;
let currentContextMenuSource = null;

// Navigation Logic
onDOMReady(() => {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            
            // 如果當前是 settings-item 但沒有 settings Section 或是 settings-item 的特定邏輯
            const targetId = item.getAttribute('data-target');
            if (!targetId) return;
            
            document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');
            
            document.querySelectorAll('.content-section').forEach(sec => sec.classList.add('hidden-section'));
            const targetSection = document.getElementById(targetId);
            if (targetSection) targetSection.classList.remove('hidden-section');
            
            // 動態控制 UI 切換按鈕的啟用與禁用
            const toggleUiBtn = document.getElementById('toggleUiBtn');
            if (toggleUiBtn) {
                if (targetId === 'syncWatch') {
                    toggleUiBtn.classList.remove('disabled-ui');
                    toggleUiBtn.title = "啟動純淨同步觀看模式 (隱藏 UI)";
                } else {
                    toggleUiBtn.classList.add('disabled-ui');
                    toggleUiBtn.title = "純淨同步觀看模式 (僅在同步觀看分頁可用)";
                }
            }
            
            // 當切換到「首頁」分頁時，通知 homeManager 確保資料已渲染
            if (targetId === 'homeSection' && window.pywebview) {
                homeManager.onHomeActivated();
            }
        });
    });
});

// ============================================================================
// JApp 1.2 首頁功能重構 — homeManager
// ============================================================================
const homeManager = (() => {
    // ── 內部狀態 ──────────────────────────────────────────────────────────────
    let currentPage    = 1;
    let totalPages     = 1;
    let currentBaseUrl = 'tktube';   // 預設來源：TKTube 最新更新
    let isSearchActive = false;      // 是否處於搜尋模式
    let isDateFiltered = false;      // 是否處於日期篩選模式
    let isLoading      = false;      // 防止重複請求
    let preloadedData  = null;       // 啟動預載快取
    let preloadDone    = false;      // 預載完成旗標

    // ── DOM 輔助 ──────────────────────────────────────────────────────────────
    const $ = (id) => document.getElementById(id);

    // ── 顯示 / 隱藏載入提示 ──────────────────────────────────────────────────
    function showLoading(show) {
        const el = $('homeLoadingText');
        const grid = $('homeGrid');
        if (!el) return;
        if (show) {
            el.style.display = 'block';
            if (grid) grid.innerHTML = '';
        } else {
            el.style.display = 'none';
        }
    }

    // ── 更新分頁顯示 ──────────────────────────────────────────────────────────
    function updatePagination() {
        const info = $('homePageInfo');
        const prev = $('prevPageBtn');
        const next = $('nextPageBtn');
        const pagination = $('homePagination');
        if (!info) return;

        if (isSearchActive) {
            if (pagination) pagination.style.display = 'none';
            return;
        }
        if (pagination) pagination.style.display = 'flex';

        info.textContent = `第 ${currentPage} 頁 / 共 ${totalPages} 頁`;
        if (prev) prev.disabled = currentPage <= 1;
        if (next) next.disabled = currentPage >= totalPages;
    }

    // ── 渲染首頁影片卡 ────────────────────────────────────────────────────────
    function renderHomeVideos(videos) {
        const grid = $('homeGrid');
        if (!grid) return;
        grid.innerHTML = '';

        if (!videos || videos.length === 0) {
            grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:3rem;color:#94a3b8;">找不到符合條件的影片</div>';
            updatePagination();
            return;
        }

        videos.forEach(v => {
            // 從 homeVideos 陣列裡的物件（cover / url 欄位）對應到 createVideoCardElement 期望的格式
            const adapted = {
                code:          v.code || '',
                title:         v.title || '',
                actress:       v.actress || '',
                img:           v.cover || v.img || '',
                preview:       v.preview || '',
                url:           v.url || '',
                upload_date:   v.upload_date || '',
                relative_time: v.relative_time || '',
                type:          v.type || '無碼破解版',
                found:         true,
                cover:         v.cover || v.img || ''
            };
            grid.appendChild(createVideoCardElement(adapted, 'home'));
        });

        updatePagination();
    }

    // ── 載入指定頁的影片資料 ──────────────────────────────────────────────────
    async function fetchPage(page, baseUrl) {
        if (isLoading) return;
        isLoading = true;
        showLoading(true);

        try {
            let urlToLoad;
            if (baseUrl.startsWith('tktube')) {
                urlToLoad = page > 1
                    ? `https://tktube.com/zh/latest-updates/${page}/`
                    : 'https://tktube.com/zh/latest-updates/';
            } else {
                urlToLoad = baseUrl;
                if (page > 1) {
                    urlToLoad = urlToLoad.includes('?')
                        ? `${urlToLoad}&page=${page}`
                        : `${urlToLoad}?page=${page}`;
                }
            }

            const res = await window.pywebview.api.get_tktube_home_videos(urlToLoad);
            if (res && res.videos) {
                currentPage = res.current_page || page;
                totalPages  = res.total_pages  || 1;
                renderHomeVideos(res.videos);
            } else {
                renderHomeVideos([]);
            }
        } catch (e) {
            console.error('[homeManager] fetchPage error:', e);
            renderHomeVideos([]);
        } finally {
            isLoading = false;
            showLoading(false);
        }
    }

    // ── 搜尋邏輯 ──────────────────────────────────────────────────────────────
    async function doSearch(query) {
        if (!query || !query.trim()) {
            isSearchActive = false;
            await fetchPage(1, currentBaseUrl);
            return;
        }

        isSearchActive = true;
        isDateFiltered = false;
        isLoading = true;
        showLoading(true);

        try {
            const res = await window.pywebview.api.search_all_platforms(query.trim());
            const videos = (res && res.videos) ? res.videos : [];
            // 格式轉換：搜尋結果欄位為 cover，需要統一
            const adapted = videos.map(v => ({
                ...v,
                img:   v.img   || v.cover || '',
                cover: v.cover || v.img   || ''
            }));
            renderHomeVideos(adapted);
        } catch (e) {
            console.error('[homeManager] search error:', e);
            renderHomeVideos([]);
        } finally {
            isLoading = false;
            showLoading(false);
        }
    }

    // ── 三級日期篩選器聯動初始化 ─────────────────────────────────────────────
    function initDateFilters() {
        const yearSel  = $('homeYearFilter');
        const monthSel = $('homeMonthFilter');
        const daySel   = $('homeDayFilter');
        if (!yearSel) return;

        // 填入年份選項（當年往前 6 年）
        const thisYear = new Date().getFullYear();
        for (let y = thisYear; y >= thisYear - 5; y--) {
            const opt = document.createElement('option');
            opt.value = y;
            opt.textContent = `${y} 年`;
            yearSel.appendChild(opt);
        }

        // 填入月份（1–12）
        function populateMonths() {
            monthSel.innerHTML = '<option value="">所有月份</option>';
            for (let m = 1; m <= 12; m++) {
                const opt = document.createElement('option');
                opt.value = String(m).padStart(2, '0');
                opt.textContent = `${m} 月`;
                monthSel.appendChild(opt);
            }
        }

        // 填入天數（動態依月份計算）
        function populateDays(year, month) {
            daySel.innerHTML = '<option value="">所有日期</option>';
            if (!year || !month) return;
            const daysInMonth = new Date(year, parseInt(month), 0).getDate();
            for (let d = 1; d <= daysInMonth; d++) {
                const opt = document.createElement('option');
                opt.value = String(d).padStart(2, '0');
                opt.textContent = `${d} 日`;
                daySel.appendChild(opt);
            }
        }

        // 聯動：年份改變
        yearSel.addEventListener('change', () => {
            const y = yearSel.value;
            if (y) {
                monthSel.disabled = false;
                populateMonths();
            } else {
                monthSel.disabled = true;
                monthSel.innerHTML = '<option value="">所有月份</option>';
                daySel.disabled = true;
                daySel.innerHTML = '<option value="">所有日期</option>';
            }
        });

        // 聯動：月份改變
        monthSel.addEventListener('change', () => {
            const m = monthSel.value;
            if (m) {
                daySel.disabled = false;
                populateDays(yearSel.value, m);
            } else {
                daySel.disabled = true;
                daySel.innerHTML = '<option value="">所有日期</option>';
            }
        });
    }

    // ── 日期篩選確認（後端二分法搜尋） ───────────────────────────────────────
    async function doDateFilter() {
        const y = $('homeYearFilter')  ? $('homeYearFilter').value  : '';
        const m = $('homeMonthFilter') ? $('homeMonthFilter').value : '';
        const d = $('homeDayFilter')   ? $('homeDayFilter').value   : '';

        if (!y) {
            showToast('⚠️ 請先選擇年份');
            return;
        }

        // 組裝目標前綴
        let prefix = y;
        if (m) prefix += `-${m}`;
        if (m && d) prefix += `-${d}`;

        isDateFiltered = true;
        isSearchActive = false;
        isLoading = true;
        showLoading(true);

        try {
            const baseUrl = 'https://tktube.com/zh/latest-updates/';
            // 呼叫後端的二分搜尋定位
            const pages = await window.pywebview.api.scan_pages_for_date(baseUrl, prefix);
            if (!pages || pages.length === 0) {
                showLoading(false);
                isLoading = false;
                const grid = $('homeGrid');
                if (grid) grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:3rem;color:#94a3b8;">找不到 ${prefix} 的影片</div>`;
                return;
            }

            // 取第一個目標頁載入
            const targetPage = pages[0];
            const urlToLoad  = targetPage > 1
                ? `https://tktube.com/zh/latest-updates/${targetPage}/`
                : 'https://tktube.com/zh/latest-updates/';

            const res = await window.pywebview.api.get_tktube_home_videos(urlToLoad);
            if (res && res.videos) {
                currentPage = res.current_page || targetPage;
                totalPages  = res.total_pages  || 1;
                // 進一步在前端過濾符合前綴的影片
                const filtered = res.videos.filter(v =>
                    v.upload_date && v.upload_date.startsWith(prefix)
                );
                renderHomeVideos(filtered.length > 0 ? filtered : res.videos);
                showToast(`📅 找到 ${prefix} 的影片，共 ${filtered.length} 部`);
            } else {
                renderHomeVideos([]);
            }
        } catch (e) {
            console.error('[homeManager] dateFilter error:', e);
            renderHomeVideos([]);
        } finally {
            isLoading = false;
            showLoading(false);
        }
    }

    // ── 清除篩選 ──────────────────────────────────────────────────────────────
    function clearFilters() {
        isSearchActive = false;
        isDateFiltered = false;
        const si = $('homeSearchInput');
        if (si) si.value = '';
        const ys = $('homeYearFilter');
        const ms = $('homeMonthFilter');
        const ds = $('homeDayFilter');
        if (ys) { ys.value = ''; }
        if (ms) { ms.value = ''; ms.disabled = true; }
        if (ds) { ds.value = ''; ds.disabled = true; }
        fetchPage(1, currentBaseUrl);
    }

    // ── 背景預載（程式啟動時立即呼叫） ───────────────────────────────────────
    async function preload() {
        if (preloadDone) return;
        console.log('[homeManager] Background preload starting...');
        try {
            const res = await window.pywebview.api.get_tktube_home_videos(
                'https://tktube.com/zh/latest-updates/'
            );
            if (res && res.videos) {
                preloadedData = res;
                preloadDone   = true;
                totalPages    = res.total_pages || 1;
                currentPage   = 1;
                console.log(`[homeManager] Preload done: ${res.videos.length} videos, ${totalPages} pages`);

                // 若使用者已切換到首頁且 grid 仍空白，立即渲染
                const homeSection = document.getElementById('homeSection');
                if (homeSection && !homeSection.classList.contains('hidden-section')) {
                    const grid = $('homeGrid');
                    if (grid && grid.innerHTML.trim() === '') {
                        renderHomeVideos(res.videos);
                    }
                }
            }
        } catch (e) {
            console.warn('[homeManager] Preload failed:', e);
        }
    }

    // ── 切換到首頁時觸發 ─────────────────────────────────────────────────────
    async function onHomeTabActivated() {
        const grid = $('homeGrid');
        if (!grid) return;

        // 若預載已完成且 grid 仍空，立即渲染預載資料
        if (preloadDone && preloadedData && grid.innerHTML.trim() === '') {
            renderHomeVideos(preloadedData.videos);
            return;
        }

        // 若 grid 已有內容，不重新載入
        if (grid.innerHTML.trim() !== '' && !isLoading) return;

        // 否則直接 fetch
        await fetchPage(1, currentBaseUrl);
    }

    // ── 事件初始化（DOMContentLoaded 後執行） ────────────────────────────────
    function bindEvents() {
        // 重載按鈕
        const reloadBtn = $('loadHomeBtn');
        if (reloadBtn) reloadBtn.addEventListener('click', () => fetchPage(1, currentBaseUrl));

        // 上一頁
        const prevBtn = $('prevPageBtn');
        if (prevBtn) prevBtn.addEventListener('click', () => {
            if (!isSearchActive && currentPage > 1) {
                fetchPage(currentPage - 1, currentBaseUrl);
            }
        });

        // 下一頁
        const nextBtn = $('nextPageBtn');
        if (nextBtn) nextBtn.addEventListener('click', () => {
            if (!isSearchActive && currentPage < totalPages) {
                fetchPage(currentPage + 1, currentBaseUrl);
            }
        });

        // 搜尋按鈕
        const searchBtn = $('homeSearchBtn');
        if (searchBtn) searchBtn.addEventListener('click', () => {
            const q = $('homeSearchInput') ? $('homeSearchInput').value : '';
            doSearch(q);
        });

        // 搜尋輸入框 Enter
        const searchInput = $('homeSearchInput');
        if (searchInput) {
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') doSearch(searchInput.value);
            });
        }

        // 確認日期篩選
        const confirmBtn = $('confirmHomeDateBtn');
        if (confirmBtn) confirmBtn.addEventListener('click', doDateFilter);

        // 清除篩選
        const clearBtn = $('clearHomeDateBtn');
        if (clearBtn) clearBtn.addEventListener('click', clearFilters);

        // 初始化聯動日期篩選器
        initDateFilters();
    }

    // ── 公開介面 ──────────────────────────────────────────────────────────────
    return {
        init:            bindEvents,
        preload:         preload,
        onHomeActivated: onHomeTabActivated
    };
})();

// 保留向後相容的空函式（其他程式碼可能殘留呼叫）
let homeLoaded = false;
async function loadHomeContent() {
    homeManager.onHomeActivated();
}

// Sync Watch Logic
const syncPanesData = {};
let paneCount = 4;
let lastClickedPaneId = null;
let hotkeyStart = localStorage.getItem('hotkey_start') || 'z';
let hotkeyEnd = localStorage.getItem('hotkey_end') || 'x';

// Run all sync and hotkey setup on DOMContentLoaded
onDOMReady(() => {
    setSyncGridSlots(4); // Default to 4 slots on startup
    
    // Register grid selector buttons
    document.querySelectorAll('.grid-sel-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const slots = btn.getAttribute('data-slots');
            setSyncGridSlots(slots);
        });
    });
    
    // Init settings hotkeys recording UI
    initSettingsHotkeys();
});

function setSyncGridSlots(slots) {
    const grid = document.getElementById('syncGrid');
    if (!grid) return;
    
    const numSlots = parseInt(slots);
    
    // Update active button state in header
    document.querySelectorAll('.grid-sel-btn').forEach(btn => {
        if (parseInt(btn.getAttribute('data-slots')) === numSlots) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    
    // Update the columns layout style dynamically
    if (numSlots === 1) {
        grid.style.gridTemplateColumns = 'repeat(1, 1fr)';
    } else if (numSlots === 2) {
        grid.style.gridTemplateColumns = 'repeat(2, 1fr)';
    } else if (numSlots === 3) {
        grid.style.gridTemplateColumns = 'repeat(3, 1fr)';
    } else if (numSlots === 4) {
        grid.style.gridTemplateColumns = 'repeat(2, 1fr)';
    } else {
        grid.style.gridTemplateColumns = 'repeat(3, 1fr)';
    }
    
    const currentPanes = grid.querySelectorAll('.sync-pane');
    const currentCount = currentPanes.length;
    
    if (currentCount < numSlots) {
        // Append new empty slots at the end
        for (let i = currentCount; i < numSlots; i++) {
            const paneId = `sync-pane-${i}`;
            const pane = document.createElement('div');
            pane.className = 'sync-pane empty-pane';
            pane.id = paneId;
            pane.innerHTML = '<span class="pane-text">等待新增影片</span>';
            
            // Focus click binding
            pane.addEventListener('click', () => {
                setActivePane(paneId);
            });
            
            grid.appendChild(pane);
        }
    } else if (currentCount > numSlots) {
        // Remove slots from the end
        for (let i = currentCount - 1; i >= numSlots; i--) {
            const paneId = `sync-pane-${i}`;
            const pane = document.getElementById(paneId);
            if (pane) {
                // Clear intervals and data
                const data = syncPanesData[paneId];
                if (data && data.monitor) {
                    clearInterval(data.monitor);
                }
                delete syncPanesData[paneId];
                
                // Remove from DOM
                pane.remove();
            }
        }
    }
    
    paneCount = numSlots;
    
    // Clear active pane focus if the active pane was removed
    if (lastClickedPaneId) {
        const activeIndex = parseInt(lastClickedPaneId.replace('sync-pane-', ''));
        if (activeIndex >= numSlots) {
            lastClickedPaneId = null;
            updateActivePaneIndicator();
        }
    }
}

function initSettingsHotkeys() {
    const startInput = document.getElementById('hotkeyStartInput');
    const endInput = document.getElementById('hotkeyEndInput');
    const saveMsg = document.getElementById('hotkeySaveMsg');
    
    if (startInput && endInput) {
        startInput.value = hotkeyStart.toUpperCase();
        endInput.value = hotkeyEnd.toUpperCase();
        
        const setupHotkeyRecording = (input, isStart) => {
            input.addEventListener('click', () => {
                input.value = "請按下任意鍵...";
                input.style.borderColor = 'var(--accent)';
                
                const keyListener = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    const pressedKey = e.key;
                    if (['Shift', 'Control', 'Alt', 'Meta'].includes(pressedKey)) return;
                    
                    const finalKey = pressedKey.toLowerCase();
                    if (isStart) {
                        hotkeyStart = finalKey;
                        localStorage.setItem('hotkey_start', finalKey);
                    } else {
                        hotkeyEnd = finalKey;
                        localStorage.setItem('hotkey_end', finalKey);
                    }
                    
                    input.value = pressedKey.toUpperCase();
                    input.style.borderColor = '';
                    
                    if (saveMsg) {
                        saveMsg.classList.remove('hidden');
                        setTimeout(() => saveMsg.classList.add('hidden'), 3000);
                    }
                    
                    updateActivePaneIndicator();
                    window.removeEventListener('keydown', keyListener, true);
                };
                
                window.addEventListener('keydown', keyListener, true);
            });
        };
        
        setupHotkeyRecording(startInput, true);
        setupHotkeyRecording(endInput, false);
    }
}

function setActivePane(paneId) {
    const pane = document.getElementById(paneId);
    if (!pane || pane.classList.contains('empty-pane')) return;
    
    lastClickedPaneId = paneId;
    
    // Remove active style from all panes
    document.querySelectorAll('.sync-pane').forEach(p => {
        p.classList.remove('active-pane');
        const pill = p.querySelector('.loop-status-pill');
        if (pill) pill.classList.remove('active-pill');
    });
    
    // Add active style to this pane
    pane.classList.add('active-pane');
    const pill = pane.querySelector('.loop-status-pill');
    if (pill) pill.classList.add('active-pill');
    
    updateActivePaneIndicator();
}

function updateActivePaneIndicator() {
    const indicator = document.getElementById('activePaneIndicator');
    if (indicator) {
        if (lastClickedPaneId) {
            const num = parseInt(lastClickedPaneId.replace('sync-pane-', '')) + 1;
            indicator.innerHTML = `🎯 鎖定視窗 #${num} (快捷鍵 [${hotkeyStart.toUpperCase()}]/[${hotkeyEnd.toUpperCase()}])`;
            indicator.style.opacity = '1';
        } else {
            indicator.innerHTML = `🎯 點選視窗可用快捷鍵控制`;
            indicator.style.opacity = '0.7';
        }
    }
}

// Global key down listener on main window
window.addEventListener('keydown', (e) => {
    // Ignore key triggers if user is typing in forms/inputs
    if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'SELECT' || document.activeElement.tagName === 'TEXTAREA') {
        return;
    }
    if (lastClickedPaneId) {
        handleGlobalHotkey(e.key, lastClickedPaneId);
    }
});

function handleGlobalHotkey(key, paneId) {
    const k = key.toLowerCase();
    if (k === hotkeyStart.toLowerCase()) {
        setLoopStart(paneId);
    } else if (k === hotkeyEnd.toLowerCase()) {
        setLoopEnd(paneId);
    }
}

async function addToSyncWatch(url) {
    if (!url) {
        alert("此影片無有效連結可播放！");
        return;
    }
    
    // Fetch clean player embed URL
    let playerUrl = url;
    if(window.pywebview) {
        playerUrl = await window.pywebview.api.get_embed_url(url);
    }

    // Find empty pane
    const emptyPanes = document.querySelectorAll('.sync-pane.empty-pane');
    if(emptyPanes.length > 0) {
        const pane = emptyPanes[0];
        pane.classList.remove('empty-pane');
        setupPaneControls(pane, playerUrl);
        showToast("已加入同步觀看");
    } else {
        alert("同步觀看欄位已滿，請先清空現有欄位或增加同步欄位數量！");
    }
}

function setupPaneControls(pane, playerUrl) {
    const paneId = pane.id;
    
    // Reset any previous data/timer
    if (syncPanesData[paneId]) {
        if (syncPanesData[paneId].monitor) clearInterval(syncPanesData[paneId].monitor);
    }
    
    syncPanesData[paneId] = {
        video: null,
        start: null,
        end: null,
        iframe: null,
        monitor: null
    };

    const isJavxx = playerUrl.includes('javxx.com');
    pane.innerHTML = `
        <iframe src="${playerUrl}" sandbox="allow-scripts allow-same-origin allow-forms allow-presentation" scrolling="no" class="${isJavxx ? 'iframe-crop-javxx' : ''}" frameborder="0" allowfullscreen></iframe>
        <div class="sync-loop-overlay">
            <div class="loop-status-pill">
                <div class="loop-btn-group">
                    <button class="loop-btn btn-set-a" onclick="setLoopStart('${paneId}'); event.stopPropagation();" title="將當前時間設為起點">🅰️ 起點</button>
                    <button class="loop-btn btn-set-b" onclick="setLoopEnd('${paneId}'); event.stopPropagation();" title="將當前時間設為終點" disabled>🅱️ 終點</button>
                    <button class="loop-btn btn-reset" onclick="resetLoop('${paneId}'); event.stopPropagation();" title="取消重播範圍" style="display:none;">🔄</button>
                    <button class="loop-btn btn-clear" onclick="clearSyncPane('${paneId}'); event.stopPropagation();" title="清空此播放欄位" style="background: rgba(239, 68, 68, 0.2); border-color: rgba(239, 68, 68, 0.3); color: #f87171;">❌</button>
                </div>
                <span class="loop-time-display">未設定</span>
            </div>
        </div>
    `;
    
    // Add overlay click listener to capture active focus pane
    const overlay = pane.querySelector('.sync-loop-overlay');
    if (overlay) {
        overlay.addEventListener('click', (e) => {
            e.stopPropagation();
            setActivePane(paneId);
        });
    }
    
    // Focus this slot automatically when a video is loaded into it
    setActivePane(paneId);

    // Start tracking the video inside this pane recursively
    trackPaneVideo(paneId);
}

function trackPaneVideo(paneId) {
    const pane = document.getElementById(paneId);
    if (!pane || pane.classList.contains('empty-pane')) return;
    
    const iframe = pane.querySelector('iframe');
    if (!iframe) return;
    
    function findVideo(win) {
        try {
            const doc = win.document;
            const video = doc.querySelector('video');
            if (video) return video;
            
            const iframes = doc.querySelectorAll('iframe');
            for (let i = 0; i < iframes.length; i++) {
                const res = findVideo(iframes[i].contentWindow);
                if (res) return res;
            }
        } catch (e) {
            // Ignore SOP errors
        }
        return null;
    }
    
    const poller = setInterval(() => {
        const currentPane = document.getElementById(paneId);
        if (!currentPane || currentPane.classList.contains('empty-pane')) {
            clearInterval(poller);
            return;
        }
        
        try {
            const video = findVideo(iframe.contentWindow);
            if (video) {
                clearInterval(poller);
                syncPanesData[paneId].video = video;
                syncPanesData[paneId].iframe = iframe;
                
                const pill = currentPane.querySelector('.loop-status-pill');
                if (pill) {
                    pill.style.borderColor = 'rgba(74, 222, 128, 0.5)';
                    pill.style.boxShadow = '0 4px 15px rgba(74, 222, 128, 0.2)';
                }
                
                // Bind click and key listeners INSIDE cross-origin iframe once video mounts!
                const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                if (iframeDoc) {
                    iframeDoc.addEventListener('click', () => {
                        setActivePane(paneId);
                    });
                    iframeDoc.addEventListener('keydown', (e) => {
                        handleGlobalHotkey(e.key, paneId);
                    });
                }
                
                startLoopMonitor(paneId);
            }
        } catch (e) {
            // keep checking
        }
    }, 1000);
}

function formatTime(secs) {
    if (isNaN(secs)) return "00:00";
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = Math.floor(secs % 60);
    
    const mm = m < 10 ? '0' + m : m;
    const ss = s < 10 ? '0' + s : s;
    
    if (h > 0) {
        const hh = h < 10 ? '0' + h : h;
        return `${hh}:${mm}:${ss}`;
    }
    return `${mm}:${ss}`;
}

function setLoopStart(paneId) {
    const data = syncPanesData[paneId];
    if (!data || !data.video) {
        showToast("⚠️ 請先播放影片後再設定！");
        return;
    }
    
    data.start = data.video.currentTime;
    
    const pane = document.getElementById(paneId);
    const btnA = pane.querySelector('.btn-set-a');
    const btnB = pane.querySelector('.btn-set-b');
    const display = pane.querySelector('.loop-time-display');
    
    btnA.classList.add('active-a');
    btnA.innerHTML = `🅰️ ${formatTime(data.start)}`;
    btnB.disabled = false;
    
    display.innerText = `${formatTime(data.start)} ➡️ ...`;
    showToast(`📍 起點設定成功: ${formatTime(data.start)}`);
}

function setLoopEnd(paneId) {
    const data = syncPanesData[paneId];
    if (!data || !data.video) {
        showToast("⚠️ 請先播放影片後再設定！");
        return;
    }
    
    if (data.start === null) {
        showToast("⚠️ 請先設定起點！");
        return;
    }
    
    const current = data.video.currentTime;
    if (current <= data.start) {
        showToast("⚠️ 終點時間必須大於起點！");
        return;
    }
    
    data.end = current;
    
    const pane = document.getElementById(paneId);
    const btnB = pane.querySelector('.btn-set-b');
    const btnReset = pane.querySelector('.btn-reset');
    const display = pane.querySelector('.loop-time-display');
    
    btnB.classList.add('active-b');
    btnB.innerHTML = `🅱️ ${formatTime(data.end)}`;
    btnReset.style.display = 'inline-flex';
    
    display.innerText = `${formatTime(data.start)} ➡️ ${formatTime(data.end)}`;
    showToast(`🔁 範圍重播已啟用: ${formatTime(data.start)} ~ ${formatTime(data.end)}`);
}

function resetLoop(paneId) {
    const data = syncPanesData[paneId];
    if (data) {
        data.start = null;
        data.end = null;
    }
    
    const pane = document.getElementById(paneId);
    if (pane) {
        const btnA = pane.querySelector('.btn-set-a');
        const btnB = pane.querySelector('.btn-set-b');
        const btnReset = pane.querySelector('.btn-reset');
        const display = pane.querySelector('.loop-time-display');
        
        btnA.classList.remove('active-a');
        btnA.innerHTML = "🅰️ 起點";
        
        btnB.classList.remove('active-b');
        btnB.innerHTML = "🅱️ 終點";
        btnB.disabled = true;
        
        btnReset.style.display = 'none';
        display.innerText = "未設定";
    }
    showToast("🔄 已取消重播範圍");
}

function clearSyncPane(paneId) {
    const pane = document.getElementById(paneId);
    if (!pane) return;
    
    const data = syncPanesData[paneId];
    if (data) {
        if (data.monitor) clearInterval(data.monitor);
        syncPanesData[paneId] = null;
    }
    
    pane.classList.add('empty-pane');
    pane.innerHTML = '<span class="pane-text">等待新增影片</span>';
    
    if (lastClickedPaneId === paneId) {
        lastClickedPaneId = null;
        updateActivePaneIndicator();
    }
    
    showToast("🗑️ 已清空播放欄位");
}

function startLoopMonitor(paneId) {
    if (syncPanesData[paneId].monitor) {
        clearInterval(syncPanesData[paneId].monitor);
    }
    
    syncPanesData[paneId].monitor = setInterval(() => {
        const data = syncPanesData[paneId];
        if (!data || !data.video || !document.getElementById(paneId) || document.getElementById(paneId).classList.contains('empty-pane')) {
            clearInterval(data.monitor);
            return;
        }
        
        const video = data.video;
        if (data.start !== null && data.end !== null) {
            if (video.currentTime >= data.end) {
                video.currentTime = data.start;
                if (video.paused) {
                    video.play().catch(() => {});
                }
            }
        }
    }, 200);
}

// Context Menu Logic
document.addEventListener('click', (e) => {
    const contextMenu = document.getElementById('customContextMenu');
    if (contextMenu) {
        contextMenu.classList.add('hidden');
    }
});

onDOMReady(() => {
    const menuSyncWatch = document.getElementById('menuSyncWatch');
    if (menuSyncWatch) {
        menuSyncWatch.addEventListener('click', () => {
            if(currentContextMenuVideo) {
                addToSyncWatch(currentContextMenuVideo.url);
            }
        });
    }

    const menuRemoveFav = document.getElementById('menuRemoveFav');
    if (menuRemoveFav) {
        menuRemoveFav.addEventListener('click', async () => {
            if(currentContextMenuVideo && currentContextMenuSource === 'fav') {
                const code = currentContextMenuVideo.code;
                if(confirm(`確定要將 [${code.toUpperCase()}] 從我的最愛中移除嗎？`)) {
                    const cleanTarget = (code || '').toLowerCase().trim();
                    allVideos = allVideos.filter(v => (v.code || '').toLowerCase().trim() !== cleanTarget);
                    renderVideos(allVideos);
                    updateStats(allVideos);
                    if(window.pywebview) {
                        await window.pywebview.api.save_videos(allVideos);
                    }
                }
            }
        });
    }

    const menuPlayMissavNormal = document.getElementById('menuPlayMissavNormal');
    if (menuPlayMissavNormal) {
        menuPlayMissavNormal.addEventListener('click', () => {
            if(currentContextMenuVideo) {
                const code = currentContextMenuVideo.code.toLowerCase().trim();
                openPlayer(`https://missav.ws/${code}`);
            }
        });
    }

    const menuPlayMissavLeaked = document.getElementById('menuPlayMissavLeaked');
    if (menuPlayMissavLeaked) {
        menuPlayMissavLeaked.addEventListener('click', () => {
            if(currentContextMenuVideo) {
                const code = currentContextMenuVideo.code.toLowerCase().trim();
                openPlayer(`https://missav.ws/${code}-uncensored-leak`);
            }
        });
    }
});

// Add menu item for adding to favorites from home
onDOMReady(() => {
    const menu = document.getElementById('customContextMenu');
    const addFavItem = document.createElement('div');
    addFavItem.className = 'menu-item';
    addFavItem.id = 'menuAddFav';
    addFavItem.textContent = '❤️ 新增至我的最愛';
    addFavItem.style.display = 'none';
    
    addFavItem.addEventListener('click', async () => {
        if (currentContextMenuSource === 'home' && currentContextMenuVideo) {
            const cleanTarget = (currentContextMenuVideo.code || '').toLowerCase().trim();
            // Case-insensitive duplicate check
            if(!allVideos.find(v => (v.code || '').toLowerCase().trim() === cleanTarget)) {
                // Ensure correct structure
                const videoData = {
                    raw: currentContextMenuVideo.code,
                    clean: currentContextMenuVideo.code.toLowerCase(),
                    code: currentContextMenuVideo.code,
                    url: currentContextMenuVideo.url,
                    img: currentContextMenuVideo.cover,
                    preview: currentContextMenuVideo.preview,
                    found: true,
                    type: currentContextMenuVideo.type,
                    actress: currentContextMenuVideo.actress,
                    upload_date: currentContextMenuVideo.upload_date || "",
                    relative_time: currentContextMenuVideo.relative_time || ""
                };
                allVideos.unshift(videoData);
                await window.pywebview.api.save_videos(allVideos);
                renderVideos(allVideos);
                updateStats(allVideos);
                showToast(`已成功將 [${videoData.code}] 加入最愛`);
            } else {
                showToast("已在最愛清單中");
            }
        }
    });
    
    menu.insertBefore(addFavItem, document.getElementById('menuRemoveFav'));
});

function initializeApp() {
    console.log("JApp: Initializing app data and prefetching home content...");
    loadData();
    // 啟動後立即背景預載首頁（不等使用者點擊首頁分頁）
    if (!homeLoaded) {
        homeLoaded = true;
        setTimeout(() => {
            console.log("JApp: Background preloading home videos...");
            homeManager.preload();
        }, 500); // 500ms 稍延以確保 favorites 載入優先完成
    }
}

if (window.pywebview && window.pywebview.api) {
    console.log("JApp: window.pywebview already exists, checking DOM readiness...");
    onDOMReady(initializeApp);
} else {
    console.log("JApp: window.pywebview not ready, waiting for pywebviewready event...");
    window.addEventListener('pywebviewready', () => {
        onDOMReady(initializeApp);
    });
}

async function loadData() {
    try {
        const data = await window.pywebview.api.get_videos();
        allVideos = data;
        updateStats(data);
        renderVideos(data);
    } catch (e) {
        document.querySelector('.loading').innerText = "資料載入失敗: " + e;
    }
}

function updateStats(videos) {
    document.getElementById('totalCount').innerText = videos.length;
    const linked = videos.filter(v => v.found).length;
    document.getElementById('linkCount').innerText = linked;
}

function getTypeClass(type) {
    if (type === '無碼破解版') return 'type-uncensored';
    if (type === '正常版') return 'type-normal';
    return 'type-none';
}

function getPreviewUrl(v) {
    if (v.preview) return v.preview;
    const imgSrc = v.img || v.cover;
    if (imgSrc && imgSrc.includes('/img2/')) {
        const parts = imgSrc.split('/img2/');
        if (parts.length > 1) {
            const subPath = parts[1].replace('/cover.webp', '');
            let cleanPath = subPath;
            if (cleanPath.startsWith('s360/')) {
                cleanPath = cleanPath.substring(5);
            }
            return `https://icdn.javxx.com/preview/${cleanPath}/preview.png`;
        }
    }
    return "";
}

function populateFilters() {
    const actressSelect = document.getElementById('actressFilter');
    const typeSelect = document.getElementById('typeFilter');
    if (!actressSelect || !typeSelect) return;

    const selectedActress = actressSelect.value;
    const selectedType = typeSelect.value;

    const actresses = new Set();
    const types = new Set();

    allVideos.forEach(v => {
        if (v.actress) {
            const clean = v.actress.replace(/\*\*/g, '');
            clean.split(/[,，\+]/).forEach(a => {
                const name = a.trim();
                if (name && name !== '未知女優' && name !== '未知' && name !== '新加入') {
                    actresses.add(name);
                }
            });
        }
        if (v.type && v.type !== '無') {
            types.add(v.type.trim());
        }
    });

    actressSelect.innerHTML = '<option value="">👤 所有女優</option>';
    Array.from(actresses).sort().forEach(a => {
        const opt = document.createElement('option');
        opt.value = a;
        opt.textContent = a;
        if (a === selectedActress) opt.selected = true;
        actressSelect.appendChild(opt);
    });

    typeSelect.innerHTML = '<option value="">🏷️ 所有類型</option>';
    Array.from(types).sort().forEach(t => {
        const opt = document.createElement('option');
        opt.value = t;
        opt.textContent = t;
        if (t === selectedType) opt.selected = true;
        typeSelect.appendChild(opt);
    });
}

function filterAndRenderVideos() {
    const term = document.getElementById('searchInput').value.toLowerCase();
    const actressVal = document.getElementById('actressFilter').value;
    const typeVal = document.getElementById('typeFilter').value;

    const filtered = allVideos.filter(v => {
        const codeMatch = v.code && v.code.toLowerCase().includes(term);
        const actressMatch = v.actress && v.actress.toLowerCase().includes(term);
        const matchesSearch = codeMatch || actressMatch;

        let matchesActress = true;
        if (actressVal) {
            matchesActress = v.actress && v.actress.replace(/\*\*/g, '').includes(actressVal);
        }

        let matchesType = true;
        if (typeVal) {
            matchesType = v.type === typeVal;
        }

        return matchesSearch && matchesActress && matchesType;
    });

    renderVideos(filtered, false);
}

function createVideoCardElement(v, source = 'fav') {
    const card = document.createElement('div');
    card.className = 'video-card';

    // 確保物件屬性安全
    const cleanCode = (v.code || '').trim().toUpperCase();
    const cleanActress = (v.actress || '').replace(/\*\*/g, '').trim();
    const displayTitle = v.title || '';
    const displayType = v.type || '正常版';

    // Add Context Menu Event
    card.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        currentContextMenuVideo = v;
        currentContextMenuSource = source;
        const menu = document.getElementById('customContextMenu');
        
        const removeBtn = document.getElementById('menuRemoveFav');
        const addFavBtn = document.getElementById('menuAddFav');
        if (source === 'home') {
            if(removeBtn) removeBtn.style.display = 'none';
            if(addFavBtn) addFavBtn.style.display = 'block';
        } else {
            if(removeBtn) removeBtn.style.display = 'block';
            if(addFavBtn) addFavBtn.style.display = 'none';
        }

        menu.style.left = e.pageX + 'px';
        menu.style.top = e.pageY + 'px';
        menu.classList.remove('hidden');
    });

    // Hover Copy for Favorites
    if (source === 'fav') {
        let lastCopied = "";
        card.addEventListener('mouseenter', async () => {
            const textToCopy = `${cleanCode} ${cleanActress}`;
            if (textToCopy !== lastCopied) {
                try {
                    if (window.pywebview && window.pywebview.api.copy_to_clipboard) {
                        const success = await window.pywebview.api.copy_to_clipboard(textToCopy);
                        if (success) {
                            lastCopied = textToCopy;
                            const codeEl = card.querySelector('.card-code');
                            const originalColor = codeEl.style.color;
                            codeEl.style.color = '#4ade80';
                            setTimeout(() => { codeEl.style.color = originalColor || ''; }, 500);
                        }
                    } else {
                        await navigator.clipboard.writeText(textToCopy);
                        lastCopied = textToCopy;
                        const codeEl = card.querySelector('.card-code');
                        const originalColor = codeEl.style.color;
                        codeEl.style.color = '#4ade80';
                        setTimeout(() => { codeEl.style.color = originalColor || ''; }, 500);
                    }
                } catch(err) {
                    console.error("Copy failed", err);
                }
            }
        });
    }

    const imgSrc = source === 'home' ? v.cover : v.img;
    const isFound = source === 'home' ? true : v.found;
    const url = v.url || '';
    const previewUrl = getPreviewUrl(v);

    const imgHtml = imgSrc 
        ? `<img src="${imgSrc}" class="card-img" alt="Cover" loading="lazy">` 
        : `<div class="no-img">無預覽圖</div>`;

    const isVideoPreview = previewUrl && (previewUrl.toLowerCase().includes('.mp4') || previewUrl.toLowerCase().includes('.webm') || previewUrl.toLowerCase().includes('/get_file/') || previewUrl.toLowerCase().includes('tktube') || !previewUrl.toLowerCase().endsWith('.png'));

    const previewHtml = isVideoPreview 
        ? `<video class="preview-video" muted loop playsinline preload="none"></video>`
        : '';

    const btnClass = isFound ? '' : 'disabled';
    const btnText = isFound ? '▶ 內建播放' : '無連結';
    
    let displayDate = '';
    const dateVal = v.upload_date ? v.upload_date.trim() : '';
    const relVal = v.relative_time ? v.relative_time.trim() : '';

    if (dateVal) {
        displayDate = dateVal;
    } else if (relVal) {
        const dateMatch = relVal.match(/\d{4}-\d{2}-\d{2}/);
        if (dateMatch) {
            displayDate = dateMatch[0];
        } else {
            // Clean non-date text and emoji
            displayDate = relVal.replace(/[^\d\-\s:]/g, '').trim();
            if (!displayDate) {
                displayDate = relVal;
            }
        }
    }

    // Format date to strictly YYYY:MM:DD (replacing '-' or '/' with ':')
    if (displayDate) {
        const match = displayDate.match(/(\d{4})[-\/\s:]?(\d{2})[-\/\s:]?(\d{2})/);
        if (match) {
            displayDate = `${match[1]}:${match[2]}:${match[3]}`;
        } else {
            displayDate = displayDate.replace(/[-\/\s]/g, ':').substring(0, 10);
        }
    }

    let dateHtml = '';
    if (displayDate) {
        dateHtml = `<div class="card-date" style="color: #94a3b8; font-size: 0.75rem; margin-bottom: 0.8rem; display: flex; align-items: center; gap: 4px;" title="日期">${displayDate}</div>`;
    }
    
    const finalActress = (cleanActress && cleanActress !== '新加入' && cleanActress !== '未知女優') 
        ? cleanActress 
        : (displayTitle ? (displayTitle.length > 20 ? displayTitle.substring(0,20)+'...' : displayTitle) : '未知女優');

    card.innerHTML = `
        <div class="card-img-wrapper">
            ${imgHtml}
            ${previewHtml}
        </div>
        <div class="card-content">
            <div class="card-code">${cleanCode}</div>
            <div class="card-actress">${finalActress.replace(/\*\*/g, '')}</div>
            <div class="card-type ${getTypeClass(displayType)}">${displayType}</div>
            ${dateHtml}
            <button class="card-link ${btnClass}" onclick="openPlayer('${url}')">${btnText}</button>
        </div>
    `;

    // Preview Hover Seek / Scrubbing Logic
    if (isVideoPreview) {
        const wrapper = card.querySelector('.card-img-wrapper');
        const video = card.querySelector('.preview-video');
        let isLoaded = false;
        let isLoading = false;

        wrapper.addEventListener('mouseenter', () => {
            if (!isLoaded && !isLoading) {
                isLoading = true;
                video.src = previewUrl;
                video.preload = "auto";
                video.load();
                isLoaded = true;
                isLoading = false;
            }
            video.play().catch(e => console.error("Play error:", e));
        });

        wrapper.addEventListener('mouseleave', () => {
            video.pause();
            if (isLoaded) {
                video.currentTime = 0;
            }
        });

        wrapper.addEventListener('mousemove', (e) => {
            if (isLoaded && video.duration) {
                const rect = wrapper.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const percent = x / rect.width;
                video.currentTime = Math.min(Math.max(0, percent * video.duration), video.duration - 0.1);
            }
        });
    }

    return card;
}

function renderVideos(videos, shouldPopulateFilters = true) {
    const grid = document.getElementById('videoGrid');
    grid.innerHTML = '';

    if (videos.length === 0) {
        grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 2rem;">找不到符合的影片</div>';
        return;
    }

    videos.forEach(v => {
        grid.appendChild(createVideoCardElement(v, 'fav'));
    });

    if (shouldPopulateFilters) {
        populateFilters();
    }
}

// Bind search and filter events
onDOMReady(() => {
    // Populate dynamic date filters on startup
    initializeDynamicDateFilters();

    const searchInput = document.getElementById('searchInput');
    const actressFilter = document.getElementById('actressFilter');
    const typeFilter = document.getElementById('typeFilter');

    if (searchInput) searchInput.addEventListener('input', filterAndRenderVideos);
    if (actressFilter) actressFilter.addEventListener('change', filterAndRenderVideos);
    if (typeFilter) typeFilter.addEventListener('change', filterAndRenderVideos);

    // homeManager 事件綁定
    homeManager.init();
});



// Modal Player Logic
async function openPlayer(url) {
    if (!url) return;
    
    // Fetch clean player embed URL
    let playerUrl = url;
    if(window.pywebview) {
        const oldIframe = document.getElementById('videoPlayer');
        if(oldIframe) oldIframe.remove(); // Remove old to reset classes
        playerUrl = await window.pywebview.api.get_embed_url(url);
    }
    
    const modal = document.getElementById('playerModal');
    const container = document.querySelector('.iframe-container');
    
    // Create new iframe with crop class
    const iframe = document.createElement('iframe');
    iframe.id = 'videoPlayer';
    iframe.src = playerUrl;
    iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-presentation');
    iframe.setAttribute('scrolling', 'no');
    const isJavxx = url.includes('javxx.com') || playerUrl.includes('javxx.com');
    if (isJavxx) {
        iframe.className = 'iframe-crop-javxx';
    } else {
        iframe.className = '';
    }
    iframe.setAttribute('frameborder', '0');
    iframe.setAttribute('allowfullscreen', 'true');
    container.appendChild(iframe);
    
    modal.classList.remove('hidden');
}

document.getElementById('closeModal').addEventListener('click', () => {
    const modal = document.getElementById('playerModal');
    const iframe = document.getElementById('videoPlayer');
    modal.classList.add('hidden');
    if(iframe) {
        iframe.src = ""; // Stop video playback
        iframe.remove(); // Clean up
    }
});

// ==========================================
// JApp Auto Update Frontend Logic
// ==========================================
let currentUpdateInfo = null;

// Initialize Update panel on startup
onDOMReady(() => {
    if (window.pywebview) {
        window.pywebview.api.get_version().then(v => {
            const currentVersionText = document.getElementById('currentVersionText');
            if (currentVersionText) currentVersionText.innerText = 'v' + v;
        });
    }
    
    const checkUpdateBtn = document.getElementById('checkUpdateBtn');
    if (checkUpdateBtn) {
        checkUpdateBtn.addEventListener('click', checkUpdate);
    }
    
    const startUpdateBtn = document.getElementById('startUpdateBtn');
    if (startUpdateBtn) {
        startUpdateBtn.addEventListener('click', startUpdate);
    }
});

async function checkUpdate() {
    const btn = document.getElementById('checkUpdateBtn');
    const statusText = document.getElementById('updateStatusText');
    const infoArea = document.getElementById('updateInfoArea');
    
    if (!window.pywebview) {
        showToast("無法連接至 Python API！");
        return;
    }
    
    btn.disabled = true;
    btn.style.opacity = '0.6';
    btn.innerText = "正在檢查...";
    statusText.innerText = "正在向 GitHub 查詢最新版本...";
    infoArea.classList.add('hidden');
    
    try {
        const res = await window.pywebview.api.check_for_updates();
        btn.disabled = false;
        btn.style.opacity = '1';
        btn.innerText = "檢查更新";
        
        if (res) {
            currentUpdateInfo = res;
            statusText.innerText = "發現新版本！請確認是否要安裝。";
            statusText.style.color = "#4ade80";
            
            const newVersionText = document.getElementById('newVersionText');
            const releaseNotesText = document.getElementById('releaseNotesText');
            
            if (newVersionText) newVersionText.innerText = 'v' + res.version;
            if (releaseNotesText) releaseNotesText.innerText = res.release_notes || "無更新說明";
            
            infoArea.classList.remove('hidden');
            showToast("發現有新版本 " + res.version + " 可用！");
        } else {
            currentUpdateInfo = null;
            statusText.innerText = "目前已是最新版本。";
            statusText.style.color = "#94a3b8";
            showToast("目前已是最新版本！");
        }
    } catch (e) {
        btn.disabled = false;
        btn.style.opacity = '1';
        btn.innerText = "檢查更新";
        statusText.innerText = "檢查更新失敗，請檢查網路連線。";
        statusText.style.color = "#f87171";
        showToast("檢查更新時發生錯誤: " + e);
    }
}

async function startUpdate() {
    const startBtn = document.getElementById('startUpdateBtn');
    const checkBtn = document.getElementById('checkUpdateBtn');
    const progressArea = document.getElementById('updateProgressArea');
    
    if (!currentUpdateInfo || !currentUpdateInfo.download_url) {
        showToast("找不到有效的下載網址！");
        return;
    }
    
    startBtn.disabled = true;
    startBtn.style.opacity = '0.6';
    startBtn.innerText = "正在下載...";
    checkBtn.disabled = true;
    checkBtn.style.opacity = '0.6';
    
    progressArea.classList.remove('hidden');
    
    try {
        const res = await window.pywebview.api.start_update(currentUpdateInfo.download_url);
        if (!res.success) {
            showToast(res.msg);
            startBtn.disabled = false;
            startBtn.style.opacity = '1';
            startBtn.innerText = "立即安裝更新";
            checkBtn.disabled = false;
            checkBtn.style.opacity = '1';
        } else {
            showToast("已啟動背景下載與更新流程...");
        }
    } catch (e) {
        startBtn.disabled = false;
        startBtn.style.opacity = '1';
        startBtn.innerText = "立即安裝更新";
        checkBtn.disabled = false;
        checkBtn.style.opacity = '1';
        showToast("啟動更新失敗: " + e);
    }
}

// Push notification progress callback from Python VersionManager
window.onUpdateProgress = function(status, percent, detail, error) {
    const progressBar = document.getElementById('updateProgressBar');
    const percentText = document.getElementById('progressPercentText');
    const detailText = document.getElementById('progressDetailText');
    const statusText = document.getElementById('updateStatusText');
    
    if (progressBar) progressBar.style.width = percent + '%';
    if (percentText) percentText.innerText = percent + '%';
    if (detailText) detailText.innerText = detail;
    
    if (status === 'downloading') {
        statusText.innerText = "正在下載新版本檔案...";
        statusText.style.color = "#3b82f6";
    } else if (status === 'extracting') {
        statusText.innerText = "下載完成！正在解壓縮檔案...";
        statusText.style.color = "#8b5cf6";
    } else if (status === 'applying') {
        statusText.innerText = "解壓縮完成！正在準備更新安裝腳本...";
        statusText.style.color = "#d946ef";
    } else if (status === 'completed') {
        statusText.innerText = "更新套用成功！";
        statusText.style.color = "#10b981";
        showToast("更新安裝成功，正在重啟程式...");
    } else if (status === 'error') {
        statusText.innerText = "更新安裝失敗";
        statusText.style.color = "#f87171";
        showToast("更新失敗: " + error);
        
        // Restore controls
        const startBtn = document.getElementById('startUpdateBtn');
        const checkBtn = document.getElementById('checkUpdateBtn');
        if (startBtn) {
            startBtn.disabled = false;
            startBtn.style.opacity = '1';
            startBtn.innerText = "立即安裝更新";
        }
        if (checkBtn) {
            checkBtn.disabled = false;
            checkBtn.style.opacity = '1';
        }
    }
};

// ==========================================
// JApp Pure Sync Mode (Stealth UI) Toggle Logic
// ==========================================
onDOMReady(() => {
    const toggleUiBtn = document.getElementById('toggleUiBtn');
    const restoreUiBtn = document.getElementById('restoreUiBtn');
    
    const enterStealthMode = () => {
        document.body.classList.add('stealth-ui-mode');
        if (restoreUiBtn) restoreUiBtn.classList.remove('hidden');
        showToast("已啟用純淨同步觀看！按 Esc 鍵或點擊左下角按鈕可恢復 UI。");
    };
    
    const exitStealthMode = () => {
        document.body.classList.remove('stealth-ui-mode');
        if (restoreUiBtn) restoreUiBtn.classList.add('hidden');
        showToast("已恢復 UI 介面。");
    };

    if (toggleUiBtn) {
        toggleUiBtn.addEventListener('click', (e) => {
            e.preventDefault();
            if (toggleUiBtn.classList.contains('disabled-ui')) {
                showToast("⚠️ 請先切換至「3. 同步觀看」分頁喔！");
                return;
            }
            enterStealthMode();
        });
    }
    
    if (restoreUiBtn) {
        restoreUiBtn.addEventListener('click', (e) => {
            e.preventDefault();
            exitStealthMode();
        });
    }
    
    // 全域 Esc 鍵退出純淨模式
    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' || e.key === 'Esc') {
            if (document.body.classList.contains('stealth-ui-mode')) {
                exitStealthMode();
            }
        }
    });
});


