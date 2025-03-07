#pragma once

#include "ve_type_defines.h"

class ISessionListener {
public:
    virtual ~ISessionListener() = default;

    /**
     * @type callback
     * @brief 启动成功
     * @param [in] video_stream_profile, 清晰度档位  <br>
     * @param [in] round_id   <br>
     * @param [in] target_id  云手机pod_id或云游戏game_id <br>
     * @param [in] reserved_id   <br>
     * @param [in] plan_id，套餐id    <br>
     *
     */
    virtual void onStartSuccess(int video_stream_profile, const char* round_id, const char* target_id, const char* reserved_id, const char* plan_id) {
        (void)video_stream_profile;
        (void)round_id;
        (void)target_id;
        (void)reserved_id;
        (void)plan_id;
    }

    /**
     * @type callback
     * @brief 云游戏/云手机停止回调
     */
    virtual void onStop() {
    }

    /**
     * @type callback
     * @brief 云机非正常退出，
     */
    virtual void onPodExited(int reason, const char* msg) {
        (void)reason;
        (void)msg;
    }

    /**
     * @type callback
     * @brief 收到音频首帧回调
     */
    virtual void onFirstAudioFrame() {
    }

    /**
     * @type callback
     * @brief 收到视频首帧回调
     * @param [in] info， 参考{@link#VideoFrameInfo}
     */
    virtual void onFirstVideoFrame(const vecommon::VideoFrameInfo& info) {
        (void)info;
    };

    /**
     * @type callback
     * @brief 拉流连接状态改变回调
     * @param [in] state， 参考{@link#StreamConnectionState}
     */
    virtual void onStreamConnectionStateChanged(vecommon::StreamConnectionState state) {
        (void)state;
    }

    /**
     * @type callback
     * @brief 收到云端实例请求开始发送音频数据事件
     */
    virtual void onRemoteAudioStartRequest() {
    }

    /**
     * @type callback
     * @brief 收到云端实例请求停止发送音频数据事件
     */
    virtual void onRemoteAudioStopRequest() {
    }

    /**
     * @type callback
     * @brief 收到云端实例请求开始发送摄像头数据事件
     */
    virtual void onRemoteVideoStartRequest() {
    }

    /**
     * @type callback
     * @brief 收到云端实例请求停止发送摄像头数据事件
     */
    virtual void onRemoteVideoStopRequest() {
    }

    /**
     * @type callback
     * @brief 音频流统计信息回调，2 秒回调一次
     */
    virtual void onAudioStats(const vecommon::AudioStats& stats) {
        (void)stats;
    }

    /**
     * @type callback
     * @brief 音视频流统计信息回调，2 秒回调一次
     */
    virtual void onVideoStats(const vecommon::VideoStats& stats) {
        (void)stats;
    }

    /**
     * @type callback
     * @brief 视频帧大小改变回调
     */
    virtual void onVideoSizeChanged(const vecommon::VideoFrameInfo& info) {
        (void)info;
    }

    /**
     * @type callback
     * @brief 清晰度切换结果回调
     */
    virtual void onVideoStreamProfileChange(bool result, int from, int to) {
        (void)result;
        (void)from;
        (void)to;
    }

    /**
     * @type callback
     * @brief 截图结果回调
     * @param [in] result   <br>
     *            +  0：截图成功    <br>
     *            + -1：存储空间不足，截图失败     <br>
     *            + -2：未知原因，截图失败       <br>
     *            + -3：截图失败，可能原因为当前页面受安全保护不允许截图，可修改 AOSP 的 persist.sys.allow_capture_secure 属性值为 true 后重试    <br>
     * @param [in] savePath 云手机实例中保存截图文件的路径 
     * @param [in] downloadUrl 截图成功时返回截图文件的下载链接，链接有效期1小时
     */
    virtual void onScreenShot(int result, const char* savePath, const char* downloadUrl) {
        (void)result;
        (void)savePath;
        (void)downloadUrl;
    }

    /**
     * @type callback
     * @brief 网络状态回调，2 秒回调一次
     */
    virtual void onNetworkQuality(vecommon::NetworkQualityState state) {
        (void)state;
    }

    /**
     * @hide phone
     * @type callback
     * @brief 操作时延回调，5 秒回调一次
     */
    virtual void onDelayDetected(int milliseconds) {
        (void)milliseconds;
    }

    /**
     * @hide phone
     * @type callback
     * @brief 远端消息通道状态改变回调
     */
    virtual void onMessageChannelStateChanged(const char* channel_id, vecommon::MessageChannelState state) {
        (void)channel_id;
        (void)state;
    }

    /**
     * @hide phone
     * @type callback
     * @brief 发送消息给游戏的发送结果回调
     */
    virtual void onSendMessageResult(bool success, const char* mid) {
        (void)success;
        (void)mid;
    }
 
    /**
     * @hide phone
     * @type callback
     * @brief 收到游戏内字符串消息回调
     */
    virtual void onStringMessageReceived(const char* str) {
        (void)str;
    }
 
