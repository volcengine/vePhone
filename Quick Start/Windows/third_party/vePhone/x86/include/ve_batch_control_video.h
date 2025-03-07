#pragma once
#include "ve_type_defines.h"
#include "ve_batch_control_listener.h"
#include "ve_external_sink.h"

class BatchControlVideo
{
public:

    BatchControlVideo(const vecommon::BatchControlVideoConfig& config) : _config(config) {};
    virtual ~BatchControlVideo() = default;

    /**
     * @type api
     * @brief 发起BatchPodStart请求，podIdList由初始化BatchControlVideo时传入的config解析得来
     */
    virtual int requestBatchPodStart() = 0;

    /**
     * @type api
     * @brief 开始批量拉流
     */
    virtual int start() = 0;

    /**
     * @type api
     * @brief 停止批量拉流
     * @param [in] async 是否异步释放资源
     */
    virtual int stop(bool async = true) = 0;

    /**
     * @type api
     * @brief 追加配置
     */
    virtual void append(const vecommon::BatchControlVideoConfig& config) = 0;

    /**
     * @type api
     * @brief 发起BatchPodStart请求，podIdList作为参数传入
     */
    virtual int requestBatchPodStart(std::vector<std::string>& podIdList) = 0;

    /**
     * @type api
     * @brief 开始批量拉流，podIdList作为参数传入
     */
    virtual int start(std::vector<std::string>& podIdList) = 0;

    /**
     * @type api
     * @brief 停止批量拉流，podIdList作为参数传入
     */
    virtual int stop(std::vector<std::string>& podIdList) = 0;

    /**
     * @type api
     * @brief 重试拉流，针对调用start后未成功拉流的pod，可尝试重新拉流
     */
    virtual int restart(std::vector<std::string>& podIdList) = 0;

    /**
     * @type api
     * @brief 批量拉流的Pod中是否包含某个Pod
     */
    virtual bool contains(const char* podId) = 0;

    /**
     * @type api
     * @brief 获取单个视频的状态
     */
    virtual vecommon::SessionStatus getVideoStatus(const char* podId) { return vecommon::SessionStatus::Idle; };

    /**
     * @type api
     * @brief 获取指定pod的视频配置
     */
    virtual vecommon::ControlVideoConfig* getVideoConfig(const char* podId) = 0;

    /**
     * @type api
     * @brief 订阅视频流
     */
    virtual int subscribe(const char* podId) = 0;

    /**
     * @type api
     * @brief 退订视频流
     */
    virtual int unsubscribe(const char* podId) = 0;

    /**
     * @type api
     * @brief 获取单个视频流的订阅状态
     */
    virtual bool isSubscribed(const char* podId) = 0;

    /**
     * @type api
     * @brief 获取单个视频流的自动订阅状态
     */
    virtual bool isAutoSubscribe(const char* podId) = 0;

    /**
     * @type api
     * @brief 更新单个视频流的渲染画布
     */
    virtual int updateCanvas(const char* podId, void* canvas) = 0;

    /**
     * @type api
     * @brief 设置外部渲染器
     */
    virtual int setExternalSink(const char* podId, VeExternalSink* externalSink) = 0;

    /**
     * @type api
     * @brief 获取外部渲染器
     */
    virtual VeExternalSink* getExternalSink(const char* podId) = 0;

    /**
     * @type api
     * @brief 设置回调监听器
     */
    virtual void setBatchControlListener(BatchControlListener* listener) = 0;


protected:
    const vecommon::BatchControlVideoConfig& _config;


};

