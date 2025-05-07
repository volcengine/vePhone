#include "ve_qk_demo.h"


const WCHAR* largeWindowClass = L"LargeWindowClass";  // 大窗口类名
const int PREVIEW_WND_PROFILE_ID = 9514; // 预览窗清晰度
const int HIGH_FPS_LARGE_WND_NUM = 20; // 高帧率大窗数量
const int HIGH_FPS_LARGE_WND_PROFILE_ID = 15307; // 高帧率大窗清晰度
const int LOW_FPS_LARGE_WND_PROFILE_ID = 15703; // 低帧率大窗清晰度

// 获取每个大窗口对应的session
static vecommon::PhoneSession* getSession(HWND hWnd) {
    return reinterpret_cast<vecommon::PhoneSession*>(GetWindowLongPtr(hWnd, GWLP_USERDATA));
}

// 为大窗口注册原始输入设备，用于接收WM_INPUT消息
static void registerInputDevices(HWND win) {
    RAWINPUTDEVICE raw_input_device{};
    raw_input_device.usUsagePage = HID_USAGE_PAGE_GENERIC;   // 设备类
    raw_input_device.usUsage = 0;
    raw_input_device.dwFlags = RIDEV_PAGEONLY;
    raw_input_device.hwndTarget = win;
    if (!RegisterRawInputDevices(&raw_input_device, 1, sizeof(RAWINPUTDEVICE))) {
        vePrint("RegisterRawInputDevices Failed! Error:{}", GetLastError());
    }
}

// 创建大窗口
static HWND createLargeWindow(std::shared_ptr<QkDemo> demo, const char* podId) {
    const wchar_t* title = AnsiToUnicode(podId);
    HWND win = CreateWindowEx(0, largeWindowClass, title, WS_OVERLAPPEDWINDOW, 100, 100,
        PLAY_WIND_WIDTH, PLAY_WIND_HEIGHT, demo->_mainWindow, NULL, demo->_instance, nullptr);
    if (!win) {
        vePrint("CreateLargeWindow Failed! Error:{}", GetLastError());
        return nullptr;
    }
    RECT wnd_rect{ 0, 0, PLAY_WIND_WIDTH, PLAY_WIND_HEIGHT };
    AdjustWindowRect(&wnd_rect, WS_OVERLAPPEDWINDOW, true);
    int width = wnd_rect.right - wnd_rect.left;
    int height = wnd_rect.bottom - wnd_rect.top;
    SetWindowPos(win, HWND_TOP, 100, 100, width, height, SWP_SHOWWINDOW);

    registerInputDevices(win);
    vePrint("CreateLargeWindow Success: podId:{} win:{}", podId, fmt::ptr(win));
    return win;
}

