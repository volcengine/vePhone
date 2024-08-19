#include "msg_processor.h"


static const USHORT MOUSE_WHEEL = RI_MOUSE_WHEEL;
static const USHORT MOUSE_BUTTON_LEFT = RI_MOUSE_LEFT_BUTTON_DOWN | RI_MOUSE_LEFT_BUTTON_UP;
static const USHORT MOUSE_BUTTON_RIGHT = RI_MOUSE_RIGHT_BUTTON_DOWN | RI_MOUSE_RIGHT_BUTTON_UP;
static const USHORT MOUSE_BUTTON_MIDDLE = RI_MOUSE_MIDDLE_BUTTON_DOWN | RI_MOUSE_MIDDLE_BUTTON_UP;
static const USHORT MOUSE_BUTTON_DOWN = RI_MOUSE_LEFT_BUTTON_DOWN | RI_MOUSE_RIGHT_BUTTON_DOWN | RI_MOUSE_MIDDLE_BUTTON_DOWN;
static const USHORT MOUSE_BUTTON_UP = RI_MOUSE_LEFT_BUTTON_UP | RI_MOUSE_RIGHT_BUTTON_UP | RI_MOUSE_MIDDLE_BUTTON_UP;

std::shared_ptr<BYTE> lpbBuffer = nullptr;
UINT dwSize = 0;
WCHAR gDialogContent[1000];
bool gIsMouseMoving = false;
bool gIsDownEventSent = false;


INT_PTR CALLBACK getDialogContent(HWND dialog, UINT message, WPARAM wparam, LPARAM lparam) {
    UNREFERENCED_PARAMETER(lparam);
    std::shared_ptr<QkDemo> demo = getDemo();
    switch (message) {
    case WM_INITDIALOG:
        demo->_isMenuShow = true;
        return (INT_PTR)TRUE;
    case WM_COMMAND:
        if (LOWORD(wparam) == IDOK || LOWORD(wparam) == IDCANCEL) {
            GetDlgItemText(dialog, IDC_EDIT_GETVALUE, gDialogContent, sizeof(gDialogContent));
            EndDialog(dialog, LOWORD(wparam));
            demo->_isMenuShow = false;
            return (INT_PTR)TRUE;
        }
        break;
    }
    return (INT_PTR)FALSE;
}

