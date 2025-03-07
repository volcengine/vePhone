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
     * @locale zh
     * @brief 发起BatchPodStart请求
     * @return 0：调用成功，<0：调用失败
     * @note podIdList由初始化BatchControlVideo时传入的config解析得来
     */
    virtual int requestBatchPodStart() = 0;

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
    virtual int requestBatchPodStart(std::vector<std::string>& podIdList) = 0;

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
    virtual int setExternalSink(const char* podId, VeExternalSink* externalSink) = 0;

    /**
     * @locale zh
     * @brief 获取某个视频流的外部渲染器
     * @param podId 视频流对应的云机ID
     * @return 外部渲染器
     */
    virtual VeExternalSink* getExternalSink(const char* podId) = 0;

    /**
     * @locale zh
     * @brief 设置批量拉流监听器
     * @param listener 监听器
     */
    virtual void setBatchControlListener(BatchControlListener* listener) = 0;

};

} // namespace vecommon
