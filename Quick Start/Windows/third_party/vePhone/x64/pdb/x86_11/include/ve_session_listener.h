#pragma once
#include "ve_type_defines.h"


namespace vecommon {

/**
 * @locale zh
 * @type callback
 * @brief 云手机会话监听器类
 */
class ISessionListener {

public:

    /**
     * @hidden
     * @locale zh
     * @brief 析构函数
     */
    virtual ~ISessionListener() = default;

    /**
     * @locale zh 
     * @brief 会话启动成功的回调
     * @param profileId 清晰度ID
     * @param roundId 可忽略
     * @param targetId 云手机podId或云游戏gameId
     * @param reservedId 可忽略
     * @param planId 可忽略
     */
    virtual void onStartSuccess(int profileId, const char* roundId, const char* targetId, const char* reservedId, const char* planId) {
        (void)profileId;
        (void)roundId;
        (void)targetId;
        (void)reservedId;
        (void)planId;
    }

    /**
     * @locale zh
     * @brief 会话停止的回调
     */
    virtual void onStop() {
    }

    /**
     * @locale zh
     * @brief Pod退出的回调
     * @param reason Pod退出原因
     * @param msg Pod退出详情
     */
    virtual void onPodExited(int reason, const char* msg) {
        (void)reason;
        (void)msg;
    }

    /**
     * @locale zh
     * @brief 收到首帧音频的回调
     */
    virtual void onFirstAudioFrame() {
    }

    /**
     * @locale zh
     * @brief 收到首帧视频的回调
     * @param info 视频首帧信息
     */
    virtual void onFirstVideoFrame(const vecommon::VideoFrameInfo& info) {
        (void)info;
    };

    /**
     * @locale zh
     * @brief 拉流连接状态改变的回调
     * @param state 连接状态
     */
    virtual void onStreamConnectionStateChanged(const vecommon::StreamConnectionState state) {
        (void)state;
    }

    /**
     * @hidden
     * @locale zh
     * @brief 云机请求开始发送音频的回调
     */
    virtual void onRemoteAudioStartRequest() {
    }

    /**
     * @hidden
     * @locale zh
     * @brief 云机请求停止发送音频的回调
     */
    virtual void onRemoteAudioStopRequest() {
    }

    /**
     * @hidden
     * @locale zh
     * @brief 云机请求开始发送视频的回调
     */
    virtual void onRemoteVideoStartRequest() {
    }

    /**
     * @hidden
     * @locale zh
     * @brief 云机请求停止发送视频的回调
     */
    virtual void onRemoteVideoStopRequest() {
    }

    /**
     * @locale zh
     * @brief 音频流统计信息回调，2s回调一次
     * @param stats 统计信息
     */
    virtual void onAudioStats(const vecommon::AudioStats& stats) {
        (void)stats;
    }

    /**
     * @locale zh
     * @brief 视频流统计信息回调，2s回调一次
     * @param stats 统计信息
     */
    virtual void onVideoStats(const vecommon::VideoStats& stats) {
        (void)stats;
    }

    /**
     * @locale zh
     * @brief 视频帧大小改变回调
     * @param info 视频帧信息
     */
    virtual void onVideoSizeChanged(const vecommon::VideoFrameInfo& info) {
        (void)info;
    }

    /**
     * @locale zh
     * @brief 清晰度ID切换结果回调
     * @param result true：成功，false：失败
     * @param from 改变前的清晰度ID
     * @param to 改变后的清晰度ID
     */
    virtual void onVideoStreamProfileChange(bool result, int from, int to) {
        (void)result;
        (void)from;
        (void)to;
    }

    /**
     * @locale zh
     * @brief 截图结果回调
     * @param result 0：成功，<0：失败
     * @param savePath 云手机实例中保存截图文件的路径
     * @param downloadUrl 截图成功时返回截图文件的下载链接，链接有效期1小时
     */
    virtual void onScreenShot(int result, const char* savePath, const char* downloadUrl) {
        (void)result;
        (void)savePath;
        (void)downloadUrl;
    }

    /**
     * @locale zh
     * @brief 网络状态回调，2s回调一次
     * @param state 网络状态
     */
    virtual void onNetworkQuality(const vecommon::NetworkQualityState state) {
        (void)state;
    }

    /**
     * @hidden
     * @locale zh
     * @brief 操作延迟回调，5 秒回调一次
     * @param delay 操作延迟，单位：毫秒
     */
    virtual void onDelayDetected(int delay) {
        (void)delay;
    }