void ProcessWmInput(PhoneSession* session, RECT& validArea, HWND hWnd, UINT message, WPARAM wParam, LPARAM lparam) {
    if (!session) {
        return;
    }
    UINT dw_size = 0;
    GetRawInputData((HRAWINPUT)lparam, RID_INPUT, NULL, &dw_size, (UINT)sizeof(RAWINPUTHEADER));
    if (dw_size == 0) {
        return;
    }
    if (dw_size > dwSize) {
        lpbBuffer.reset(new BYTE[dw_size]);
        dwSize = dw_size;
    }
    GetRawInputData((HRAWINPUT)lparam, RID_INPUT, (LPVOID)lpbBuffer.get(), (PUINT)&dwSize, (UINT)sizeof(RAWINPUTHEADER));   // 第二次调用获取原始输入数据，读入lpbBuffer

    RAWINPUT* raw = (RAWINPUT*)lpbBuffer.get();
    if (raw->header.dwType == RIM_TYPEMOUSE) {
        USHORT mouse_button = raw->data.mouse.usButtonFlags;
        POINT point;
        GetCursorPos(&point);
        RECT mouse_rect = validArea;
        mouse_rect.right += 1;
        mouse_rect.bottom += 1;
        int picture_width = validArea.right - validArea.left;
        int picture_height = validArea.bottom - validArea.top;
        if (!PtInRect(&mouse_rect, point)) {
            // 当光标移动到画面外时，需要发送Up事件
            if (gIsMouseMoving) {
                vecommon::MouseKeyData key;
                key.key = VK_LBUTTON;
                key.down = false;
                key.abs_x = (point.x - validArea.left) * 65535 / picture_width;
                key.abs_y = (point.y - validArea.top) * 65535 / picture_height;
                session->sendMouseKey(key);
                //vePrint("ProcessWmInput action:{} pos:[{}, {}] sid:{} win:{}", "CANCEL", point.x, point.y, session->getSessionId(), fmt::ptr(hWnd));

                gIsMouseMoving = false;
                gIsDownEventSent = false;
            }
            return;
        }

        // mouse move 只有发送了Down事件才可以发送Move事件
        if (gIsDownEventSent && (raw->data.mouse.lLastX != 0 || raw->data.mouse.lLastY != 0)) {
            gIsMouseMoving = true;

            vecommon::MouseMoveData move;
            move.abs_x = (point.x - validArea.left) * 65535 / picture_width;
            move.abs_y = (point.y - validArea.top) * 65535 / picture_height;
            move.delta_x = raw->data.mouse.lLastX;
            move.delta_y = raw->data.mouse.lLastY;
            session->sendMouseMove(move);
            //vePrint("ProcessWmInput action:{} pos:[{}, {}] sid:{} win:{}", "MOVE", point.x, point.y, session->getSessionId(), fmt::ptr(hWnd));
        }

        // mouse key
        uint8_t button = 0;
        if (mouse_button & MOUSE_BUTTON_LEFT) {
            button = VK_LBUTTON;
        }
        else if (mouse_button & MOUSE_BUTTON_RIGHT) {
            button = VK_RBUTTON;
        }
        else if (mouse_button & MOUSE_BUTTON_MIDDLE) {
            button = VK_MBUTTON;
        }
        if (button != 0) {
            gIsMouseMoving = false;

            bool is_down = false;
            if (mouse_button & MOUSE_BUTTON_DOWN) {
                is_down = true;
            }

            vecommon::MouseKeyData key;
            key.key = button;
            key.down = is_down;
            key.abs_x = (point.x - validArea.left) * 65535 / picture_width;
            key.abs_y = (point.y - validArea.top) * 65535 / picture_height;
            session->sendMouseKey(key);
            gIsDownEventSent = is_down;
            //vePrint("ProcessWmInput action:{} pos:[{}, {}] sid:{} win:{}", is_down ? "DOWN" : "UP", point.x, point.y, session->getSessionId(), fmt::ptr(hWnd));
        }

        // mouse wheel
        if (mouse_button & MOUSE_WHEEL) {
            short wheel_v = (short)LOWORD(raw->data.mouse.usButtonData);
            vecommon::MouseWheelDataArm wheelData;
            wheelData.x = (point.x - validArea.left) * 65535 / picture_width;
            wheelData.y = (point.y - validArea.top) * 65535 / picture_height;
            wheelData.action = 8;
            wheelData.axis_v = wheel_v < 0 ? -1.0 : 1.0;
            session->sendMouseWheel(wheelData);
        }
    }
}

void ProcessWmChar(PhoneSession* session, HWND hWnd, UINT message, WPARAM wParam, LPARAM lParam) {
    if (!session) {
        return;
    }

    // 过滤有效按键: wparam为字符的ASCII码，这里需要过滤0-31
    if ((wParam >= 0 && wParam <= 31)) {
        return;
    }
    const std::string& str = unicodeToUtf8(std::wstring(1, (WCHAR)wParam));
    vecommon::ImeCompositionData data{};
    data.str = str.c_str();
    session->sendImeComposition(data);
}

