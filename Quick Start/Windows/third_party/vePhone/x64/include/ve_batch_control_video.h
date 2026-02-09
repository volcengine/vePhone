#pragma once
#include "ve_type_defines.h"
#include "ve_batch_control_listener.h"
#include "ve_external_sink.h"


namespace vecommon {

/**
 * @locale zh
 * @type api
 * @brief 批量拉流控制类
 */
class BatchControlVideo {

public:

    /**
     * @hidden
     * @locale zh
     * @brief 析构函数
     */
    virtual ~BatchControlVideo() = default;

    /**
     * @hidden
     * @locale zh
     * @brief 更新拉流token
     * @param podId 视频流对应的云机ID
     * @param token 新的拉流token
     */
    virtual void updateToken(const std::string& podId, const std::string& token) = 0;

    /**
     * @hidden
     * @locale zh
     * @brief 获取roomId
     * @param podId 视频流对应的云机ID
     * @return podId对应的roomId
     */
    virtual const std::string& getRoomId(const std::string& podId) = 0;

    /**
     * @hidden
     * @locale zh
     * @brief 获取streamProvider
     * @param podId 视频流对应的云机ID
     * @return podId对应的streamProvider
     */
    virtual const std::string& getStreamProvider(const std::string& podId) = 0;

    /**
     * @hidden
     * @locale zh
     * @brief 获取reserveId
     * @param podId 视频流对应的云机ID
     * @return podId对应的reserveId
     */
    virtual const std::string& getReserveId(const std::string& podId) = 0;

    /**
     * @locale zh
     * @brief 更新鉴权信息，建议在requestBatchPodStart前调用
     * @param ak 用户鉴权临时 access key
     * @param sk 用户鉴权临时 secret key
     * @param token 用户鉴权临时 token
     * @return 0：调用成功，<0：调用失败
     */
    virtual int updateAuthInfo(const char* ak, const char* sk, const char* token) = 0;

    /**
     * @locale zh
     * @brief 发起BatchPodStart请求
     * @return 0：调用成功，<0：调用失败
     * @note podIdList由初始化BatchControlVideo时传入的config解析得来
     */
    virtual int requestBatchPodStart(const char* sessionId = nullptr) = 0;

    /**
     * @locale zh
     * @brief 开始批量拉流
     * @return 0：调用成功，<0：调用失败
     */
    virtual int start() = 0;

    /**
     * @locale zh
     * @brief 停止批量拉流
     * @param async 是否异步释放资源
     * @return 0：调用成功，<0：调用失败
     */
    virtual int stop(bool async = true) = 0;

    /**
     * @locale zh
     * @brief 追加配置
     * @param config 批量拉流控制配置信息
     */
    virtual void append(const vecommon::BatchControlVideoConfig& config) = 0;

    /**
     * @locale zh
     * @brief 发起BatchPodStart请求，podIdList作为参数传入
     * @param podIdList podId列表
     * @return 0：调用成功，<0：调用失败
     */
    virtual int requestBatchPodStart(std::vector<std::string>& podIdList, const char* sessionId = nullptr) = 0;

    /**
     * @locale zh
     * @brief 开始批量拉流，podIdList作为参数传入
     * @param podIdList podId列表
     * @return 0：调用成功，<0：调用失败
     */
    virtual int start(std::vector<std::string>& podIdList) = 0;

    /**
     * @locale zh
     * @brief 停止批量拉流，podIdList作为参数传入
     * @param podIdList podId列表
     * @return 0：调用成功，<0：调用失败
     */
    virtual int stop(std::vector<std::string>& podIdList) = 0;

    /**
     * @locale zh
     * @brief 重试拉流，针对调用start后未成功拉流的pod，可尝试重新拉流
     * @param podIdList podId列表
     * @return 0：调用成功，<0：调用失败
     */
    virtual int restart(std::vector<std::string>& podIdList) = 0;

    /**
     * @locale zh
     * @brief 批量拉流的Pod列表中是否包含某个Pod
     * @return true：包含，false：不包含
     */
    virtual bool contains(const char* podId) = 0;

    /**
     * @locale zh
     * @brief 获取某个视频流的状态
     * @param podId 视频流对应的云机ID
     * @return 视频流的状态
     */
    virtual vecommon::SessionStatus getVideoStatus(const char* podId) { 
        return vecommon::SessionStatus::Idle; 
    };

    /**
     * @locale zh
     * @brief 获取某个视频流的配置
     * @param podId 视频流对应的云机ID
     * @return 视频流的配置
     */
    virtual vecommon::ControlVideoConfig* getVideoConfig(const char* podId) = 0;