// 大窗口的消息处理函数
static LRESULT CALLBACK LargeWindowProc(HWND hWnd, UINT message, WPARAM wParam, LPARAM lParam) {
    vecommon::PhoneSession* curSession = reinterpret_cast<vecommon::PhoneSession*>(GetWindowLongPtr(hWnd, GWLP_USERDATA));
    switch (message) {
    case WM_SETFOCUS:
    {
        registerInputDevices(hWnd);
        vecommon::PhoneSession* session = getSession(hWnd);
        std::shared_ptr<QkDemo> demo = getDemo();
        if (session && demo) {
            demo->updateValidArea(hWnd);
            demo->_focusedSession = session;
            RECT& rect = demo->_validArea;
            vePrint("LargeWindowProc: getFocus sid:{} win:{}", session->getSessionId(), fmt::ptr(hWnd));
        }
        break;
    }
    case WM_KILLFOCUS:
    {
        //vePrint("LargeWindowProc: loseFocus win:{}", fmt::ptr(hWnd));
        break;
    }
    case WM_LBUTTONDOWN:
    {
        vecommon::PhoneSession* session = getSession(hWnd);
        std::shared_ptr<QkDemo> demo = getDemo();
        if (session && demo && demo->_focusedSession != session) {
            demo->updateValidArea(hWnd);
            demo->_focusedSession = session;
            RECT& rect = demo->_validArea;
        }
        break;
    }
    case WM_MOVE:
    case WM_SIZE:
    {
        vecommon::PhoneSession* session = getSession(hWnd);
        std::shared_ptr<QkDemo> demo = getDemo();
        if (session && demo) {
            demo->updateValidArea(hWnd);
            demo->_focusedSession = session;
        }
        break;
    }
    case WM_INPUT:
    {
        std::shared_ptr<QkDemo> demo = getDemo();
        if (demo && !demo->_isMenuShow) {
            ProcessWmInput(demo->_focusedSession, demo->_validArea, hWnd, message, wParam, lParam);
        }
        break;
    }
    case WM_CHAR:
    {
        std::shared_ptr<QkDemo> demo = getDemo();
        if (demo && !demo->_isMenuShow) {
            ProcessWmChar(demo->_focusedSession, hWnd, message, wParam, lParam);
        }
        break;
    }
    case WM_INITMENUPOPUP:
    {
        std::shared_ptr<QkDemo> demo = getDemo();
        if (demo) {
            demo->_isMenuShow = true;
        }
        break;
    }
    case WM_UNINITMENUPOPUP:
    {
        std::shared_ptr<QkDemo> demo = getDemo();
        if (demo) {
            demo->_isMenuShow = false;
        }
        break;
    }
    case WM_KEYDOWN:
    case WM_SYSKEYDOWN:
    case WM_KEYUP:
    case WM_SYSKEYUP:
    {
        vecommon::PhoneSession* session = getSession(hWnd);
        std::shared_ptr<QkDemo> demo = getDemo();
        if (session && demo && !demo->_isMenuShow) {
            ProcessWmKeyAction(session, hWnd, message, wParam, lParam);
        }
        break;
    }
    case WM_COMMAND:
    {
        vecommon::PhoneSession* session = getSession(hWnd);
        std::shared_ptr<QkDemo> demo = getDemo();
        std::string podId;
        if (demo->_sessionToPodId.find(session) != demo->_sessionToPodId.end()) {
            podId = demo->_sessionToPodId[session];
        }
        QkSessionListener* listener = nullptr;
        if (demo->_sessionToListener.find(session) != demo->_sessionToListener.end()) {
            listener = demo->_sessionToListener[session];
        }
        if (session && demo) {
            ProcessWmCmd(session, podId, listener, demo->_instance, hWnd, wParam, lParam);
        }
        break;
    }
    case WM_PAINT:
    {
        PAINTSTRUCT ps;
        HDC hdc = BeginPaint(hWnd, &ps);
        // TODO: 在此处添加使用 hdc 的任何绘图代码
        EndPaint(hWnd, &ps);
        break;
    }
    case WM_DESTROY:
    {
        vecommon::PhoneSession* session = getSession(hWnd);
        std::shared_ptr<QkDemo> demo = getDemo();

        if (session) {
            session->stop();
        }
        // 关掉大窗后，将map中对应的信息清除
        if (demo->_sessionToPodId.find(session) != demo->_sessionToPodId.end()) {
            demo->_podIdToLargeWnd.erase(demo->_sessionToPodId[session]);
            demo->_sessionToPodId.erase(session);
            demo->_sessionToListener.erase(session);
        }
        session = nullptr;
        break;
    }
    default:
        return DefWindowProc(hWnd, message, wParam, lParam);
    }
    return 0;
}