    /**
     * @hidden
     * @locale zh
     * @brief 云机消息通道状态改变回调
     * @param channelId 通道ID
     * @param state 通道状态
     */
    virtual void onMessageChannelStateChanged(const char* channelId, vecommon::MessageChannelState state) {
        (void)channelId;
        (void)state;
    }

    /**
     * @hidden
     * @locale zh
     * @brief 发送消息到云机的结果回调
     * @param success true：成功，false：失败
     * @param mid 消息ID
     */
    virtual void onSendMessageResult(bool success, const char* mid) {
        (void)success;
        (void)mid;
    }

    /**
     * @hidden
     * @locale zh
     * @brief 收到云机字符串消息的回调
     * @param str 字符串数据
     */
    virtual void onStringMessageReceived(const char* str) {
        (void)str;
    }

    /**
     * @hidden
     * @locale zh
     * @brief 收到云机消息的回调
     * @param data 二进制数据
     * @param len 消息长度
     */
    virtual void onBinaryMessageReceived(const uint8_t* data, int len) {
        (void)data;
        (void)len;  
    }

    /**
     * @locale zh 
     * @brief 错误回调
     * @param code 错误码
     * @param msg 错误信息
     */
    virtual void onError(int code, const char* msg) {
        (void)code;
        (void)msg;
    }

    /**
     * @locale zh 
     * @brief 警告回调
     * @param code 警告码
     */
    virtual void onWarning(int code) {
        (void)code;
    }

    /**
     * @locale zh 
     * @brief 是否启用本地键盘回调
     * @param enable true：开启，false：关闭
     */
    virtual void onKeyboardEnable(bool enable) {
        (void)enable;
    }

    /**
     * @locale zh 
     * @brief 云机收到本地用户状态后的回调
     * @param state true：后台，false：前台
     */
    virtual void onBackgroundSwitched(bool state) {
        (void)state;
    }

    /**
     * @locale zh 
     * @brief 云机应用切换到后台的回调
     * @param type 切换类型
     */
    virtual void onRemoteSwitchedBackground(const vecommon::RemoteGameSwitchType type) {
        (void)type;
    }

    /**
     * @locale zh 
     * @brief 云机应用切换到前台的回调
     * @param type 切换类型
     */
    virtual void onRemoteSwitchedForeground(const vecommon::RemoteGameSwitchType type) {
        (void)type;
    }

    /**
     * @hidden
     */
    virtual void onOutputCursorPos(const vecommon::MouseCursorPos& data) {
        (void)data;
    }

    /**
     * @hidden
     */
    virtual void onOutputCursorVisibility(bool visible) {
        (void)visible;
    }

    /**
     * @hidden
     */
    virtual void onOutputGamepadVibration(const vecommon::GamepadVibrationData& data) {
        (void)data;
    }

    /**
     * @hidden
     */
    virtual void onOutputImeState(const vecommon::ImeStateData& data) {
        (void)data;
    }

    /**
     * @locale zh 
     * @brief 设置无操作回收时长成功的回调
     * @param time 无操作回收时长，单位：秒
     */
    virtual void onAutoRecycleTimeCallBack(int time) {
        (void)time;
    }

    /**
     * @locale zh 
     * @brief 云机导航栏状态改变的回调
     * @param status 状态 0：隐藏，1：开启，-1：参数错误
     * @param reason 原因 0：云机切换，1：SDK调用getNavBarStatus，2：SDK调用setNavBarStatus，-1：参数错误
     */
    virtual void onNavBarStatus(int status, int reason) {
        (void)status;
        (void)reason;
    }

    /**
     * @locale zh 
     * @brief 云机屏幕旋转的回调
     * @param rotation 方向 0|180：竖屏，90|270：横屏
     */
    virtual void onRemoteRotation(int rotation) {
        (void)rotation;
    }

    /**
     * @locale zh 
     * @brief 本地渲染画布旋转的回调
     * @param degree 旋转角度
     */
    virtual void onLocalScreenRotate(const vecommon::RotateDegree degree) {
        (void)degree;
    }

    /**
     * @locale zh 
     * @brief 云机输入框更新的回调
     * @param show true：输入框显示，false：输入框隐藏
     * @param text 当前输入框内容
     * @param start 开始位置
     * @param stop 结束位置
     */
    virtual void onEditExchanged(bool show, const char* text, int start, int stop) {
        (void)show;
        (void)text;
        (void)start;
        (void)stop;
    }

    /**
     * @locale zh 
     * @brief 云机收到剪切板消息的回调
     * @param message 剪切板内容
     */
    virtual void onClipBoardMessageReceived(const char* message) {
        (void)message;
    }

