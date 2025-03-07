#pragma once
#include "ve_session.h"
#include "ve_type_defines.h"
#include "ve_session_listener.h"
#include "ve_external_sink.h"
#include "ve_stream.h"


namespace vecommon {

/**
 * @locale zh
 * @type api
 * @brief 云手机会话类
 */
class PhoneSession : public Session {

public:

    /**
     * @hidden
     * @locale zh
     * @brief 析构函数
     */
    virtual ~PhoneSession() = default;

    /**
     * @hidden
     * @locale zh
     * @brief 设置云机同步房间信息
     */
    virtual void setStreamVector(const std::vector<VeStream*>& vector) = 0;

    /**
     * @locale zh
     * @brief 启动云手机会话
     */
    virtual void start() override {};

    /**
     * @hidden
     * @locale zh
     * @brief 通过podInfo启动云手机会话
     * @param podInfo 调用OpenAPI RequestBatchPodStart接口获取的response信息
     */
    virtual void start(const char* podInfo) = 0;

    /**
     * @locale zh
     * @brief 停止云手机会话
     */
    virtual void stop() override {};

     /**
      * @locale zh
      * @brief 获取云手机会话ID
      * @return 云手机会话ID
      */
    virtual const char* getSessionId() override { 
        return ""; 
    };

    /**
     * @locale zh
     * @brief 获取云手机会话状态
     * @return 云手机会话状态
     */
    virtual vecommon::SessionStatus getSessionStatus() override { 
        return vecommon::SessionStatus::Idle; 
    };

    /**
     * @locale zh
     * @brief 设置云手机会话监听器，建议在调用start接口之前设置
     * @param listener 监听器
     */
    virtual void setListener(vecommon::ISessionListener* listener) override {};

    /**
     * @locale zh
     * @brief 关闭音频
     * @param mute 是否关闭
     */
    virtual void setAudioMute(bool mute) = 0;

    /**
     * @locale zh
     * @brief 关闭视频
     * @param mute 是否关闭
     */
    virtual void setVideoMute(bool mute) = 0;

    /**
     * @locale zh
     * @brief 音频是否关闭
     * @return true：已关闭，false 未关闭
     */
    virtual bool isAudioMuted() = 0;

    /**
     * @locale zh
     * @brief 视频是否关闭
     * @return true：已关闭，false 未关闭
     */
    virtual bool isVideoMuted() = 0;

    /**
     * @locale zh
     * @brief 更新本地渲染画布
     * @param canvas 渲染画布
     */
    virtual void updateCanvas(void* canvas) = 0;

    /**
     * @hidden
     * @locale zh
     * @brief 开始发送本地摄像头数据
     */
    virtual void startSendVideoStream() = 0;

    /**
     * @hidden
     * @locale zh
     * @brief 停止发送本地摄像头数据
     */
    virtual void stopSendVideoStream() = 0;

    /**
     * @hidden
     * @locale zh
     * @brief 切换摄像头，默认为前置
     * @param id 摄像头ID
     */
    virtual void switchCamera(const vecommon::CameraId id) = 0;

    /**
     * @deprecated
     * @locale zh
     * @brief 切换当前视频流清晰度档位
     * @param profileId 清晰度档位ID
     * @note 建议使用{@link PhoneSession#setVideoStreamProfileId(int profileId)}
     */
    virtual void switchVideoStreamProfile(int profileId) = 0;

    /**
     * @locale zh
     * @brief 发送键盘按键事件
     * @param keyCode 键盘按键
     *          - 3：HOME 主页
     *          - 4：BACK 返回
     *          - 82：MENU 菜单
     *          - 187：APP_SWITCH 最近任务
     * @note 参考Android KeyCode {https://developer.android.com/reference/android/view/KeyEvent}
     */
    virtual void sendKeyCode(int keyCode) = 0;


    /**
     * @locale zh
     * @brief 发送键盘按键事件
     * @param keyCode
     *          - 3：HOME 主页
     *          - 4：BACK 返回
     *          - 82：MENU 菜单
     *          - 187：APP_SWITCH 最近任务
     * @param down 是否为按键状态
     * @note 可以选择发送单状态(DOWN或UP)，如需模拟一些状态要求较高的按键实践，例如DELETE等，推荐使用
     */
    virtual void sendKeyCode(int keyCode, bool down) = 0;

    /**
     * @locale zh
     * @brief 发送鼠标按键事件
     * @param data 鼠标按键事件
     */
    virtual void sendMouseKey(const vecommon::MouseKeyData& data) = 0;

    /**
     * @locale zh
     * @brief 发送鼠标移动事件
     * @param data 鼠标移动事件
     */
    virtual void sendMouseMove(const vecommon::MouseMoveData& data) = 0;