// 预览窗口的消息处理函数
static LRESULT CALLBACK PreviewWindowProc(HWND hWnd, UINT message, WPARAM wParam, LPARAM lParam) {
    const char* pod_id = reinterpret_cast<const char*>(GetWindowLongPtr(hWnd, GWLP_USERDATA));
    std::shared_ptr<QkDemo> demo = getDemo();
    if (!pod_id || !demo) {
        return 0;
    }
    if (!demo->_renderX) {
        vePrint("PreviewWindowProc renderX not inited!");
        return 0;
    }

    switch (message) {
    case WM_LBUTTONDOWN:
        break;
    case WM_LBUTTONUP:
    {
        if (demo->_podIdToLargeWnd.find(pod_id) != demo->_podIdToLargeWnd.end()) {
            HWND win = demo->_podIdToLargeWnd[pod_id];
            SetFocus(win);
            break;
        }
        vecommon::PhoneSessionConfig config = demo->_phoneConfigs[pod_id];
        if (!config.basicConfig.canvas) {
            demo->_sessionRoundId = "session_round_id_" + std::to_string(getCurrentTimeMs());
            demo->_sessionUserId = "session_user_id_" + std::string(demo->_renderX->getDeviceId());
            config.basicConfig.userId = demo->_sessionUserId.c_str();
            config.basicConfig.accountId = demo->_accountId.c_str();
            config.podId = pod_id;
            config.productId = demo->_productId.c_str();
            config.basicConfig.ak = demo->_ak.c_str();
            config.basicConfig.sk = demo->_sk.c_str();
            config.basicConfig.token = demo->_token.c_str();
            config.roundId = demo->_sessionRoundId.c_str();
            config.basicConfig.autoRecycleTime = 7200;
            // 对于打开的前20个大窗，使用高帧率；之后打开的大窗使用低帧率。以此来降低设备功耗。
            if (demo->_sessionToPodId.size() <= HIGH_FPS_LARGE_WND_NUM) {
                config.basicConfig.videoStreamProfileId = HIGH_FPS_LARGE_WND_PROFILE_ID;
            }
            else {
                config.basicConfig.videoStreamProfileId = LOW_FPS_LARGE_WND_PROFILE_ID;
            }
            config.enableLocalKeyboard = true;
            config.muteAudio = false;
            config.basicConfig.canvas = createLargeWindow(demo, pod_id);
            config.basicConfig.externalRender = false;
            config.basicConfig.externalRenderFormat = vecommon::FrameFormat::ARGB;
        }

        HWND win = static_cast<HWND>(config.basicConfig.canvas);
        if (!win) {
            break;
        }
        ShowWindow(win, demo->_cmdShowValue);
        UpdateWindow(win);
        demo->_podIdToLargeWnd[pod_id] = win;

        QkSessionListener* listener = new QkSessionListener(pod_id, config, win);
        vecommon::PhoneSession* session = demo->_renderX->createPhoneSession(config, listener);
        listener->setSession(session);
        session->start();
        demo->_sessionToPodId[session] = pod_id;
        demo->_sessionToListener[session] = listener;

        // bind data to window
        SetWindowLongPtr(win, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(session));
        break;
    }
    case WM_PAINT:
    {
        PAINTSTRUCT ps;
        HDC hdc = BeginPaint(hWnd, &ps);
        HBRUSH bgBrush = CreateSolidBrush(RGB(215, 215, 215));
        RECT rect;
        GetClientRect(hWnd, &rect);
        FillRect(hdc, &rect, bgBrush);
        DeleteObject(bgBrush);
        EndPaint(hWnd, &ps);
        break;
    }

    default:
        return DefWindowProc(hWnd, message, wParam, lParam);
    }
    return 0;
}

QkDemo::QkDemo(int cmd, HWND mainWnd, HINSTANCE instance) :
    _mainWindow(mainWnd), _cmdShowValue(cmd), _instance(instance) {
    LoadStringW(instance, IDS_APP_TITLE, _szTitle, 100);
    LoadStringW(instance, IDC_VEPHONEQKDEMO, _szWindowClass, 100);

    Gdiplus::GdiplusStartup(&_gdiplusToken, &_gdiplusStartupInput, nullptr);

    WINDOWINFO info = { sizeof(WINDOWINFO) };
    GetWindowInfo(mainWnd, &info);
    _mainWindowWidth = info.rcClient.right - info.rcClient.left;
    _mainWindowHeight = info.rcClient.bottom - info.rcClient.top;

    // regsiter play window class
    WNDCLASSEXW wcChild = { 0 };
    wcChild.cbSize = sizeof(WNDCLASSEX);
    wcChild.lpfnWndProc = LargeWindowProc;
    wcChild.hInstance = _instance;
    wcChild.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    wcChild.lpszClassName = largeWindowClass;
    wcChild.hIcon = LoadIcon(_instance, MAKEINTRESOURCE(IDC_VEPHONEQKDEMO));
    wcChild.hCursor = LoadCursor(nullptr, IDC_ARROW);
    wcChild.lpszMenuName = MAKEINTRESOURCEW(IDC_LARGE_WINDOW);
    wcChild.hIconSm = LoadIcon(wcChild.hInstance, MAKEINTRESOURCE(IDI_SMALL));

    RegisterClassExW(&wcChild);

    readConfigIni(); // 从配置文件中读取鉴权信息

    initCloudRenderX(); // 初始化VePhoneSDK
}