    /**
     * @hide phone
     * @type callback
     * @brief 收到游戏内二进制数据消息回调
     */
    virtual void onBinaryMessageReceived(const uint8_t* data, int len) {
        (void)data;
        (void)len;  
    }

    /**
     * @type callback
     * @brief SDK内部产生的错误回调
     * @param [in] code，参考开发者文档
     */
    virtual void onError(int code, const char* msg) {
        (void)code;
        (void)msg;
    }
    
    /**
     * @type callback
     * @brief SDK内部产生的警告回调
     * @param [in] code，参考开发者文档
     */
    virtual void onWarning(int code) {
        (void)code;
    }

    /**
     * @type callback
     * @brief 是否启用本地键盘回调
     */
    virtual void onKeyboardEnable(bool enable) {
        (void)enable;
    }

    /**
     * @type callback
     * @brief 云端收到本地用户状态后的回调
     */
    virtual void onBackgroundSwitched(bool state) {
        (void)state;
    }

    /**
     * @type callback
     * @brief  应用切换到后台回调
     */
    virtual void onRemoteSwitchedBackground(vecommon::RemoteGameSwitchType type) {
        (void)type;
    }

    /**
     * @type callback
     * @brief  应用切换到前台回调
     */
    virtual void onRemoteSwitchedForeground(vecommon::RemoteGameSwitchType type) {
        (void)type;
    }

    /**
     * @hide phone
     * @type callback
     * @brief  输出游戏中鼠标位置
     */
    virtual void onOutputCursorPos(const vecommon::MouseCursorPos& data) {
        (void)data;
    }

    /**
     * @hide phone
     * @type callback
     * @brief  输出游戏中鼠标是否显示，客户端需要同步修改鼠标隐藏状态
     */
    virtual void onOutputCursorVisibility(bool visible) {
        (void)visible;
    }

    /**
     * @hide phone
     * @type callback
     * @brief 输出游戏中手柄震动事件
     */
    virtual void onOutputGamepadVibration(const vecommon::GamepadVibrationData& data) {
        (void)data;
    }

    /**
     * @hide phone
     * @type callback
     * @brief 输出游戏中输入法状态
     */
    virtual void onOutputImeState(const vecommon::ImeStateData& data) {
        (void)data;
    }

    /**
     * @type callback
     * @brief 请求auto recycle time成功回调
     */
    virtual void onAutoRecycleTimeCallBack(int seconds) {
        (void)seconds;
    }

    /**
     * @type callback
     * @brief 云手机状态栏状态改变回调
     * @param [in] status, 0:隐藏导航栏，1:打开导航栏，-1: 参数错误
     * @param [in] reason,
     *              +   0: pod端切换   <br>
     *              +   1: 客户端通过getNavBarStatus()获取状态回调     <br>
     *              +   2: 客户端通过setNavBarStatus(bool status)接口调用    <br>
     *              +  -1: 参数错误    <br>
     *
     */
    virtual void onNavBarStatus(int status, int reason) {
        (void)status;
        (void)reason;
    }

    /**
     * @type callback
     * @brief 云端pod屏幕旋转
     * @param [in] rotation, 竖屏: 0或180，横屏: 90或270
     * @note 调用{@link vephone_engine#rotateScreen(vecommon::RotateDegree degree)}成功后会回调，     <br>
     *          +   此时拉流渲染方向已经改变，可以通过此回调对容器布局、大小、方向等进行改变     <br>
     *
     */
    virtual void onRemoteRotation(int rotation) {
        (void)rotation;
    }

    /**
     * @type callback
     * @brief 本地容器旋转完成
     * @param [in] degree, 旋转角度
     * @note 调用{@link vephone_engine#rotateScreen(vecommon::RotateDegree degree)}成功后会回调，     <br>
     *          +   此时拉流渲染方向已经改变，可以通过此回调对容器布局、大小、方向等进行改变     <br>
     *
     */
    virtual void onLocalScreenRotate(vecommon::RotateDegree degree) {
        (void)degree;
    }

    /**
     * @type callback
     * @brief 云端输入框更新
     * @param [in] show, true输入框显示，false输入框隐藏
     * @param [in] text, 当前输入框内容
     * @param [in] start / stop, 起止位置
     */
    virtual void onEditExchanged(bool show, const char* text, int start, int stop) {
        (void)show;
        (void)text;
        (void)start;
        (void)stop;
    }

    /**
     * @type callback
     * @brief 云端剪切板返回
     * @param [in] message, 剪切板内容
     */
    virtual void onClipBoardMessageReceived(const char* message) {
        (void)message;
    }

    /**
     * @type callback
     * @brief 远端实例加房成功，可以在该回调中订阅/取消订阅 视频流/音频流
     * @param [in] podUserId, 远端实例的用户ID
     */
    virtual void onPodJoined(const char* podUserId) {
        (void)podUserId;
    }