    /**
     * @locale zh
     * @brief 发送多点触控事件，如果单点鼠标操控，请使用{@link PhoneSession#sendMouseKey()}
     * @param data 多点触控事件
     * @note 多点触控需要使用者保证pointId的唯一性来管理，否则达不到预期效果
     */
    virtual void sendMulitTouch(const vecommon::MulitTouchData& data) = 0;

    /**
     * @locale zh
     * @brief 发送鼠标滚轮事件
     * @param data 鼠标滚轮事件
     */
    virtual void sendMouseWheel(const vecommon::MouseWheelDataArm& data) = 0;

    /**
     * @locale zh
     * @brief 发送输入法事件
     * @param data 输入法事件
     */
    virtual void sendImeComposition(const vecommon::ImeCompositionData& data) = 0;

    /**
     * @locale zh
     * @brief 发送输入法事件, 用于云机同步场景
     * @param data 输入法事件
     * @param podId 指定发送的podId
     */
    virtual void sendImeComposition(const vecommon::ImeCompositionData& data, const char* podId) = 0;

    /**
     * @locale zh
     * @brief 发送文本覆盖云端文本框内容
     * @param txt 文本消息
     */
    virtual void sendEditTextInput(const char* txt) = 0;

    /**
     * @locale zh
     * @brief 发送快捷键消息
     * @param hotKey 快捷键
     */
    virtual void sendHotKeyMessage(const vecommon::HotKey hotKey) = 0;

    /**
     * @locale zh
     * @brief 发送本地剪贴板数据到云端，支持发送文本数据
     * @param clipText 剪切板内容，请保证UTF-8编码
     */
    virtual void sendClipBoardMessage(const char* clipText) = 0;

    /**
     * @locale zh
     * @brief 开启云端键盘输入能力
     * @param enable true：开启，false：关闭
     */
    virtual void setKeyboardEnable(bool enable) = 0;

    /**
     * @locale zh
     * @brief 开启本地键盘输入能力
     * @param enable true：开启，false：关闭
     */
    virtual void setLocalKeyboardEnable(bool enable) = 0;

    /**
     * @locale zh
     * @brief 开启鼠标滚轮能力
     * @param enable true：开启，false：关闭
     */
    virtual void setMouseWheelEnable(bool enable) = 0;

    /**
     * @locale zh
     * @brief 设置客户端应用切换前后台的状态
     * @param state true：后台，false：前台
     */
    virtual void switchBackground(bool state) = 0;

    /**
     * @locale zh
     * @brief 切换云端应用到前台
     * @param pkgName 应用包名
     */
    virtual void setRemoteForeground(const char* pkgName) = 0;

    /**
     * @locale zh
     * @brief 设置保活时长
     * @param time 保活时长，单位：秒
     * @return 0：调用成功，<0：调用失败
     */
    virtual int setIdleTime(int time) = 0;

    /**
     * @locale zh
     * @brief 查询当前保活时长
     * @return 0：调用成功，<0：调用失败
     */
    virtual int getIdleTime() = 0;

    /**
     * @locale zh
     * @brief 设置无操作回收时长
     * @param time 无操作回收时长，单位：秒
     * @return 0：调用成功，<0：调用失败
     * @note 超时后客户端会收到Pod退出事件
     */
    virtual int setAutoRecycleTime(int time) = 0;

    /**
     * @locale zh
     * @brief 查询当前无操作回收时长
     * @return 0：调用成功，<0：调用失败
     */
    virtual int getAutoRecycleTime() = 0;

    /**
     * @locale zh
     * @brief 增大云端设备音量
     */
    virtual void volumeUp() = 0;

    /**
     * @locale zh
     * @brief 减小云端设备音量
     */
    virtual void volumeDown() = 0;

    /**
     * @locale zh
     * @brief 设置导航栏开关状态
     * @param status 1：开启，0：打开
     * @note 开启状态时，Launcher和非全面屏应用会显示导航栏，但申请全面屏时，应用导航栏自动隐藏
     */
    virtual void setNavBarStatus(int status) = 0;

    /**
     * @locale zh
     * @brief 获取云手机导航栏状态
     */
    virtual void getNavBarStatus() = 0;

    /**
     * @locale zh
     * @brief 旋转本地渲染画布
     * @param degree 旋转角度
     * @param podAutoRotation 本地渲染画布旋转的同时云机是否同步旋转(云机支持角度：0|90|270)
     */
    virtual void rotateScreen(const vecommon::RotateDegree degree, bool podAutoRotation) = 0;

    /**
     * @locale zh
     * @brief 云机截图
     * @param saveOnPod 是否保存截图文件在云机中
     * @return 0：调用成功，<0：调用失败
     */
    virtual int screenShot(bool saveOnPod) = 0;

    /**
     * @locale zh
     * @brief 发送摇一摇的指令到云端实例
     * @param duration 摇一摇时长，单位：毫秒，取值范围：[1800, 30000]
     * @return 0：调用成功，<0：调用失败
     */
    virtual int sendShakeEventToRemote(int duration) = 0;