/* 
* 火山鉴权信息从文件中读取，文件位置工程根目录，文件内容形如：
* ak:your_ak
* sk:your_sk
* token:your_token
* accountId:your_account_id
* productId:your_product_id
*/
void QkDemo::readConfigIni() {
    std::string path = GetPathAppend(".", "sts.ini");
    std::ifstream ifs(path.c_str(), std::ios::in);
    if (!ifs.is_open()) {
        vePrint("Invalid Config File!");
        return;
    }
    std::map<std::string, std::string> res;
    const int buf_len = 1024;
    char buffer[buf_len] = { 0 };
    while (ifs.getline(buffer, buf_len)) {
        std::vector<std::string> kv;
        splitString(buffer, ":", kv);
        if (kv.size() != 2) {
            continue;
        }
        res[kv[0]] = kv[1];
    }
    ifs.close();

    for (auto it = res.begin(); it != res.end(); ++it) {
        if (std::string("ak") == it->first) {
            _ak = it->second;
        }
        else if (std::string("sk") == it->first) {
            _sk = it->second;
        }
        else if (std::string("token") == it->first) {
            _token = it->second;
        }
        else if (std::string("accountId") == it->first) {
            _accountId = it->second;
        }
        else if (std::string("productId") == it->first) {
            _productId = it->second;
        }
    }
}

int QkDemo::WndProc(HWND hWnd, UINT message, WPARAM wParam, LPARAM lParam) {
    switch (message) {
    case WM_COMMAND:
    {
        ProcessCmd(hWnd, wParam, lParam);
        break;
    }
    case WM_DESTROY:
    {
        releaseCloudRenderX();
        PostQuitMessage(0);
        break;
    }
    default:
        return DefWindowProc(hWnd, message, wParam, lParam);
    }
    return 0;
}

void QkDemo::ProcessCmd(HWND hWnd, WPARAM wParam, LPARAM lParam) {
    std::map<int, void (QkDemo::*)()> tests = {
        {ID_BCV_INIT_CONFIG, &QkDemo::initBcvConfig},
        {ID_BCV_BATCH_POD_START, &QkDemo::reqBatchPodStart},
        {ID_BCV_START, &QkDemo::start},
        {ID_BCV_STOP, &QkDemo::stop},
        {ID_START_EVENT_SYNC, &QkDemo::startEventSync},
        {ID_STOP_EVENT_SYNC, &QkDemo::stopEventSync},
    };
    int wmId = LOWORD(wParam);
    auto test = tests[wmId];
    if (test) {
        (this->*test)();
    }
}

void QkDemo::onBatchPodStartResult(int code, const char* msg, const std::vector<vecommon::PodInfo>* pod_list, const std::vector<vecommon::PodError>* pod_errors) {
    vePrint("QkDemo::onBatchPodStartResult code:{} msg:{}", code, msg);
}

void QkDemo::onStartSuccess(const char* pod_id) {
    vePrint("QkDemo::onStartSuccess podId:{}", pod_id);
}

void QkDemo::onPodJoin(const char* pod_id) {
    vePrint("QkDemo::onPodJoin podId:{}", pod_id);
    bool isAutoSub = _batchControlVideo == nullptr ? false : _batchControlVideo->isAutoSubscribe(pod_id);
    bool isSub = _batchControlVideo == nullptr ? false : _batchControlVideo->isSubscribed(pod_id);
    if (_batchControlVideo) {
        // setup external video sink if use external render.
        if (_bcvConfig.externalRender) {
            auto vc = _batchControlVideo->getVideoConfig(pod_id);
            if (vc) {
                QkExternalSink* sink = new QkExternalSink();
                sink->setCanvas(static_cast<HWND>(vc->canvas));
                _batchControlVideo->setExternalSink(pod_id, sink);
            }
        }
        // subscribe manually if not auto-subscribe.
        if (!isAutoSub) {
            _batchControlVideo->subscribe(pod_id);
        }
    }
}