    /**
     * @locale zh 
     * @brief 云机加房成功的回调
     * @param podUserId 云机的用户ID
     * @note 收到该回调后可以进行音视频流的订阅和退订操作，在此之前可能会操作失败
     */
    virtual void onPodJoined(const char* podUserId) {
        (void)podUserId;
    }

    /**
     * @locale zh 
     * @brief 发送摇一摇事件的结果回调
     * @param result 结果 0：异常，1：完成，2：进行中
     * @param msg 结果的详细信息
     */
    virtual void onShakeResponse(int result, const char* msg) {
        (void)result;
        (void)msg;
    }

    /**
     * @locale zh 
     * @brief 音频注入的结果回调
     * @param result 结果 1：成功，0或者-1：失败
     * @param msg 结果的详细信息
     */
    virtual void onAudioInjectionResponse(int result, const char* msg) {
        (void)result;
        (void)msg;
    }

    /**
     * @locale zh 
     * @brief 音频注入状态改变的回调
     * @param callUserId 改变音频注入状态的用户ID
     * @param state 音频注入状态 true：开启，false：关闭
     * @param code 错误码 0：成功，<0：失败
     * @param msg 错误信息
     */
    virtual void onAudioInjectionStateChanged(const char* callUserId, bool state, int code, const char* msg) {
        (void)callUserId;
        (void)state;
        (void)code;
        (void)msg;
    }

    /**
     * @locale zh 
     * @brief 查询音频注入状态的结果回调
     * @param state 音频注入状态 true：开启，false：关闭
     * @param code 错误码 0：成功，<0：失败
     * @param msg 错误信息
     */
    virtual void onGetAudioInjectionState(bool state, int code, const char* msg) {
        (void)state;
        (void)code;
        (void)msg;
    }

    /**
     * @locale zh 
     * @brief 视频注入状态改变的回调
     * @param callUserId 改变视频注入状态的用户ID
     * @param state 视频注入状态 true：开启，false：关闭
     * @param code 错误码 0：成功，<0：失败
     * @param msg 错误信息
     */
    virtual void onVideoInjectionStateChanged(const char* callUserId, bool state, int code, const char* msg) {
        (void)callUserId;
        (void)state;
        (void)code;
        (void)msg;
    }

    /**
     * @locale zh 
     * @brief 查询视频注入状态的结果回调
     * @param state 视频注入状态 true：开启， false：关闭
     * @param code code 错误码 0：成功，<0：失败
     * @param msg 错误信息
     */
    virtual void onGetVideoInjectionState(bool state, int code, const char* msg) {
        (void)state;
        (void)code;
        (void)msg;
    }

    /**
     * @locale zh 
     * @brief 键盘类型改变的回调
     * @param code 错误码 0：成功，<0：失败，1000：不允许设置
     * @param type 键盘类型
     */
    virtual void onKeyboardTypeChanged(int code, const vecommon::KeyboardType type) {
        (void)code;
        (void)type;
    }

    /**
     * @locale zh 
     * @brief 查询键盘类型的结果回调
     * @param code 错误码 0：成功，<0：失败
     * @param type 键盘类型
     */
    virtual void onGetKeyboardTypeResult(int code, const vecommon::KeyboardType type) {
        (void)code;
        (void)type;
    }

    /**
     * @locale zh 
     * @brief 用户加房回调
     * @param userId 用户ID
     */
    virtual void onUserJoin(const std::string& userId) {
        (void)userId;
    }

    /**
     * @locale zh 
     * @brief 用户离房回调
     * @param userId 用户ID
     */
    virtual void onUserLeave(const std::string& userId) {
        (void)userId;
    }

    /**
     * @locale zh 
     * @brief 操控权改变的回调
     * @param state 操控权状态
     */
    virtual void onControlStateChanged(const vecommon::ControlState& state) {
        (void)state;
    }

    /**
     * @locale zh 
     * @brief 改变操控权的结果回调
     * @param code 错误码 0：成功，<0：失败
     * @param state 操控权状态
     * @param msg 错误信息
     */
    virtual void onEnableControlResult(int code, const vecommon::ControlState& state, const std::string& msg) {
        (void)code;
        (void)state;
        (void)msg;
    }

    /**
     * @locale zh 
     * @brief 查询操控权的结果回调
     * @param code 错误码 0：成功，<0：失败
     * @param state 操控权状态
     * @param msg 错误信息
     */
    virtual void onHasControlResult(int code, const vecommon::ControlState& state, const std::string& msg) {
        (void)code;
        (void)state;
        (void)msg;
    }

