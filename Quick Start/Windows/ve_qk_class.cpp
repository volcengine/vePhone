#include "ve_qk_class.h"
#include <gdiplus.h>
#pragma comment(lib, "gdiplus.lib")


void QkExternalSink::onFrame(VeExtVideoFrame* frame) {
    if (!frame) {
        return;
    }
    int width = frame->width();
    int height = frame->height();
    //vePrint("QkExternalSink::onFrame width:{} height:{}", width, height);
    int lineStride = frame->getPlaneStride(0);
    uint8_t* originData = frame->getPlaneData(0);
    Gdiplus::Bitmap bitmap(width, height, lineStride, PixelFormat32bppARGB, originData);
    HDC hdc = GetDC(_window);
    Gdiplus::Graphics graphics(hdc);
    WINDOWINFO winInfo = { 0 };
    winInfo.cbSize = sizeof(winInfo);
    GetWindowInfo(reinterpret_cast<HWND>(_window), &winInfo);
    int drawWidth = winInfo.rcClient.right - winInfo.rcClient.left;
    int drawHeight = winInfo.rcClient.bottom - winInfo.rcClient.top;
    graphics.DrawImage(&bitmap, 0, 0, drawWidth, drawHeight);
    ReleaseDC(_window, hdc);
}

void QkExternalSink::setCanvas(HWND win) {
    _window = win;
}

void QkSessionListener::onStartSuccess(int video_stream_profile, const char* round_id, const char* target_id, const char* reserved_id, const char* plan_id) {
    vePrint("QkSessionListener::onStartSuccess podId:{} profileId:{}", _podId, video_stream_profile);
}

void QkSessionListener::onStop() {
    vePrint("QkSessionListener::onStop podId:{}", _podId);
}

void QkSessionListener::onFirstVideoFrame(const vecommon::VideoFrameInfo& info) {
    vePrint("QkSessionListener::onFirstVideoFrame podId:{} width:{} height:{} rotation:{}", _podId, info.width, info.height, static_cast<int>(info.rotation));
}

void QkSessionListener::onVideoStreamProfileChange(bool result, int from, int to) {
    vePrint("QkSessionListener::onVideoStreamProfileChange podId:{} result:{} from:{} to:{}", _podId, result, from, to);
}

void QkSessionListener::onError(int code, const char* msg) {
    vePrint("QkSessionListener::onError podId:{} code:{} msg:{}", _podId, code, msg);
}

void QkSessionListener::onPodExited(int reason, const char* msg) {
    vePrint("QkSessionListener::onPodExited podId:{} reason:{} msg:{}", _podId, reason, msg);
}

void QkSessionListener::onPodJoined(const char* podUserId) {
    vePrint("QkSessionListener::onPodJoined podId:{}", _podId);
}

void QkSessionListener::onRemoteRotation(int rotation) {
    vePrint("QkSessionListener::onRemoteRotation podId:{} rotation:{}", _podId, rotation);

    // 如果rotation_mode为portrait，不处理旋转事件
    if (&_config && _config.rotationMode == vecommon::RotationMode::PORTRAIT) {
        return;
    }

    if (_rotationLocalDegree != vecommon::RotateDegree::DEGREE_0) {
        // 回退渲染旋转角度
        rotateScreen(vecommon::RotateDegree::DEGREE_0, false);
    }

    if (rotation == 0 || rotation == 180) {
        resizeWindow(false);
        _isLocalLandscape = false;
        _isRemoteLandscape = false;
    }
    else {
        resizeWindow(true);
        _isLocalLandscape = true;
        _isRemoteLandscape = true;
    }
}

void QkSessionListener::onLocalScreenRotate(vecommon::RotateDegree degree) {
    vePrint("QkSessionListener::onLocalScreenRotate podId:{} degree:{}", _podId, static_cast<int>(degree));
}

void QkSessionListener::onAutoRecycleTimeCallBack(int seconds) {
    vePrint("QkSessionListener::onAutoRecycleTimeCallBack podId:{} seconds:{}", _podId, seconds);
}

void QkSessionListener::onShakeResponse(int result, const char* msg) {
    vePrint("QkSessionListener::onShakeResponse podId:{} result:{} msg:{}", _podId, result, msg);
}