void QkDemo::onFirstVideoFrameArrived(const char* pod_id, int video_stream_profile) {
    vePrint("QkDemo::onFirstVideoFrameArrived podId:{} profileId:{}", pod_id, video_stream_profile);
}

void QkDemo::onStop(const char* pod_id) {
    vePrint("QkDemo::onStop podId:{}", pod_id);
}

void QkDemo::onError(const char* pod_id, int code, const char* msg) {
    vePrint("QkDemo::onError podId:{} code:{} msg:{}", pod_id, code, msg);
}

void QkDemo::onWarning(const char* pod_id, int code, const char* msg) {
    vePrint("QkDemo::onWarning podId:{} code:{} msg:{}", pod_id, code, msg);
}

void QkDemo::onEventSyncError(int code, const char* msg, const char* userId) {
    vePrint("QkDemo::onEventSyncError code:{} msg:{} userId:{}", code, msg, userId);
}

void QkDemo::onMasterJoinRoomSuccess() {
    vePrint("QkDemo::onMasterJoinRoomSuccess");
}

void QkDemo::onContorlledUserJoined(const char* userId, const char* roomId) {
    vePrint("QkDemo::onContorlledUserJoined userId:{} roomId:{}", userId, roomId);
}

void QkDemo::onContorlledUserLeave(const char* userId, const char* roomId) {
    vePrint("QkDemo::onContorlledUserLeave userId:{} roomId:{}", userId, roomId);
}

void QkDemo::onSupportFeatureResult(vecommon::Feature feature, int code, const char* msg) {
    vePrint("QkDemo::onSupportFeatureResult feature:{} code:{} msg:{}", static_cast<int>(feature), code, msg);
}

void QkDemo::initCloudRenderX() {
    _renderX = vecommon::CreateVeCloudRenderX();
    _renderX->prepare(_accountId);
    _renderX->setDebug(true, ".\\qk_demo_logs");
}

void QkDemo::releaseCloudRenderX() {
    vecommon::DestroyVeCloudRenderX();
}

void QkDemo::initBcvConfig() {
    _podIdList.push_back("7493823438495898379");
    _podIdList.push_back("7493823620365015817");

    _bcvUserId = "bcv_user_id_" + std::string(_renderX->getDeviceId());
    _bcvRoundId = "bcv_round_id_" + std::to_string(getCurrentTimeMs());
    _bcvConfig.accountId = _accountId.c_str();
    _bcvConfig.ak = _ak.c_str();
    _bcvConfig.sk = _sk.c_str();
    _bcvConfig.token = _token.c_str();
    _bcvConfig.userId = _bcvUserId.c_str();
    _bcvConfig.roundId = _bcvRoundId.c_str();
    _bcvConfig.videoStreamProfileId = PREVIEW_WND_PROFILE_ID;
    _bcvConfig.waitTime = 10;
    _bcvConfig.productId = _productId.c_str();
    _bcvConfig.externalRenderFormat = vecommon::FrameFormat::ARGB;
    _bcvConfig.externalRender = true;
    _bcvConfig.autoRecycleTime = 7200;

    _bcvConfig.videoConfigs.clear();
    _preWndList.clear();
    for (auto& id : _podIdList) {
        const char* podId = id.c_str();
        HWND win = createPreviewWindow(podId);
        if (win == nullptr) {
            vePrint("CreatePreviewWindow Failed! Error:{}", GetLastError());
            break;
        }
        _preWndList.push_back(win);
        vecommon::ControlVideoConfig config;
        config.canvas = win;
        config.podId = podId;
        config.autoSubscribe = true;
        _bcvConfig.videoConfigs.push_back(config);
    }
}

void QkDemo::reqBatchPodStart() {
    if (_batchControlVideo) {
        delete _batchControlVideo;
        _batchControlVideo = nullptr;
    }
    if (_renderX) {
        _batchControlVideo = _renderX->createBatchControlVideo(_bcvConfig);
        _batchControlVideo->setBatchControlListener(this);
        _batchControlVideo->requestBatchPodStart();
    }
}

void QkDemo::start() {
    if (_batchControlVideo) {
        _batchControlVideo->start();
    }
}

