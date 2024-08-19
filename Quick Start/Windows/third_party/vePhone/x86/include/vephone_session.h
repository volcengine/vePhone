#pragma once

#include "vesession.h"
#include "ve_type_defines.h"
#include "ve_session_listener.h"
#include "ve_external_sink.h"
#include "ve_stream.h"

/**
 * @type api
 * @brief 云手机场景会话
 */
class PhoneSession :
    public vecommon::Session {

public:
    virtual ~PhoneSession() = default;

    virtual bool requestPodStart() { return false; };

    virtual void setStreamVector(std::vector<VeStream*> vector) = 0;

    /**
     * @type api
     * @brief 启动云手机
     */
    virtual void start() override {};

    /**
     * @type api
     * @brief 通过PodInfo启动云手机
     */
    virtual void start(const char* podInfo) = 0;

    /**
     * @type api
     * @brief 停止云手机
     */
    virtual void stop() override {};

    /**
     * @type api
     * @brief 获取会话 ID
     */
    virtual const char* getSessionId() override { return ""; };

    /**
     * @type api
     * @brief 获取会话状态
     */
    virtual vecommon::SessionStatus getSessionStatus() override { return vecommon::SessionStatus::Idle; };

    /**
     * @type api
     * @brief 设置监听回调
     * @note 通常建议在调用session start流程之前设置监听
     */
    virtual void setListener(ISessionListener* listener) override {};

    /**
     * @type api
     * @brief 音频mute开关
     */
    virtual void setAudioMute(bool mute) = 0;

    /**
     * @type api
     * @brief 视频mute开关
     */
    virtual void setVideoMute(bool mute) = 0;

    /**
     * @type api
     * @brief 音频是否mute
     */
    virtual bool isAudioMuted() = 0;

    /**
     * @type api
     * @brief 视频是否mute
     */
    virtual bool isVideoMuted() = 0;

    /**
     * @type api
     * @brief 更新本地渲染画布
     */
    virtual void updateCanvas(void* canvas) = 0;

    /**
     * @type api
     * @brief 开始发送本地摄像头数据
     */
    virtual void startSendVideoStream() = 0;

    /**
     * @type api
     * @brief 停止发送本地摄像头数据
     */
    virtual void stopSendVideoStream() = 0;

    /**
     * @type api
     * @brief 切换摄像头，默认为前置{@link #CameraId::Front}
     * @param [in] CameraId 云手机清晰度档位id范围  <br>
     */
    virtual void switchCamera(vecommon::CameraId id) = 0;

    /**
     * @type api
     * @brief 切换当前视频流清晰度档位
     * @param [in] streamProfileId 云手机清晰度档位id范围
     * @note 参考 [云手机清晰度档位官方说明文档]
     */
    virtual void switchVideoStreamProfile(int profileId) = 0;

    /**
     * @type api
     * @brief 发送键盘按键事件
     * @note 此Api是发送一次完整的DOWN + UP事件，如需模拟HOME BACK MENU等系统功能键，推荐使用
     *
     * @param [in] keyCode 参考Android KeyCode {https://developer.android.com/reference/android/view/KeyEvent} <br>
     *     + key 3   HOME，home键         <br>
     *     + key 4   BACK，返回键           <br>
     *     + key 82  MENU，菜单键           <br>
     *     + key 187 APP_SWITCH，最近任务列表          <br>
     */
    virtual void sendKeyCode(const int keyCode) = 0;


    /**
     * @type api
     * @brief 发送键盘按键事件
     * @note 可以选择发送单状态（DOWN 或 UP），如需模拟一些状态要求较高的按键实践，例如DELETE等，推荐使用
     *
     * @param [in] keyCode 参考Android KeyCode {https://developer.android.com/reference/android/view/ KeyEvent}    <br>
     *     + key 3   HOME，home键         <br>
     *     + key 4   BACK，返回键           <br>
     *     + key 82  MENU，菜单键           <br>
     *     + key 187 APP_SWITCH，最近任务列表          <br>
     * @param [in] down，true为DOWN状态、false为UP状态
     */
    virtual void sendKeyCode(const int keyCode, bool down) = 0;

    /**
     * @type api
     * @brief 发送鼠标按键事件
     * @param [in] data，参考{@link #MouseKeyData}
     */
    virtual void sendMouseKey(const vecommon::MouseKeyData& data) = 0;

    /**
     * @type api
     * @brief 发送鼠标移动事件
     * @param [in] data，参考{@link #MouseMoveData}
     */
    virtual void sendMouseMove(const vecommon::MouseMoveData& data) = 0;


    /**
     * @type api
     * @brief 发送多点触控事件，如果单点鼠标操控，请使用{@link#sendMouseKey()}
     * @param [in] data, 参考{@link#MulitTouchData}
     * @note 多点触控需要使用者保证pointId的唯一性来管理，否则达不到预期效果
     */
    virtual void sendMulitTouch(const vecommon::MulitTouchData& data) = 0;

    /**
     * @type api
     * @brief 发送鼠标滚轮事件（ARM）
     * @param [in] data，参考{@link #MouseWheelDataArm}
     */
    virtual void sendMouseWheel(const vecommon::MouseWheelDataArm& data) = 0;

    /**
     * @type api
     * @brief 发送输入法事件
     * @param [in] data，参考{@link #ImeCompositionData}
     */
    virtual void sendImeComposition(const vecommon::ImeCompositionData& data) = 0;

    /**
     * @type api
     * @brief 发送文本覆盖云端文本框内容
     * @param [in] data，参考{@link #ImeCompositionData}
     */
    virtual void sendEditTextInput(const char* txt) = 0;

    /**
     * @type api
     * @brief 发送本地剪贴板数据到云端，支持发送文本数据
     * @param [in] clipText，剪切板内容，请保证UTF-8编码 <br>
     *
     */
    virtual void sendClipBoardMessage(const char* clipText) = 0;

    /**
     * @type api
     * @brief 开启使用云端键盘能力
     * @param [in] enable，打开或关闭
     */
    virtual void setKeyboardEnable(bool enable) = 0;

    /**
     * @type api
     * @brief 开启本地键盘输入能力
     * @param [in] enable，打开或关闭
     */
    virtual void setLocalKeyboardEnable(bool enable) = 0;

    /**
    * @type api
    * @brief 打开或关闭鼠标滚轮
    * @param [in] enable，打开或关闭
    */
    virtual void setMouseWheelEnable(bool enable) = 0;

    /**
     * @type api
     * @brief 设置客户端应用或游戏切换前后台的状态
     * @param [in] state，true切后台 / false切前台
     */
    virtual void switchBackground(bool state) = 0;

    /**
     * @type api
     * @brief 切换云端App到前台，适用于云手机
     * @param [in] pkgName，云端app包名
     */
    virtual void setRemoteForeground(const char* pkgName) = 0;

    /**
     * @type api
     * @brief 设置客户端无操作后，云端游戏的保活时间
     * @param [in] seconds，超时时长/秒
     */
    virtual void setIdleTime(int seconds) = 0;

    /**
     * @type api
     * @brief 设置无操作回收服务时间，超时后客户都会收到Pod退出事件
     * @param [in] seconds，超时时长/秒
     */
    virtual void setAutoRecycleTime(int seconds) = 0;

    /**
     * @type api
     * @brief 获取当前误操作回收时间，通过{IEventHandler#onAutoRecycleTimeCallBack}回调结果
     */
    virtual void getAutoRecycleTime() = 0;

    /**
     * @type api
     * @brief 增大云端设备音量
     */
    virtual void volumeUp() = 0;

    /**
     * @type api
     * @brief 减小云端设备音量
     */
    virtual void volumeDown() = 0;

    /**
     * @type api
     * @brief 设置导航栏开关状态
     * @param [in] status <br>
     *          +  1 打开导航栏，launcher和非全面屏应用会显示导航栏，但申请全面屏时，应用导航栏自动隐藏   <br>
     *          +  0 隐藏导航栏   <br>
     */
    virtual void setNavBarStatus(int status) = 0;

    /**
     * @type api
     * @brief 获取云手机导航栏状态，通过{@link #onNavBarStatus(int status, int reason)回调
     */
    virtual void getNavBarStatus() = 0;

    /**
     * @type api
     * @brief 屏幕旋转
     *
     * @param [in] degree 旋转角度，参考{vecommon::RotateDegree}
     * @param [in] podAutoRotation 本地渲染旋转的同时云机是否同步旋转(云机支持角度 0 \ 90 \ 270)
     *
     */
    virtual void rotateScreen(const vecommon::RotateDegree degree, bool podAutoRotation) = 0;

    /**
     * @type api
     * @brief 截取图片
     * @param [in] saveOnPod <br>
     *          +  true 上传截图文件到火山引擎对象存储，并保存截图文件在云手机实例中  <br>
     *          +  false 上传截图文件到火山引擎对象存储，上传完成后，删除保存在云手机实例中的文件 <br>
     */
    virtual void screenShot(bool saveOnPod) = 0;

    /**
     * @type api
     * @brief 发送摇一摇的指令到云端实例
     * @param duration 摇一摇时长，单位：毫秒，取值范围：[1800, 30000]
     * @return 0：调用成功，<0：调用失败
     */
    virtual int sendShakeEventToRemote(int duration) = 0;

    /**
     * @type api
     * @brief 发送音频注入的指令到云端实例
     * @param cmd 1: 开始注入 0: 停止注入, 参考{vecommon::AudioInjectionCmd}
     * @param filePath 云端实例的音频文件所在目录，
     *                 只有开始注入时才需要该目录，
     *                 停止注入时可以传nullptr
     * @return 0：调用成功，<0：调用失败
     */
    virtual int sendAudioInjectionEventToRemote(const vecommon::AudioInjectionCmd cmd, const char* filePath) = 0;

    /*
    * @type api
    * @brief 设置云端实例的音频注入状态
    * @param state true: 开启 false: 关闭
    * @return 0：调用成功，<0：调用失败
    */
    virtual int setAudioInjectionState(bool state) = 0;

    /*
    * @type api
    * @brief 查询云端实例的音频注入状态
    * @return 0：调用成功，<0：调用失败
    */
    virtual int getAudioInjectionState() = 0;

    /*
    * @type api
    * @brief 设置云端实例的视频注入状态
    * @param state true: 开启 false: 关闭
    * @return 0：调用成功，<0：调用失败
    */
    virtual int setVideoInjectionState(bool state) = 0;

    /*
    * @type api
    * @brief 查询云端实例的视频注入状态
    * @return 0：调用成功，<0：调用失败
    */
    virtual int getVideoInjectionState() = 0;

    /**
     * @type api
     * @brief 设置外部渲染器
     * @param [in] externalSink 参考{@link VeExternalSink}
     */
    virtual void setExternalSink(VeExternalSink* externalSink) = 0;

    /**
     * @type api
     * @brief 获取当前外部渲染器
     */
    virtual VeExternalSink* getExternalSink() = 0;

};