    /**
     * @locale zh 
     * @brief 查询所有用户操控权的结果回调
     * @param code 错误码 0：成功，<0：失败
     * @param states 操控权状态列表
     * @param msg 错误信息
     */
    virtual void onAllControlsResult(int code, const std::vector<vecommon::ControlState>& states, const std::string& msg) {
        (void)code;
        (void)states;
        (void)msg;
    }

    /**
     * @locale zh
     * @brief 屏幕录制状态回调
     * @param status 录制状态
     *          - 0：录制成功，正常结束，上传TOS成功，返回录像文件保存路径
     *          - 1：录制成功，正常结束，云机本地端保存成功
     *          - 2：开始录制成功
     *          - 3：开始录制失败，正在录制中时调用了开始录制
     *          - 4：结束录制失败，没有录制中的任务
     *          - 5：录制失败，云手机存储空间不足，已占用存储空间总量的80%
     *          - 6：录制结束，达到录制时限，返回录像文件保存路径
     *          - 7：开始录制失败，录制时长超过上限
     * @param savePath 录屏文件的保存路径
     * @param downloadUrl 录屏文件的下载链接
     * @param msg 提示信息
     */
    virtual void onRecordingStatus(int status, const std::string& savePath, const std::string& downloadUrl, const std::string& msg) {
        (void)status;
        (void)savePath;
        (void)downloadUrl;
        (void)msg;
    }

    /**
     * @locale zh
     * @brief 无操作回收时长发生改变的回调
     * @param callUserId 改变无操作回收时长的用户ID
     * @param code 错误码 0：成功，<0：失败
     * @param time 无操作回收时长
     */
    virtual void onAutoRecycleTimeChanged(const std::string& callUserId, int code, int time) {
        (void)callUserId;
        (void)code;
        (void)time;
    }

    /**
     * @locale zh
     * @brief 获取无操作回收时长的结果回调
     * @param code 错误码 0：成功，<0：失败
     * @param time 无操作回收时长
     */
    virtual void onGetAutoRecycleTimeResult(int code, int time) {
        (void)code;
        (void)time;
    }

    /**
     * @locale zh
     * @brief 保活时长发生改变的回调
     * @param callUserId 改变保活时长的用户ID
     * @param code 错误码 0：成功，<0：失败
     * @param time 保活时长
     */
    virtual void onIdleTimeChanged(const std::string& callUserId, int code, int time) {
        (void)callUserId;
        (void)code;
        (void)time;
    }

    /**
     * @locale zh
     * @brief 获取保活时长的结果回调
     * @param code 错误码 0：成功，<0：失败
     * @param time 保活时长
     */
    virtual void onGetIdleTimeResult(int code, int time) {
        (void)code;
        (void)time;
    }

    /**
     * @locale zh
     * @brief 清晰度档位发生改变的回调
     * @param callUserId 改变清晰度档位的用户ID
     * @param success true：成功，false：失败
     * @param from 改变前的清晰度档位
     * @param current 当前的清晰度档位
     */
    virtual void onVideoStreamProfileIdChanged(const std::string& callUserId, bool success, int from, int current) {
        (void)callUserId;
        (void)success;
        (void)from;
        (void)current;
    }

    /**
     * @locale zh
     * @brief 查询清晰度档位的结果回调
     * @param success true：成功，false：失败
     * @param current 当前的清晰度档位
     */
    virtual void onGetVideoStreamProfileIdResult(bool success, int current) {
        (void)success;
        (void)current;
    }

    /**
     * @locale zh
     * @brief 接收到通道消息的回调
     * @param message 消息体
     */
    virtual void onReceiveChannelMessage(const vecommon::ChannelMessage message) {
        (void)message;
    }

    /**
     * @locale zh
     * @brief 发送通道消息的结果回调
     * @param success true：成功，false：失败
     * @param msgId 消息ID
     */
    virtual void onSendChannelMessageResult(bool success, const std::string& msgId) {
        (void)success;
        (void)msgId;
    }

    /**
     * @locale zh
     * @brief 消息通道状态改变回调
     * @param remoteUid 通道ID
     * @param state 通道状态
     */
    virtual void onMessageChannelStateChanged(const std::string& remoteUid, const vecommon::MessageChannelState state) {
        (void)remoteUid;
        (void)state;
    }

    /**
     * @locale zh
     * @brief 消息通道错误回调
     * @param code 错误码
     * @param msg 错误信息
     */
    virtual void onMessageChannelError(int code, const std::string& msg) {
        (void)code;
        (void)msg;
    }
};

} // namespace vecommon