    /**
     * @type callback
     * @brief 摇一摇结果返回
     * @param [in] result 摇一摇结果，0：异常，1：完成，2：进行中
     *        [in] msg 摇一摇结果的详细信息
     */
    virtual void onShakeResponse(int result, const char* msg) {
        (void)result;
        (void)msg;
    }

    /**
    * @type callback
    * @brief 音频注入结果返回
    * @param [in] result 音频注入结果，1：成功，0或者-1：失败
    *        [in] msg 音频注入结果的详细信息
    */
    virtual void onAudioInjectionResponse(int result, const char* msg) {
        (void)result;
        (void)msg;
    }

    /*
    * @type callback
    * @brief 音频注入状态改变的回调
    * @param [in] callUserId 改变音频注入状态的用户ID
    *        [in] state 音频注入状态 true：开启 false：关闭
    *        [in] code 错误码 0：成功 <0：失败
    *        [in] msg 错误信息
    */
    virtual void onAudioInjectionStateChanged(const char* callUserId, bool state, int code, const char* msg) {
        (void)callUserId;
        (void)state;
        (void)code;
        (void)msg;
    }

    /*
    * @type callback
    * @brief 查询音频注入状态的结果回调
    * @param [in] state 音频注入状态 true：开启 false：关闭
    *        [in] code 错误码 0：成功 <0：失败
    *        [in] msg 错误信息
    */
    virtual void onGetAudioInjectionState(bool state, int code, const char* msg) {
        (void)state;
        (void)code;
        (void)msg;
    }

    /*
    * @type callback
    * @brief 视频注入状态改变的回调
    * @param [in] callUserId 改变视频注入状态的用户ID
    *        [in] state 视频注入状态 true：开启 false：关闭
    *        [in] code 错误码 0：成功 <0：失败
    *        [in] msg 错误信息
    */
    virtual void onVideoInjectionStateChanged(const char* callUserId, bool state, int code, const char* msg) {
        (void)callUserId;
        (void)state;
        (void)code;
        (void)msg;
    }

    /*
    * @type callback
    * @brief 查询视频注入状态的结果回调
    * @param [in] state 视频注入状态 true：开启 false：关闭
    *        [in] code 错误码 0：成功 <0：失败
    *        [in] msg 错误信息
    */
    virtual void onGetVideoInjectionState(bool state, int code, const char* msg) {
        (void)state;
        (void)code;
        (void)msg;
    }

    /*
    * @type callback
    * @brief 键盘类型改变的回调
    * @param [in] code 错误码 0：成功 <0：失败 1000：不允许设置
    *        [in] type 键盘类型，详见vecommon::KeyboardType
    */
    virtual void onKeyboardTypeChanged(int code, vecommon::KeyboardType type) {
        (void)code;
        (void)type;
    }

    /*
    * @type callback
    * @brief 查询键盘类型的结果回调
    * @param [in] code 错误码 0：成功 <0：失败
    *        [in] type 键盘类型，详见vecommon::KeyboardType
    */
    virtual void onGetKeyboardTypeResult(int code, vecommon::KeyboardType type) {
        (void)code;
        (void)type;
    }

    /*
    * @type callback
    * @brief 用户加房回调
    * @param [in] userId 用户ID
    */
    virtual void onUserJoin(const std::string& userId) {
        (void)userId;
    }

    /*
    * @type callback
    * @brief 用户离房回调
    * @param [in] userId 用户ID
    */
    virtual void onUserLeave(const std::string& userId) {
        (void)userId;
    }

    /**
    * @type callback
    * @brief 操控权改变的回调
    * @param [in] state 操控权状态
    */
    virtual void onControlStateChanged(const vecommon::ControlState& state) {
        (void)state;
    }

    /**
    * @type callback
    * @brief 调用{@link PhoneSession#enableControl}的结果回调
    * @param [in] code  错误码 0：成功 <0：失败
    * @param [in] state 操控权状态
    * @param [in] msg   错误信息
    */
    virtual void onEnableControlResult(int code, const vecommon::ControlState& state, const std::string& msg) {
        (void)code;
        (void)state;
        (void)msg;
    }

    /**
    * @type callback
    * @brief 调用{@link PhoneSession#hasControl}的结果回调
    * @param [in] code  错误码 0：成功 <0：失败
    * @param [in] state 操控权状态
    * @param [in] msg   错误信息
    */
    virtual void onHasControlResult(int code, const vecommon::ControlState& state, const std::string& msg) {
        (void)code;
        (void)state;
        (void)msg;
    }

    /**
    * @type callback
    * @brief 调用{@link PhoneSession#getAllControls}的结果回调
    * @param [in] code   错误码 0：成功 <0：失败
    * @param [in] states 操控权状态列表
    * @param [in] msg    错误信息
    */
    virtual void onAllControlsResult(int code, const std::vector<vecommon::ControlState>& states, const std::string& msg) {
        (void)code;
        (void)states;
        (void)msg;
    }
};