void QkSessionListener::onAudioInjectionResponse(int result, const char* msg) {
    vePrint("QkSessionListener::onAudioInjectionResponse podId:{} result:{} msg:{}", _podId, result, msg);
}

void QkSessionListener::onScreenShot(int result, const char* savePath, const char* downloadUrl) {
    vePrint("QkSessionListener::onScreenShot podId:{} result:{} savePath:{} downloadUrl:{}", _podId, result, savePath, downloadUrl);
}

void QkSessionListener::onNavBarStatus(int status, int reason) {
    vePrint("QkSessionListener::onNavBarStatus podId:{} status:{} reason:{}", _podId, status, reason);
}

void QkSessionListener::setSession(PhoneSession* session) {
    _session = session;
}

void QkSessionListener::rotateScreen(vecommon::RotateDegree degree, bool withPod) {
    if (!_session) {
        vePrint("QkSessionListener::rotateScreen _session==nullptr");
        return;
    }
    _session->rotateScreen(degree, withPod);

    if (&_config && _config.rotationMode == vecommon::RotationMode::PORTRAIT) {
        if (degree == vecommon::RotateDegree::DEGREE_270
            || degree == vecommon::RotateDegree::DEGREE_90) {
            resizeWindow(true);
        }
        else {
            resizeWindow(false);
        }
    }
    else {
        if (degree == vecommon::RotateDegree::DEGREE_270
            || degree == vecommon::RotateDegree::DEGREE_90) { // 本地旋转画布
            if (_isLocalLandscape && _isRemoteLandscape) { // 本地横屏，远端横屏
                resizeWindow(_isLocalLandscape = false);
            }
            else if (!_isLocalLandscape && _isRemoteLandscape) { // 本地竖屏，远端横屏
                resizeWindow(_isLocalLandscape = false);
            }
            else if (_isLocalLandscape && !_isRemoteLandscape) { // 本地横屏，远端竖屏
                resizeWindow(_isLocalLandscape = true);
            }
            else if (!_isLocalLandscape && !_isRemoteLandscape) { // 本地竖屏，远端竖屏
                resizeWindow(_isLocalLandscape = true);
            }
        }
        else {
            if (_isLocalLandscape && _isRemoteLandscape) { // 本地横屏，远端横屏
                resizeWindow(_isLocalLandscape = true);
            }
            else if (!_isLocalLandscape && _isRemoteLandscape) { // 本地竖屏，远端横屏
                resizeWindow(_isLocalLandscape = true);
            }
            else if (_isLocalLandscape && !_isRemoteLandscape) { // 本地横屏，远端竖屏
                resizeWindow(_isLocalLandscape = false);
            }
            else if (!_isLocalLandscape && !_isRemoteLandscape) { // 本地竖屏，远端竖屏
                resizeWindow(_isLocalLandscape = false);
            }
        }
    }
}

void QkSessionListener::resizeWindow(bool shouldLocalLandscape) {
    // 1. 计算旋转后的窗口宽高
    int resizedWidth, resizedHeight;
    if (shouldLocalLandscape) {
        resizedWidth = PLAY_WIND_HEIGHT;
        resizedHeight = PLAY_WIND_WIDTH;
    }
    else {
        resizedWidth = PLAY_WIND_WIDTH;
        resizedHeight = PLAY_WIND_HEIGHT;
    }

    // 2. 加上菜单栏后，调整窗口宽高
    RECT adjustedWindow{ 0, 0, resizedWidth, resizedHeight };
    AdjustWindowRect(&adjustedWindow, WS_OVERLAPPEDWINDOW, true);

    // 3. 加上菜单栏后，计算旋转后的窗口宽高
    int width = adjustedWindow.right - adjustedWindow.left;
    int height = adjustedWindow.bottom - adjustedWindow.top;
    int newWidth, newHeight;
    if (shouldLocalLandscape) {
        newWidth = max(width, height);
        newHeight = min(width, height);
    }
    else {
        newWidth = min(width, height);
        newHeight = max(width, height);
    }

    // 4. 更新原始窗口的宽高
    RECT rcWindow;
    GetWindowRect(_hwnd, &rcWindow);
    SetWindowPos(_hwnd, HWND_TOP, rcWindow.left, rcWindow.top, newWidth, newHeight, SWP_SHOWWINDOW);
}