void ProcessWmKeyAction(PhoneSession* session, HWND hWnd, UINT message, WPARAM wParam, LPARAM lparam) {
    if (!session) {
        return;
    }
    if (wParam == VK_PROCESSKEY || wParam == VK_PACKET) {
        return;
    }
    bool down = message == WM_KEYDOWN || message == WM_SYSKEYDOWN;

    // 处理Ctrl+V
    if (down && wParam == 'V' && ::GetKeyState(VK_CONTROL) < 0) {
        const std::string& str = getClipboardContent();
        vecommon::ImeCompositionData data{};
        data.str = str.c_str();
        session->sendImeComposition(data);
        return;
    }
    int keyCode = -1;
    switch (wParam) {
    case VK_ESCAPE:
    {
        // TO  Android KEYCODE_ESCAPE = 111
        keyCode = 111;
        break;
    }
    case VK_DELETE:
    {
        // TO  Android KEYCODE_FORWARD_DEL = 112
        keyCode = 112;
        break;
    }
    case VK_BACK:
    {
        // TO  Android KEYCODE_DEL = 67
        keyCode = 67;
        break;
    }
    case VK_RETURN:
    {
        // TO  Android KEYCODE_ENTER = 66
        keyCode = 66;
        break;
    }
    case VK_TAB:
    {
        // TO  Android KEYCODE_TAB = 61
        keyCode = 61;
        break;
    }
    case VK_UP:
    {
        // TO  Android KEYCODE_DPAD_UP = 19
        keyCode = 19;
        break;
    }
    case VK_DOWN:
    {
        // TO  Android KEYCODE_DPAD_DOWN = 20
        keyCode = 20;
        break;
    }
    case VK_LEFT:
    {
        // TO  Android KEYCODE_DPAD_LEFT = 21
        keyCode = 21;
        break;
    }
    case VK_RIGHT:
    {
        // TO  Android KEYCODE_DPAD_RIGHT = 22
        keyCode = 22;
        break;
    }
    default:
        break;
    }

    if (keyCode != -1) {
        session->sendKeyCode(keyCode, down);
    }
}