    /**
     * @locale zh
     * @brief 发送音频注入的指令到云端实例
     * @param cmd 注入指令
     * @param filePath 云端实例的音频文件所在目录，只有开始注入时才需要该目录，停止注入时可以传nullptr
     * @return 0：调用成功，<0：调用失败
     */
    virtual int sendAudioInjectionEventToRemote(const vecommon::AudioInjectionCmd cmd, const char* filePath) = 0;

    /**
     * @locale zh
     * @brief 设置云端实例的音频注入状态
     * @param state true: 开启 false: 关闭
     * @return 0：调用成功，<0：调用失败
     */
    virtual int setAudioInjectionState(bool state) = 0;

    /**
     * @locale zh
     * @brief 查询云端实例的音频注入状态
     * @return 0：调用成功，<0：调用失败
     */
    virtual int getAudioInjectionState() = 0;

    /**
     * @locale zh
     * @brief 设置云端实例的视频注入状态
     * @param state 注入状态 true：开启，false：关闭
     * @return 0：调用成功，<0：调用失败
     */
    virtual int setVideoInjectionState(bool state) = 0;

    /**
     * @locale zh
     * @brief 查询云端实例的视频注入状态
     * @return 0：调用成功，<0：调用失败
     */
    virtual int getVideoInjectionState() = 0;

    /**
     * @locale zh
     * @brief 设置键盘类型
     * @param type 键盘类型
     * @return 0：调用成功，<0：调用失败
     */
    virtual int setKeyboardType(const vecommon::KeyboardType type) = 0;

    /**
     * @locale zh
     * @brief 查询键盘类型
     * @return 0：调用成功，<0：调用失败
     */
    virtual int getKeyboardType() = 0;

    /**
     * @locale zh
     * @brief 设置指定用户对云手机的操控权
     * @param userId 用户ID
     * @param enable 是否具有操控权
     * @return 0：调用成功，<0：调用失败
     */
    virtual int enableControl(const std::string& userId, bool enable) = 0;

    /**
     * @locale zh
     * @brief 查询指定用户对云手机的操控权
     * @param userId 用户ID
     * @return 0：调用成功，<0：调用失败
     */
    virtual int hasControl(const std::string& userId) = 0;

    /**
     * @locale zh
     * @brief 查询所有用户对云手机的操控权
     * @return 0：调用成功，<0：调用失败
     */
    virtual int getAllControls() = 0;

    /**
     * @locale zh
     * @brief 设置外部渲染器
     * @param externalSink 外部渲染器
     */
    virtual void setExternalSink(VeExternalSink* externalSink) = 0;

    /**
     * @locale zh
     * @brief 获取当前外部渲染器
     * @return 当前外部渲染器
     */
    virtual VeExternalSink* getExternalSink() = 0;

    /**
     * @locale zh
     * @brief 启动云机应用
     * @param pkgName 应用包名
     * @return 0：调用成功，<0：调用失败
     */
    virtual int launchApp(const std::string& pkgName) = 0;

    /**
     * @locale zh
     * @brief 关闭云机应用
     * @param pkgName 应用包名
     * @return 0：调用成功，<0：调用失败
     */
    virtual int closeApp(const std::string& pkgName) = 0;

    /**
     * @locale zh
     * @brief 开始屏幕录制
     * @param duration 录制时长，单位：秒，支持最大设置14400(4小时)
     * @param saveOnPod 是否将录屏文件保存至云机
     *          - true：录屏文件保存至云机，/sdcard/Pictures/Recordings/路径下文件超过500个时，会清理之前的录屏文件
     *          - false：录屏文件会上传到TOS，TOS保存24小时
     * @return 0：调用成功，<0：调用失败
     */
    virtual int startRecording(int duration, bool saveOnPod) = 0;

    /**
     * @locale zh
     * @brief 停止屏幕录制
     * @return 0：调用成功，<0：调用失败
     */
    virtual int stopRecording() = 0;

    /**
     * @locale zh
     * @brief 设置视频流清晰度档位
     * @param profileId 清晰度档位ID
     * @return 0：调用成功，<0：调用失败
     */
    virtual int setVideoStreamProfileId(int profileId) = 0;

    /**
     * @locale zh
     * @brief 查询当前视频流清晰度档位
     * @return 0：调用成功，<0：调用失败
     */
    virtual int getVideoStreamProfileId() = 0;

    /**
     * @locale zh
     * @brief 发送通道消息
     * @param payload 消息内容
     * @param needAck 是否需要回执
     * @param destChannelUid 目标通道ID
     * @return 消息体
     */
    virtual vecommon::ChannelMessage sendChannelMessage(const std::string& payload, bool needAck, const std::string& destChannelUid) = 0;

};

} // namespace vecommon