void QkDemo::stop() {
    if (_batchControlVideo) {
        _batchControlVideo->stop();
    }

    // 停止拉流后，将窗口置灰
    for (int i = 0; i < _preWndList.size(); i++) {
        HWND win = _preWndList[i];
        RECT clientRect;
        GetClientRect(win, &clientRect);
        HDC hdc = GetDC(win);
        HBRUSH bgBrush = CreateSolidBrush(RGB(215, 215, 215));
        FillRect(hdc, &clientRect, bgBrush);
        DeleteObject(bgBrush);
        ReleaseDC(win, hdc);
    }
}

void QkDemo::startEventSync() {
    bool ret = false;
    if (_renderX) {
        std::vector<std::string> podIdList = _podIdList;
        _eventSyncRoundId = "event_sync_round_id_" + std::to_string(getCurrentTimeMs());
        _eventSyncUserId = "event_sync_user_id_" + std::string(_renderX->getDeviceId());
        _eventSyncConfig.ak = _ak.c_str();
        _eventSyncConfig.sk = _sk.c_str();
        _eventSyncConfig.token = _token.c_str();
        _eventSyncConfig.roundId = _eventSyncRoundId.c_str();
        _eventSyncConfig.productId = _productId.c_str();
        _eventSyncConfig.userId = _eventSyncUserId.c_str();
        _eventSyncConfig.controlledPodIdList = podIdList;
        _eventSyncConfig.enableForce = true;
        _eventSyncConfig.softwareVersion = "3010609";
        ret = _renderX->startEventSync(_eventSyncConfig, this);
    }
    vePrint("QkDemo::startEventSync ret:{}", ret);
}

void QkDemo::stopEventSync() {
    bool ret = false;
    if (_renderX) {
        ret = _renderX->stopEventSync();
    }
    vePrint("QkDemo::stopEventSync ret:{}", ret);
}

void QkDemo::checkIfSupportWallpaper() {
    bool ret = false;
    if (_renderX) {
        _supportFeatureConfig.ak = _ak.c_str();
        _supportFeatureConfig.sk = _sk.c_str();
        _supportFeatureConfig.token = _token.c_str();
        _supportFeatureConfig.productId = _productId.c_str();
        _supportFeatureConfig.podIdList = _podIdList;
        _supportFeatureConfig.feature = vecommon::Feature::WALLPAPER;
        ret = _renderX->checkIfSupportFeature(_supportFeatureConfig, this);
    }
    vePrint("QkDemo::checkIfSupportWallpaper ret:{}", ret);
}

HWND QkDemo::createPreviewWindow(const char* pod_id) {
    int startX = CHILD_MARING + (CHILD_WIDTH + CHILD_MARING) * _lineWindowCount;
    bool newLine = startX + CHILD_WIDTH + CHILD_MARING > _mainWindowWidth;
    if (newLine) {
        _lineWindowCount = 0;
        _lineCount++;
        startX = CHILD_MARING;
    }
    _lineWindowCount++;
    int startY = CHILD_MARING + (CHILD_HEIGHT + CHILD_MARING) * _lineCount;

    HWND hwndChild = CreateWindowEx(0, _szWindowClass, _szTitle, WS_CHILD | WS_VISIBLE, startX, startY,
        CHILD_WIDTH, CHILD_HEIGHT, _mainWindow, NULL, _instance, nullptr);
    if (hwndChild == nullptr) {
        vePrint("CreatePreviewWindow Failed! Error:{}", GetLastError());
        return nullptr;
    }
    SetWindowLongPtr(hwndChild, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(&PreviewWindowProc));
    SetWindowLongPtr(hwndChild, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(pod_id));

    return hwndChild;
}

void QkDemo::updateValidArea(HWND mainWnd) {
    WINDOWINFO info = { sizeof(WINDOWINFO) };
    GetWindowInfo(mainWnd, &info);
    int client_width = info.rcClient.right - info.rcClient.left;
    int client_height = info.rcClient.bottom - info.rcClient.top;
    _validArea.left = info.rcClient.left;
    _validArea.right = info.rcClient.right;
    _validArea.top = info.rcClient.top;
    _validArea.bottom = info.rcClient.bottom;
}