void ProcessWmCmd(PhoneSession* session, std::string& podId, QkSessionListener* listener, HINSTANCE instance, HWND hWnd, WPARAM wParam, LPARAM lParam) {
    if (!session) {
        return;
    }
    int wmId = LOWORD(wParam);
    // 分析菜单选择:
    switch (wmId) {
        // 操控
    case ID_SWITCH_PROFILE_ID:
    {
        if (IDCANCEL == DialogBox(instance, MAKEINTRESOURCE(IDD_DIALOG_GETVALUE), hWnd, getDialogContent)) {
            break;
        }
        try {
            session->switchVideoStreamProfile(std::stoi(gDialogContent));
        }
        catch (...) {}
        break;
    }
    case ID_SET_AUTO_RECYCLE_TIME:
    {
        if (IDCANCEL == DialogBox(instance, MAKEINTRESOURCE(IDD_DIALOG_GETVALUE), hWnd, getDialogContent)) {
            break;
        }
        try {
            session->setAutoRecycleTime(std::stoi(gDialogContent));
        }
        catch (...) {}
        break;
    }
    case ID_ENABLE_LOCAL_BROAD:
    {
        if (IDCANCEL == DialogBox(instance, MAKEINTRESOURCE(IDD_DIALOG_GETVALUE), hWnd, getDialogContent)) {
            break;
        }
        try {
            session->setLocalKeyboardEnable(std::stoi(gDialogContent));
        }
        catch (...) {}
        break;
    }
    case ID_ENABLE_MOUSE_WHEEL:
    {
        if (IDCANCEL == DialogBox(instance, MAKEINTRESOURCE(IDD_DIALOG_GETVALUE), hWnd, getDialogContent)) {
            break;
        }
        try {
            session->setMouseWheelEnable(std::stoi(gDialogContent));
        }
        catch (...) {}
        break;
    }
    case ID_MUTE_VIDEO:
    {
        if (IDCANCEL == DialogBox(instance, MAKEINTRESOURCE(IDD_DIALOG_GETVALUE), hWnd, getDialogContent)) {
            break;
        }
        try {
            session->setVideoMute(std::stoi(gDialogContent));
        }
        catch (...) {}
        break;
    }
    case ID_MUTE_AUDIO:
    {
        if (IDCANCEL == DialogBox(instance, MAKEINTRESOURCE(IDD_DIALOG_GETVALUE), hWnd, getDialogContent)) {
            break;
        }
        try {
            session->setAudioMute(std::stoi(gDialogContent));
        }
        catch (...) {}
        break;
    }
    case ID_SEND_SHAKE_EVENT:
    {
        if (IDCANCEL == DialogBox(instance, MAKEINTRESOURCE(IDD_DIALOG_GETVALUE), hWnd, getDialogContent)) {
            break;
        }
        try {
            session->sendShakeEventToRemote(std::stoi(gDialogContent));
        }
        catch (...) {}
        break;
    }
    case ID_START_AUDIO_INJECTION:
    {
        if (IDCANCEL == DialogBox(instance, MAKEINTRESOURCE(IDD_DIALOG_GETVALUE), hWnd, getDialogContent)) {
            break;
        }
        try {
            char filePath[100];
            sprintf_s(filePath, "%ws", gDialogContent);
            session->sendAudioInjectionEventToRemote(vecommon::AudioInjectionCmd::START, filePath);
        }
        catch (...) {}
        break;
    }
    case ID_STOP_AUDIO_INJECTION:
    {
        session->sendAudioInjectionEventToRemote(vecommon::AudioInjectionCmd::STOP, nullptr);
        break;
    }
    case ID_SET_NAV_BAR_STATUS:
    {
        if (IDCANCEL == DialogBox(instance, MAKEINTRESOURCE(IDD_DIALOG_GETVALUE), hWnd, getDialogContent)) {
            break;
        }
        try {
            session->setNavBarStatus(std::stoi(gDialogContent));
        }
        catch (...) {}
        break;
    }
    case ID_GET_NAV_BAR_STATUS:
    {
        session->getNavBarStatus();
        break;
    }
    case ID_ROTATE_SCREEN_ONLY_LOCAL:
    {
        if (IDCANCEL == DialogBox(instance, MAKEINTRESOURCE(IDD_DIALOG_GETVALUE), hWnd, getDialogContent)) {
            break;
        }
        try {
            if (listener) {
                listener->rotateScreen(static_cast<vecommon::RotateDegree>(std::stoi(gDialogContent)), false);
            }
        }
        catch (...) {}
        break;
    }
    case ID_ROTATE_SCREEN_WITH_POD:
    {
        if (IDCANCEL == DialogBox(instance, MAKEINTRESOURCE(IDD_DIALOG_GETVALUE), hWnd, getDialogContent)) {
            break;
        }
        try {
            if (listener) {
                listener->rotateScreen(static_cast<vecommon::RotateDegree>(std::stoi(gDialogContent)), true);
            }
        }
        catch (...) {}
        break;
    }
    case ID_SCREEN_SHOT:
    {
        session->screenShot(true);
        break;
    }

    // 群控
    case ID_SET_MASTER:
    {
        std::shared_ptr<QkDemo> demo = getDemo();
        demo->_renderX->setMasterSession(session);
        break;
    }
    case ID_RESET_MASTER:
    {
        std::shared_ptr<QkDemo> demo = getDemo();
        demo->_renderX->setMasterSession(nullptr);
        break;
    }

    // KEYCODE
    case ID_SEND_KEY_HOME:
    {
        session->sendKeyCode(3);
        break;
    }
    case ID_SEND_KEY_BACK:
    {
        session->sendKeyCode(4);
        break;
    }
    case ID_SEND_KEY_RECENT:
    {
        session->sendKeyCode(187);
        break;
    }
    case ID_SEND_KEY_VOLUME_UP:
    {
        session->volumeUp();
        break;
    }
    case ID_SEND_KEY_VOLUME_DOWN:
    {
        session->volumeDown();
        break;
    }

    // 其他
    case IDM_EXIT:
        DestroyWindow(hWnd);
        break;
    default:
        break;
    }
}