    /**
     * @locale zh
     * @brief 订阅某个视频流
     * @param podId 视频流对应的云机ID
     * @return 0：调用成功，<0：调用失败
     */
    virtual int subscribe(const char* podId) = 0;

    /**
     * @locale zh
     * @brief 退订某个视频流
     * @param podId 视频流对应的云机ID
     * @return 0：调用成功，<0：调用失败
     */
    virtual int unsubscribe(const char* podId) = 0;

    /**
     * @locale zh
     * @brief 是否已经订阅某个视频流
     * @param podId 视频流对应的云机ID
     * @return true：是，false：否
     */
    virtual bool isSubscribed(const char* podId) = 0;

    /**
     * @locale zh
     * @brief 某个视频流是否为自动订阅
     * @param podId 视频流对应的云机ID
     * @return true：是，false：否
     */
    virtual bool isAutoSubscribe(const char* podId) = 0;

    /**
     * @hidden
     * @locale zh
     * @brief 更新某个视频流的渲染画布
     * @param podId 视频流对应的云机ID
     * @param canvas 渲染画布
     * @return 0：调用成功，<0：调用失败
     */
    virtual int updateCanvas(const char* podId, void* canvas) = 0;

    /**
     * @locale zh
     * @brief 设置某个视频流的外部渲染器
     * @param podId 视频流对应的云机ID
     * @param externalSink 外部渲染器
     * @return 0：调用成功，<0：调用失败
     */
    virtual int setExternalVideoSink(const char* podId, VeExternalVideoSink* externalSink) = 0;

    /**
     * @locale zh
     * @brief 获取某个视频流的外部渲染器
     * @param podId 视频流对应的云机ID
     * @return 外部渲染器
     */
    virtual VeExternalVideoSink* getExternalVideoSink(const char* podId) = 0;

    /**
     * @hidden
     * @locale zh
     * @brief 设置某个视频流的清晰度档位
     * @param podId 视频流对应的云机ID
     * @param profileId 清晰度档位ID
     * @return 0：调用成功，<0：调用失败
     */
    virtual int setVideoStreamProfileId(const char* podId, int profileId) = 0;

    /**
     * @locale zh
     * @brief 设置批量拉流监听器
     * @param listener 监听器
     */
    virtual void setBatchControlListener(BatchControlListener* listener) = 0;

    /**
     * @locale zh
     * @brief 向某个视频流发送键盘按键事件
     * @param keyCode 键盘按键
     *          - 3：HOME 主页
     *          - 4：BACK 返回
     *          - 82：MENU 菜单
     *          - 187：APP_SWITCH 最近任务
     * @note 参考Android KeyCode {https://developer.android.com/reference/android/view/KeyEvent}
     * @return 0：调用成功，<0：调用失败
     */
    virtual int sendKeyCode(const char* podId, int keyCode) = 0;

    /**
     * @locale zh
     * @brief 向某个视频流发送键盘按键事件
     * @param keyCode
     *          - 3：HOME 主页
     *          - 4：BACK 返回
     *          - 82：MENU 菜单
     *          - 187：APP_SWITCH 最近任务
     * @param down 是否为按键状态
     * @note 可以选择发送单状态(DOWN或UP)，如需模拟一些状态要求较高的按键实践，例如DELETE等，推荐使用
     * @return 0：调用成功，<0：调用失败
     */
    virtual int sendKeyCode(const char* podId, int keyCode, bool down) = 0;

    /**
     * @locale zh
     * @brief 向某个视频流发送鼠标按键事件
     * @param podId 视频流对应的云机ID
     * @param data 鼠标按键事件
     * @return 0：调用成功，<0：调用失败
     */
    virtual int sendMouseKey(const char* podId, const vecommon::MouseKeyData& data) = 0;

    /**
     * @locale zh
     * @brief 向某个视频流发送鼠标移动事件
     * @param podId 视频流对应的云机ID
     * @param data 鼠标移动事件
     * @return 0：调用成功，<0：调用失败
     */
    virtual int sendMouseMove(const char* podId, const vecommon::MouseMoveData& data) = 0;

    /**
     * @locale zh
     * @brief 向某个视频流发送输入法事件
     * @param podId 视频流对应的云机ID
     * @param data 输入法事件
     * @return 0：调用成功，<0：调用失败
     */
    virtual int sendImeComposition(const char* podId, const vecommon::ImeCompositionData& data) = 0;

};

} // namespace vecommon
